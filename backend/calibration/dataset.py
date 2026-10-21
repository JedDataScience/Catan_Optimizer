"""
dataset.py — Random boards → varied starting drafts → simulated games →
one row per player with their starting-position features and win count.

Why the drafts are deliberately imperfect: if every simulated player picked
the "best" spot, all starting positions would look alike and the data
couldn't show which features matter. Drafting with a low greediness
(DRAFT_TEMPERATURE) produces a spread of strong, average and weak positions.

Every board, draft and game is generated from a seed derived from the board
id, so the same board can be rebuilt later (evaluate.py does this for the
held-out boards).
"""

import random
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List, Tuple

from board import (
    DEFAULT_PORT_TYPES,
    PORT_SLOTS,
    RESOURCE_COUNTS,
    TOKEN_COUNTS,
    Hex,
    Intersection,
    apply_board_state,
    build_hex_grid,
    build_intersection_map,
)
from scorer import (
    DEFAULT_PARAMS,
    NON_DESERT,
    compute_board_scarcity,
    compute_diversity_quality,
    compute_expansion,
    compute_synergy_bonus,
    compute_weighted_pip,
    synergy_strength,
    SYNERGY_PAIRS,
    _pips_per_resource,
)
from simulation import OpponentSampler, build_snake_draft, get_exclusion_zone

from .game import BoardInfo, Game
from .policy import GreedyPolicy

NUM_PLAYERS       = 4
DRAFT_TEMPERATURE = 0.75   # low greediness → varied positions (the app's opponents use 1.5)
TEST_EVERY        = 5      # every 5th board is held out for validation (20%)
BASE_SEED         = 20_261_021

PAIR_NAMES = [f"pair_{a}_{b}" for a, b, _ in SYNERGY_PAIRS]


def is_test_board(board_id: int) -> bool:
    return board_id % TEST_EVERY == 0


def board_seed(board_id: int) -> int:
    return BASE_SEED + board_id


# ---------------------------------------------------------------------------
# Boards
# ---------------------------------------------------------------------------

def _hex_neighbours(intersections: List[Intersection]) -> Dict[int, set]:
    """Hexes are neighbours when an intersection touches both."""
    nb: Dict[int, set] = {}
    for i in intersections:
        for a in i.hex_ids:
            nb.setdefault(a, set()).update(h for h in i.hex_ids if h != a)
    return nb


_GEOMETRY = build_intersection_map(build_hex_grid())
_HEX_NEIGHBOURS = _hex_neighbours(_GEOMETRY)


def make_board(seed: int) -> Tuple[List[Hex], List[Intersection], List[str]]:
    """A random legal board (6s and 8s never adjacent) with shuffled port types."""
    rng = random.Random(seed)
    resources = [r for r, c in RESOURCE_COUNTS.items() for _ in range(c)]
    tokens = [n for n, c in TOKEN_COUNTS.items() for _ in range(c)]
    while True:
        rng.shuffle(resources)
        rng.shuffle(tokens)
        it = iter(tokens)
        numbers = [None if r == "desert" else next(it) for r in resources]
        hot = [i for i, n in enumerate(numbers) if n in (6, 8)]
        if all(b not in _HEX_NEIGHBOURS[a] for a in hot for b in hot):
            break
    ports = list(DEFAULT_PORT_TYPES)
    rng.shuffle(ports)
    board = [{"id": i, "resource": r, "number": n} for i, (r, n) in enumerate(zip(resources, numbers))]
    hexes = apply_board_state(build_hex_grid(), board)
    return hexes, build_intersection_map(hexes), ports


def draft(hexes, intersections, seed: int, temperature: float = DRAFT_TEMPERATURE) -> List[Tuple[int, int]]:
    """A snake draft where every player picks with pip-and-pair-weighted randomness."""
    random.seed(seed)  # OpponentSampler draws from the global random module
    hmap = {h.id: h for h in hexes}
    sampler = OpponentSampler(intersections, hmap, compute_board_scarcity(hexes), temperature=temperature)
    excluded: set = set()
    firsts: Dict[int, int] = {}
    picks: List[Tuple[int, int]] = []
    for player in build_snake_draft(NUM_PLAYERS):
        node = sampler.place(excluded, own_first=firsts.get(player))
        firsts.setdefault(player, node)
        picks.append((player, node))
    return picks


# ---------------------------------------------------------------------------
# Features of one player's starting position
# ---------------------------------------------------------------------------

def player_features(pid: int, picks, hexes, intersections, ports) -> Dict[str, float]:
    hmap = {h.id: h for h in hexes}
    imap = {i.id: i for i in intersections}
    scarcity = compute_board_scarcity(hexes)
    mine = [n for p, n in picks if p == pid]
    hex_ids = imap[mine[0]].hex_ids + imap[mine[1]].hex_ids   # a shared hex counts twice
    pips = _pips_per_resource(hex_ids, hmap)
    blocked = get_exclusion_zone([n for _, n in picks], intersections)
    port_at = {}
    for (a, b), t in zip(PORT_SLOTS, ports):
        port_at[a] = port_at[b] = t
    my_ports = {port_at[n] for n in mine if n in port_at}

    row: Dict[str, float] = {f"pips_{r}": pips.get(r, 0) for r in NON_DESERT}
    row.update({f"scar_{r}": scarcity[r] for r in NON_DESERT})
    row["pips_total"] = sum(pips.values())
    row["pips_x_scarcity"] = sum(pips.get(r, 0) * scarcity[r] for r in NON_DESERT)
    row["n_types"] = len(pips)
    for (a, b, _), name in zip(SYNERGY_PAIRS, PAIR_NAMES):
        row[name] = synergy_strength(pips.get(a, 0), pips.get(b, 0)) if a in pips and b in pips else 0.0
    row["expansion_pips"] = sum(compute_expansion(imap[n], imap, hmap, blocked, scarcity, 0.0)[1] for n in mine) / 2
    row["port_any"] = int("any" in my_ports)
    row["port_2to1"] = int(any(t != "any" for t in my_ports))
    # The current app's components (DEFAULT_PARAMS), for the old-vs-new comparison
    row["old_wpip"] = compute_weighted_pip(hex_ids, hmap, scarcity, 1.0, DEFAULT_PARAMS)
    row["old_dq"] = compute_diversity_quality(hex_ids, hmap, 1.0, DEFAULT_PARAMS)
    row["old_syn"] = compute_synergy_bonus(hex_ids, hmap, 1.0, DEFAULT_PARAMS)
    return row


# ---------------------------------------------------------------------------
# One board → rows
# ---------------------------------------------------------------------------

def simulate_board(args) -> List[Dict[str, float]]:
    board_id, games = args
    seed = board_seed(board_id)
    hexes, intersections, ports = make_board(seed)
    picks = draft(hexes, intersections, seed)
    info = BoardInfo(hexes, intersections, ports)
    policy = GreedyPolicy()

    wins = [0] * NUM_PLAYERS
    vp_sum = [0] * NUM_PLAYERS
    win_rounds: List[List[int]] = [[] for _ in range(NUM_PLAYERS)]
    no_winner = 0
    for g in range(games):
        result = Game(info, picks, NUM_PLAYERS, policy, seed=seed * 1000 + g).run()
        if result.winner is None:
            no_winner += 1
        else:
            wins[result.winner] += 1
            win_rounds[result.winner].append(result.rounds)
        for p in range(NUM_PLAYERS):
            vp_sum[p] += result.vp[p]

    rows = []
    for pid in range(NUM_PLAYERS):
        row = {
            "board_id": board_id,
            "test": int(is_test_board(board_id)),
            "seat": pid,
            "wins": wins[pid],
            "games": games,
            "no_winner_games": no_winner,
            "mean_vp": vp_sum[pid] / games,
            "mean_win_round": (sum(win_rounds[pid]) / len(win_rounds[pid])) if win_rounds[pid] else None,
        }
        row.update(player_features(pid, picks, hexes, intersections, ports))
        rows.append(row)
    return rows


def build_dataset(n_boards: int, games: int, workers: int):
    """Simulate every board in parallel and return a pandas DataFrame."""
    import pandas as pd

    tasks = [(b, games) for b in range(n_boards)]
    rows: List[Dict[str, float]] = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for board_rows in pool.map(simulate_board, tasks, chunksize=8):
            rows.extend(board_rows)
    return pd.DataFrame(rows)
