"""
main.py — FastAPI application for the Catan Settlement Optimizer (v2).

Endpoints:
  POST /recommend      — Top 5 recommended intersections (strategy-aware)
  POST /analyze        — Final breakdown after all placements
  POST /board-analysis — Board-level resource scarcity analysis
  GET  /health         — Startup check; verifies 54 intersections
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

from board import build_hex_grid, build_intersection_map, apply_board_state, PIP_VALUES
from simulation import recommend
from scorer import (
    compute_combined_stats,
    compute_expected_resources,
    compute_board_analysis,
    explain,
)
from robber import get_robber_discount

app = FastAPI(title="Catan Settlement Optimizer", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Precompute board geometry once at startup
_BASE_HEXES     = build_hex_grid()
_INTERSECTIONS  = build_intersection_map(_BASE_HEXES)
_INTERSECTION_COUNT = len(_INTERSECTIONS)

print(f"[startup] Board geometry loaded: {_INTERSECTION_COUNT} intersections")
if _INTERSECTION_COUNT != 54:
    print(f"[startup] WARNING: Expected 54 intersections, got {_INTERSECTION_COUNT}")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class HexData(BaseModel):
    id: int
    resource: Optional[str] = None
    number: Optional[int] = None


class PlacedSettlement(BaseModel):
    intersection_id: int
    player: int  # 0-indexed


class RecommendRequest(BaseModel):
    board: List[HexData]
    placed_settlements: List[PlacedSettlement] = Field(default_factory=list)
    user_position: int = 0
    num_players: int = Field(default=4, ge=2, le=4)
    draft_step: int = 0
    s1_id: Optional[int] = None
    n_simulations: int = Field(default=5000, ge=500, le=10000)
    strategy_weight: float = Field(default=1.0, ge=0.0, le=1.0)


class AnalyzeRequest(BaseModel):
    board: List[HexData]
    s1_id: int
    s2_id: int
    all_placements: List[PlacedSettlement] = Field(default_factory=list)
    strategy_weight: float = Field(default=1.0, ge=0.0, le=1.0)


class BoardAnalysisRequest(BaseModel):
    board: List[HexData]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/recommend")
def recommend_endpoint(req: RecommendRequest):
    """
    Run Monte Carlo simulation and return top 5 recommended intersections.
    Respects strategy_weight (0.0 = raw production, 1.0 = win-path optimization).
    """
    import copy
    hexes         = copy.deepcopy(_BASE_HEXES)
    hexes         = apply_board_state(hexes, [h.model_dump() for h in req.board])
    intersections = build_intersection_map(hexes)

    placed = [p.model_dump() for p in req.placed_settlements]

    rankings = recommend(
        hexes=hexes,
        intersections=intersections,
        placed_settlements=placed,
        user_position=req.user_position,
        num_players=req.num_players,
        draft_step=req.draft_step,
        s1_id=req.s1_id,
        n_simulations=req.n_simulations,
        strategy_weight=req.strategy_weight,
    )

    return {"rankings": rankings}


@app.post("/analyze")
def analyze_endpoint(req: AnalyzeRequest):
    """
    Return the final resource breakdown for the user's two settled intersections.
    """
    import copy
    hexes         = copy.deepcopy(_BASE_HEXES)
    hexes         = apply_board_state(hexes, [h.model_dump() for h in req.board])
    intersections = build_intersection_map(hexes)
    hmap          = {h.id: h for h in hexes}
    imap          = {i.id: i for i in intersections}

    if req.s1_id not in imap or req.s2_id not in imap:
        raise HTTPException(status_code=400, detail="Invalid settlement intersection IDs.")

    s1 = imap[req.s1_id]
    s2 = imap[req.s2_id]

    pip_total, diversity, expected_resources = compute_combined_stats(
        s1.hex_ids, s2.hex_ids, hmap
    )

    s1_pip = sum(PIP_VALUES.get(hmap[hid].number, 0) for hid in s1.hex_ids if hid in hmap and hmap[hid].number)
    s2_pip = sum(PIP_VALUES.get(hmap[hid].number, 0) for hid in s2.hex_ids if hid in hmap and hmap[hid].number)

    s1_exp = compute_expected_resources(s1.hex_ids, hmap)
    s2_exp = compute_expected_resources(s2.hex_ids, hmap)

    robber_discount = get_robber_discount(hexes, [req.s1_id, req.s2_id], intersections)

    # Board scarcity for context-aware explanation
    board_analysis = compute_board_analysis(hexes)
    scarcity = board_analysis["scarcity"]

    explanation = explain(
        pip_total=pip_total,
        diversity=diversity,
        expected_resources=expected_resources,
        robber_discount=robber_discount,
        strategy_weight=req.strategy_weight,
        scarcity=scarcity,
    )

    return {
        "combined_pip_total":   pip_total,
        "diversity":            diversity,
        "expected_resources":   expected_resources,
        "robber_discount":      robber_discount,
        "explanation":          explanation,
        "board_analysis":       board_analysis,
        "s1": {
            "intersection_id":    req.s1_id,
            "pip_total":          s1_pip,
            "expected_resources": s1_exp,
        },
        "s2": {
            "intersection_id":    req.s2_id,
            "pip_total":          s2_pip,
            "expected_resources": s2_exp,
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
    import copy
    hexes = copy.deepcopy(_BASE_HEXES)
    hexes = apply_board_state(hexes, [h.model_dump() for h in req.board])
    analysis = compute_board_analysis(hexes)
    return analysis


@app.get("/health")
def health():
    ok = _INTERSECTION_COUNT == 54
    return {
        "status":        "ok" if ok else "degraded",
        "intersections": _INTERSECTION_COUNT,
        "expected":      54,
        "version":       "2.0.0",
    }
