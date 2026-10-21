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
from typing import Dict, List, Optional, Set, Tuple

from board import Hex, Intersection, PIP_VALUES

NON_DESERT = ["forest", "hills", "fields", "pasture", "mountains"]

# ---------------------------------------------------------------------------
# Resource strategic values (win-path mode)
# ---------------------------------------------------------------------------
# Based on competitive analysis: Ore/Wheat are critical for cities and dev cards,
# Sheep enables dev cards, Wood/Brick are early-game only.

STRATEGIC_VALUE: Dict[str, float] = {
    "fields":    1.35,   # Wheat  — most valuable, needed for almost everything
    "mountains": 1.25,   # Ore    — essential for cities and dev cards
    "pasture":   1.10,   # Sheep  — strong with ore/wheat (dev cards)
    "forest":    0.90,   # Wood   — early game (roads/settlements)
    "hills":     0.90,   # Brick  — early game (roads/settlements)
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

SYNERGY_PAIRS = [
    ("mountains", "fields",  1.40),   # Ore + Wheat  = city engine (dominant)
    ("mountains", "pasture", 1.20),   # Ore + Sheep  = dev cards
    ("fields",    "pasture", 1.15),   # Wheat + Sheep = dev cards
    ("forest",    "hills",   1.10),   # Wood + Brick  = early roads/settlements
    ("forest",    "fields",  1.05),   # Wood + Wheat  = settlements
    ("hills",     "fields",  1.05),   # Brick + Wheat = settlements
]

# ---------------------------------------------------------------------------
# Canonical scoring weights — single source of truth
# ---------------------------------------------------------------------------

SCORE_WEIGHTS = {
    "pip":       0.40,   # weighted pip total (resource + scarcity adjusted)
    "diversity": 0.15,   # quality-weighted diversity
    "follow_up": 0.20,   # Monte Carlo: value of best S2 still open (S1 only)
    "synergy":   0.15,   # resource pair complementarity
    "expansion": 0.10,   # best open spots two roads away
}

# Port bonus weight at strategy_weight = 1 (ports only matter in win-path mode)
PORT_WEIGHT = 0.05

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

RESOURCE_LABELS = {
    "forest":    "Wood",
    "hills":     "Brick",
    "fields":    "Wheat",
    "pasture":   "Sheep",
    "mountains": "Ore",
}

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
        strat = STRATEGIC_VALUE.get(h.resource, 1.0)
        raw   = STRATEGIC_VALUE_RAW.get(h.resource, 1.0)
        # Linearly interpolate between raw and strategic
        eff_strat = raw + strategy_weight * (strat - raw)
        # Scarcity boost: scarce resource gets up to +60% extra
        scar  = scarcity.get(h.resource, 0.0)
        eff_strat *= (1.0 + 0.6 * strategy_weight * scar)
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

    strat_sum = sum(STRATEGIC_VALUE.get(r, 1.0) for r in resources)
    raw_sum   = float(len(resources))
    return raw_sum + strategy_weight * (strat_sum - raw_sum)


# ---------------------------------------------------------------------------
# Synergy bonus
# ---------------------------------------------------------------------------

def compute_synergy_bonus(
    hex_ids: List[int],
    hmap: Dict[int, Hex],
    strategy_weight: float = 1.0,
) -> float:
    """
    Compute a synergy multiplier (≥ 1.0) based on resource pair complementarity.
    Only meaningful when strategy_weight > 0.
    """
    if strategy_weight == 0.0:
        return 1.0

    present = _resources_present(hex_ids, hmap)
    bonus = 1.0
    for r_a, r_b, mult in SYNERGY_PAIRS:
        if r_a in present and r_b in present:
            # Blend: at strategy_weight=1 get full mult, at 0 get 1.0
            bonus *= 1.0 + strategy_weight * (mult - 1.0)
    return round(bonus, 4)


# ---------------------------------------------------------------------------
# Ports
# ---------------------------------------------------------------------------

def compute_port_boost(
    intersection_id: int,
    ports: List[Tuple[Tuple[int, int], str]],   # [((a, b), port_type)]
    strategy_weight: float = 1.0,
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
            best = max(best, PORT_STRATEGIC_BOOST.get(port_type, 0.0))
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
) -> Tuple[float, int]:
    """
    How good are the spots you could expand to with two roads?

    Targets are intersections exactly two edges away (neighbours of
    neighbours, minus the spot itself and its direct neighbours, which the
    distance rule forbids anyway). Only open targets — not already occupied
    or blocked — count.

    Returns (sum of weighted pips of the best EXPANSION_TOP_N targets,
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
                compute_weighted_pip(imap[t].hex_ids, hmap, scarcity, strategy_weight),
                compute_pip_total(imap[t].hex_ids, hmap),
            )
            for t in two_away
            if t not in excluded
        ),
        reverse=True,
    )[:EXPANSION_TOP_N]

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
    if strategy_weight > 0.5 and synergy_bonus > 1.15:
        present = set(expected_resources.keys())
        if "mountains" in present and "fields" in present:
            parts.append("Ore and Wheat together enable the city engine — the strongest late-game strategy.")
        elif "mountains" in present and "pasture" in present:
            parts.append("Ore and Sheep pair well for development cards and army control.")
        elif "fields" in present and "pasture" in present:
            parts.append("Wheat and Sheep support a development card strategy.")
        elif "forest" in present and "hills" in present:
            parts.append("Wood and Brick fuel early road and settlement expansion.")
        else:
            parts.append("Strong resource complementarity.")
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
