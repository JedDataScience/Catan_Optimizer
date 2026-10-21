"""
scorer.py — Advanced scoring, normalisation, and explanation for Catan settlement
             recommendations.

SCORING MODEL (v2):

  weighted_pip = sum over adj hexes of:
      pip_value(hex) * strategic_value(resource) * (1 + scarcity_boost(resource, board))

  synergy_bonus = multiplier for complementary resource pairs (city engine, rush etc.)

  final_score =
      pip_weight         * norm_weighted_pip
    + diversity_weight   * norm_diversity_quality   ← quality-weighted diversity, not flat count
    + availability_weight * norm_availability        ← fraction of sims spot was unblocked
    + synergy_weight     * norm_synergy_bonus        ← pair complementarity (S2 only)
    - robber_penalty     * norm_robber_risk           ← from robber.py (static)

All components are normalised to [0, 1] across all candidates before combining.

strategy_weight (0.0 → 1.0) is passed in per-request:
  0.0 = pure raw production (flat pip sum, no resource weighting)
  1.0 = full win-path optimisation (Ore/Wheat prioritised, synergy bonuses)
  Values in between linearly interpolate.
"""

from __future__ import annotations
from typing import List, Dict, Optional
from board import Hex, Intersection, PIP_VALUES

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
# Applied when both resources appear in the combined S1+S2 hex set.
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
    "pip":          0.45,   # weighted pip total (resource + scarcity adjusted)
    "diversity":    0.20,   # quality-weighted diversity
    "availability": 0.20,   # Monte Carlo availability (fraction unblocked)
    "synergy":      0.15,   # resource pair complementarity
}

# Fallback for deterministic path (no availability data)
_PIP_W_FALLBACK  = 0.55
_DIV_W_FALLBACK  = 0.25
_SYN_W_FALLBACK  = 0.20

RESOURCE_LABELS = {
    "forest":    "Wood",
    "hills":     "Brick",
    "fields":    "Wheat",
    "pasture":   "Sheep",
    "mountains": "Ore",
}

# ---------------------------------------------------------------------------
# Board-level analysis: scarcity weights
# ---------------------------------------------------------------------------

def compute_board_scarcity(hexes: List[Hex]) -> Dict[str, float]:
    """
    Compute a scarcity score [0.0 .. 1.0] for each resource type on this board.

    Method:
      1. Sum pip values for every hex of each resource type.
      2. Normalise to get each resource's "production share" of the board.
      3. Scarcity = 1.0 - production_share (normalised so rarest = 1.0).

    Returns a dict like:
      {"forest": 0.1, "hills": 0.8, "fields": 0.4, "pasture": 0.2, "mountains": 0.9}
    A value near 1.0 means that resource is very scarce (few/low pip hexes).
    """
    pip_by_resource: Dict[str, float] = {}
    for h in hexes:
        if h.resource and h.resource != "desert" and h.number:
            pip_by_resource[h.resource] = (
                pip_by_resource.get(h.resource, 0.0) + PIP_VALUES[h.number]
            )

    non_desert = ["forest", "hills", "fields", "pasture", "mountains"]
    total = sum(pip_by_resource.get(r, 0.0) for r in non_desert) or 1.0

    # Production share for each resource
    shares = {r: pip_by_resource.get(r, 0.0) / total for r in non_desert}

    # Scarcity = inverse share, normalised to [0, 1]
    max_share = max(shares.values()) or 1.0
    scarcity = {r: 1.0 - (shares[r] / max_share) for r in non_desert}
    return scarcity


def compute_board_analysis(hexes: List[Hex]) -> Dict:
    """
    Return a full board analysis dict:
      - scarcity per resource (0 = abundant, 1 = scarce)
      - total pip per resource
      - abundance label per resource
    """
    pip_by_resource: Dict[str, float] = {}
    for h in hexes:
        if h.resource and h.resource != "desert" and h.number:
            pip_by_resource[h.resource] = (
                pip_by_resource.get(h.resource, 0.0) + PIP_VALUES[h.number]
            )

    non_desert = ["forest", "hills", "fields", "pasture", "mountains"]
    total = sum(pip_by_resource.get(r, 0.0) for r in non_desert) or 1.0
    shares = {r: pip_by_resource.get(r, 0.0) / total for r in non_desert}
    max_share = max(shares.values()) or 1.0
    scarcity = {r: round(1.0 - (shares[r] / max_share), 3) for r in non_desert}

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
        "pip_by_resource": {r: round(pip_by_resource.get(r, 0.0), 1) for r in non_desert},
        "label": {r: abundance_label(scarcity[r]) for r in non_desert},
        "total_board_pips": round(total, 1),
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
    Compute a resource-weighted pip score for a set of hex IDs.

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

def compute_diversity_quality(
    hex_ids: List[int],
    hmap: Dict[int, Hex],
    strategy_weight: float = 1.0,
) -> float:
    """
    Quality-weighted diversity: counts distinct resource types but weights
    them by strategic value when strategy_weight > 0.

    0.0 mode → flat count of distinct resources (original behavior)
    1.0 mode → strategic sum (Ore/Wheat types count more than Wood/Brick)
    """
    resources = {
        hmap[hid].resource
        for hid in hex_ids
        if hid in hmap
        and hmap[hid].resource
        and hmap[hid].resource != "desert"
    }
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

    present = {
        hmap[hid].resource
        for hid in hex_ids
        if hid in hmap and hmap[hid].resource and hmap[hid].resource != "desert"
    }
    bonus = 1.0
    for r_a, r_b, mult in SYNERGY_PAIRS:
        if r_a in present and r_b in present:
            # Blend: at strategy_weight=1 get full mult, at 0 get 1.0
            effective = 1.0 + strategy_weight * (mult - 1.0)
            bonus *= effective
    return round(bonus, 4)


# ---------------------------------------------------------------------------
# Legacy helpers (backward compatibility)
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
    resources = {
        hmap[hid].resource
        for hid in hex_ids
        if hid in hmap and hmap[hid].resource and hmap[hid].resource != "desert"
    }
    return len(resources)


def compute_expected_resources(
    hex_ids: List[int], hmap: Dict[int, Hex]
) -> Dict[str, float]:
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
    out: Dict[str, float] = {}
    for hid in s1_hex_ids + s2_hex_ids:
        h = hmap.get(hid)
        if h and h.number and h.resource and h.resource != "desert":
            prob = PIP_VALUES[h.number] / 36.0
            out[h.resource] = round(out.get(h.resource, 0.0) + prob, 4)
    return out


def compute_combined_stats(
    s1_hex_ids: List[int],
    s2_hex_ids: List[int],
    hmap: Dict[int, Hex],
):
    all_unique_ids = list(set(s1_hex_ids + s2_hex_ids))
    pip_total = compute_pip_total(all_unique_ids, hmap)
    diversity = compute_diversity(all_unique_ids, hmap)
    expected  = compute_combined_expected_resources(s1_hex_ids, s2_hex_ids, hmap)
    return pip_total, diversity, expected


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def normalise(values: List[float]) -> List[float]:
    mn, mx = min(values), max(values)
    if mx == mn:
        return [0.5] * len(values)
    return [(v - mn) / (mx - mn) for v in values]


# ---------------------------------------------------------------------------
# Deterministic fallback scoring (no availability data)
# ---------------------------------------------------------------------------

def score_candidates(
    candidates: List[Intersection],
    hmap: Dict[int, Hex],
    s1_hex_ids: Optional[List[int]] = None,
    scarcity: Optional[Dict[str, float]] = None,
    strategy_weight: float = 1.0,
) -> List[dict]:
    if scarcity is None:
        scarcity = {}

    rows = []
    for c in candidates:
        if s1_hex_ids:
            combined_ids = list(set(s1_hex_ids + c.hex_ids))
            wpip   = compute_weighted_pip(combined_ids, hmap, scarcity, strategy_weight)
            dq     = compute_diversity_quality(combined_ids, hmap, strategy_weight)
            syn    = compute_synergy_bonus(combined_ids, hmap, strategy_weight)
            exp_res = compute_combined_expected_resources(s1_hex_ids, c.hex_ids, hmap)
            pip_display = compute_pip_total(combined_ids, hmap)
            div_display = compute_diversity(combined_ids, hmap)
        else:
            wpip    = compute_weighted_pip(c.hex_ids, hmap, scarcity, strategy_weight)
            dq      = compute_diversity_quality(c.hex_ids, hmap, strategy_weight)
            syn     = compute_synergy_bonus(c.hex_ids, hmap, strategy_weight)
            exp_res = compute_expected_resources(c.hex_ids, hmap)
            pip_display = compute_pip_total(c.hex_ids, hmap)
            div_display = compute_diversity(c.hex_ids, hmap)

        rows.append({
            "intersection_id":    c.id,
            "weighted_pip":       wpip,
            "diversity_quality":  dq,
            "synergy_bonus":      syn,
            "pip_total":          pip_display,
            "diversity":          div_display,
            "expected_resources": exp_res,
            "_raw_score":         None,
        })

    if not rows:
        return rows

    norm_wpip = normalise([r["weighted_pip"]      for r in rows])
    norm_dq   = normalise([r["diversity_quality"] for r in rows])
    norm_syn  = normalise([r["synergy_bonus"]     for r in rows])

    for i, r in enumerate(rows):
        r["_raw_score"] = (
            _PIP_W_FALLBACK * norm_wpip[i]
            + _DIV_W_FALLBACK * norm_dq[i]
            + _SYN_W_FALLBACK * norm_syn[i]
        )

    return rows


def rank_candidates(scored_rows: List[dict], top_n: int = 5) -> List[dict]:
    sorted_rows = sorted(scored_rows, key=lambda r: r["_raw_score"], reverse=True)
    for rank_idx, r in enumerate(sorted_rows):
        r["rank"]  = rank_idx + 1
        r["score"] = round(r["_raw_score"], 4)
        r["explanation"] = explain(
            pip_total=r["pip_total"],
            diversity=r["diversity"],
            expected_resources=r["expected_resources"],
            weighted_pip=r.get("weighted_pip", 0),
            synergy_bonus=r.get("synergy_bonus", 1.0),
            strategy_weight=1.0,
        )
        del r["_raw_score"]
    return sorted_rows[:top_n]


# ---------------------------------------------------------------------------
# Context-aware explanation generator
# ---------------------------------------------------------------------------

def explain(
    pip_total: int,
    diversity: int,
    expected_resources: Dict[str, float],
    weighted_pip: float = 0.0,
    synergy_bonus: float = 1.0,
    robber_discount: float = 0.0,
    strategy_weight: float = 1.0,
    scarcity: Optional[Dict[str, float]] = None,
) -> str:
    """
    Generate a 2-3 sentence context-aware explanation for a recommended intersection.
    Considers strategy mode, resource scarcity, synergy pairs, and robber risk.
    """
    parts = []

    # ── Sentence 1: production strength + best resources ────────────────────
    top = sorted(expected_resources.items(), key=lambda x: -x[1])
    top_names = [RESOURCE_LABELS.get(r, r) for r, _ in top[:2]]

    if strategy_weight > 0.5 and weighted_pip > 0:
        # Win-path mode: note strategic value
        if pip_total >= 13:
            base = f"High-probability spot with strong {' and '.join(top_names)} output"
        elif pip_total >= 10:
            base = f"Reliable production of {' and '.join(top_names)}"
        else:
            base = f"Moderate production, primarily {' and '.join(top_names)}"
    else:
        # Raw mode: just the numbers
        if pip_total >= 13:
            base = f"Excellent pip coverage ({pip_total} pips) producing {' and '.join(top_names)}"
        elif pip_total >= 10:
            base = f"Solid pip total ({pip_total}) with {' and '.join(top_names)} production"
        else:
            base = f"Lower pip total ({pip_total}) — relies on {' and '.join(top_names)}"

    # Scarcity callout
    if scarcity and strategy_weight > 0.3 and top:
        top_res = top[0][0]
        s = scarcity.get(top_res, 0.0)
        if s > 0.65:
            base += f" — {RESOURCE_LABELS.get(top_res, top_res)} is scarce on this board, adding significant value"

    parts.append(base + ".")

    # ── Sentence 2: synergy or diversity ────────────────────────────────────
    if strategy_weight > 0.5 and synergy_bonus > 1.15:
        # Strong synergy detected
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
            parts.append("Strong resource complementarity between your two settlements.")
    elif diversity >= 3:
        parts.append("Covers 3 distinct resource types — good flexibility to adapt your strategy.")
    elif diversity == 2:
        parts.append("Covers 2 resource types; complement with your second settlement.")
    else:
        parts.append("Specialised in a single resource — pair with a very different second spot.")

    # ── Sentence 3: robber risk (only if elevated) ───────────────────────────
    if robber_discount > 0.15:
        pct = round(robber_discount * 100)
        parts.append(
            f"Note: robber risk is elevated (~{pct}% expected output loss) "
            "due to high-value adjacent hexes — opponents will target these."
        )
    elif robber_discount > 0.08:
        parts.append("Moderate robber exposure — keep an eye on the high-pip hexes nearby.")

    return " ".join(parts)
