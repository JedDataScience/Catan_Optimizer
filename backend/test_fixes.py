"""
test_fixes.py — Checks for the follow-up metric, port table, and shared-hex scoring.

Run from the backend folder:
    uv run python test_fixes.py

Plain asserts, no test framework needed. Each test prints PASS or raises.
"""

import random
import time

from board import build_hex_grid, build_intersection_map, apply_board_state, PIP_VALUES
from scorer import compute_combined_stats, compute_pip_total, compute_board_scarcity
from simulation import (
    _STANDARD_PORT_INTERSECTIONS,
    OpponentSampler,
    compute_follow_up,
    compute_pair_value,
    get_exclusion_zone,
    get_valid_intersections,
    recommend,
)

# ---------------------------------------------------------------------------
# A fixed, legal board (19 hexes: 4 forest, 3 hills, 4 fields, 4 pasture,
# 3 mountains, 1 desert; standard number tokens)
# ---------------------------------------------------------------------------

RESOURCES = [
    "mountains", "pasture", "forest",
    "fields", "hills", "pasture", "hills",
    "fields", "forest", "desert", "forest", "mountains",
    "forest", "mountains", "fields", "pasture",
    "hills", "fields", "pasture",
]
NUMBERS = [10, 2, 9, 12, 6, 4, 10, 9, 11, None, 3, 8, 8, 3, 4, 5, 5, 6, 11]

BOARD = [{"id": i, "resource": r, "number": n} for i, (r, n) in enumerate(zip(RESOURCES, NUMBERS))]

HEXES = apply_board_state(build_hex_grid(), BOARD)
INTERSECTIONS = build_intersection_map(HEXES)
HMAP = {h.id: h for h in HEXES}
SCARCITY = compute_board_scarcity(HEXES)


def check(name, fn):
    fn()
    print(f"PASS  {name}")


# ---------------------------------------------------------------------------
# Ports
# ---------------------------------------------------------------------------

def test_ports_are_real_coastal_edges():
    assert len(_STANDARD_PORT_INTERSECTIONS) == 9, "standard board has 9 ports"

    kinds = [res for _, res in _STANDARD_PORT_INTERSECTIONS]
    assert kinds.count("any") == 4, "expected 4 generic 3:1 ports"
    assert sorted(k for k in kinds if k != "any") == sorted(
        ["forest", "hills", "fields", "pasture", "mountains"]
    ), "expected one 2:1 port per resource"

    used = set()
    for (a, b), res in _STANDARD_PORT_INTERSECTIONS:
        ia, ib = INTERSECTIONS[a], INTERSECTIONS[b]
        # The two ends of a port must be joined by one edge...
        assert b in ia.adjacent_ids, f"port {a}-{b} ({res}): not adjacent"
        # ...on the coast: both corners touch fewer than 3 hexes...
        assert len(ia.hex_ids) < 3 and len(ib.hex_ids) < 3, f"port {a}-{b}: not coastal"
        # ...and the edge borders exactly one land hex (the other side is sea)
        assert len(set(ia.hex_ids) & set(ib.hex_ids)) == 1, f"port {a}-{b}: not an outer edge"
        # No intersection serves two ports
        assert not ({a, b} & used), f"port {a}-{b}: overlaps another port"
        used |= {a, b}


# ---------------------------------------------------------------------------
# Shared hexes
# ---------------------------------------------------------------------------

def test_shared_hex_counts_twice():
    # Two corners of the centre-ring hex 8 (forest, 11) that aren't neighbours,
    # so both could legally hold settlements
    corners = [i for i in INTERSECTIONS if 8 in i.hex_ids]
    a = corners[0]
    b = next(c for c in corners[1:] if c.id not in a.adjacent_ids)

    pip_total, _, expected = compute_combined_stats(a.hex_ids, b.hex_ids, HMAP)
    separate = compute_pip_total(a.hex_ids, HMAP) + compute_pip_total(b.hex_ids, HMAP)
    assert pip_total == separate, f"combined {pip_total} != sum of parts {separate}"

    # The shared hex (11 → 2 pips) appears in expected resources twice: 2 × 2/36
    assert abs(expected["forest"] - (
        sum(PIP_VALUES[HMAP[h].number] for h in a.hex_ids + b.hex_ids
            if HMAP[h].resource == "forest") / 36
    )) < 1e-3


# ---------------------------------------------------------------------------
# Follow-up
# ---------------------------------------------------------------------------

def _follow_up(n_opponents, n_simulations=300, placed=(0,)):
    excl = get_exclusion_zone(list(placed), INTERSECTIONS)
    cands = get_valid_intersections(INTERSECTIONS, excl)
    sampler = OpponentSampler(INTERSECTIONS, HMAP)
    return cands, excl, compute_follow_up(
        cands, INTERSECTIONS, HMAP, excl, n_opponents, n_simulations, SCARCITY, 1.0, sampler,
    )


def test_follow_up_exact_without_opponents():
    # With no opponents in between, follow-up = best legal S2 pair, exactly
    cands, excl, fu = _follow_up(n_opponents=0)
    for c in cands:
        zone = {c.id} | set(c.adjacent_ids)
        best = max(
            compute_pair_value(c.hex_ids, s.hex_ids, HMAP, SCARCITY, 1.0)
            for s in INTERSECTIONS if s.id not in excl and s.id not in zone
        )
        assert abs(fu[c.id][0] - best) < 1e-9, f"candidate {c.id}: {fu[c.id][0]} != {best}"


def test_opponents_only_lower_follow_up():
    # Opponents can only remove S2 options, never add them
    random.seed(1)
    _, _, none = _follow_up(n_opponents=0)
    _, _, six  = _follow_up(n_opponents=6)
    for cid in none:
        assert six[cid][0] <= none[cid][0] + 1e-9, f"candidate {cid} improved with opponents"
    # And with 6 greedy opponents, at least some candidates must lose value
    assert any(six[cid][0] < none[cid][0] - 1e-9 for cid in none)


def test_only_picks_before_next_turn_count():
    # 4 players, user is last (position 3): S1 at step 3, S2 at step 4 — no
    # opponents in between, so two runs with different seeds must agree
    def run(seed):
        random.seed(seed)
        return recommend(HEXES, INTERSECTIONS,
                         [{"intersection_id": 0, "player": 0},
                          {"intersection_id": 20, "player": 1},
                          {"intersection_id": 40, "player": 2}],
                         user_position=3, num_players=4, draft_step=3,
                         s1_id=None, n_simulations=500)
    assert run(1) == run(2), "results should be deterministic with no opponents in between"


def test_s2_has_no_follow_up():
    recs = recommend(HEXES, INTERSECTIONS,
                     [{"intersection_id": 0, "player": 0}, {"intersection_id": 30, "player": 1}],
                     user_position=0, num_players=2, draft_step=3,
                     s1_id=0, n_simulations=500)
    assert recs and all(r["follow_up_pips"] is None for r in recs)


def test_s1_reports_follow_up():
    recs = recommend(HEXES, INTERSECTIONS, [], user_position=0, num_players=4,
                     draft_step=0, s1_id=None, n_simulations=500)
    assert len(recs) == 5 and all(r["follow_up_pips"] is not None for r in recs)


# ---------------------------------------------------------------------------
# Timing (worst case: 4 players, user picks first → 6 opponents in between)
# ---------------------------------------------------------------------------

def report_timing():
    for n in (5000, 10000):
        t0 = time.perf_counter()
        recommend(HEXES, INTERSECTIONS, [], user_position=0, num_players=4,
                  draft_step=0, s1_id=None, n_simulations=n)
        print(f"TIME  /recommend worst case, {n} sims: {time.perf_counter() - t0:.2f}s")


if __name__ == "__main__":
    check("ports are real coastal edges", test_ports_are_real_coastal_edges)
    check("shared hex counts twice", test_shared_hex_counts_twice)
    check("follow-up exact without opponents", test_follow_up_exact_without_opponents)
    check("opponents only lower follow-up", test_opponents_only_lower_follow_up)
    check("only picks before next turn count", test_only_picks_before_next_turn_count)
    check("S2 has no follow-up", test_s2_has_no_follow_up)
    check("S1 reports follow-up", test_s1_reports_follow_up)
    report_timing()
