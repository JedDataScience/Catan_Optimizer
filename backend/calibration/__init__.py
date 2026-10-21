"""
calibration — Offline tooling that fits the optimizer's scoring values from
simulated games. Not used by the running app.

    game.py      core-game simulator (rules)
    policy.py    the greedy strategy every simulated player follows
    dataset.py   random boards + drafts + games → one row per player
    fit.py       statistical models that turn the dataset into scoring values
    evaluate.py  head-to-head: do the new values pick spots that win more?
    run.py       runs everything and writes REPORT.md

Run from backend/:
    uv run --group calibration python -m calibration.run [--quick]
"""
