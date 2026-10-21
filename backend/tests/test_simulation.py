"""
test_simulation.py — Follow-up metric, opponent model, and ranking (simulation.py).
"""

import random

import pytest

from board import DEFAULT_PORT_TYPES
from scorer import compute_expected_resources
from simulation import (
    OPPONENT_STRATEGY_WEIGHT,
    OPPONENT_TEMPERATURE,
    OpponentSampler,
    compute_follow_up,
    compute_pair_value,
    get_exclusion_zone,
    get_valid_intersections,
    recommend,
)
from tests.helpers import greedy_draft


def _follow_up(intersections, hmap, scarcity, window_players, n_simulations=300):
    excl = get_exclusion_zone([0], intersections)
    cands = get_valid_intersections(intersections, excl)
    sampler = OpponentSampler(intersections, hmap, scarcity)
    fu = compute_follow_up(
        cands, intersections, hmap, excl, window_players, {}, n_simulations, scarcity, 1.0, sampler,
    )
    return cands, excl, fu


def _recommend(hexes, intersections, **kwargs):
    args = dict(
        placed_settlements=[], user_position=0, num_players=4, draft_step=0,
        s1_id=None, port_types=DEFAULT_PORT_TYPES, n_simulations=500, strategy_weight=1.0,
    )
    args.update(kwargs)
    return recommend(hexes, intersections, **args)


# ---------------------------------------------------------------------------
# Follow-up
# ---------------------------------------------------------------------------

def test_follow_up_is_exact_without_opponents(intersections, hmap, scarcity):
    cands, excl, fu = _follow_up(intersections, hmap, scarcity, window_players=[])
    for c in cands:
        zone = {c.id} | set(c.adjacent_ids)
        best = max(
            compute_pair_value(c.hex_ids, s.hex_ids, hmap, scarcity, 1.0)
            for s in intersections if s.id not in excl and s.id not in zone
        )
        assert fu[c.id][0] == pytest.approx(best)


def test_opponents_only_lower_follow_up(intersections, hmap, scarcity):
    random.seed(1)
    _, _, none = _follow_up(intersections, hmap, scarcity, window_players=[])
    # Players 1-3 take their first picks, then player 3 their second
    _, _, four = _follow_up(intersections, hmap, scarcity, window_players=[1, 2, 3, 3])
    for cid in none:
        assert four[cid][0] <= none[cid][0] + 1e-9
    assert any(four[cid][0] < none[cid][0] - 1e-9 for cid in none)


def test_no_opponents_in_window_is_deterministic(hexes, intersections):
    # 4 players, user is last (position 3): S1 at step 3, S2 at step 4
    placed = greedy_draft(4, steps=3)

    def run(seed):
        random.seed(seed)
        return _recommend(hexes, intersections, placed_settlements=placed, user_position=3, draft_step=3)

    assert run(1) == run(2)


def test_s1_reports_follow_up_and_s2_does_not(hexes, intersections):
    s1 = _recommend(hexes, intersections)
    assert len(s1) == 5 and all(r["follow_up_pips"] is not None for r in s1)

    placed = greedy_draft(2, steps=3)   # snake [0, 1, 1, 0]: user's S2 is step 3
    s2 = _recommend(
        hexes, intersections, num_players=2, placed_settlements=placed,
        draft_step=3, s1_id=placed[0]["intersection_id"],
    )
    assert s2 and all(r["follow_up_pips"] is None for r in s2)


# ---------------------------------------------------------------------------
# Opponent model
# ---------------------------------------------------------------------------

def test_first_pick_weights(intersections, hmap, scarcity):
    sampler = OpponentSampler(intersections, hmap, scarcity)
    for i in intersections:
        value = compute_pair_value(i.hex_ids, [], hmap, scarcity, OPPONENT_STRATEGY_WEIGHT)
        assert sampler._first.weights[i.id] == pytest.approx(max(value, 0.1) ** OPPONENT_TEMPERATURE)


def test_second_pick_weights_pair_with_own_first(intersections, hmap, scarcity):
    sampler = OpponentSampler(intersections, hmap, scarcity)
    first = intersections[20]
    picker = sampler._second_picker(first.id)
    for i in intersections:
        value = compute_pair_value(first.hex_ids, i.hex_ids, hmap, scarcity, OPPONENT_STRATEGY_WEIGHT)
        assert picker.weights[i.id] == pytest.approx(max(value, 0.1) ** OPPONENT_TEMPERATURE)


def test_opponent_picks_respect_distance_rule(intersections, hmap, scarcity):
    random.seed(3)
    sampler = OpponentSampler(intersections, hmap, scarcity)
    excluded = set()
    picks = [sampler.place(excluded) for _ in range(8)]
    for a in picks:
        for b in picks:
            if a != b:
                assert b not in intersections[a].adjacent_ids


# ---------------------------------------------------------------------------
# Ranking output
# ---------------------------------------------------------------------------

def test_ranking_output_is_consistent(hexes, intersections, hmap):
    recs = _recommend(hexes, intersections)
    scores = [r["score"] for r in recs]
    assert [r["rank"] for r in recs] == [1, 2, 3, 4, 5]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == 100   # best spot on the board
    for r in recs:
        exp = compute_expected_resources(intersections[r["intersection_id"]].hex_ids, hmap)
        assert r["cards_per_roll"] == pytest.approx(sum(exp.values()), abs=1e-3)
