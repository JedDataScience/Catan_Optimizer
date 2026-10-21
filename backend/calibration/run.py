"""
run.py — Run the whole calibration and write REPORT.md.

From backend/:
    uv run --group calibration python -m calibration.run            # full run
    uv run --group calibration python -m calibration.run --quick    # ~2-minute smoke run

Outputs:
    calibration/REPORT.md             the write-up (committed)
    calibration/output/dataset.csv    one row per player per board
    calibration/output/evaluation.csv head-to-head results
    calibration/output/params.json    the calibrated ScoringParams
    calibration/output/*.png          plots

Nothing here changes the app. Applying the calibrated values is a separate,
reviewed step.
"""

import argparse
import json
import os
import time
from dataclasses import asdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # write image files, no window
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from scorer import DEFAULT_PARAMS, RESOURCE_LABELS  # noqa: E402

from . import evaluate, fit  # noqa: E402
from .dataset import build_dataset, is_test_board  # noqa: E402
from .game import MAX_TURNS  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"

FULL  = dict(boards=3000, games=20, eval_boards=300, eval_games=30, bootstrap=300)
QUICK = dict(boards=200, games=10, eval_boards=12, eval_games=10, bootstrap=40)


def md_table(df: pd.DataFrame, floatfmt: str = "{:.3f}") -> str:
    """A small Markdown table renderer (avoids an extra dependency)."""
    cols = list(df.columns)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    # itertuples keeps each column's own type, so integer columns (seat) stay integers
    for row in df.itertuples(index=False):
        cells = [floatfmt.format(v) if isinstance(v, float) else str(v) for v in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def plot_resources(table: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6, 3.2))
    x = range(len(table))
    ax.bar([i - 0.2 for i in x], table["current"], width=0.4, label="Current", color="#A3AEB1")
    ax.bar([i + 0.2 for i in x], table["fitted"], width=0.4, label="Calibrated", color="#4FB3A9",
           yerr=[table["fitted"] - table["ci_low"], table["ci_high"] - table["fitted"]], capsize=4)
    ax.set_xticks(list(x), [RESOURCE_LABELS[r] for r in table["resource"]])
    ax.axhline(1.0, color="#173B3A", lw=0.8, ls=":")
    ax.set_ylabel("Value per pip (average = 1)")
    ax.set_title("Resource values with 95% confidence intervals")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_head_to_head(summary: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6, 3.2))
    s = summary.sort_values("win_rate")
    ax.barh(s["arm"], s["win_rate"], color="#F2B33D")
    ax.axvline(0.25, color="#173B3A", lw=0.8, ls=":", label="Fair share (25%)")
    ax.set_xlabel("Win rate of the seat using this picker")
    ax.set_title("Head-to-head on held-out boards")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true", help="small smoke run (~2 minutes)")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--reuse-dataset", action="store_true", help="skip simulation if output/dataset.csv exists")
    args = parser.parse_args()
    cfg = QUICK if args.quick else FULL
    OUT.mkdir(parents=True, exist_ok=True)
    timings = {}

    # 1. Dataset
    t = time.perf_counter()
    data_path = OUT / "dataset.csv"
    if args.reuse_dataset and data_path.exists():
        df = pd.read_csv(data_path)
    else:
        df = build_dataset(cfg["boards"], cfg["games"], args.workers)
        df.to_csv(data_path, index=False)
    timings["Simulate dataset"] = time.perf_counter() - t
    print(f"[dataset] {len(df)} rows, {timings['Simulate dataset']:.0f}s")

    # 2. Fit
    t = time.perf_counter()
    report = fit.fit_all(df, bootstrap_reps=cfg["bootstrap"])
    timings["Fit models"] = time.perf_counter() - t
    (OUT / "params.json").write_text(json.dumps(asdict(report.params), indent=2))
    print(f"[fit] done in {timings['Fit models']:.0f}s")

    # 3. Head-to-head on held-out boards
    t = time.perf_counter()
    test_ids = [b for b in range(cfg["boards"]) if is_test_board(b)][: cfg["eval_boards"]]
    arms = evaluate.build_arms(report.params)
    results = evaluate.run_evaluation(test_ids, arms, cfg["eval_games"], args.workers)
    results.to_csv(OUT / "evaluation.csv", index=False)
    summary, by_seat = evaluate.summarise(results)
    timings["Head-to-head"] = time.perf_counter() - t
    print(f"[evaluate] done in {timings['Head-to-head']:.0f}s")

    plot_resources(report.resource_table, OUT / "resource_values.png")
    plot_head_to_head(summary, OUT / "head_to_head.png")
    write_report(df, report, summary, by_seat, timings, cfg, args)
    print(f"[report] wrote {HERE / 'REPORT.md'}")


def write_report(df, report, summary, by_seat, timings, cfg, args) -> None:
    n_games = int(df.groupby("board_id")["games"].first().sum())
    no_winner = int(df.groupby("board_id")["no_winner_games"].first().sum())
    seat_share = df.groupby("seat")["wins"].sum() / df.groupby("board_id")["games"].first().sum()
    rate = summary.set_index("arm")["win_rate"]
    best_cal = max((a for a in rate.index if a.startswith("calibrated")), key=lambda a: rate[a])
    best_row = summary.set_index("arm").loc[best_cal]

    sanity = [
        ("Most-pips beats a random pick", rate["most_pips"] > rate["random"]),
        ("Current values beat most-pips", rate["current"] > rate["most_pips"]),
        ("Every seat wins 15-35% of dataset games", bool(((seat_share > 0.15) & (seat_share < 0.35)).all())),
        (f"Games finishing within {MAX_TURNS} rounds", no_winner == 0),
    ]

    lines = [
        "# Scoring calibration report",
        "",
        f"_{'Quick smoke run' if args.quick else 'Full run'}: {cfg['boards']:,} boards × {cfg['games']} games "
        f"({n_games:,} games) for fitting; {cfg['eval_boards']} held-out boards × 4 seats × "
        f"{cfg['eval_games']} games per picker for the head-to-head._",
        "",
        "## Summary",
        "",
        f"- Best calibrated picker (**{best_cal}**) wins **{best_row['win_rate']:.1%}** of games from its seat, "
        f"vs **{rate['current']:.1%}** with the current values: a difference of "
        f"**{best_row['diff_vs_current']:+.1%}** (95% CI {best_row['ci_low']:+.1%} to {best_row['ci_high']:+.1%}).",
        "- " + ("The interval excludes zero, so the improvement is unlikely to be luck."
                if best_row["ci_low"] > 0 else
                "The interval includes zero, so this run can't show the calibrated values are better."),
        "",
        "## Sanity checks",
        "",
        *[f"- {'✅' if ok else '❌'} {label}" for label, ok in sanity],
        "",
        "## Head-to-head (held-out boards)",
        "",
        md_table(summary),
        "",
        "Win rate by seat (rows) and picker (columns):",
        "",
        md_table(by_seat.reset_index()),
        "",
        "![Head-to-head](output/head_to_head.png)",
        "",
        "## Resource values",
        "",
        "Value of one pip of each resource relative to the average resource, from Model 1.",
        "",
        md_table(report.resource_table),
        "",
        f"Scarcity boost: **{report.scarcity_boost[0]:.2f}** (95% CI {report.scarcity_boost[1]:.2f} to "
        f"{report.scarcity_boost[2]:.2f}); current value {DEFAULT_PARAMS.scarcity_boost:.2f}.",
        "",
        "![Resource values](output/resource_values.png)",
        "",
        "## Resource pairs (synergy multipliers)",
        "",
        md_table(report.pair_table),
        "",
        "## Component weights",
        "",
        md_table(report.weights_table),
        "",
        "Calibrated `score_weights`: " + ", ".join(f"{k} {v:.2f}" for k, v in report.params.score_weights.items())
        + f"; port weight {report.params.port_weight:.2f}. Follow-up weight is chosen head-to-head (see above).",
        "",
        "## Does the score predict held-out winners?",
        "",
        "Log-loss: how well predicted win chances match what happened (lower is better). "
        "Spearman: average rank correlation between score and win rate among a board's four players "
        "(1 = perfect ordering).",
        "",
        md_table(report.validation),
        "",
        "## Notes from the fit",
        "",
        *([f"- {n}" for n in report.notes] or ["- None."]),
        "",
        "## Full Model 2 coefficients",
        "",
        md_table(report.component_table.reset_index().rename(columns={"index": "term"})),
        "",
        "## Method",
        "",
        "1. **Dataset.** Random legal boards (6s and 8s never adjacent, ports shuffled). Four players draft "
        "with deliberate randomness so the data covers strong and weak positions. Every starting position is "
        "played out many times by identical greedy players (`policy.py`).",
        "2. **Models.** Binomial GLMs (logistic regression on wins out of games) with seat indicators so turn "
        "order isn't credited to the spot. Standard errors are cluster-robust by board, because players on the "
        "same board compete with each other. Resource-value intervals come from a bootstrap over boards.",
        "3. **Validation.** Fitted on 80% of boards; scored on the held-out 20%.",
        "4. **Head-to-head.** On held-out boards one seat drafts with each picker while the others use the app's "
        f"opponent model at a high greediness ({evaluate.EVAL_OPPONENT_TEMPERATURE:g}; the app assumes 1.5 for "
        "casual players). Opponent draws and dice use the same seeds across pickers (a paired comparison). "
        "Win rates well above 25% for the recommender arms mean it out-drafts these opponents, as intended.",
        "",
        "## Limitations",
        "",
        "- Results are only as realistic as the simulated play: one greedy strategy for everyone, no Longest "
        "Road, and the bank never runs out. Progress cards (Road Building, Year of Plenty, Monopoly) are played "
        "by simple rules, and player trades are one-for-one only, accepted when both sides need what they get "
        "(never with a player on 8+ VP). Real tables negotiate more freely.",
        "- The follow-up variants differ from each other by about a point, which is within noise; only their "
        "difference from the current values is clearly established.",
        "- Model 2's pair multipliers are a linear approximation around a typical position.",
        "- The follow-up weight and the opponent model can't be learned from final positions; the follow-up "
        "weight is chosen from the head-to-head grid instead.",
        "",
        "## Runtime",
        "",
        *[f"- {k}: {v:.0f}s" for k, v in timings.items()],
        f"- Workers: {args.workers}",
        "",
    ]
    (HERE / "REPORT.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
