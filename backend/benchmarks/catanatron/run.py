"""
run.py — Paired benchmark in Catanatron: does a strong AlphaBeta player win
more when our recommender picks its two starting settlements?

Every game: the player under test (RED) plus three plain AlphaBeta opponents.
Catanatron shuffles seats. The arms differ only in RED's two setup
settlements; everything else is identical AlphaBeta play.

Paired design: every arm plays the same list of seeds, so each arm sees the
same boards, the same seats and the same game randomness (the game has its
own random-number generator, which our players never touch).

From backend/:
    uv run --group benchmark --group calibration python -m benchmarks.catanatron.run [--quick] [--games N]
"""

import argparse
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from catanatron import Color, Game
from catanatron.state_functions import get_actual_victory_points

from scorer import ScoringParams

from .players import AB_PARAMS, N_SIMS_PER_PICK, MostPipsPlayer, RecommenderPlayer, make_alphabeta

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
BASE_SEED = 7_000
TEST = Color.RED
OPPONENTS = (Color.BLUE, Color.ORANGE, Color.WHITE)

# The scoring values in use before calibration (see backend/calibration/REPORT.md)
HAND_PICKED = ScoringParams(
    strategic_value={"fields": 1.35, "mountains": 1.25, "pasture": 1.10, "forest": 0.90, "hills": 0.90, "desert": 0.0},
    score_weights={"pip": 0.40, "diversity": 0.15, "follow_up": 0.20, "synergy": 0.15, "expansion": 0.10},
    synergy_pairs=(("mountains", "fields", 1.40), ("mountains", "pasture", 1.20), ("fields", "pasture", 1.15),
                   ("forest", "hills", 1.10), ("forest", "fields", 1.05), ("hills", "fields", 1.05)),
    port_weight=0.05,
    scarcity_boost=0.60,
)

ARMS = {
    "alphabeta":              lambda c: make_alphabeta(c),          # control: AlphaBeta's own setup
    "recommender":            lambda c: RecommenderPlayer(c),       # current (calibrated) values
    "recommender_handpicked": lambda c: RecommenderPlayer(c, params=HAND_PICKED),
    "most_pips":              lambda c: MostPipsPlayer(c),
}


def play_one(args) -> dict:
    arm, seed = args
    players = [ARMS[arm](TEST)] + [make_alphabeta(c) for c in OPPONENTS]
    game = Game(players, seed=seed)
    winner = game.play()
    return {
        "arm": arm,
        "seed": seed,
        "seat": list(game.state.colors).index(TEST),
        "win": int(winner == TEST),
        "no_winner": int(winner is None),
        "vp": get_actual_victory_points(game.state, TEST),
        "turns": game.state.num_turns,
    }


def wilson(wins: int, n: int, z: float = 1.96):
    """95% Wilson interval for a proportion (well-behaved even near 0 or 1)."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return centre - half, centre + half


def summarise(df: pd.DataFrame, reps: int = 4000, seed: int = 0):
    wide = df.pivot_table(index="seed", columns="arm", values="win")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(wide), size=(reps, len(wide)))
    rows = []
    for arm in ARMS:
        g = df[df["arm"] == arm]
        lo, hi = wilson(int(g["win"].sum()), len(g))
        diff = (wide[arm] - wide["alphabeta"]).to_numpy()
        boot = diff[idx].mean(axis=1)
        rows.append({
            "arm": arm, "games": len(g), "win_rate": g["win"].mean(), "ci_low": lo, "ci_high": hi,
            "diff_vs_alphabeta": diff.mean(),
            "diff_ci_low": float(np.quantile(boot, 0.025)), "diff_ci_high": float(np.quantile(boot, 0.975)),
            "mean_vp": g["vp"].mean(), "mean_turns": g["turns"].mean(),
        })
    by_seat = df.pivot_table(index="seat", columns="arm", values="win", aggfunc="mean")
    return pd.DataFrame(rows), by_seat


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        out.append("| " + " | ".join(f"{v:.3f}" if isinstance(v, float) else str(v) for v in row) + " |")
    return "\n".join(out)


def write_report(summary: pd.DataFrame, by_seat: pd.DataFrame, df: pd.DataFrame, runtime: float, args) -> None:
    s = summary.set_index("arm")
    rec = s.loc["recommender"]
    verdict = ("The interval is above zero, so the recommender's starting spots measurably help a strong player."
               if rec["diff_ci_low"] > 0 else
               "The interval includes zero, so this run can't show a difference from AlphaBeta's own picks."
               if rec["diff_ci_high"] > 0 else
               "The interval is below zero: AlphaBeta's own starting picks did better than the recommender's.")
    games_per_arm = int(s["games"].iloc[0])
    lines = [
        "# Catanatron benchmark",
        "",
        f"_{'Quick run' if args.quick else 'Full run'}: {games_per_arm:,} paired games per arm, "
        f"{len(ARMS)} arms ({games_per_arm * len(ARMS):,} games), in [Catanatron](https://github.com/bcollazo/catanatron), "
        "an independent Catan engine._",
        "",
        "## Question",
        "",
        "When a strong search player (Catanatron's AlphaBeta) lets our recommender choose its two starting "
        "settlements, does it win more than when it chooses them itself?",
        "",
        "## Answer",
        "",
        f"- With the recommender's picks, the player won **{rec['win_rate']:.1%}** of games vs "
        f"**{s.loc['alphabeta', 'win_rate']:.1%}** with AlphaBeta's own picks: **{rec['diff_vs_alphabeta']:+.1%}** "
        f"(95% CI {rec['diff_ci_low']:+.1%} to {rec['diff_ci_high']:+.1%}).",
        f"- {verdict}",
        f"- Earlier hand-picked values: {s.loc['recommender_handpicked', 'win_rate']:.1%} "
        f"({s.loc['recommender_handpicked', 'diff_vs_alphabeta']:+.1%} vs AlphaBeta). "
        f"Most-pips baseline: {s.loc['most_pips', 'win_rate']:.1%}.",
        "",
        "## Results",
        "",
        "Win rate = share of games won by the player under test (fair share with 4 equal players: 25%). "
        "`diff_vs_alphabeta` is the paired difference from the control on the same seeds, with a bootstrap 95% CI.",
        "",
        md_table(summary),
        "",
        "Win rate by seat (0 = first to place):",
        "",
        md_table(by_seat.reset_index()),
        "",
        "## Method",
        "",
        "- **Players.** Every game has the player under test plus three plain AlphaBeta opponents "
        f"(depth {AB_PARAMS.depth}, pruning {'on' if AB_PARAMS.prunning else 'off'}). The arms differ *only* in the "
        "test player's two setup settlements; setup roads and the whole rest of the game are identical AlphaBeta play.",
        "- **Arms.** `alphabeta` (control: its own setup picks), `recommender` (our current values), "
        "`recommender_handpicked` (the values used before calibration), `most_pips` (highest-pip legal spot).",
        f"- **Recommender settings.** Long-game strategy (slider at 1.0), {N_SIMS_PER_PICK:,} Monte Carlo runs per pick, "
        "#1 recommendation played. The Catanatron board, ports and draft so far are translated into this project's "
        "board model (`mapping.py`, verified by tests: one-to-one corners, identical roads, identical production).",
        "- **Paired design.** All arms play the same seeds, so they see the same boards and seats, and the game's own "
        "random-number generator (dice, cards) is untouched by our players.",
        "",
        "## Limitations",
        "",
        "- Still simulated play, not human games, though from a different engine and much stronger players than this "
        "project's own simulator.",
        "- Catanatron's bots don't make player-to-player trades.",
        "- Opponents are all the same AlphaBeta bot; results against human or mixed opponents may differ.",
        "",
        "## Runtime",
        "",
        f"- {runtime / 60:.1f} minutes on {args.workers} workers; games with no winner: {int(df['no_winner'].sum())}.",
        "",
    ]
    (HERE / "BENCHMARK.md").write_text("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true", help="40 games per arm")
    parser.add_argument("--games", type=int, default=1200, help="games per arm (default 1200)")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    args = parser.parse_args()
    n = 40 if args.quick else args.games
    OUT.mkdir(parents=True, exist_ok=True)

    tasks = [(arm, BASE_SEED + i) for i in range(n) for arm in ARMS]
    start = time.perf_counter()
    rows = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for k, row in enumerate(pool.map(play_one, tasks, chunksize=4), 1):
            rows.append(row)
            if k % max(1, len(tasks) // 10) == 0:
                print(f"[benchmark] {k}/{len(tasks)} games, {time.perf_counter() - start:.0f}s", flush=True)
    runtime = time.perf_counter() - start
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "games.csv", index=False)
    summary, by_seat = summarise(df)
    write_report(summary, by_seat, df, runtime, args)
    print(summary.to_string(index=False))
    print(f"[benchmark] wrote {HERE / 'BENCHMARK.md'} in {runtime / 60:.1f} min")


if __name__ == "__main__":
    main()
