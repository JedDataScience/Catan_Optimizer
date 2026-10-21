"""
simulation.py — Monte Carlo recommendation engine (v4).

How a candidate spot C is scored for the user's next settlement:
  - Static components (same in every simulation, so computed once):
      weighted pip, diversity quality, synergy, expansion, port bonus.
  - Follow-up (S1 only, Monte Carlo): the user takes C *now*, so C itself
    can never be blocked. What can be blocked is the user's second
    settlement. Each simulation takes C, plays out only the opponent picks
    between now and the user's next turn, and records the best S2 pair
    still open. follow_up = mean of that value.
  - When placing S2 (the user's last pick) nothing comes after it, so the
    follow-up term is dropped and its weight is spread over the rest.

Opponents are "average players": they value spots the same way the user's
scoring does, at a middling strategy weight, and pick with probability
proportional to value ** temperature. An opponent's second pick is scored as
a pair with their own first pick, so it complements it.

Shared hexes: if S1 and S2 touch the same hex, that hex pays out for both
settlements, so combined hex lists are NOT deduplicated when summing pips.

Sync note: get_exclusion_zone() in this file and getExclusionZone() in
frontend/src/utils/intersectionMap.js must remain logically identical
(occupied ids + all their immediate neighbours).
"""

import bisect
import random
from itertools import accumulate
from typing import Dict, List, Optional, Set, Tuple

from board import PORT_SLOTS, Hex, Intersection
from scorer import (
    DEFAULT_PARAMS,
    ScoringParams,
    compute_board_scarcity,
    compute_diversity,
    compute_diversity_quality,
    compute_expansion,
    compute_expected_resources,
    compute_pip_total,
    compute_port_boost,
    compute_synergy_bonus,
    compute_weighted_pip,
    explain,
    normalise,
    standardise,
)

# How opponents value spots (0 = raw pips, 1 = full win-path weighting)
OPPONENT_STRATEGY_WEIGHT = 0.5

# Opponent greediness: pick probability ∝ value ** temperature.
# 1.5 makes good spots ~2-3x more likely than average ones (casual-to-
# intermediate play); 0 would be uniform random.
OPPONENT_TEMPERATURE = 1.5

# After this many blocked draws in a row, stop rejection sampling and pick
# directly from the open spots (only happens when the board is nearly full).
_MAX_REJECTIONS = 50


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
# Pair value (shared by the user's follow-up and the opponent model)
# ---------------------------------------------------------------------------

def compute_pair_value(
    s1_hex_ids: List[int],
    s2_hex_ids: List[int],
    hmap: Dict[int, Hex],
    scarcity: Dict[str, float],
    strategy_weight: float,
    params: ScoringParams = DEFAULT_PARAMS,
) -> float:
    """
    Value of a settlement pair: weighted pips × synergy bonus. Pass an empty
    s2_hex_ids to value a single spot.
    Hex lists are concatenated, not deduplicated — a shared hex pays out twice.
    """
    combined = s1_hex_ids + s2_hex_ids
    return (
        compute_weighted_pip(combined, hmap, scarcity, strategy_weight, params)
        * compute_synergy_bonus(combined, hmap, strategy_weight, params)
    )


# ---------------------------------------------------------------------------
# Smart opponent placement
# ---------------------------------------------------------------------------

class _WeightedPicker:
    """
    Picks an open intersection with probability proportional to fixed weights.

    Uses rejection sampling: draw from the full weight list and redraw if the
    spot is blocked. That gives exactly the same distribution as re-weighting
    only the open spots, but each draw is a fast binary search instead of
    rebuilding a 54-item list — this runs millions of times per request.
    """

    def __init__(self, weights: List[float]):
        self.weights = weights
        # Running totals: a uniform draw in [0, total) lands in spot i's
        # slice with probability weight_i / total
        self.cum_weights = list(accumulate(weights))
        self.total = self.cum_weights[-1]
        self._last = len(weights) - 1

    def pick(self, excluded: Set[int]) -> Optional[int]:
        for _ in range(_MAX_REJECTIONS):
            idx = min(bisect.bisect_right(self.cum_weights, random.random() * self.total), self._last)
            if idx not in excluded:
                return idx
        # Board nearly full: sample explicitly from what's left
        open_ids = [i for i in range(len(self.weights)) if i not in excluded]
        if not open_ids:
            return None
        return random.choices(open_ids, weights=[self.weights[i] for i in open_ids], k=1)[0]


class OpponentSampler:
    """
    Places simulated opponent settlements.

    First pick:  weight ∝ value(spot) ** temperature
    Second pick: weight ∝ value(own first + spot) ** temperature, so the
                 opponent builds a complementary pair.

    Second-pick weights depend on the opponent's first pick; one weight list
    per first pick is built lazily and cached.

    Assumes intersections[i].id == i (true for build_intersection_map).
    """

    def __init__(
        self,
        intersections: List[Intersection],
        hmap: Dict[int, Hex],
        scarcity: Dict[str, float],
        temperature: float = OPPONENT_TEMPERATURE,
        strategy_weight: float = OPPONENT_STRATEGY_WEIGHT,
    ):
        self.intersections = intersections
        self.hmap = hmap
        self.scarcity = scarcity
        self.temperature = temperature
        self.strategy_weight = strategy_weight

        self._first = _WeightedPicker([self._weight(i.hex_ids, []) for i in intersections])
        self._second: Dict[int, _WeightedPicker] = {}

    def _weight(self, first_hex_ids: List[int], spot_hex_ids: List[int]) -> float:
        value = compute_pair_value(first_hex_ids, spot_hex_ids, self.hmap, self.scarcity, self.strategy_weight)
        # Floor keeps zero-value spots (e.g. desert-only) pickable as a last resort
        return max(value, 0.1) ** self.temperature

    def _second_picker(self, first_id: int) -> _WeightedPicker:
        if first_id not in self._second:
            first_hex_ids = self.intersections[first_id].hex_ids
            self._second[first_id] = _WeightedPicker(
                [self._weight(first_hex_ids, i.hex_ids) for i in self.intersections]
            )
        return self._second[first_id]

    def place(self, excluded: Set[int], own_first: Optional[int] = None) -> Optional[int]:
        """
        Pick one open spot for an opponent (pairing with `own_first` if this
        is their second settlement), add it + its neighbours to `excluded`,
        and return its id.
        """
        picker = self._first if own_first is None else self._second_picker(own_first)
        idx = picker.pick(excluded)
        if idx is None:
            return None
        chosen = self.intersections[idx]
        excluded.add(chosen.id)
        excluded.update(chosen.adjacent_ids)
        return chosen.id


# ---------------------------------------------------------------------------
# Follow-up (S1 only): how good a second settlement will still be open?
# ---------------------------------------------------------------------------

def compute_follow_up(
    candidates: List[Intersection],
    intersections: List[Intersection],
    hmap: Dict[int, Hex],
    known_exclusion: Set[int],
    window_players: List[int],
    known_firsts: Dict[int, int],
    n_simulations: int,
    scarcity: Dict[str, float],
    strategy_weight: float,
    sampler: OpponentSampler,
    params: ScoringParams = DEFAULT_PARAMS,
) -> Dict[int, Tuple[float, float]]:
    """
    For each S1 candidate C, estimate what the user's best S2 will be after
    the opponent picks that happen before the user's next turn.

    window_players: who picks at each step between now and the user's next
                    turn, in order (all opponents).
    known_firsts:   {player: intersection_id} for opponents who have already
                    placed their first settlement.

    Returns {candidate_id: (avg best pair value, avg pips of that S2 spot)}.
    """
    # With no opponents in between, nothing is random: one pass is exact
    if not window_players:
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
                    compute_pair_value(c.hex_ids, s.hex_ids, hmap, scarcity, strategy_weight, params),
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
            excl   = set(base_excl)
            firsts = dict(known_firsts)
            for player in window_players:
                # A player who already has a settlement is making their second pick
                placed = sampler.place(excl, own_first=firsts.get(player))
                if placed is None:
                    break
                firsts.setdefault(player, placed)
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
    port_types: List[str],            # port type per slot in board.PORT_SLOTS
    n_simulations: int = 5000,
    strategy_weight: float = 1.0,     # 0.0 = raw production, 1.0 = win-path
    params: ScoringParams = DEFAULT_PARAMS,  # scoring values (calibration swaps these)
) -> List[dict]:
    """
    Recommend the top 5 intersections for the user's next settlement.
    Assumes the request was validated (schemas.RecommendRequest).

    `params` only changes how the *user's* options are valued. The simulated
    opponents always use the default model, so comparing two sets of params
    compares the user's choices against identical opponents.
    """
    hmap = {h.id: h for h in hexes}
    imap = {i.id: i for i in intersections}
    ports = list(zip(PORT_SLOTS, port_types))

    # Precompute board-level scarcity for weighted pip scoring
    scarcity = compute_board_scarcity(hexes)

    snake_draft = build_snake_draft(num_players)

    # Spots already blocked by placed settlements (distance rule)
    known_occupied  = [p["intersection_id"] for p in placed_settlements]
    known_exclusion = get_exclusion_zone(known_occupied, intersections)

    # For S2 scoring: S1's hex_ids
    s1_hex_ids = imap[s1_id].hex_ids if s1_id is not None else None
    is_pair = s1_hex_ids is not None

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
        window_players = snake_draft[draft_step + 1:next_user_step]
        known_firsts: Dict[int, int] = {}
        for p in placed_settlements:
            known_firsts.setdefault(p["player"], p["intersection_id"])
        sampler = OpponentSampler(intersections, hmap, scarcity)
        follow_up = compute_follow_up(
            candidates, intersections, hmap, known_exclusion,
            window_players, known_firsts, n_simulations, scarcity, strategy_weight, sampler, params,
        )

    # Static components per candidate
    rows = []
    for c in candidates:
        # For S2, score the pair. Not deduplicated — a shared hex pays out twice.
        hex_ids = s1_hex_ids + c.hex_ids if is_pair else c.hex_ids
        expansion, expansion_pips = compute_expansion(
            c, imap, hmap, known_exclusion, scarcity, strategy_weight, params,
        )
        row = {
            "intersection_id": c.id,
            "wpip":           compute_weighted_pip(hex_ids, hmap, scarcity, strategy_weight, params),
            "dq":             compute_diversity_quality(hex_ids, hmap, strategy_weight, params),
            "syn":            compute_synergy_bonus(hex_ids, hmap, strategy_weight, params),
            "expansion":      expansion,
            "expansion_pips": expansion_pips,
            "port_boost":     compute_port_boost(c.id, ports, strategy_weight, params),
            # Unweighted values for the UI
            "pip_total":      compute_pip_total(hex_ids, hmap),
            "diversity":      compute_diversity(hex_ids, hmap),
        }
        if use_follow_up:
            row["follow_up"], row["follow_up_pips"] = follow_up[c.id]
        rows.append(row)

    # Component weights. Without a follow-up term (S2), rescale the rest so
    # they still sum to 1.
    component_keys = {"pip": "wpip", "diversity": "dq", "synergy": "syn", "expansion": "expansion"}
    if use_follow_up:
        component_keys["follow_up"] = "follow_up"
    weight_sum = sum(params.score_weights[k] for k in component_keys)
    weights    = {k: params.score_weights[k] / weight_sum for k in component_keys}

    # Z-score every component across candidates, then take the weighted sum
    z      = {k: standardise([r[field] for r in rows]) for k, field in component_keys.items()}
    z_port = standardise([r["port_boost"] for r in rows])

    port_w = params.port_weight * strategy_weight   # port awareness only matters in win-path mode
    for i, r in enumerate(rows):
        r["_raw_score"] = (
            (1.0 - port_w) * sum(weights[k] * z[k][i] for k in weights)
            + port_w * z_port[i]
        )

    # Display score: 0-100 relative to the best and worst spot on this board
    for r, scaled in zip(rows, normalise([r["_raw_score"] for r in rows])):
        r["display_score"] = round(100 * scaled)

    # Sort and take top 5
    rows.sort(key=lambda r: r["_raw_score"], reverse=True)
    top = rows[:5]

    # Enrich with full details for the response
    result = []
    for rank_idx, r in enumerate(top):
        c = imap[r["intersection_id"]]
        hex_ids = s1_hex_ids + c.hex_ids if is_pair else c.hex_ids
        exp_res = compute_expected_resources(hex_ids, hmap)

        result.append({
            "rank":              rank_idx + 1,
            "intersection_id":   r["intersection_id"],
            "score":             r["display_score"],
            "cards_per_roll":    round(sum(exp_res.values()), 3),
            "pip_total":         r["pip_total"],
            "diversity":         r["diversity"],
            # Expected pips of the best S2 still open (S1 only; None for S2)
            "follow_up_pips":    round(r["follow_up_pips"], 1) if use_follow_up else None,
            "expansion_pips":    r["expansion_pips"],
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
                is_pair=is_pair,
                expansion_pips=r["expansion_pips"],
                params=params,
            ),
        })

    return result
