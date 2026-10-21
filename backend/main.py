"""
main.py — FastAPI application for the Catan Settlement Optimizer (v3).

Endpoints:
  POST /recommend      — Top 5 recommended intersections (strategy-aware)
  POST /analyze        — Final breakdown after the draft is complete
  POST /board-analysis — Board-level resource scarcity analysis
  GET  /health         — Startup check; verifies 54 intersections

Requests are validated by the models in schemas.py; invalid input gets a
422 response with a readable `detail` before any simulation runs.

Environment variables:
  CORS_ORIGINS — comma-separated frontend origins allowed to call the API
                 (default: the Vite dev server on localhost:5173)
"""

import copy
import os
from typing import List, Tuple

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from board import Hex, Intersection, apply_board_state, build_hex_grid, build_intersection_map
from robber import compute_robber_expected_loss
from schemas import AnalyzeRequest, BoardAnalysisRequest, HexData, RecommendRequest
from scorer import (
    compute_board_analysis,
    compute_combined_stats,
    compute_expected_resources,
    compute_pip_total,
    explain,
)
from simulation import recommend

app = FastAPI(title="Catan Settlement Optimizer", version="3.0.0")

_DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("CORS_ORIGINS", _DEFAULT_ORIGINS).split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Precompute board geometry once at startup
_BASE_HEXES         = build_hex_grid()
_INTERSECTION_COUNT = len(build_intersection_map(_BASE_HEXES))

print(f"[startup] Board geometry loaded: {_INTERSECTION_COUNT} intersections")


def _build_board(board: List[HexData]) -> Tuple[List[Hex], List[Intersection]]:
    """Fresh hexes with this request's resources/numbers, plus intersections."""
    hexes = apply_board_state(copy.deepcopy(_BASE_HEXES), [h.model_dump() for h in board])
    return hexes, build_intersection_map(hexes)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/recommend")
def recommend_endpoint(req: RecommendRequest):
    """
    Return the top 5 recommended intersections for the user's next settlement.
    Respects strategy_weight (0.0 = raw production, 1.0 = win-path optimization).
    """
    hexes, intersections = _build_board(req.board)

    rankings = recommend(
        hexes=hexes,
        intersections=intersections,
        placed_settlements=[p.model_dump() for p in req.placed_settlements],
        user_position=req.user_position,
        num_players=req.num_players,
        draft_step=req.draft_step,
        s1_id=req.s1_id,
        port_types=req.ports,
        n_simulations=req.n_simulations,
        strategy_weight=req.strategy_weight,
    )
    return {"rankings": rankings}


@app.post("/analyze")
def analyze_endpoint(req: AnalyzeRequest):
    """
    Return the final resource breakdown for the user's two settlements,
    including the long-run robber model (needs every player's placements).
    """
    hexes, intersections = _build_board(req.board)
    hmap = {h.id: h for h in hexes}
    imap = {i.id: i for i in intersections}

    s1 = imap[req.s1_id]
    s2 = imap[req.s2_id]

    pip_total, diversity, expected_resources = compute_combined_stats(s1.hex_ids, s2.hex_ids, hmap)

    robber_loss = compute_robber_expected_loss(
        hexes, intersections,
        [p.model_dump() for p in req.all_placements],
        user_player=req.user_position,
        num_players=req.num_players,
    )

    # Board scarcity for context-aware explanation
    board_analysis = compute_board_analysis(hexes)

    explanation = explain(
        pip_total=pip_total,
        diversity=diversity,
        expected_resources=expected_resources,
        strategy_weight=req.strategy_weight,
        scarcity=board_analysis["scarcity"],
        is_pair=True,
        robber_loss=robber_loss,
    )

    return {
        "combined_pip_total":   pip_total,
        "diversity":            diversity,
        "expected_resources":   expected_resources,
        "cards_per_roll":       round(sum(expected_resources.values()), 3),
        "robber_expected_loss": robber_loss,
        "explanation":          explanation,
        "board_analysis":       board_analysis,
        "s1": {
            "intersection_id":    req.s1_id,
            "pip_total":          compute_pip_total(s1.hex_ids, hmap),
            "expected_resources": compute_expected_resources(s1.hex_ids, hmap),
        },
        "s2": {
            "intersection_id":    req.s2_id,
            "pip_total":          compute_pip_total(s2.hex_ids, hmap),
            "expected_resources": compute_expected_resources(s2.hex_ids, hmap),
        },
    }


@app.post("/board-analysis")
def board_analysis_endpoint(req: BoardAnalysisRequest):
    """
    Return a resource scarcity analysis for the given board configuration.
    Called as soon as the board is complete (before running simulations).

    Returns per-resource:
      - scarcity score [0=abundant .. 1=very scarce]
      - total pip count
      - abundance label: "abundant" | "moderate" | "scarce" | "very scarce"
    """
    hexes, _ = _build_board(req.board)
    return compute_board_analysis(hexes)


@app.get("/health")
def health():
    ok = _INTERSECTION_COUNT == 54
    return {
        "status":        "ok" if ok else "degraded",
        "intersections": _INTERSECTION_COUNT,
        "expected":      54,
        "version":       app.version,
    }
