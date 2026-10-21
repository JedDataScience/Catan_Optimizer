"""
scorer.py — Scoring components, normalisation, and explanations for Catan
             settlement recommendations.

SCORING MODEL (v3):

  weighted_pip = sum over adjacent hexes of
      pip_value(hex) * strategic_value(resource) * (1 + scarcity_boost(resource, board))

  diversity_quality = distinct resource types, weighted by strategic value
  synergy_bonus     = multiplier for complementary resource pairs (city engine etc.)
  follow_up         = value of the best S2 still open after opponents pick
                      (Monte Carlo, S1 only; see simulation.py)
  expansion         = weighted pips of the best 2 open spots two roads away

  final_score = sum of SCORE_WEIGHTS[k] * z_score(component k)
                + a small port bonus (win-path mode only)

Components have different units, so each is converted to a z-score (how many
standard deviations it sits from the average candidate) before combining.
Unlike min-max scaling, one extreme candidate doesn't squash all the others.

strategy_weight (0.0 → 1.0) is passed in per-request:
  0.0 = pure raw production (flat pip sum, no resource weighting)
  1.0 = full win-path optimisation (Ore/Wheat prioritised, synergy bonuses)
  Values in between linearly interpolate.

Shared hexes: when both settlements touch the same hex it pays out for each,
so combined hex lists are concatenated, never deduplicated, when summing.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from board import Hex, Intersection, PIP_VALUES

NON_DESERT = ["forest", "hills", "fields", "pasture", "mountains"]

# ---------------------------------------------------------------------------
# Resource strategic values (win-path mode)
# ---------------------------------------------------------------------------
# Calibrated from 60,000 simulated games (backend/calibration/REPORT.md):
# the value of one pip of each resource relative to the average resource.
# (Previous hand-picked values in brackets.)

STRATEGIC_VALUE: Dict[str, float] = {
    "mountains": 1.21,   # Ore    — cities and dev cards            [1.25]
    "fields":    1.16,   # Wheat  — needed for almost everything    [1.35]
    "hills":     0.97,   # Brick  — roads and settlements           [0.90]
    "forest":    0.91,   # Wood   — roads and settlements           [0.90]
    "pasture":   0.75,   # Sheep  — rarely the bottleneck           [1.10]
    "desert":    0.00,
}

# Raw production mode: all resources equal
STRATEGIC_VALUE_RAW: Dict[str, float] = {
    "fields":    1.0,
    "mountains": 1.0,
    "pasture":   1.0,
    "forest":    1.0,
    "hills":     1.0,
    "desert":    0.0,
}

# ---------------------------------------------------------------------------
# Resource synergy pairs
# Each tuple: (resource_a, resource_b, win_path_multiplier)
# Applied when both resources appear in the hexes being scored.
# ---------------------------------------------------------------------------

# Calibrated (REPORT.md); previous values in brackets. Ore + Sheep showed no
# clear effect in the simulations, so it gets no bonus.
SYNERGY_PAIRS = [
    ("mountains", "fields",  1.14),   # Ore + Wheat   = city engine            [1.40]
    ("mountains", "pasture", 1.00),   # Ore + Sheep   = no clear effect        [1.20]
    ("fields",    "pasture", 1.05),   # Wheat + Sheep = dev cards              [1.15]
    ("forest",    "hills",   1.08),   # Wood + Brick  = roads/settlements      [1.10]
    ("forest",    "fields",  1.04),   # Wood + Wheat  = settlements            [1.05]
    ("hills",     "fields",  1.04),   # Brick + Wheat = settlements            [1.05]
]

# Explanation sentence per pair (see explain)
SYNERGY_SENTENCES = {
    frozenset({"mountains", "fields"}):  "Ore and Wheat together enable the city engine — the strongest late-game strategy.",
    frozenset({"mountains", "pasture"}): "Ore and Sheep pair well for development cards and army control.",
    frozenset({"fields", "pasture"}):    "Wheat and Sheep support a development card strategy.",
    frozenset({"forest", "hills"}):      "Wood and Brick fuel early road and settlement expansion.",
    frozenset({"forest", "fields"}):     "Wood and Wheat cover most of what a new settlement needs.",
    frozenset({"hills", "fields"}):      "Brick and Wheat cover most of what a new settlement needs.",
}

# A pair's bonus is at full strength once its weaker resource has this many
# pips (one 6 or 8); below that it scales down linearly (see synergy_strength)
SYNERGY_FULL_PIPS = 5

# ---------------------------------------------------------------------------
# Canonical scoring weights — single source of truth
# ---------------------------------------------------------------------------

# Calibrated (REPORT.md); previous values in brackets. Weights are relative:
# recommend() rescales whichever ones apply so they sum to 1. Follow-up can't
# be fitted from final positions, so 0.30 is the best of the head-to-head
# grid (0.1 / 0.2 / 0.3).
SCORE_WEIGHTS = {
    "pip":       0.428,  # weighted pip total (resource + scarcity adjusted)  [0.40]
    "diversity": 0.110,  # quality-weighted diversity                          [0.15]
    "follow_up": 0.300,  # Monte Carlo: value of best S2 still open (S1 only)  [0.20]
    "synergy":   0.074,  # resource pair complementarity                       [0.15]
    "expansion": 0.188,  # best open spots two roads away                      [0.10]
}

# Port bonus weight at strategy_weight = 1 (ports only matter in win-path mode)
PORT_WEIGHT = 0.09  # calibrated [0.05]

# A fully scarce resource is worth up to this much extra (calibrated [0.60])
SCARCITY_BOOST = 0.52

# Port types: resource → strategic boost for a settlement on that port
PORT_STRATEGIC_BOOST = {
    "mountains": 0.12,   # 2:1 ore port — strong with ore strategy
    "fields":    0.12,   # 2:1 wheat port
    "pasture":   0.08,   # 2:1 sheep port
    "forest":    0.06,   # 2:1 wood port
    "hills":     0.06,   # 2:1 brick port
    "any":       0.04,   # 3:1 generic port
}

# How many expansion targets count (you realistically build toward 1-2)
EXPANSION_TOP_N = 2

# Explanation thresholds (unweighted pips). A pair of settlements has about
# twice the pips of a single spot, so it gets its own cutoffs.
SINGLE_PIPS_HIGH  = 13
SINGLE_PIPS_SOLID = 10
PAIR_PIPS_HIGH    = 22
PAIR_PIPS_SOLID   = 17
# Top ~15% of spots on random boards (median is ~19), so the sentence is
# only shown when expansion genuinely stands out
EXPANSION_PIPS_STRONG = 23
# Mention a resource pair only when its bonus is at least this big. Scaled to
# the calibrated multipliers (the strongest pair, Ore + Wheat, is 1.14).
SYNERGY_SENTENCE_MIN_BONUS = 1.05

RESOURCE_LABELS = {
    "forest":    "Wood",
    "hills":     "Brick",
    "fields":    "Wheat",
    "pasture":   "Sheep",
    "mountains": "Ore",
}


# ---------------------------------------------------------------------------
# Tunable scoring values, bundled so they can be swapped as a unit
# ---------------------------------------------------------------------------
# The app always uses DEFAULT_PARAMS (built from the constants above). The
# calibration tooling (backend/calibration/) passes alternative ScoringParams
# to compare candidate values head-to-head without editing module constants.

@dataclass(frozen=True)
class ScoringParams:
    strategic_value:   Dict[str, float] = field(default_factory=lambda: dict(STRATEGIC_VALUE))
    score_weights:     Dict[str, float] = field(default_factory=lambda: dict(SCORE_WEIGHTS))
    synergy_pairs:     Tuple[Tuple[str, str, float], ...] = tuple(SYNERGY_PAIRS)
    synergy_full_pips: float = SYNERGY_FULL_PIPS
    port_weight:       float = PORT_WEIGHT
    port_boost:        Dict[str, float] = field(default_factory=lambda: dict(PORT_STRATEGIC_BOOST))
    expansion_top_n:   int = EXPANSION_TOP_N
    scarcity_boost:    float = SCARCITY_BOOST


DEFAULT_PARAMS = ScoringParams()

# ---------------------------------------------------------------------------
# Board-level analysis: scarcity
# ---------------------------------------------------------------------------

def _pips_by_resource(hexes: List[Hex]) -> Dict[str, float]:
    """Total pip value of every hex of each resource type."""
    pips: Dict[str, float] = {r: 0.0 for r in NON_DESERT}
    for h in hexes:
        if h.resource in pips and h.number:
            pips[h.resource] += PIP_VALUES[h.number]
    return pips


def compute_board_scarcity(hexes: List[Hex]) -> Dict[str, float]:
    """
    Compute a scarcity score [0.0 .. 1.0] for each resource type on this board.

    Method:
      1. Sum pip values for every hex of each resource type.
      2. Each resource's "production share" = its pips / all pips.
      3. Scarcity = 1 - share / largest share (most common resource = 0).

    A value near 1.0 means that resource is very scarce (few/low pip hexes).
    """
    pips = _pips_by_resource(hexes)
    total = sum(pips.values()) or 1.0
    shares = {r: pips[r] / total for r in NON_DESERT}
    max_share = max(shares.values()) or 1.0
    return {r: 1.0 - (shares[r] / max_share) for r in NON_DESERT}


def compute_board_analysis(hexes: List[Hex]) -> Dict:
    """
    Return a full board analysis dict:
      - scarcity per resource (0 = abundant, 1 = scarce)
      - total pip per resource
      - abundance label per resource
    """
    pips = _pips_by_resource(hexes)
    scarcity = {r: round(s, 3) for r, s in compute_board_scarcity(hexes).items()}

    def abundance_label(s: float) -> str:
        if s < 0.25:
            return "abundant"
        elif s < 0.55:
            return "moderate"
        elif s < 0.80:
            return "scarce"
        else:
            return "very scarce"

    return {
        "scarcity": scarcity,
        "pip_by_resource": {r: round(pips[r], 1) for r in NON_DESERT},
        "label": {r: abundance_label(scarcity[r]) for r in NON_DESERT},
        "total_board_pips": round(sum(pips.values()), 1),
    }


# ---------------------------------------------------------------------------
# Weighted pip scoring
# ---------------------------------------------------------------------------

def compute_weighted_pip(
    hex_ids: List[int],
    hmap: Dict[int, Hex],
    scarcity: Dict[str, float],
    strategy_weight: float = 1.0,
    params: ScoringParams = DEFAULT_PARAMS,
) -> float:
    """
    Compute a resource-weighted pip score for a list of hex IDs.

    strategy_weight:
      0.0 → all resources equal (raw production)
      1.0 → full strategic weighting (Ore/Wheat prioritised)
      Interpolated linearly in between.
    """
    total = 0.0
    for hid in hex_ids:
        h = hmap.get(hid)
        if not h or not h.number or not h.resource or h.resource == "desert":
            continue
        pip = PIP_VALUES[h.number]
        strat = params.strategic_value.get(h.resource, 1.0)
        raw   = STRATEGIC_VALUE_RAW.get(h.resource, 1.0)
        # Linearly interpolate between raw and strategic
        eff_strat = raw + strategy_weight * (strat - raw)
        # Scarcity boost: a scarce resource gets up to params.scarcity_boost extra
        scar  = scarcity.get(h.resource, 0.0)
        eff_strat *= (1.0 + params.scarcity_boost * strategy_weight * scar)
        total += pip * eff_strat
    return round(total, 3)


# ---------------------------------------------------------------------------
# Diversity quality score
# ---------------------------------------------------------------------------

def _resources_present(hex_ids: List[int], hmap: Dict[int, Hex]) -> Set[str]:
    return {
        hmap[hid].resource
        for hid in hex_ids
        if hid in hmap and hmap[hid].resource and hmap[hid].resource != "desert"
    }


def compute_diversity_quality(
    hex_ids: List[int],
    hmap: Dict[int, Hex],
    strategy_weight: float = 1.0,
    params: ScoringParams = DEFAULT_PARAMS,
) -> float:
    """
    Quality-weighted diversity: counts distinct resource types but weights
    them by strategic value when strategy_weight > 0.

    0.0 mode → flat count of distinct resources
    1.0 mode → strategic sum (Ore/Wheat types count more than Wood/Brick)
    """
    resources = _resources_present(hex_ids, hmap)
    if strategy_weight == 0.0:
        return float(len(resources))

    strat_sum = sum(params.strategic_value.get(r, 1.0) for r in resources)
    raw_sum   = float(len(resources))
    return raw_sum + strategy_weight * (strat_sum - raw_sum)


# ---------------------------------------------------------------------------
# Synergy bonus
# ---------------------------------------------------------------------------

def _pips_per_resource(hex_ids: List[int], hmap: Dict[int, Hex]) -> Dict[str, int]:
    """Pips of each resource over these hexes (a repeated hex counts again)."""
    pips: Dict[str, int] = {}
    for hid in hex_ids:
        h = hmap.get(hid)
        if h and h.number and h.resource and h.resource != "desert":
            pips[h.resource] = pips.get(h.resource, 0) + PIP_VALUES[h.number]
    return pips


def synergy_strength(pips_a: float, pips_b: float, full_pips: float = SYNERGY_FULL_PIPS) -> float:
    """
    How fully a resource pair "works" [0..1]: limited by the weaker side.

    A pair needs real production of both resources: a single 2 or 12 (1 pip)
    of ore doesn't make an ore-and-wheat city engine. Strength grows linearly
    with the weaker side's pips and is full at `full_pips` (default: one 6 or 8).
    """
    return min(min(pips_a, pips_b) / full_pips, 1.0)


def compute_synergy_bonus(
    hex_ids: List[int],
    hmap: Dict[int, Hex],
    strategy_weight: float = 1.0,
    params: ScoringParams = DEFAULT_PARAMS,
) -> float:
    """
    Compute a synergy multiplier (≥ 1.0) based on resource pair complementarity,
    scaled by how much of each resource in the pair is actually produced.
    Only meaningful when strategy_weight > 0.
    """
    if strategy_weight == 0.0:
        return 1.0

    pips = _pips_per_resource(hex_ids, hmap)
    bonus = 1.0
    for r_a, r_b, mult in params.synergy_pairs:
        if r_a in pips and r_b in pips:
            strength = synergy_strength(pips[r_a], pips[r_b], params.synergy_full_pips)
            # Blend: full multiplier at strategy_weight=1 and full strength
            bonus *= 1.0 + strategy_weight * strength * (mult - 1.0)
    return round(bonus, 4)


def strongest_synergy(
    expected_resources: Dict[str, float],
    params: ScoringParams = DEFAULT_PARAMS,
) -> Optional[Tuple[str, str]]:
    """
    The pair contributing the most bonus, given expected cards per roll per
    resource (pips = cards × 36). None if no pair reaches half strength, so
    explanations only mention pairs that genuinely work.
    """
    best, best_gain = None, 0.0
    for r_a, r_b, mult in params.synergy_pairs:
        if r_a in expected_resources and r_b in expected_resources:
            strength = synergy_strength(
                expected_resources[r_a] * 36, expected_resources[r_b] * 36, params.synergy_full_pips,
            )
            gain = strength * (mult - 1.0)
            if strength >= 0.5 and gain > best_gain:
                best, best_gain = (r_a, r_b), gain
    return best


# ---------------------------------------------------------------------------
# Ports
# ---------------------------------------------------------------------------

def compute_port_boost(
    intersection_id: int,
    ports: List[Tuple[Tuple[int, int], str]],   # [((a, b), port_type)]
    strategy_weight: float = 1.0,
    params: ScoringParams = DEFAULT_PARAMS,
) -> float:
    """
    Return a small boost [0.0..0.12] if a settlement here can trade through a
    port. Only the port's own two intersections can use it. Scales with
    strategy_weight.
    """
    if strategy_weight == 0.0:
        return 0.0

    best = 0.0
    for port_ids, port_type in ports:
        if intersection_id in port_ids:
            best = max(best, params.port_boost.get(port_type, 0.0))
    return round(best * strategy_weight, 4)


# ---------------------------------------------------------------------------
# Expansion potential
# ---------------------------------------------------------------------------

def compute_expansion(
    intersection: Intersection,
    imap: Dict[int, Intersection],
    hmap: Dict[int, Hex],
    excluded: Set[int],
    scarcity: Dict[str, float],
    strategy_weight: float = 1.0,
    params: ScoringParams = DEFAULT_PARAMS,
) -> Tuple[float, int]:
    """
    How good are the spots you could expand to with two roads?

    Targets are intersections exactly two edges away (neighbours of
    neighbours, minus the spot itself and its direct neighbours, which the
    distance rule forbids anyway). Only open targets — not already occupied
    or blocked — count.

    Returns (sum of weighted pips of the best params.expansion_top_n targets,
             their unweighted pip total for display).
    """
    neighbours = set(intersection.adjacent_ids)
    two_away = {
        far
        for n in neighbours
        for far in imap[n].adjacent_ids
    } - neighbours - {intersection.id}

    scored = sorted(
        (
            (
                compute_weighted_pip(imap[t].hex_ids, hmap, scarcity, strategy_weight, params),
                compute_pip_total(imap[t].hex_ids, hmap),
            )
            for t in two_away
            if t not in excluded
        ),
        reverse=True,
    )[:params.expansion_top_n]

    return (
        round(sum(w for w, _ in scored), 3),
        sum(p for _, p in scored),
    )


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def compute_pip_total(hex_ids: List[int], hmap: Dict[int, Hex]) -> int:
    """Unweighted pip sum — used for display/UI, not primary scoring."""
    return sum(
        PIP_VALUES.get(hmap[hid].number, 0)
        for hid in hex_ids
        if hid in hmap and hmap[hid].number
    )


def compute_diversity(hex_ids: List[int], hmap: Dict[int, Hex]) -> int:
    """Flat diversity count — used for display/UI."""
    return len(_resources_present(hex_ids, hmap))


def compute_expected_resources(
    hex_ids: List[int], hmap: Dict[int, Hex]
) -> Dict[str, float]:
    """Expected cards of each resource per dice roll (pips / 36 per hex)."""
    out: Dict[str, float] = {}
    for hid in hex_ids:
        h = hmap.get(hid)
        if h and h.number and h.resource and h.resource != "desert":
            prob = PIP_VALUES[h.number] / 36.0
            out[h.resource] = round(out.get(h.resource, 0.0) + prob, 4)
    return out


def compute_combined_expected_resources(
    s1_hex_ids: List[int],
    s2_hex_ids: List[int],
    hmap: Dict[int, Hex],
) -> Dict[str, float]:
    """
    Combined expected resources for two settlements.
    Intentionally NOT deduplicated — if both settlements touch the same hex,
    that hex produces for both (correct Catan rule).
    """
    return compute_expected_resources(s1_hex_ids + s2_hex_ids, hmap)


def compute_combined_stats(
    s1_hex_ids: List[int],
    s2_hex_ids: List[int],
    hmap: Dict[int, Hex],
):
    # Not deduplicated: a hex touched by both settlements pays out twice.
    # (Diversity counts distinct resource types, so duplicates don't affect it.)
    all_ids = s1_hex_ids + s2_hex_ids
    pip_total = compute_pip_total(all_ids, hmap)
    diversity = compute_diversity(all_ids, hmap)
    expected  = compute_combined_expected_resources(s1_hex_ids, s2_hex_ids, hmap)
    return pip_total, diversity, expected


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def normalise(values: List[float]) -> List[float]:
    """Min-max scale to [0, 1]. Used for the 0-100 display score only."""
    mn, mx = min(values), max(values)
    if mx == mn:
        return [0.5] * len(values)
    return [(v - mn) / (mx - mn) for v in values]


def standardise(values: List[float]) -> List[float]:
    """
    Z-scores: (value - mean) / standard deviation. Used to combine score
    components with different units. All-equal values → all 0 (the
    component can't separate candidates, so it shouldn't move the ranking).
    """
    if len(values) < 2:
        return [0.0] * len(values)
    mean = statistics.fmean(values)
    sd   = statistics.pstdev(values)
    if sd == 0:
        return [0.0] * len(values)
    return [(v - mean) / sd for v in values]


# ---------------------------------------------------------------------------
# Context-aware explanation generator
# ---------------------------------------------------------------------------

def explain(
    pip_total: int,
    diversity: int,
    expected_resources: Dict[str, float],
    weighted_pip: float = 0.0,
    synergy_bonus: float = 1.0,
    strategy_weight: float = 1.0,
    scarcity: Optional[Dict[str, float]] = None,
    is_pair: bool = False,
    robber_loss: Optional[float] = None,
    expansion_pips: Optional[int] = None,
    params: ScoringParams = DEFAULT_PARAMS,
) -> str:
    """
    Generate a short context-aware explanation for a recommendation.

    is_pair:        pip_total covers both settlements (S2 / final analysis),
                    so the pair thresholds apply.
    robber_loss:    long-run share of production the robber blocks (only
                    known once the draft is complete).
    expansion_pips: pips of the best open spots two roads away.
    """
    parts = []
    high, solid = (PAIR_PIPS_HIGH, PAIR_PIPS_SOLID) if is_pair else (SINGLE_PIPS_HIGH, SINGLE_PIPS_SOLID)

    # ── Sentence 1: production strength + best resources ────────────────────
    top = sorted(expected_resources.items(), key=lambda x: -x[1])
    top_names = " and ".join(RESOURCE_LABELS.get(r, r) for r, _ in top[:2]) or "no resources"

    if strategy_weight > 0.5 and weighted_pip > 0:
        # Win-path mode: describe strategic strength
        if pip_total >= high:
            base = f"High-probability spot with strong {top_names} output"
        elif pip_total >= solid:
            base = f"Reliable production of {top_names}"
        else:
            base = f"Moderate production, primarily {top_names}"
    else:
        # Raw mode: just the numbers
        if pip_total >= high:
            base = f"Excellent pip coverage ({pip_total} pips) producing {top_names}"
        elif pip_total >= solid:
            base = f"Solid pip total ({pip_total}) with {top_names} production"
        else:
            base = f"Lower pip total ({pip_total}) — relies on {top_names}"

    # Scarcity callout
    if scarcity and strategy_weight > 0.3 and top:
        top_res = top[0][0]
        if scarcity.get(top_res, 0.0) > 0.65:
            base += f" — {RESOURCE_LABELS.get(top_res, top_res)} is scarce on this board, adding significant value"

    parts.append(base + ".")

    # ── Sentence 2: synergy or diversity ────────────────────────────────────
    # Only name a pair that genuinely works (both sides produce meaningfully)
    pair = (strongest_synergy(expected_resources, params)
            if strategy_weight > 0.5 and synergy_bonus >= SYNERGY_SENTENCE_MIN_BONUS else None)
    if pair:
        parts.append(SYNERGY_SENTENCES.get(frozenset(pair), "Strong resource complementarity."))
    elif diversity >= 3:
        parts.append(f"Covers {diversity} distinct resource types — good flexibility to adapt your strategy.")
    elif diversity == 2:
        parts.append("Covers 2 resource types; complement with your other settlement.")
    else:
        parts.append("Specialised in a single resource — pair with a very different spot.")

    # ── Sentence 3: expansion (only if strong) ──────────────────────────────
    if expansion_pips is not None and expansion_pips >= EXPANSION_PIPS_STRONG:
        parts.append(f"Good room to grow: strong open spots ({expansion_pips} pips) are two roads away.")

    # ── Sentence 4: robber risk (only if elevated) ──────────────────────────
    if robber_loss is not None:
        pct = round(robber_loss * 100)
        if robber_loss > 0.15:
            parts.append(
                f"Robber risk is elevated: in the long run it blocks about {pct}% of your "
                "production, because your best hexes are also opponents' best targets."
            )
        elif robber_loss > 0.08:
            parts.append(f"Moderate robber exposure (about {pct}% of production blocked in the long run).")

    return " ".join(parts)
