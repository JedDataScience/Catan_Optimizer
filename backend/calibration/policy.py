"""
policy.py — The greedy strategy every simulated player follows.

It is deliberately simple and identical for all players, so differences in
results come from the starting positions, not from smarter play. It ranks
spots by raw pips only, so it has no built-in opinion about which resources
matter; that's what the calibration is trying to measure.

Each turn, after the roll, the player repeatedly builds the first thing in
this list that they can afford (using bank/port trades if needed):

  1. City        on their best settlement
  2. Settlement  on their best legal spot
  3. Road        toward the best free spot within 3 roads (only when they
                 have no legal settlement spot already)
  4. Dev card

If nothing is affordable they save their cards for next turn.

Trading, when the next build is a few cards short:
  1. One-for-one with another player, if that player is missing the card
     offered for their own next build and can spare the card asked for.
     Nobody trades with a player at LEADER_VP or more. At most
     MAX_PLAYER_TRADES per turn.
  2. Otherwise with the bank, at 4:1 or the player's port rate.
Trades only happen if they complete the build.

Progress cards, played after the roll (one dev card per turn in total):
  Year of Plenty  if two free cards complete a build
  Monopoly        on the resource opponents hold most of (at least 3 cards)
  Road Building   when the player is extending toward a new settlement spot
"""

from collections import deque
from typing import Dict, List, Optional, Tuple

from .game import COSTS, LARGEST_ARMY_MIN, LEADER_VP, RESOURCES, Game, edge

ROAD_SEARCH_DEPTH = 3
MAX_BUILDS_PER_TURN = 12   # safety stop; real turns build far fewer
MAX_PLAYER_TRADES = 2      # one-for-one trades per turn
MONOPOLY_MIN_TAKE = 3


class GreedyPolicy:

    # ── Setup ──────────────────────────────────────────────────────────────

    def setup_road(self, game: Game, pid: int, node: int) -> int:
        """Point the free setup road toward the best open spot two steps away."""
        info = game.info

        def value(nb: int) -> Tuple[int, int]:
            spots = [x for x in info.adj[nb] if x != node and game.spot_is_free(x)]
            return (max((info.node_pips[x] for x in spots), default=-1), -nb)

        options = [nb for nb in info.adj[node] if edge(node, nb) not in game.road_owner]
        return max(options, key=value)

    # ── Dice-time decisions ────────────────────────────────────────────────

    def maybe_play_knight(self, game: Game, pid: int) -> bool:
        """Play a knight if the robber blocks us, or if it wins Largest Army."""
        p = game.players[pid]
        own_hexes = {h for n in p.buildings for h in game.info.node_hexes[n]}
        if game.robber in own_hexes:
            return True
        mine = p.knights_played + 1
        holder = game.army_holder
        if holder == pid or mine < LARGEST_ARMY_MIN:
            return False
        return holder is None or mine > game.players[holder].knights_played

    def discard(self, game: Game, pid: int, n: int) -> List[str]:
        """Discard from the biggest piles first."""
        hand = dict(game.players[pid].hand)
        out = []
        for _ in range(n):
            res = max(RESOURCES, key=lambda r: (hand[r], r))
            hand[res] -= 1
            out.append(res)
        return out

    # ── Building ───────────────────────────────────────────────────────────

    def _options(self, game: Game, pid: int) -> List[Tuple[str, object]]:
        """Build options in priority order: (item, where)."""
        p = game.players[pid]
        info = game.info
        options: List[Tuple[str, object]] = []

        if game.pieces_left(pid, "city"):
            best = max(p.settlements, key=lambda n: (info.node_pips[n], -n))
            options.append(("city", best))

        spots = game.legal_settlements(pid) if game.pieces_left(pid, "settlement") else []
        if spots:
            options.append(("settlement", max(spots, key=lambda n: (info.node_pips[n], -n))))
        elif game.pieces_left(pid, "road"):
            step = self.road_toward_best_spot(game, pid)
            if step is not None:
                options.append(("road", step))

        if game.pieces_left(pid, "dev"):
            options.append(("dev", None))
        return options

    def choose_and_build(self, game: Game, pid: int) -> None:
        for _ in range(MAX_BUILDS_PER_TURN):
            built = False
            for item, where in self._options(game, pid):
                if game.can_afford(pid, item) or self._trade_for(game, pid, item):
                    self._build(game, pid, item, where)
                    built = True
                    break
            if not built:
                return

    def _build(self, game: Game, pid: int, item: str, where) -> None:
        if item == "city":
            game.build_city(pid, where)
        elif item == "settlement":
            game.build_settlement(pid, where)
        elif item == "road":
            game.build_road(pid, *where)
        else:
            game.buy_dev(pid)

    # ── Trading ────────────────────────────────────────────────────────────

    def _wish(self, game: Game, pid: int) -> Dict[str, int]:
        """
        Cost of what a player is saving for next: a cheap stand-in for their
        top build option (no road search), used to judge trade offers.
        """
        if game.pieces_left(pid, "city"):
            return COSTS["city"]
        if game.pieces_left(pid, "settlement") and game.legal_settlements(pid):
            return COSTS["settlement"]
        if game.pieces_left(pid, "road"):
            return COSTS["road"]
        return COSTS["dev"]

    def _player_deal(self, game: Game, pid: int, need: str, hand: Dict[str, int],
                     others: Dict[int, Dict[str, int]], cost: Dict[str, int]) -> Optional[Tuple[int, str]]:
        """
        Find (other player, card to give) for a one-for-one trade that gets
        `need`. The other player must be missing the card offered for their
        own next build and have a spare `need` card.
        """
        if game.vp(pid) >= LEADER_VP:
            return None  # nobody helps a near-winner
        for other in sorted(others):
            if game.vp(other) >= LEADER_VP:
                continue
            theirs = others[other]
            wish = self._wish(game, other)
            if theirs[need] - wish.get(need, 0) < 1:
                continue  # they can't spare it
            offers = [
                g for g in RESOURCES
                if g != need and hand[g] - cost.get(g, 0) >= 1 and theirs[g] < wish.get(g, 0)
            ]
            if offers:
                return other, max(offers, key=lambda g: (hand[g] - cost.get(g, 0), g))
        return None

    def _trade_for(self, game: Game, pid: int, item: str) -> bool:
        """
        Make `item` affordable using only cards the item itself doesn't
        need: one-for-one player trades first, then bank/port trades.
        Plans on copies of the hands and only trades if the plan completes
        the item.
        """
        p = game.players[pid]
        hand = dict(p.hand)
        others = {o.pid: dict(o.hand) for o in game.players if o.pid != pid}
        cost = COSTS[item]
        player_trades_left = MAX_PLAYER_TRADES - p.player_trades_this_turn
        plan: List[Tuple] = []
        for res in RESOURCES:
            while hand[res] < cost.get(res, 0):
                deal = self._player_deal(game, pid, res, hand, others, cost) if player_trades_left > 0 else None
                if deal is not None:
                    other, give = deal
                    hand[give] -= 1
                    hand[res] += 1
                    others[other][give] += 1
                    others[other][res] -= 1
                    player_trades_left -= 1
                    plan.append(("player", give, other, res))
                    continue
                # Bank: spare cards = more than this item uses; cheapest rate first
                givers = [
                    g for g in RESOURCES
                    if g != res and hand[g] - cost.get(g, 0) >= game.trade_rate(pid, g)
                ]
                if not givers:
                    return False
                give = min(givers, key=lambda g: (game.trade_rate(pid, g), -(hand[g] - cost.get(g, 0)), g))
                hand[give] -= game.trade_rate(pid, give)
                hand[res] += 1
                plan.append(("bank", give, res))
        for step in plan:
            if step[0] == "player":
                _, give, other, get = step
                game.player_trade(pid, give, other, get)
                p.player_trades_this_turn += 1
            else:
                _, give, get = step
                game.bank_trade(pid, give, get)
        return bool(plan)

    # ── Progress cards ─────────────────────────────────────────────────────

    def maybe_play_progress(self, game: Game, pid: int) -> None:
        """Play at most one progress card if it clearly helps this turn."""
        p = game.players[pid]
        cards = p.dev_cards

        if "year_of_plenty" in cards:
            for item, _ in self._options(game, pid):
                short = [r for r in RESOURCES for _ in range(max(0, COSTS[item].get(r, 0) - p.hand[r]))]
                if 1 <= len(short) <= 2:
                    picks = (short + short)[:2] if len(short) == 1 else short
                    game.play_year_of_plenty(pid, picks)
                    return

        if "monopoly" in cards:
            held = {r: sum(o.hand[r] for o in game.players if o.pid != pid) for r in RESOURCES}
            best = max(RESOURCES, key=lambda r: (held[r], r))
            if held[best] >= MONOPOLY_MIN_TAKE:
                game.play_monopoly(pid, best)
                return

        if "road_building" in cards and not game.legal_settlements(pid):
            if self.road_toward_best_spot(game, pid) is not None:
                game.play_road_building(pid, lambda: self.road_toward_best_spot(game, pid))

    # ── Road planning ──────────────────────────────────────────────────────

    def road_toward_best_spot(self, game: Game, pid: int) -> Optional[Tuple[int, int]]:
        """
        Breadth-first search (shortest paths) from the player's network, up to
        ROAD_SEARCH_DEPTH new roads. Pick the free settlement spot with the most
        pips (then the nearest) and return the first road on the way there.
        """
        info = game.info
        starts = [n for n in game.network_nodes(pid) if game.can_extend_from(pid, n)]
        depth: Dict[int, int] = {n: 0 for n in starts}
        first_step: Dict[int, Tuple[int, int]] = {}
        queue = deque(starts)
        best: Optional[Tuple[Tuple[int, int, int], int]] = None

        while queue:
            a = queue.popleft()
            if depth[a] >= ROAD_SEARCH_DEPTH or not game.can_extend_from(pid, a):
                continue
            for b in info.adj[a]:
                e = edge(a, b)
                owner = game.road_owner.get(e)
                if (owner is not None and owner != pid) or b in depth:
                    continue
                if owner == pid:
                    continue  # already ours; b is in the network (a start node)
                depth[b] = depth[a] + 1
                first_step[b] = first_step.get(a, (a, b))
                queue.append(b)
                if game.spot_is_free(b):
                    key = (info.node_pips[b], -depth[b], -b)
                    if best is None or key > best[0]:
                        best = (key, b)

        if best is None:
            return None
        return first_step[best[1]]
