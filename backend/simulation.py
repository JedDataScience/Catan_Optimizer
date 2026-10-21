"""
simulation.py — Monte Carlo recommendation engine (v3).

How a candidate spot C is scored for the user's next settlement:
  - Static components (same every simulation, so computed once):
      weighted pip, diversity quality, synergy, port proximity.
  - Follow-up (S1 only, Monte Carlo): the user takes C *now*, so C itself
    can never be blocked. What can be blocked is the user's second
    settlement. Each simulation takes C, places only the opponent picks that
    happen between now and the user's next turn (pip-weighted sampling), and
    records the best S2 pair still open. follow_up = mean of that value.
  - When placing S2 (the user's last pick) nothing comes after it, so the
    follow-up term is dropped and its weight is spread over the rest.

Shared hexes: if S1 and S2 touch the same hex, that hex pays out for both
settlements, so combined hex lists are NOT deduplicated when summing pips.

Sync note: get_exclusion_zone() in this file and getExclusionZone() in
frontend/src/utils/intersectionMap.js must remain logically identical
(occupied ids + all their immediate neighbours).
"""

import bisect
import random
from itertools import accumulate
from typing import List, Optional, Set, Dict, Tuple

from board import Hex, Intersection
from scorer import (
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
# Smart opponent placement
# ---------------------------------------------------------------------------

# After this many blocked draws in a row, stop rejection sampling and pick
# directly from the open spots (only happens when the board is nearly full).
_MAX_REJECTIONS = 50


class OpponentSampler:
    """
    Places simulated opponent settlements using pip-weighted sampling.

    Opponents are modelled as "reasonably smart": a spot's chance of being
    picked is proportional to pip_total ** temperature (higher = greedier,
    0 = uniform random). temperature=1.5 means good spots are ~2-3x more
    likely to be taken than average ones (casual-to-intermediate play).

    Uses rejection sampling: draw from the fixed board-wide weights and
    redraw if the spot is blocked. That gives exactly the same distribution
    as re-weighting only the open spots, but each draw is a fast binary
    search instead of rebuilding a 54-item weight list — this runs millions
    of times per request.

    Assumes intersections[i].id == i (true for build_intersection_map).
    """

    def __init__(self, intersections: List[Intersection], hmap: Dict[int, Hex], temperature: float = 1.5):
        self.intersections = intersections
        self.weights = [
            max(compute_pip_total(i.hex_ids, hmap), 0.1) ** temperature
            for i in intersections
        ]
        # Running total of weights: a uniform draw in [0, total) lands in
        # spot i's slice with probability weight_i / total.
        self.cum_weights = list(accumulate(self.weights))
        self.total = self.cum_weights[-1]

    def place(self, excluded: Set[int]) -> Optional[int]:
        """Pick one open spot, add it + its neighbours to `excluded`, return its id."""
        last = len(self.cum_weights) - 1
        for _ in range(_MAX_REJECTIONS):
            idx = min(bisect.bisect_right(self.cum_weights, random.random() * self.total), last)
            if idx not in excluded:
                break
        else:
            # Board nearly full: sample explicitly from what's left
            open_ids = [i.id for i in self.intersections if i.id not in excluded]
            if not open_ids:
                return None
            idx = random.choices(open_ids, weights=[self.weights[i] for i in open_ids], k=1)[0]

        chosen = self.intersections[idx]
        excluded.add(chosen.id)
        excluded.update(chosen.adjacent_ids)
        return chosen.id


# ---------------------------------------------------------------------------
# Port proximity scoring
# ---------------------------------------------------------------------------

# Port types: resource → strategic boost for a settlement on that port
PORT_STRATEGIC_BOOST = {
    "mountains": 0.12,   # 2:1 ore port — strong with ore strategy
    "fields":    0.12,   # 2:1 wheat port
    "pasture":   0.08,   # 2:1 sheep port
    "forest":    0.06,   # 2:1 wood port
    "hills":     0.06,   # 2:1 brick port
    "any":       0.04,   # 3:1 generic port
}

# Standard 9-port frame: 4 generic 3:1 ports + one 2:1 port per resource.
# Each port sits on one coastal edge, i.e. two adjacent intersections on the
# same outer hex. Positions follow the standard spacing around the board's
# 30 coastal edges (gaps of 3, 3, 4 edges, repeated). Which resource sits on
# which port is a placeholder: real boards shuffle port types.
# IDs match board.py's numbering; test_fixes.py verifies the geometry.
_STANDARD_PORT_INTERSECTIONS = [
    ([8, 9],   "any"),        # top
    ([10, 13], "fields"),     # upper right
    ([22, 37], "mountains"),  # right
    ([45, 46], "any"),        # lower right
    ([50, 53], "hills"),      # bottom
    ([47, 48], "any"),        # lower left
    ([26, 40], "forest"),     # left, lower
    ([16, 28], "pasture"),    # left, upper
    ([2, 3],   "any"),        # upper left
]


def compute_port_proximity_boost(intersection_id: int, strategy_weight: float = 1.0) -> float:
    """
    Return a small boost [0.0..0.12] if a settlement here can trade through a
    port. Only the port's own two intersections can use it. Scales with
    strategy_weight.
    """
    if strategy_weight == 0.0:
        return 0.0

    best_boost = 0.0
    for port_ids, port_resource in _STANDARD_PORT_INTERSECTIONS:
        if intersection_id in port_ids:
            best_boost = max(best_boost, PORT_STRATEGIC_BOOST.get(port_resource, 0.0))

    return round(best_boost * strategy_weight, 4)


# ---------------------------------------------------------------------------
# Follow-up (S1 only): how good a second settlement will still be open?
# ---------------------------------------------------------------------------

def compute_pair_value(
    s1_hex_ids: List[int],
    s2_hex_ids: List[int],
    hmap: Dict[int, Hex],
    scarcity: Dict[str, float],
    strategy_weight: float,
) -> float:
    """
    Value of a two-settlement pair: weighted pips × synergy bonus.
    Hex lists are concatenated, not deduplicated — a shared hex pays out twice.
    """
    combined = s1_hex_ids + s2_hex_ids
    return (
        compute_weighted_pip(combined, hmap, scarcity, strategy_weight)
        * compute_synergy_bonus(combined, hmap, strategy_weight)
    )


def compute_follow_up(
    candidates: List[Intersection],
    intersections: List[Intersection],
    hmap: Dict[int, Hex],
    known_exclusion: Set[int],
    n_opponents: int,
    n_simulations: int,
    scarcity: Dict[str, float],
    strategy_weight: float,
    sampler: OpponentSampler,
) -> Dict[int, Tuple[float, float]]:
    """
    For each S1 candidate C, estimate what the user's best S2 will be after
    the `n_opponents` picks that happen before the user's next turn.

    Returns {candidate_id: (avg best pair value, avg pips of that S2 spot)}.
    """
    # With no opponents in between, nothing is random: one pass is exact
    if n_opponents == 0:
        n_simulations = 1

    open_now = get_valid_intersections(intersections, known_exclusion)
    results: Dict[int, Tuple[float, float]] = {}

    for c in candidates:
        c_zone = {c.id} | set(c.adjacent_ids)

        # Every S2 the user could pair with C, best first, so each simulation
        # can stop at the first option that is still open
        options = sorted(
            (
                (
                    compute_pair_value(c.hex_ids, s.hex_ids, hmap, scarcity, strategy_weight),
                    compute_pip_total(s.hex_ids, hmap),
                    s.id,
                )
                for s in open_now
                if s.id not in c_zone
            ),
            reverse=True,
        )
        if not options:
            results[c.id] = (0.0, 0.0)
            continue

        base_excl = known_exclusion | c_zone
        total_value = 0.0
        total_pips  = 0.0

        for _ in range(n_simulations):
            excl = set(base_excl)
            for _ in range(n_opponents):
                if sampler.place(excl) is None:
                    break
            # Best remaining S2 (adds nothing if every option got blocked)
            for value, pips, sid in options:
                if sid not in excl:
                    total_value += value
                    total_pips  += pips
                    break

        results[c.id] = (total_value / n_simulations, total_pips / n_simulations)

    return results


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
    Recommend the top 5 intersections for the user's next settlement.

    Uses smart (pip-weighted) opponent sampling for the S1 follow-up term
    and strategy-aware scoring for everything else.
    """
    hmap = {h.id: h for h in hexes}
    imap = {i.id: i for i in intersections}

    # Precompute board-level scarcity for weighted pip scoring
    scarcity = compute_board_scarcity(hexes)

    snake_draft = build_snake_draft(num_players)

    # Spots already blocked by placed settlements (distance rule)
    known_occupied  = [p["intersection_id"] for p in placed_settlements]
    known_exclusion = get_exclusion_zone(known_occupied, intersections)

    # For S2 scoring: S1's hex_ids
    s1_hex_ids = imap[s1_id].hex_ids if s1_id is not None and s1_id in imap else None

    candidates = get_valid_intersections(intersections, known_exclusion)
    if not candidates:
        return []

    # Follow-up only applies when placing S1 and the user has a later pick
    next_user_step = next(
        (s for s in range(draft_step + 1, len(snake_draft)) if snake_draft[s] == user_position),
        None,
    )
    use_follow_up = s1_id is None and next_user_step is not None

    follow_up: Dict[int, Tuple[float, float]] = {}
    if use_follow_up:
        # Every pick strictly between now and the user's next turn is an opponent's
        n_opponents = next_user_step - draft_step - 1
        sampler = OpponentSampler(intersections, hmap, temperature=1.5)
        follow_up = compute_follow_up(
            candidates, intersections, hmap, known_exclusion,
            n_opponents, n_simulations, scarcity, strategy_weight, sampler,
        )

    # Static components per candidate
    rows = []
    for c in candidates:
        # For S2, score the pair. Not deduplicated — a shared hex pays out twice.
        hex_ids = s1_hex_ids + c.hex_ids if s1_hex_ids is not None else c.hex_ids
        row = {
            "intersection_id": c.id,
            "wpip":       compute_weighted_pip(hex_ids, hmap, scarcity, strategy_weight),
            "dq":         compute_diversity_quality(hex_ids, hmap, strategy_weight),
            "syn":        compute_synergy_bonus(hex_ids, hmap, strategy_weight),
            "port_boost": compute_port_proximity_boost(c.id, strategy_weight),
            # Unweighted values for the UI
            "pip_total":  compute_pip_total(hex_ids, hmap),
            "diversity":  compute_diversity(hex_ids, hmap),
        }
        if use_follow_up:
            row["follow_up"], row["follow_up_pips"] = follow_up[c.id]
        rows.append(row)

    # Component weights. Without a follow-up term (S2), rescale the rest so
    # they still sum to 1.
    component_keys = {"pip": "wpip", "diversity": "dq", "synergy": "syn"}
    if use_follow_up:
        component_keys["follow_up"] = "follow_up"
    weight_sum = sum(SCORE_WEIGHTS[k] for k in component_keys)
    weights    = {k: SCORE_WEIGHTS[k] / weight_sum for k in component_keys}

    # Normalise every component to [0, 1] across candidates before combining
    norm      = {k: normalise([r[field] for r in rows]) for k, field in component_keys.items()}
    norm_port = normalise([r["port_boost"] for r in rows])

    port_w = 0.05 * strategy_weight   # port awareness only matters in win-path mode
    rem    = 1.0 - port_w             # remaining weight split among main components

    for i, r in enumerate(rows):
        r["_raw_score"] = (
            rem * sum(weights[k] * norm[k][i] for k in weights)
            + port_w * norm_port[i]
        )

    # Sort and take top 5
    rows.sort(key=lambda r: r["_raw_score"], reverse=True)
    top = rows[:5]

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
            # Expected pips of the best S2 still open (S1 only; None for S2)
            "follow_up_pips":    round(r["follow_up_pips"], 1) if use_follow_up else None,
            "weighted_pip":      round(r["wpip"], 2),
            "synergy_bonus":     round(r["syn"], 3),
            "port_boost":        r["port_boost"],
            "expected_resources": exp_res,
            "explanation": explain(
                pip_total=r["pip_total"],
                diversity=r["diversity"],
                expected_resources=exp_res,
                weighted_pip=r["wpip"],
                synergy_bonus=r["syn"],
                strategy_weight=strategy_weight,
                scarcity=scarcity,
            ),
        })

    return result
