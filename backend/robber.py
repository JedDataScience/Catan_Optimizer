"""
robber.py — Robber placement logic for the Catan simulation.

When a 7 is rolled, the robber is placed on the hex that maximises damage
to opponents (highest pip_value × opponent_count), excluding any hex already
adjacent to the user's settlements and the desert.

Simplification note (v1): The robber is NOT simulated per-roll in the Monte
Carlo engine (simulation.py). Instead, get_robber_discount() provides a
static risk metric shown in the Analysis view. True per-round simulation
(50 rolls per game × 10,000 sims) would require significant additional work
and is deferred to a future version.
"""

from typing import List, Optional, Set
from board import Hex, Intersection, PIP_VALUES


def place_robber_optimally(
    hexes: List[Hex],
    user_settlement_ids: List[int],
    opponent_settlement_ids: List[int],
    intersections: List['Intersection'],
    current_robber_hex: Optional[int],
) -> Optional[int]:
    """
    Return the hex id where the robber should be placed to maximise damage
    to the opponent settlements while NOT touching any hex adjacent to the
    user's own settlements.

    Returns None (robber stays) if no valid target exists.
    """
    # Build set of hex ids adjacent to user settlements
    user_adj_hexes: Set[int] = set()
    imap = {i.id: i for i in intersections}
    for sid in user_settlement_ids:
        if sid in imap:
            user_adj_hexes.update(imap[sid].hex_ids)

    # Build map: hex_id → count of opponent settlements adjacent
    opp_adj: dict = {}
    for sid in opponent_settlement_ids:
        if sid in imap:
            for hid in imap[sid].hex_ids:
                opp_adj[hid] = opp_adj.get(hid, 0) + 1

    best_hex: Optional[int] = None
    best_damage: float = -1.0

    for h in hexes:
        if h.resource == "desert":
            continue
        if h.number is None:
            continue
        if h.id in user_adj_hexes:
            continue  # cannot block own production

        pip = PIP_VALUES.get(h.number, 0)
        opp_count = opp_adj.get(h.id, 0)
        damage = pip * opp_count

        if damage > best_damage:
            best_damage = damage
            best_hex = h.id

    return best_hex  # None if no valid target


def get_robber_discount(
    hexes: List[Hex],
    user_settlement_ids: List[int],
    intersections: List['Intersection'],
) -> float:
    """
    Estimate what fraction of production is at risk from the robber.

    Computed as: (sum of pip values of user-adjacent hexes) /
                 (sum of pip values of all non-desert hexes).

    A high value means this intersection sits on high-value hexes that are
    also prime robber targets. Used as an informational metric only.
    """
    imap = {i.id: i for i in intersections}
    user_adj_hexes: Set[int] = set()
    for sid in user_settlement_ids:
        if sid in imap:
            user_adj_hexes.update(imap[sid].hex_ids)

    hmap = {h.id: h for h in hexes}
    total_pips = sum(PIP_VALUES.get(h.number, 0) for h in hexes if h.number)
    adj_pips = sum(
        PIP_VALUES.get(hmap[hid].number, 0)
        for hid in user_adj_hexes
        if hid in hmap and hmap[hid].number
    )

    if total_pips == 0:
        return 0.0
    return round(adj_pips / total_pips, 4)
