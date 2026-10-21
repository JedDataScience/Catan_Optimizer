# Catan Settlement Optimizer

A web app that recommends the best starting settlement placements in Catan. You set up a board (resources and number tokens on all 19 hexes), pick the number of players and your turn order, and the backend runs Monte Carlo simulations to rank intersections by expected resource output.

## Features

- Interactive board setup, or a randomized board
- Top 5 recommended intersections for each settlement, with strategy-aware scoring
- Robber modeled as an adversary in the simulation
- Probability and expected-resource breakdowns explaining each recommendation
- Board-level resource scarcity analysis

## Tech stack

| Layer    | Tools                          |
|----------|--------------------------------|
| Frontend | React (Vite), Recharts, Axios  |
| Backend  | Python, FastAPI, Uvicorn       |

## Project structure

```
backend/
  main.py         FastAPI app and endpoints
  board.py        Hex grid and intersection geometry
  simulation.py   Monte Carlo placement simulation
  scorer.py       Scoring, stats, and explanations
  robber.py       Robber placement logic
frontend/
  src/            React components and board utilities
```

## Running locally

**1. Backend** (runs on http://localhost:8000)

```bash
cd backend
uv venv
uv pip install -r requirements.txt
uv run uvicorn main:app --reload
```

**2. Frontend** (runs on http://localhost:5173)

```bash
cd frontend
npm install
npm run dev
```

Then open http://localhost:5173 in your browser.

## API endpoints

| Method | Path              | Description                                   |
|--------|-------------------|-----------------------------------------------|
| POST   | `/recommend`      | Top 5 recommended intersections               |
| POST   | `/analyze`        | Final breakdown after all placements          |
| POST   | `/board-analysis` | Board-level resource scarcity analysis        |
| GET    | `/health`         | Startup check (verifies 54 intersections)     |

## Scope

- Only the two starting settlements per player are simulated (no roads, cities, or dev cards)
- Ports and trading are not modeled
- 2–4 players; recommendations are always from Player 1's perspective

See [catan_project_description.md](catan_project_description.md) for the full design spec.
