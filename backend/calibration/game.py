"""
game.py — A seeded simulator of the core Catan game.

Rules modelled:
  - Setup from given placements; each player starts with one card per hex
    touching their *second* settlement (the real rule).
  - Roll 2d6. Settlements produce 1 card, cities 2; the robber's hex produces
    nothing.
  - On a 7: anyone holding more than 7 cards discards half (rounded down),
    then the roller moves the robber (robber.place_robber_optimally) and
    steals one random card from a player on that hex.
  - Roads, settlements, cities and dev cards at real costs and piece limits.
    Settlements must touch the builder's road network and obey the distance
    rule; roads can't pass through an opponent's building.
  - Bank trades at 4:1, or 3:1 / 2:1 with the matching port.
  - Simple player-to-player trades: one card for one card, accepted only if
    the other player needs what they get and can spare what they give, and
    never with a player close to winning (8+ VP). See policy.py.
  - Dev deck of 25: 14 knights, 5 victory points, 2 Road Building, 2 Year of
    Plenty, 2 Monopoly. Knights move the robber; Largest Army (3+) is worth
    2 VP. At most one dev card per turn, never on the turn it was bought.
  - First to 10 VP on their own turn wins. Games stop at MAX_TURNS rounds.

Not modelled (stated in the calibration report): Longest Road, multi-card or
negotiated trades, and the bank running out of cards.

Every random choice draws from the game's own random.Random(seed), so the
same seed always replays the same game.
"""

import random
from dataclasses import dataclass, field
from typing import Callable, Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

from board import PORT_SLOTS, PIP_VALUES, Hex, Intersection
from robber import place_robber_optimally

RESOURCES = ("forest", "hills", "fields", "pasture", "mountains")

COSTS: Dict[str, Dict[str, int]] = {
    "road":       {"forest": 1, "hills": 1},
    "settlement": {"forest": 1, "hills": 1, "fields": 1, "pasture": 1},
    "city":       {"fields": 2, "mountains": 3},
    "dev":        {"fields": 1, "pasture": 1, "mountains": 1},
}

PIECE_LIMITS = {"road": 15, "settlement": 5, "city": 4}

WIN_VP           = 10
MAX_TURNS        = 250   # rounds (every player has had a turn)
DISCARD_LIMIT    = 7     # more than this many cards on a 7 → discard half
LARGEST_ARMY_MIN = 3
DEV_DECK         = (["knight"] * 14 + ["vp"] * 5
                    + ["road_building"] * 2 + ["year_of_plenty"] * 2 + ["monopoly"] * 2)
PROGRESS_CARDS   = ("road_building", "year_of_plenty", "monopoly")
LEADER_VP        = 8     # nobody trades with a player this close to winning

Edge = FrozenSet[int]


def edge(a: int, b: int) -> Edge:
    return frozenset((a, b))


# ---------------------------------------------------------------------------
# Static board data, precomputed once per board for fast lookups
# ---------------------------------------------------------------------------

class BoardInfo:
    def __init__(self, hexes: List[Hex], intersections: List[Intersection], port_types: Sequence[str]):
        self.hexes = hexes
        self.intersections = intersections
        self.hex_resource = {h.id: h.resource for h in hexes}
        self.hex_number = {h.id: h.number for h in hexes}
        self.desert = next(h.id for h in hexes if h.resource == "desert")

        self.adj: List[Set[int]] = [set(i.adjacent_ids) for i in intersections]
        self.node_hexes: List[List[int]] = [list(i.hex_ids) for i in intersections]

        self.hex_corners: Dict[int, List[int]] = {h.id: [] for h in hexes}
        for i in intersections:
            for hid in i.hex_ids:
                self.hex_corners[hid].append(i.id)

        # Which hexes pay out on each roll
        self.hexes_by_roll: Dict[int, List[int]] = {}
        for h in hexes:
            if h.number:
                self.hexes_by_roll.setdefault(h.number, []).append(h.id)

        # Port type available at each port intersection
        self.port_at: Dict[int, str] = {}
        for (a, b), ptype in zip(PORT_SLOTS, port_types):
            self.port_at[a] = ptype
            self.port_at[b] = ptype

        # Raw pip value of each intersection (used by the policy to rank spots)
        self.node_pips: List[int] = [
            sum(PIP_VALUES.get(self.hex_number[hid], 0) for hid in i.hex_ids if self.hex_number[hid])
            for i in intersections
        ]


# ---------------------------------------------------------------------------
# Players and results
# ---------------------------------------------------------------------------

@dataclass
class Player:
    pid: int
    hand: Dict[str, int] = field(default_factory=lambda: {r: 0 for r in RESOURCES})
    settlements: Set[int] = field(default_factory=set)
    cities: Set[int] = field(default_factory=set)
    roads: Set[Edge] = field(default_factory=set)
    dev_cards: List[str] = field(default_factory=list)      # playable
    new_dev_cards: List[str] = field(default_factory=list)  # bought this turn
    knights_played: int = 0
    vp_cards: int = 0
    ports: Set[str] = field(default_factory=set)
    played_dev_this_turn: bool = False
    player_trades_this_turn: int = 0

    @property
    def buildings(self) -> Set[int]:
        return self.settlements | self.cities

    def hand_size(self) -> int:
        return sum(self.hand.values())


@dataclass
class GameResult:
    winner: Optional[int]
    rounds: int
    vp: List[int]
    reached_win_round: List[Optional[int]]   # round each player reached WIN_VP (winner only here)


# ---------------------------------------------------------------------------
# The game
# ---------------------------------------------------------------------------

class Game:
    """
    placements: [(player, intersection_id), ...] in draft order (each player twice).
    policy:     object with setup_road / choose_and_build / maybe_play_knight / discard
                (see policy.py).
    """

    def __init__(self, info: BoardInfo, placements: Sequence[Tuple[int, int]], num_players: int,
                 policy, seed: int):
        self.info = info
        self.rng = random.Random(seed)
        self.policy = policy
        self.players = [Player(pid=p) for p in range(num_players)]
        self.owner: Dict[int, int] = {}      # intersection → player with a building there
        self.road_owner: Dict[Edge, int] = {}
        self.robber = info.desert
        self.deck = DEV_DECK[:]
        self.rng.shuffle(self.deck)
        self.army_holder: Optional[int] = None
        self.round = 0

        seen: Dict[int, int] = {}
        for pid, node in placements:
            self._place_settlement(pid, node, free=True)
            road_to = policy.setup_road(self, pid, node)
            self._place_road(pid, node, road_to, free=True)
            seen[pid] = seen.get(pid, 0) + 1
            if seen[pid] == 2:
                # Second settlement: one card per touching hex
                for hid in info.node_hexes[node]:
                    res = info.hex_resource[hid]
                    if res != "desert":
                        self.players[pid].hand[res] += 1

    # ── Queries ────────────────────────────────────────────────────────────

    def vp(self, pid: int) -> int:
        p = self.players[pid]
        army = 2 if self.army_holder == pid else 0
        return len(p.settlements) + 2 * len(p.cities) + p.vp_cards + army

    def spot_is_free(self, node: int) -> bool:
        """Empty, and no building on any neighbouring intersection (distance rule)."""
        if node in self.owner:
            return False
        return not any(n in self.owner for n in self.info.adj[node])

    def network_nodes(self, pid: int) -> Set[int]:
        """Intersections a player's buildings and roads touch."""
        p = self.players[pid]
        nodes = set(p.buildings)
        for e in p.roads:
            nodes |= e
        return nodes

    def can_extend_from(self, pid: int, node: int) -> bool:
        """A road can continue from `node` unless an opponent's building sits there."""
        owner = self.owner.get(node)
        return owner is None or owner == pid

    def legal_roads(self, pid: int) -> List[Tuple[int, int]]:
        out = []
        for a in self.network_nodes(pid):
            if not self.can_extend_from(pid, a):
                continue
            for b in self.info.adj[a]:
                if edge(a, b) not in self.road_owner:
                    out.append((a, b))
        return out

    def legal_settlements(self, pid: int) -> List[int]:
        p = self.players[pid]
        road_nodes = set()
        for e in p.roads:
            road_nodes |= e
        return [n for n in road_nodes if self.spot_is_free(n)]

    def trade_rate(self, pid: int, resource: str) -> int:
        ports = self.players[pid].ports
        if resource in ports:
            return 2
        if "any" in ports:
            return 3
        return 4

    def can_afford(self, pid: int, item: str) -> bool:
        hand = self.players[pid].hand
        return all(hand[r] >= n for r, n in COSTS[item].items())

    def pieces_left(self, pid: int, item: str) -> bool:
        p = self.players[pid]
        if item == "road":
            return len(p.roads) < PIECE_LIMITS["road"]
        if item == "settlement":
            return len(p.settlements) < PIECE_LIMITS["settlement"]
        if item == "city":
            return len(p.cities) < PIECE_LIMITS["city"] and bool(p.settlements)
        if item == "dev":
            return bool(self.deck)
        raise ValueError(item)

    # ── Actions (each validates and pays) ──────────────────────────────────

    def _pay(self, pid: int, item: str) -> None:
        hand = self.players[pid].hand
        for r, n in COSTS[item].items():
            hand[r] -= n
            assert hand[r] >= 0, f"player {pid} paid for {item} without the cards"

    def _place_settlement(self, pid: int, node: int, free: bool = False) -> None:
        assert self.spot_is_free(node), f"illegal settlement at {node}"
        if not free:
            assert node in self.legal_settlements(pid)
            self._pay(pid, "settlement")
        p = self.players[pid]
        p.settlements.add(node)
        self.owner[node] = pid
        if node in self.info.port_at:
            p.ports.add(self.info.port_at[node])

    def _place_road(self, pid: int, a: int, b: int, free: bool = False) -> None:
        e = edge(a, b)
        assert e not in self.road_owner and b in self.info.adj[a], f"illegal road {a}-{b}"
        if not free:
            assert (a, b) in self.legal_roads(pid) or (b, a) in self.legal_roads(pid)
            self._pay(pid, "road")
        self.players[pid].roads.add(e)
        self.road_owner[e] = pid

    def build_settlement(self, pid: int, node: int) -> None:
        self._place_settlement(pid, node)

    def build_road(self, pid: int, a: int, b: int) -> None:
        self._place_road(pid, a, b)

    def build_city(self, pid: int, node: int) -> None:
        p = self.players[pid]
        assert node in p.settlements, f"no settlement to upgrade at {node}"
        self._pay(pid, "city")
        p.settlements.remove(node)
        p.cities.add(node)

    def buy_dev(self, pid: int) -> None:
        assert self.deck, "dev deck is empty"
        self._pay(pid, "dev")
        card = self.deck.pop()
        p = self.players[pid]
        if card == "vp":
            p.vp_cards += 1          # victory point cards count immediately (kept hidden in real play)
        else:
            p.new_dev_cards.append(card)

    def bank_trade(self, pid: int, give: str, get: str) -> None:
        rate = self.trade_rate(pid, give)
        hand = self.players[pid].hand
        assert hand[give] >= rate, f"player {pid} can't trade {rate} {give}"
        hand[give] -= rate
        hand[get] += 1

    def player_trade(self, pid: int, give: str, other: int, get: str) -> None:
        """One card for one card between two players (acceptance is the policy's job)."""
        mine, theirs = self.players[pid].hand, self.players[other].hand
        assert pid != other and mine[give] >= 1 and theirs[get] >= 1, "illegal player trade"
        assert self.vp(other) < LEADER_VP and self.vp(pid) < LEADER_VP, "nobody trades with a near-winner"
        mine[give] -= 1
        theirs[give] += 1
        theirs[get] -= 1
        mine[get] += 1

    # ── Dev cards ──────────────────────────────────────────────────────────

    def _use_dev(self, pid: int, card: str) -> None:
        p = self.players[pid]
        assert not p.played_dev_this_turn, "only one dev card per turn"
        p.dev_cards.remove(card)       # raises if not held / bought this turn
        p.played_dev_this_turn = True

    def play_road_building(self, pid: int, next_road: Callable[[], Optional[Tuple[int, int]]]) -> int:
        """
        Up to two free roads. `next_road` is asked for each one after the
        previous is placed (so the second can extend the first). Returns how
        many were placed.
        """
        self._use_dev(pid, "road_building")
        placed = 0
        for _ in range(2):
            step = next_road() if self.pieces_left(pid, "road") else None
            if step is None:
                break
            a, b = step
            assert (a, b) in self.legal_roads(pid) or (b, a) in self.legal_roads(pid), f"illegal road {a}-{b}"
            self._place_road(pid, a, b, free=True)
            placed += 1
        return placed

    def play_year_of_plenty(self, pid: int, picks: Sequence[str]) -> None:
        """Take any two resource cards from the bank."""
        assert len(picks) == 2 and all(r in RESOURCES for r in picks)
        self._use_dev(pid, "year_of_plenty")
        for r in picks:
            self.players[pid].hand[r] += 1

    def play_monopoly(self, pid: int, resource: str) -> int:
        """Every other player hands over all their cards of `resource`. Returns how many."""
        self._use_dev(pid, "monopoly")
        taken = 0
        for other in self.players:
            if other.pid != pid:
                taken += other.hand[resource]
                other.hand[resource] = 0
        self.players[pid].hand[resource] += taken
        return taken

    def play_knight(self, pid: int) -> None:
        p = self.players[pid]
        self._use_dev(pid, "knight")
        p.knights_played += 1
        self._update_army(pid)
        self._move_robber(pid)

    # ── Turn mechanics ─────────────────────────────────────────────────────

    def _update_army(self, pid: int) -> None:
        mine = self.players[pid].knights_played
        if mine < LARGEST_ARMY_MIN:
            return
        if self.army_holder is None or mine > self.players[self.army_holder].knights_played:
            self.army_holder = pid

    def _move_robber(self, pid: int) -> None:
        own = list(self.players[pid].buildings)
        others = [n for n, o in self.owner.items() if o != pid]
        target = place_robber_optimally(self.info.hexes, own, others, self.info.intersections)
        if target is None or target == self.robber:
            # Nothing worth blocking: park it on the desert (or any other hex not touching us)
            own_hexes = {h for n in own for h in self.info.node_hexes[n]}
            options = [h.id for h in self.info.hexes if h.id != self.robber and h.id not in own_hexes]
            target = self.info.desert if self.info.desert in options else (options[0] if options else self.robber)
        self.robber = target

        victims = sorted({
            self.owner[n] for n in self.info.hex_corners[target]
            if n in self.owner and self.owner[n] != pid and self.players[self.owner[n]].hand_size() > 0
        })
        if victims:
            victim = self.players[self.rng.choice(victims)]
            cards = [r for r in RESOURCES for _ in range(victim.hand[r])]
            stolen = self.rng.choice(cards)
            victim.hand[stolen] -= 1
            self.players[pid].hand[stolen] += 1

    def _produce(self, roll: int) -> None:
        for hid in self.info.hexes_by_roll.get(roll, ()):
            if hid == self.robber:
                continue
            res = self.info.hex_resource[hid]
            for node in self.info.hex_corners[hid]:
                owner = self.owner.get(node)
                if owner is not None:
                    self.players[owner].hand[res] += 2 if node in self.players[owner].cities else 1

    def _roll_seven(self, roller: int) -> None:
        for p in self.players:
            n = p.hand_size()
            if n > DISCARD_LIMIT:
                for res in self.policy.discard(self, p.pid, n // 2):
                    p.hand[res] -= 1
        self._move_robber(roller)

    def play_turn(self, pid: int) -> None:
        p = self.players[pid]
        # Cards bought last turn become playable now
        p.dev_cards.extend(p.new_dev_cards)
        p.new_dev_cards.clear()
        p.played_dev_this_turn = False
        p.player_trades_this_turn = 0

        # A knight may be played before rolling (at most one dev card per turn)
        if "knight" in p.dev_cards and self.policy.maybe_play_knight(self, pid):
            self.play_knight(pid)

        roll = self.rng.randint(1, 6) + self.rng.randint(1, 6)
        if roll == 7:
            self._roll_seven(pid)
        else:
            self._produce(roll)

        # Progress cards are played after the roll, when the player knows their hand
        if not p.played_dev_this_turn and any(c in PROGRESS_CARDS for c in p.dev_cards):
            self.policy.maybe_play_progress(self, pid)

        self.policy.choose_and_build(self, pid)

    def run(self) -> GameResult:
        n = len(self.players)
        reached: List[Optional[int]] = [None] * n
        while self.round < MAX_TURNS:
            self.round += 1
            for pid in range(n):
                self.play_turn(pid)
                if self.vp(pid) >= WIN_VP:
                    reached[pid] = self.round
                    return GameResult(pid, self.round, [self.vp(i) for i in range(n)], reached)
        return GameResult(None, self.round, [self.vp(i) for i in range(n)], reached)
