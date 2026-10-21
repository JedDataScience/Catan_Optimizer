"""
evaluate.py — Head-to-head: do the calibrated values pick spots that win more?

For each held-out board and each seat, the "user" drafts both settlements
with one of several pickers (the arms) while the other three seats draft
with the app's opponent model at a high greediness (strong, but not
identical every time). Then the resulting position is played out.

Why strong opponents: against weak, mostly random opponents every sensible
picker wins most games, which hides the differences we want to measure.

Arms:
  random          a random legal spot (floor)
  most_pips       always the spot with the most pips (simple baseline)
  current         recommend() with the app's current values
  calibrated_fuX  recommend() with the calibrated values, follow-up weight X

Paired design ("common random numbers"): for a given board and seat, the
opponents' random draws and the game dice use the same seeds in every arm,
so a difference between arms comes from the user's picks, not luck.

Uncertainty: the per-board difference in win rate between two arms is
resampled over boards (bootstrap) to get a 95% confidence interval.
"""

import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from typing import Dict, List, Tuple

from scorer import DEFAULT_PARAMS, ScoringParams, compute_board_scarcity, compute_pip_total
from simulation import OpponentSampler, build_snake_draft, get_exclusion_zone, recommend

from .dataset import NUM_PLAYERS, board_seed, make_board
from .game import BoardInfo, Game
from .policy import GreedyPolicy

N_SIMS_PER_PICK = 300           # recommend() Monte Carlo runs per pick (app default is 5000)
EVAL_OPPONENT_TEMPERATURE = 4.0 # opponents' greediness here (the app models casual players at 1.5)


def build_arms(calibrated: ScoringParams, follow_ups=(0.1, 0.2, 0.3)) -> Dict[str, object]:
    arms: Dict[str, object] = {"random": "random", "most_pips": "most_pips", "current": DEFAULT_PARAMS}
    for fu in follow_ups:
        arms[f"calibrated_fu{fu:.1f}"] = replace(calibrated, score_weights={**calibrated.score_weights, "follow_up": fu})
    return arms


def _user_pick(arm, step, seat, placed, hexes, intersections, ports, rng: random.Random) -> int:
    open_spots = [i for i in intersections
                  if i.id not in get_exclusion_zone([p["intersection_id"] for p in placed], intersections)]
    if arm == "random":
        return rng.choice(open_spots).id
    if arm == "most_pips":
        hmap = {h.id: h for h in hexes}
        return max(open_spots, key=lambda i: (compute_pip_total(i.hex_ids, hmap), -i.id)).id
    mine = [p["intersection_id"] for p in placed if p["player"] == seat]
    recs = recommend(hexes, intersections, placed, user_position=seat, num_players=NUM_PLAYERS,
                     draft_step=step, s1_id=mine[0] if mine else None, port_types=ports,
                     n_simulations=N_SIMS_PER_PICK, strategy_weight=1.0, params=arm)
    return recs[0]["intersection_id"]


def play_board_seat(args) -> List[Dict[str, float]]:
    board_id, seat, arms, games = args
    seed = board_seed(board_id)
    hexes, intersections, ports = make_board(seed)
    hmap = {h.id: h for h in hexes}
    info = BoardInfo(hexes, intersections, ports)
    policy = GreedyPolicy()
    rows = []

    for name, arm in arms.items():
        sampler = OpponentSampler(intersections, hmap, compute_board_scarcity(hexes),
                                  temperature=EVAL_OPPONENT_TEMPERATURE)
        placed: List[dict] = []
        excluded: set = set()
        firsts: Dict[int, int] = {}
        user_rng = random.Random(seed * 10 + seat)
        for step, player in enumerate(build_snake_draft(NUM_PLAYERS)):
            if player == seat:
                node = _user_pick(arm, step, seat, placed, hexes, intersections, ports, user_rng)
                excluded.add(node)
                excluded.update(intersections[node].adjacent_ids)
            else:
                random.seed(seed * 100 + seat * 10 + step)   # same opponent draws in every arm
                node = sampler.place(excluded, own_first=firsts.get(player))
            firsts.setdefault(player, node)
            placed.append({"intersection_id": node, "player": player})

        picks: List[Tuple[int, int]] = [(p["player"], p["intersection_id"]) for p in placed]
        wins = 0
        for g in range(games):
            result = Game(info, picks, NUM_PLAYERS, policy, seed=(seed * 7 + seat) * 1000 + g).run()
            wins += int(result.winner == seat)
        rows.append({"board_id": board_id, "seat": seat, "arm": name, "wins": wins, "games": games})
    return rows


def run_evaluation(board_ids: List[int], arms: Dict[str, object], games: int, workers: int):
    import pandas as pd

    tasks = [(b, s, arms, games) for b in board_ids for s in range(NUM_PLAYERS)]
    rows: List[Dict[str, float]] = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for r in pool.map(play_board_seat, tasks, chunksize=2):
            rows.extend(r)
    return pd.DataFrame(rows)


def summarise(results, baseline: str = "current", reps: int = 2000, seed: int = 0):
    """Win rate per arm, and each arm's paired difference vs `baseline` with a bootstrap CI."""
    import numpy as np
    import pandas as pd

    results = results.assign(rate=results["wins"] / results["games"])
    per_board = results.pivot_table(index="board_id", columns="arm", values="rate", aggfunc="mean")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(per_board), size=(reps, len(per_board)))

    rows = []
    for arm in per_board.columns:
        diff = (per_board[arm] - per_board[baseline]).to_numpy()
        boot = diff[idx].mean(axis=1)
        rows.append({
            "arm": arm,
            "win_rate": float(per_board[arm].mean()),
            f"diff_vs_{baseline}": float(diff.mean()),
            "ci_low": float(np.quantile(boot, 0.025)),
            "ci_high": float(np.quantile(boot, 0.975)),
        })
    by_seat = results.pivot_table(index="seat", columns="arm", values="rate", aggfunc="mean")
    return pd.DataFrame(rows).sort_values("win_rate", ascending=False), by_seat
