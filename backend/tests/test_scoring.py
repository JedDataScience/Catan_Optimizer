"""
test_scoring.py — Scoring components and explanations (scorer.py).
"""

import statistics

import pytest

from board import DEFAULT_PORT_TYPES, PIP_VALUES, PORT_SLOTS, Hex
from scorer import (
    compute_combined_stats,
    compute_expansion,
    compute_pip_total,
    compute_port_boost,
    compute_synergy_bonus,
    explain,
    standardise,
)


# ---------------------------------------------------------------------------
# Synergy: a pair only counts in proportion to its weaker side
# ---------------------------------------------------------------------------

def _hexes(*specs):
    """hmap from (resource, number) pairs, ids 0..n-1."""
    return {i: Hex(id=i, resource=r, number=n) for i, (r, n) in enumerate(specs)}


def test_lone_two_or_twelve_barely_triggers_synergy():
    weak = _hexes(("fields", 8), ("mountains", 12))   # wheat 5 pips, ore 1 pip
    full = _hexes(("fields", 8), ("mountains", 6))    # wheat 5 pips, ore 5 pips
    weak_bonus = compute_synergy_bonus([0, 1], weak, strategy_weight=1.0)
    full_bonus = compute_synergy_bonus([0, 1], full, strategy_weight=1.0)
    assert full_bonus == pytest.approx(1.40)          # Ore + Wheat at full strength
    assert weak_bonus == pytest.approx(1 + 0.4 * 1 / 5)  # 1 pip of 5 → a fifth of the bonus
    assert weak_bonus < full_bonus


def test_explanation_only_names_pairs_that_work():
    lone_ore  = {"fields": 5 / 36, "mountains": 1 / 36}
    solid_ore = {"fields": 5 / 36, "mountains": 4 / 36}
    assert "Ore and Wheat" not in explain(14, 2, lone_ore, weighted_pip=10, synergy_bonus=1.3)
    assert "Ore and Wheat" in explain(14, 2, solid_ore, weighted_pip=10, synergy_bonus=1.3)


# ---------------------------------------------------------------------------
# Shared hexes
# ---------------------------------------------------------------------------

def test_shared_hex_counts_twice(intersections, hmap):
    # Two non-neighbouring corners of hex 8 (forest, 11): both could hold settlements
    corners = [i for i in intersections if 8 in i.hex_ids]
    a = corners[0]
    b = next(c for c in corners[1:] if c.id not in a.adjacent_ids)

    pip_total, _, expected = compute_combined_stats(a.hex_ids, b.hex_ids, hmap)
    assert pip_total == compute_pip_total(a.hex_ids, hmap) + compute_pip_total(b.hex_ids, hmap)

    # Forest output includes hex 8 twice
    forest_pips = sum(
        PIP_VALUES[hmap[h].number] for h in a.hex_ids + b.hex_ids if hmap[h].resource == "forest"
    )
    assert expected["forest"] == pytest.approx(forest_pips / 36, abs=1e-3)


# ---------------------------------------------------------------------------
# Ports
# ---------------------------------------------------------------------------

def test_port_boost_only_on_port_intersections(imap):
    ports = list(zip(PORT_SLOTS, DEFAULT_PORT_TYPES))
    on_port = {i for slot in PORT_SLOTS for i in slot}
    for iid in imap:
        boost = compute_port_boost(iid, ports, strategy_weight=1.0)
        assert (boost > 0) == (iid in on_port), f"intersection {iid}"


def test_port_boost_follows_port_type():
    slot = PORT_SLOTS[0]
    ore  = compute_port_boost(slot[0], [(slot, "mountains")], 1.0)
    any_ = compute_port_boost(slot[0], [(slot, "any")], 1.0)
    assert ore > any_ > 0
    assert compute_port_boost(slot[0], [(slot, "mountains")], 0.0) == 0.0


# ---------------------------------------------------------------------------
# Expansion
# ---------------------------------------------------------------------------

def _graph_distance_2(imap, start):
    """Independent check: breadth-first search for nodes exactly 2 edges away."""
    dist = {start: 0}
    frontier = [start]
    for d in (1, 2):
        nxt = []
        for node in frontier:
            for n in imap[node].adjacent_ids:
                if n not in dist:
                    dist[n] = d
                    nxt.append(n)
        frontier = nxt
    return {n for n, d in dist.items() if d == 2}


def test_expansion_uses_best_two_open_spots_two_roads_away(imap, hmap, scarcity):
    c = imap[20]
    targets = _graph_distance_2(imap, c.id)
    blocked = {max(targets)}  # pretend one target is taken

    _, pips = compute_expansion(c, imap, hmap, blocked, scarcity, strategy_weight=0.0)

    open_pips = sorted((compute_pip_total(imap[t].hex_ids, hmap) for t in targets - blocked), reverse=True)
    assert pips == sum(open_pips[:2])


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def test_standardise_gives_mean_0_sd_1():
    z = standardise([1.0, 2.0, 3.0, 10.0])
    assert statistics.fmean(z) == pytest.approx(0.0)
    assert statistics.pstdev(z) == pytest.approx(1.0)


def test_standardise_constant_values_are_neutral():
    assert standardise([5.0, 5.0, 5.0]) == [0.0, 0.0, 0.0]


# ---------------------------------------------------------------------------
# Explanations
# ---------------------------------------------------------------------------

RES = {"fields": 0.2, "mountains": 0.1}


def test_pair_uses_higher_pip_thresholds():
    # 18 pips is excellent for one spot but only solid for a pair
    single = explain(18, 2, RES, strategy_weight=0.0, is_pair=False)
    pair   = explain(18, 2, RES, strategy_weight=0.0, is_pair=True)
    assert single.startswith("Excellent")
    assert pair.startswith("Solid")


def test_robber_sentence_only_with_known_loss():
    assert "robber" not in explain(12, 2, RES).lower()
    assert "blocks about 20%" in explain(12, 2, RES, robber_loss=0.2)
