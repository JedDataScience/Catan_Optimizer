"""
simulation.py — Monte Carlo recommendation engine (v2).

Improvements over v1:
  - Smart opponent placement: opponents weighted toward high-pip intersections
    (proportional sampling with temperature parameter) instead of uniform random.
  - Weighted pip scoring: uses scorer.compute_weighted_pip() with board-scarcity
    and strategic resource multipliers instead of flat pip sums.
  - Synergy scoring: pair complementarity bonus applied per candidate.
  - strategy_weight parameter (0.0 → raw, 1.0 → win-path) propagated through.
  - Port proximity awareness: bonus for intersections adjacent to port tiles.

Sync note: get_exclusion_zone() in this file and getExclusionZone() in
frontend/src/utils/intersectionMap.js must remain logically identical
(occupied ids + all their immediate neighbours).
"""

import random
from collections import defaultdict
from typing import List, Optional, Set, Dict

from board import Hex, Intersection, PIP_VALUES
from scorer import (
    score_candidates,
    rank_candidates,
    compute_combined_stats,
    compute_pip_total,
    compute_diversity,
    compute_weighted_pip,
    compute_diversity_quality,
    compute_synergy_bonus,
    compute_expected_resources,
    compute_combined_expected_resources,
    compute_board_scarcity,
    explain,
    SCORE_WEIGHTS,
    normalise,
)


# ---------------------------------------------------------------------------
# Snake-draft order helpers
# ---------------------------------------------------------------------------

def build_snake_draft(num_players: int) -> List[int]:
    """
    Build the snake draft order for num_players players.

    Examples:
      build_snake_draft(2) → [0, 1, 1, 0]
      build_snake_draft(3) → [0, 1, 2, 2, 1, 0]
      build_snake_draft(4) → [0, 1, 2, 3, 3, 2, 1, 0]
    """
    fwd = list(range(num_players))
    return fwd + list(reversed(fwd))


# ---------------------------------------------------------------------------
# Distance-rule helpers
# SYNC: must match getExclusionZone() in intersectionMap.js exactly.
# ---------------------------------------------------------------------------

def get_exclusion_zone(occupied_ids: List[int], intersections: List[Intersection]) -> Set[int]:
    """
    Return all intersection ids that cannot be used due to the distance rule:
    the occupied ids themselves + all their immediate neighbours (adjacent_ids).
    """
    imap = {i.id: i for i in intersections}
    blocked: Set[int] = set()
    for oid in occupied_ids:
        blocked.add(oid)
        if oid in imap:
            blocked.update(imap[oid].adjacent_ids)
    return blocked


def get_valid_intersections(intersections: List[Intersection], excluded: Set[int]) -> List[Intersection]:
    return [i for i in intersections if i.id not in excluded]


# ---------------------------------------------------------------------------
# Smart opponent placement (v2)
# ---------------------------------------------------------------------------

def place_smart_opponent(
    valid: List[Intersection],
    excluded: Set[int],
    hmap: Dict[int, Hex],
    temperature: float = 1.5,
) -> Optional[int]:
    """
    Place a simulated opponent settlement using pip-weighted sampling.

    Opponents are modelled as "reasonably smart" — they prefer higher-pip
    intersections but don't always take the absolute best spot (temperature
    controls rationality: higher = greedier, 0 = uniform random).

    temperature=1.5 means good spots are ~2-3x more likely to be taken than
    average spots, which reflects casual-to-intermediate player behaviour.
    """
    choices = [i for i in valid if i.id not in excluded]
    if not choices:
        return None

    if temperature == 0.0:
        chosen = random.choice(choices)
    else:
        weights = []
        for intersection in choices:
            pip = sum(
                PIP_VALUES.get(hmap[hid].number, 0)
                for hid in intersection.hex_ids
                if hid in hmap and hmap[hid].number
            )
            # Raise to temperature power so high-pip spots get disproportionate weight
            weights.append(max(pip, 0.1) ** temperature)

        chosen = random.choices(choices, weights=weights, k=1)[0]

    excluded.add(chosen.id)
    excluded.update(chosen.adjacent_ids)
    return chosen.id


# ---------------------------------------------------------------------------
# Port proximity scoring
# ---------------------------------------------------------------------------

# Standard Catan port positions: each port is defined by which intersection IDs
# it touches and what resource it offers (or "any" for 3:1).
# These are fixed for the standard board layout computed by board.py.
# Port awareness boosts intersections near high-value ports.

# Port types: resource → strategic boost for being adjacent
PORT_STRATEGIC_BOOST = {
    "mountains": 0.12,   # 2:1 ore port — strong with ore strategy
    "fields":    0.12,   # 2:1 wheat port
    "pasture":   0.08,   # 2:1 sheep port
    "forest":    0.06,   # 2:1 wood port
    "hills":     0.06,   # 2:1 brick port
    "any":       0.04,   # 3:1 generic port
}

# Standard board port definitions: (intersection_ids_touching_port, resource)
# Derived from standard Catan board geometry (pointy-top, 3-4-5-4-3 layout).
# These IDs correspond to the intersection numbering produced by board.py.
_STANDARD_PORT_INTERSECTIONS = [
    # Top coast
    ([0, 1],     "any"),
    ([2, 3],     "mountains"),
    # Upper-right coast
    ([4, 10],    "fields"),
    ([11, 18],   "any"),
    # Lower-right coast
    ([25, 33],   "hills"),
    ([34, 40],   "any"),
    # Bottom coast
    ([41, 46],   "forest"),
    ([47, 50],   "any"),
    # Lower-left coast
    ([51, 53],   "pasture"),
    ([43, 48],   "any"),
    # Upper-left coast
    ([22, 29],   "any"),
    ([6, 14],    "any"),
]


def compute_port_proximity_boost(
    intersection_id: int,
    intersections: List[Intersection],
    strategy_weight: float = 1.0,
) -> float:
    """
    Return a small boost [0.0..0.12] if this intersection is adjacent to
    a valuable port. Scales with strategy_weight.
    """
    if strategy_weight == 0.0:
        return 0.0

    imap = {i.id: i for i in intersections}
    node = imap.get(intersection_id)
    if not node:
        return 0.0

    nearby_ids = {intersection_id} | set(node.adjacent_ids)
    best_boost = 0.0

    for port_ids, port_resource in _STANDARD_PORT_INTERSECTIONS:
        if any(pid in nearby_ids for pid in port_ids):
            boost = PORT_STRATEGIC_BOOST.get(port_resource, 0.0)
            best_boost = max(best_boost, boost)

    return round(best_boost * strategy_weight, 4)


# ---------------------------------------------------------------------------
# Main recommendation function
# ---------------------------------------------------------------------------

def recommend(
    hexes: List[Hex],
    intersections: List[Intersection],
    placed_settlements: List[dict],   # [{intersection_id, player}]
    user_position: int,               # 0-indexed
    num_players: int,                 # 2-4
    draft_step: int,                  # current step in the draft (user is about to place)
    s1_id: Optional[int],             # None when recommending S1; set for S2
    n_simulations: int = 5000,
    strategy_weight: float = 1.0,     # 0.0 = raw production, 1.0 = win-path
) -> List[dict]:
    """
    Run a batch Monte Carlo to recommend the top 5 intersections for the
    user's next settlement placement.

    Uses smart (pip-weighted) opponent sampling and strategy-aware scoring.
    """
    hmap = {h.id: h for h in hexes}
    imap = {i.id: i for i in intersections}

    # Precompute board-level scarcity for weighted pip scoring
    scarcity = compute_board_scarcity(hexes)

    # Build the snake draft order
    snake_draft = build_snake_draft(num_players)

    # IDs already occupied
    known_occupied  = [p["intersection_id"] for p in placed_settlements]
    known_exclusion = get_exclusion_zone(known_occupied, intersections)

    # Determine future opponent draft steps
    future_steps          = list(range(draft_step + 1, len(snake_draft)))
    future_opponent_steps = [s for s in future_steps if snake_draft[s] != user_position]

    # For S2 scoring: pre-fetch S1's hex_ids
    s1_hex_ids = imap[s1_id].hex_ids if s1_id is not None and s1_id in imap else None

    # Accumulate scores across simulations
    sim_wpip:   Dict[int, List[float]] = defaultdict(list)
    sim_dq:     Dict[int, List[float]] = defaultdict(list)
    sim_syn:    Dict[int, List[float]] = defaultdict(list)
    sim_counts: Dict[int, int]         = defaultdict(int)

    for _ in range(n_simulations):
        excl = set(known_exclusion)

        # Place future opponents using smart (pip-weighted) sampling
        for _ in future_opponent_steps:
            place_smart_opponent(intersections, excl, hmap, temperature=1.5)

        candidates = get_valid_intersections(intersections, excl)
        if not candidates:
            continue

        for c in candidates:
            if s1_hex_ids is not None:
                combined = list(set(s1_hex_ids + c.hex_ids))
            else:
                combined = c.hex_ids

            wpip = compute_weighted_pip(combined, hmap, scarcity, strategy_weight)
            dq   = compute_diversity_quality(combined, hmap, strategy_weight)
            syn  = compute_synergy_bonus(combined, hmap, strategy_weight)

            sim_wpip[c.id].append(wpip)
            sim_dq[c.id].append(dq)
            sim_syn[c.id].append(syn)
            sim_counts[c.id] += 1

    if not sim_wpip:
        # Fallback: deterministic scoring
        candidates = get_valid_intersections(intersections, known_exclusion)
        scored = score_candidates(candidates, hmap, s1_hex_ids, scarcity, strategy_weight)
        return rank_candidates(scored)

    # Aggregate: mean per candidate
    all_stats = []
    for cid, wpip_samples in sim_wpip.items():
        avg_wpip = sum(wpip_samples) / len(wpip_samples)
        avg_dq   = sum(sim_dq[cid])  / len(sim_dq[cid])
        avg_syn  = sum(sim_syn[cid]) / len(sim_syn[cid])
        avail    = sim_counts[cid] / n_simulations

        c = imap[cid]
        port_boost = compute_port_proximity_boost(cid, intersections, strategy_weight)

        # Display pip and diversity (unweighted, for UI)
        if s1_hex_ids is not None:
            combined_ids = list(set(s1_hex_ids + c.hex_ids))
            pip_display  = compute_pip_total(combined_ids, hmap)
            div_display  = compute_diversity(combined_ids, hmap)
        else:
            pip_display = compute_pip_total(c.hex_ids, hmap)
            div_display = compute_diversity(c.hex_ids, hmap)

        all_stats.append({
            "intersection_id":   cid,
            "avg_wpip":          avg_wpip,
            "avg_dq":            avg_dq,
            "avg_syn":           avg_syn,
            "availability":      round(avail, 3),
            "port_boost":        port_boost,
            "pip_total":         pip_display,
            "diversity":         div_display,
            "_raw_score":        None,
        })

    if not all_stats:
        return []

    # Normalise all components
    norm_wpip  = normalise([r["avg_wpip"]      for r in all_stats])
    norm_dq    = normalise([r["avg_dq"]        for r in all_stats])
    norm_syn   = normalise([r["avg_syn"]       for r in all_stats])
    norm_avail = normalise([r["availability"]  for r in all_stats])
    norm_port  = normalise([r["port_boost"]    for r in all_stats])

    port_w = 0.05 * strategy_weight   # port awareness only matters in win-path mode
    rem    = 1.0 - port_w             # remaining weight split among main components

    for i, r in enumerate(all_stats):
        r["_raw_score"] = (
            rem * (
                SCORE_WEIGHTS["pip"]          * norm_wpip[i]   +
                SCORE_WEIGHTS["diversity"]    * norm_dq[i]     +
                SCORE_WEIGHTS["availability"] * norm_avail[i]  +
                SCORE_WEIGHTS["synergy"]      * norm_syn[i]
            )
            + port_w * norm_port[i]
        )

    # Sort and take top 5
    all_stats.sort(key=lambda r: r["_raw_score"], reverse=True)
    top = all_stats[:5]

    # Enrich with full details for the response
    result = []
    for rank_idx, r in enumerate(top):
        c = imap[r["intersection_id"]]

        if s1_hex_ids is not None:
            exp_res = compute_combined_expected_resources(s1_hex_ids, c.hex_ids, hmap)
        else:
            exp_res = compute_expected_resources(c.hex_ids, hmap)

        result.append({
            "rank":              rank_idx + 1,
            "intersection_id":   r["intersection_id"],
            "score":             round(r["_raw_score"], 4),
            "pip_total":         r["pip_total"],
            "diversity":         r["diversity"],
            "availability":      r["availability"],
            "weighted_pip":      round(r["avg_wpip"], 2),
            "synergy_bonus":     round(r["avg_syn"], 3),
            "port_boost":        r["port_boost"],
            "expected_resources": exp_res,
            "explanation": explain(
                pip_total=r["pip_total"],
                diversity=r["diversity"],
                expected_resources=exp_res,
                weighted_pip=r["avg_wpip"],
                synergy_bonus=r["avg_syn"],
                strategy_weight=strategy_weight,
                scarcity=scarcity,
            ),
        })

    return result
