"""
seat0.py — Why does the recommender do worse when it places first?

Runs paired games with the player under test always in seat 0 (Catanatron
picks seats from the game seed, so we keep only seeds that seat it first),
comparing variants that each test one hypothesis:

  H0  noise                         recommender vs the control, many more games
  H1  follow-up weight too high     follow-up 0.0 / 0.15 (current 0.30)
  H2  simulated opponents too mild  opponent greediness 4.0 (current 1.5)
  H3  one pick is the problem       recommender for S1 only / S2 only
  H4  resource weighting costs pips raw production (strategy slider at 0)
      (added after the quick run showed S1 trading pips for ore and wheat)

Each arm differs only in the test player's two setup settlements; the rest
of every game is identical AlphaBeta play. Every setup pick is logged so the
report can show *how* the picks differ, not just which arm wins.

From backend/:
    uv run --group benchmark --group calibration python -m benchmarks.catanatron.seat0 [--quick] [--games N]
"""

import argparse
import os
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
from catanatron import Color, Game
from catanatron.models.player import RandomPlayer

from scorer import DEFAULT_PARAMS

from .players import AlphaBetaLogged, RecommenderPlayer, make_alphabeta
from .run import md_table, wilson

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
TEST = Color.RED
OPPONENTS = (Color.BLUE, Color.ORANGE, Color.WHITE)
FIRST_SEED = 50_000


def _with_follow_up(weight: float):
    return replace(DEFAULT_PARAMS, score_weights={**DEFAULT_PARAMS.score_weights, "follow_up": weight})


ARMS = {
    "alphabeta":       ("Control: AlphaBeta's own picks", lambda c: AlphaBetaLogged(c)),
    "recommender":     ("H0: current recommender", lambda c: RecommenderPlayer(c)),
    "follow_up_0.00":  ("H1: no follow-up term", lambda c: RecommenderPlayer(c, params=_with_follow_up(0.0))),
    "follow_up_0.15":  ("H1: half the follow-up weight", lambda c: RecommenderPlayer(c, params=_with_follow_up(0.15))),
    "greedy_opp_4":    ("H2: greedier simulated opponents", lambda c: RecommenderPlayer(c, opponent_temperature=4.0)),
    "rec_s1_only":     ("H3: recommender S1, AlphaBeta S2", lambda c: RecommenderPlayer(c, use_for=("s1",))),
    "rec_s2_only":     ("H3: AlphaBeta S1, recommender S2", lambda c: RecommenderPlayer(c, use_for=("s2",))),
    "raw_production":  ("H4: no resource weighting (slider at 0)", lambda c: RecommenderPlayer(c, strategy_weight=0.0)),
}


def seat0_seeds(n: int, start: int = FIRST_SEED) -> List[int]:
    """
    The first `n` seeds (from `start`) that put the test player in seat 0.
    Seating depends only on the seed and the order of the players list, so
    cheap placeholder players give the same answer as the real ones.
    """
    out, seed = [], start
    while len(out) < n:
        g = Game([RandomPlayer(c) for c in (TEST, *OPPONENTS)], seed=seed)
        if list(g.state.colors).index(TEST) == 0:
            out.append(seed)
        seed += 1
    return out


def play_one(args) -> dict:
    arm, seed = args
    test_player = ARMS[arm][1](TEST)
    game = Game([test_player] + [make_alphabeta(c) for c in OPPONENTS], seed=seed)
    winner = game.play()
    row = {"arm": arm, "seed": seed, "seat": list(game.state.colors).index(TEST),
           "win": int(winner == TEST), "turns": game.state.num_turns}
    for p in test_player.picks:
        k = p["pick"]
        row.update({f"{k}_pips": p["pips"], f"{k}_rank": p["pip_rank"], f"{k}_best_open": p["best_open_pips"],
                    f"{k}_by": p["chosen_by"], f"{k}_pred_follow_up": p["predicted_follow_up_pips"]})
        for res, pips in p["resources"].items():
            row[f"{k}_{res}"] = pips
    return row


def holm(pvalues: dict) -> dict:
    """Holm step-down adjustment: controls the chance of any false positive across the arms."""
    order = sorted(pvalues, key=pvalues.get)
    m, running, out = len(order), 0.0, {}
    for i, k in enumerate(order):
        running = max(running, min(1.0, (m - i) * pvalues[k]))
        out[k] = running
    return out


def summarise(df: pd.DataFrame, reps: int = 4000, seed: int = 0):
    wide = df.pivot_table(index="seed", columns="arm", values="win")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(wide), size=(reps, len(wide)))
    rows, pvals = [], {}
    for arm, (label, _) in ARMS.items():
        g = df[df["arm"] == arm]
        lo, hi = wilson(int(g["win"].sum()), len(g))
        diff = (wide[arm] - wide["alphabeta"]).to_numpy()
        boot = diff[idx].mean(axis=1)
        row = {"arm": arm, "tests": label, "games": len(g), "win_rate": g["win"].mean(), "ci_low": lo, "ci_high": hi,
               "diff": diff.mean(), "diff_ci_low": float(np.quantile(boot, 0.025)),
               "diff_ci_high": float(np.quantile(boot, 0.975))}
        if arm != "alphabeta":
            # Two-sided bootstrap p-value for "no difference from the control"
            pvals[arm] = float(min(1.0, 2 * min((boot <= 0).mean(), (boot >= 0).mean())))
        rows.append(row)
    adjusted = holm(pvals)
    for r in rows:
        r["p_holm"] = adjusted.get(r["arm"], float("nan"))
    return pd.DataFrame(rows)


def pick_table(df: pd.DataFrame) -> pd.DataFrame:
    res_cols = ["fields", "mountains", "hills", "forest", "pasture"]
    rows = []
    for arm in ARMS:
        g = df[df["arm"] == arm]
        row = {
            "arm": arm,
            "s1_pips": g["s1_pips"].mean(),
            "s1_top_pip_share": (g["s1_rank"] == 1).mean(),
            "s1_pips_below_best": (g["s1_best_open"] - g["s1_pips"]).mean(),
            "s2_pips": g["s2_pips"].mean(),
            "total_pips": (g["s1_pips"] + g["s2_pips"]).mean(),
        }
        for r in res_cols:
            row[f"s1+s2_{r}"] = (g.get(f"s1_{r}", 0).fillna(0) + g.get(f"s2_{r}", 0).fillna(0)).mean() \
                if f"s1_{r}" in g or f"s2_{r}" in g else 0.0
        pred = g["s1_pred_follow_up"].dropna() if "s1_pred_follow_up" in g else pd.Series(dtype=float)
        row["predicted_s2_pips"] = pred.mean() if len(pred) else float("nan")
        rows.append(row)
    return pd.DataFrame(rows)


def write_report(summary: pd.DataFrame, picks: pd.DataFrame, runtime: float, args) -> None:
    s = summary.set_index("arm")
    n = int(s.loc["alphabeta", "games"])
    sig = [a for a in s.index if a != "alphabeta" and s.loc[a, "p_holm"] < 0.05]
    lines = [
        "# Seat 0 investigation",
        "",
        f"_{'Quick run' if args.quick else 'Full run'}: {n:,} paired games per arm, test player always placing first "
        f"(seat 0), {len(ARMS)} arms. Same AlphaBeta play everywhere except the test player's two setup settlements._",
        "",
        "## Win rates from seat 0",
        "",
        "`diff` is the paired difference from the control (AlphaBeta's own picks) on the same seeds, with a bootstrap "
        "95% CI. `p_holm` is the two-sided p-value adjusted for comparing every arm with the control (Holm).",
        "",
        md_table(summary),
        "",
        "Arms that differ from the control after adjustment: " + (", ".join(f"`{a}`" for a in sig) if sig else "none") + ".",
        "",
        "## What each arm picks",
        "",
        "Pips are raw dice pips (a 6 or 8 is 5). `s1_top_pip_share` is how often the first settlement was the open spot "
        "with the most pips; `s1_pips_below_best` is how many pips it gave up versus that spot. `predicted_s2_pips` is "
        "what the recommender's follow-up expected the second settlement to have; compare it with `s2_pips`. Resource "
        "columns are the average pips of each resource across both settlements.",
        "",
        md_table(picks),
        "",
        "## Runtime",
        "",
        f"- {runtime / 60:.1f} minutes on {args.workers} workers.",
        "",
    ]
    (HERE / "SEAT0.md").write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true", help="50 games per arm")
    parser.add_argument("--games", type=int, default=800, help="games per arm (default 800)")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = parser.parse_args()
    n = 50 if args.quick else args.games
    OUT.mkdir(parents=True, exist_ok=True)

    seeds = seat0_seeds(n)
    tasks = [(arm, seed) for seed in seeds for arm in ARMS]
    start = time.perf_counter()
    rows = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for k, row in enumerate(pool.map(play_one, tasks, chunksize=4), 1):
            rows.append(row)
            if k % max(1, len(tasks) // 10) == 0:
                print(f"[seat0] {k}/{len(tasks)} games, {time.perf_counter() - start:.0f}s", flush=True)
    runtime = time.perf_counter() - start
    df = pd.DataFrame(rows)
    assert (df["seat"] == 0).all(), "seed filtering failed: a game didn't seat the test player first"
    df.to_csv(OUT / "seat0_games.csv", index=False)
    summary, picks = summarise(df), pick_table(df)
    write_report(summary, picks, runtime, args)
    print(summary[["arm", "win_rate", "diff", "diff_ci_low", "diff_ci_high", "p_holm"]].to_string(index=False))
    print(f"[seat0] wrote {HERE / 'SEAT0.md'} in {runtime / 60:.1f} min")


if __name__ == "__main__":
    main()
