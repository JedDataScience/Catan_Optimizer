"""
robber.py — Robber placement and the long-run robber model.

Placement rule: when a player rolls a 7, they move the robber to the hex that
does the most damage to everyone else (pip value × number of other players'
settlements on it). They never block a hex their own settlements touch, and
the desert is never a target.

Long-run model: on any 7, each player is equally likely to be the roller, and
the robber stays put until the next 7. So in the long run, the robber sits on
roller p's target with probability 1 / num_players. The user's expected loss
is the average, over all possible rollers, of the share of the user's
production that roller's target hex blocks. This needs every player's
settlements, so it is only computed once the draft is complete (/analyze).
"""

from typing import Dict, List, Optional, Set

from board import Hex, Intersection, PIP_VALUES


def place_robber_optimally(
    hexes: List[Hex],
    roller_settlement_ids: List[int],
    other_settlement_ids: List[int],
    intersections: List[Intersection],
) -> Optional[int]:
    """
    Return the hex id where the roller should put the robber: the hex that
    maximises damage to the other players' settlements without touching the
    roller's own.

    Returns None (robber stays where it is) if no hex would hurt anyone.
    """
    imap = {i.id: i for i in intersections}

    # Hexes the roller's own settlements touch: off limits
    own_hexes: Set[int] = set()
    for sid in roller_settlement_ids:
        if sid in imap:
            own_hexes.update(imap[sid].hex_ids)

    # hex_id → number of other players' settlements on it
    others_on_hex: Dict[int, int] = {}
    for sid in other_settlement_ids:
        if sid in imap:
            for hid in imap[sid].hex_ids:
                others_on_hex[hid] = others_on_hex.get(hid, 0) + 1

    best_hex: Optional[int] = None
    best_damage = 0  # a target must actually hurt someone

    for h in hexes:
        if h.resource == "desert" or h.number is None or h.id in own_hexes:
            continue
        damage = PIP_VALUES.get(h.number, 0) * others_on_hex.get(h.id, 0)
        if damage > best_damage:
            best_damage = damage
            best_hex = h.id

    return best_hex


def compute_robber_expected_loss(
    hexes: List[Hex],
    intersections: List[Intersection],
    placements: List[dict],   # [{intersection_id, player}] — the full draft
    user_player: int,
    num_players: int,
) -> float:
    """
    Long-run expected share [0..1] of the user's production blocked by the
    robber (see the module docstring for the model).

    A hex touched by both user settlements counts twice, matching how it pays
    out. A roller who is the user never blocks their own hexes, so their
    term is always 0.
    """
    imap = {i.id: i for i in intersections}
    hmap = {h.id: h for h in hexes}

    by_player: Dict[int, List[int]] = {p: [] for p in range(num_players)}
    for pl in placements:
        by_player.setdefault(pl["player"], []).append(pl["intersection_id"])

    # The user's pips per hex (duplicates kept: a shared hex pays twice)
    user_pips_on_hex: Dict[int, int] = {}
    for sid in by_player.get(user_player, []):
        for hid in imap[sid].hex_ids:
            h = hmap[hid]
            if h.number:
                user_pips_on_hex[hid] = user_pips_on_hex.get(hid, 0) + PIP_VALUES[h.number]

    total_user_pips = sum(user_pips_on_hex.values())
    if total_user_pips == 0:
        return 0.0

    total_loss = 0.0
    for roller in range(num_players):
        others = [sid for p, ids in by_player.items() if p != roller for sid in ids]
        target = place_robber_optimally(hexes, by_player.get(roller, []), others, intersections)
        if target is not None:
            total_loss += user_pips_on_hex.get(target, 0) / total_user_pips

    return round(total_loss / num_players, 4)
