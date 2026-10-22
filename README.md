# Catan Settlement Optimizer

A web app that recommends the best starting settlement placements in Catan. You set up a board (resources and number tokens on all 19 hexes, plus port types), pick the number of players and your turn order, and the backend ranks every open intersection, using Monte Carlo simulation to model what opponents will take before your next pick.

**Does it work?** In 4,800 games in [Catanatron](https://github.com/bcollazo/catanatron), an independent Catan engine, a strong AI player that let the recommender choose its two starting settlements won **28.5%** of four-player games, against **23.9%** when it chose them itself (+4.6 points, 95% CI +1.4 to +7.8). The scoring values behind it were fitted from 60,000 simulated games. Full methodology and results: **[ANALYSIS.md](ANALYSIS.md)**.

## Features

- Interactive board setup with port types, or a randomized board
- Top 5 recommended intersections for each settlement, with strategy-aware scoring:
  - weighted pips, resource diversity, and resource synergy
  - **second-spot follow-up**: how good a second settlement will still be open after opponents pick (simulated)
  - **expansion**: the best open spots two roads away
  - port access
- Opponents modelled as average players who build complementary pairs
- Long-run robber model: the share of your production the robber blocks
- Board-level resource scarcity analysis
- Input validation with readable error messages

## Tech stack

| Layer    | Tools                                     |
|----------|-------------------------------------------|
| Frontend | React (Vite), Recharts, Vitest            |
| Backend  | Python, FastAPI, Uvicorn, pytest (via uv) |

## Project structure

```
backend/
  main.py         FastAPI app and endpoints
  schemas.py      Request models and validation
  board.py        Hex grid, intersection geometry, port slots
  simulation.py   Monte Carlo follow-up and opponent model
  scorer.py       Scoring components and explanations
  robber.py       Robber placement and long-run robber model
  scripts/        export_geometry.py (writes the shared fixture)
  calibration/    game simulator and scoring-value fitting (REPORT.md)
  benchmarks/     Catanatron benchmark (BENCHMARK.md, SEAT0.md)
  tests/          pytest suite
frontend/src/
  App.jsx         App shell and backend calls
  state/          Reducer (app state)
  api/            Backend client
  components/     Board, overlays, and side panels
  utils/          Board geometry, ports, randomizer, validation
shared/
  board_geometry.json   Geometry both test suites check against
```

## Running locally

**1. Backend** (runs on http://localhost:8000)

```bash
cd backend
uv sync
uv run uvicorn main:app --reload
```

**2. Frontend** (runs on http://localhost:5173)

```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:5173 in your browser.

### Configuration

| Variable       | Where          | Default                                         | Purpose                                     |
|----------------|----------------|-------------------------------------------------|---------------------------------------------|
| `VITE_API_URL` | `frontend/.env`| `http://localhost:8000`                         | Backend URL (see `frontend/.env.example`)   |
| `CORS_ORIGINS` | backend env    | `http://localhost:5173,http://127.0.0.1:5173`   | Comma-separated origins allowed to call the API |

## Tests

```bash
cd backend && uv run pytest
```

```bash
cd frontend && npm test && npm run lint
```

The Python and JavaScript board geometry are both checked against `shared/board_geometry.json`, so intersection ids can't drift apart. After an intentional geometry change, regenerate it with `uv run python -m scripts.export_geometry` from `backend/`.

## Scoring calibration

The scoring values in `backend/scorer.py` (resource values, pair bonuses, component weights) are fitted from simulated games, not hand-picked. `backend/calibration/` simulates full games (production, robber, building, bank/port and simple player trades, dev cards) from thousands of random starting positions, fits logistic regressions on who wins, and then checks the new values head-to-head on held-out boards. Results and methods are in [backend/calibration/REPORT.md](backend/calibration/REPORT.md).

To re-run it (about 5 minutes; add `--quick` for a short smoke run):

```bash
cd backend && uv run --group calibration python -m calibration.run
```

The run writes a report and `calibration/output/params.json`; it never changes the app's values by itself.

## External benchmark (Catanatron)

`backend/benchmarks/catanatron/` tests the recommender inside [Catanatron](https://github.com/bcollazo/catanatron), an independent Catan engine with strong AlphaBeta search bots. Its AlphaBeta player chooses its two starting settlements with our recommender (or a baseline), then plays the rest of the game unchanged. That's compared with the same player choosing for itself, on the same seeds. Results are in [BENCHMARK.md](backend/benchmarks/catanatron/BENCHMARK.md), with a follow-up on placing first in [SEAT0.md](backend/benchmarks/catanatron/SEAT0.md).

To re-run it (about 20 minutes; add `--quick` for a one-minute check):

```bash
cd backend && uv run --group benchmark --group calibration python -m benchmarks.catanatron.run
```

The overall write-up of both the calibration and the benchmark is [ANALYSIS.md](ANALYSIS.md).

## API endpoints

| Method | Path              | Description                                   |
|--------|-------------------|-----------------------------------------------|
| POST   | `/recommend`      | Top 5 recommended intersections               |
| POST   | `/analyze`        | Final breakdown once the draft is complete    |
| POST   | `/board-analysis` | Board-level resource scarcity analysis        |
| GET    | `/health`         | Startup check (verifies 54 intersections)     |

Invalid requests (wrong resource or token counts, illegal placements, out-of-turn requests, …) get HTTP 422 with a `detail` explaining what was wrong.

## Scope

- Only the two starting settlements per player are modelled (no roads, cities, or dev cards)
- Ports sit at the 9 standard positions; their types are set by the user
- The robber is a long-run expected-loss model, not a turn-by-turn simulation
- Trading is not modelled
- 2–4 players; recommendations are for the user's chosen turn position

[catan_project_description.md](catan_project_description.md) is the original v1 design spec; this README describes the current behaviour.
