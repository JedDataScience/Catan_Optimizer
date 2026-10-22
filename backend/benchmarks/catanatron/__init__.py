"""
catanatron — Benchmark the recommender inside Catanatron, an independent Catan
engine with strong search bots (https://github.com/bcollazo/catanatron).

    mapping.py  translate a Catanatron board into this project's board model
    players.py  AlphaBeta players that use our recommender (or a baseline)
                for their two starting settlements
    run.py      play many paired games and write BENCHMARK.md

Run from backend/:
    uv run --group benchmark --group calibration python -m benchmarks.catanatron.run [--quick]
"""
