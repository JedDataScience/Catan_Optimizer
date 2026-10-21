"""
test_api.py — Endpoints and request validation (main.py, schemas.py).
"""

import copy

import pytest
from fastapi.testclient import TestClient

from board import DEFAULT_PORT_TYPES
from main import app
from tests.helpers import BOARD, greedy_draft

client = TestClient(app)


def _recommend_body(**overrides):
    body = {"board": copy.deepcopy(BOARD), "num_players": 4, "user_position": 0,
            "draft_step": 0, "n_simulations": 500}
    body.update(overrides)
    return body


def _analyze_body(num_players=2, **overrides):
    placements = greedy_draft(num_players)
    user = [p["intersection_id"] for p in placements if p["player"] == 0]
    body = {"board": copy.deepcopy(BOARD), "all_placements": placements,
            "num_players": num_players, "user_position": 0, "s1_id": user[0], "s2_id": user[1]}
    body.update(overrides)
    return body


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------

def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_recommend_ok():
    r = client.post("/recommend", json=_recommend_body())
    assert r.status_code == 200
    assert len(r.json()["rankings"]) == 5


def test_recommend_s2_ok():
    placed = greedy_draft(2, steps=3)
    r = client.post("/recommend", json=_recommend_body(
        num_players=2, placed_settlements=placed, draft_step=3, s1_id=placed[0]["intersection_id"],
    ))
    assert r.status_code == 200


def test_analyze_ok():
    r = client.post("/analyze", json=_analyze_body())
    assert r.status_code == 200
    data = r.json()
    assert data["combined_pip_total"] == data["s1"]["pip_total"] + data["s2"]["pip_total"]
    assert 0.0 <= data["robber_expected_loss"] <= 1.0


def test_board_analysis_ok():
    r = client.post("/board-analysis", json={"board": BOARD})
    assert r.status_code == 200
    assert set(r.json()["scarcity"]) == {"forest", "hills", "fields", "pasture", "mountains"}


# ---------------------------------------------------------------------------
# Validation: every rule rejects bad input with 422
# ---------------------------------------------------------------------------

def _board_with(**changes):
    """Copy of BOARD with {hex_id: {field: value}} changes applied."""
    board = copy.deepcopy(BOARD)
    for hid, patch in changes.items():
        board[int(hid)].update(patch)
    return board


BAD_RECOMMEND = {
    "hex id out of range":    dict(board=_board_with(**{"0": {"id": 19}})),
    "duplicate hex":          dict(board=copy.deepcopy(BOARD[:18]) + [copy.deepcopy(BOARD[0])]),
    "unknown resource":       dict(board=_board_with(**{"0": {"resource": "gold"}})),
    "wrong resource counts":  dict(board=_board_with(**{"0": {"resource": "forest"}})),
    "number 7":               dict(board=_board_with(**{"0": {"number": 7}})),
    "desert with number":     dict(board=_board_with(**{"9": {"number": 6}})),
    "wrong token counts":     dict(board=_board_with(**{"1": {"number": 6}})),
    "bad port counts":        dict(ports=["any"] * 9),
    "too few ports":          dict(ports=DEFAULT_PORT_TYPES[:8]),
    "user position too high": dict(num_players=2, user_position=3),
    "not the user's turn":    dict(draft_step=1, placed_settlements=greedy_draft(4, steps=1)),
    "placements don't match step": dict(draft_step=7, placed_settlements=[]),
    "wrong player order":     dict(user_position=1, draft_step=1,
                                   placed_settlements=[{"intersection_id": 20, "player": 2}]),
    "distance rule":          dict(user_position=2, draft_step=2,
                                   placed_settlements=[{"intersection_id": 20, "player": 0},
                                                       {"intersection_id": 21, "player": 1}]),
    "intersection out of range": dict(user_position=1, draft_step=1,
                                      placed_settlements=[{"intersection_id": 54, "player": 0}]),
    "s1_id on first pick":    dict(s1_id=5),
    "s1_id not user's":       dict(num_players=2, draft_step=3, s1_id=0,
                                   placed_settlements=greedy_draft(2, steps=3)),
    "too many simulations":   dict(n_simulations=100000),
}


@pytest.mark.parametrize("case", BAD_RECOMMEND, ids=list(BAD_RECOMMEND))
def test_recommend_rejects_bad_input(case):
    r = client.post("/recommend", json=_recommend_body(**BAD_RECOMMEND[case]))
    assert r.status_code == 422, r.json()
    assert r.json()["detail"], "422 responses must say what was wrong"


def test_analyze_rejects_incomplete_draft():
    body = _analyze_body()
    body["all_placements"] = body["all_placements"][:-1]
    assert client.post("/analyze", json=body).status_code == 422


def test_analyze_rejects_swapped_settlements():
    body = _analyze_body()
    body["s1_id"], body["s2_id"] = body["s2_id"], body["s1_id"]
    assert client.post("/analyze", json=body).status_code == 422


# ---------------------------------------------------------------------------
# Scoring info (the "How scoring works" panel)
# ---------------------------------------------------------------------------

def test_scoring_info_reports_the_values_in_use():
    from scorer import DEFAULT_PARAMS
    data = client.get("/scoring-info").json()
    for r, v in data["resource_values"].items():
        assert v == DEFAULT_PARAMS.strategic_value[r]
    assert data["port_weight"] == DEFAULT_PARAMS.port_weight
    assert len(data["pairs"]) == len(DEFAULT_PARAMS.synergy_pairs)


def test_scoring_info_weights_are_shares():
    w = client.get("/scoring-info").json()["weights"]
    assert sum(w["first_settlement"].values()) == pytest.approx(1.0, abs=1e-3)
    assert sum(w["second_settlement"].values()) == pytest.approx(1.0, abs=1e-3)
    assert "follow_up" in w["first_settlement"]
    assert "follow_up" not in w["second_settlement"]


def test_scoring_info_without_calibration_summary(tmp_path):
    from main import build_scoring_info
    info = build_scoring_info(summary_path=tmp_path / "missing.json")
    assert info["calibration"] is None
    assert info["resource_values"]


def test_scoring_info_includes_committed_summary():
    cal = client.get("/scoring-info").json()["calibration"]
    assert cal is not None
    assert cal["ci_low"] <= cal["difference"] <= cal["ci_high"]
