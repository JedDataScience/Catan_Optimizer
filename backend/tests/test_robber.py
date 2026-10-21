"""
test_robber.py — Robber placement and the long-run robber model (robber.py).
"""

import pytest

from board import PIP_VALUES
from robber import compute_robber_expected_loss, place_robber_optimally
from tests.helpers import greedy_draft


def _by_player(placements):
    out = {}
    for p in placements:
        out.setdefault(p["player"], []).append(p["intersection_id"])
    return out


def test_roller_never_blocks_own_hexes(hexes, intersections, imap):
    by_player = _by_player(greedy_draft(4))
    for roller, own in by_player.items():
        others = [s for p, ids in by_player.items() if p != roller for s in ids]
        target = place_robber_optimally(hexes, own, others, intersections)
        own_hexes = {h for s in own for h in imap[s].hex_ids}
        assert target is None or target not in own_hexes


def test_no_damage_means_robber_stays(hexes, intersections):
    assert place_robber_optimally(hexes, [20], [], intersections) is None


def test_expected_loss_matches_hand_calculation(hexes, intersections, imap, hmap):
    # 2 players. Player 0 (the user) rolling never hurts themself, so the
    # expected loss is half of what player 1's best robber move blocks.
    placements = greedy_draft(2)
    by_player = _by_player(placements)
    user, opp = by_player[0], by_player[1]

    # The user's pips per hex (a shared hex counts twice)
    user_pips = {}
    for s in user:
        for h in imap[s].hex_ids:
            if hmap[h].number:
                user_pips[h] = user_pips.get(h, 0) + PIP_VALUES[hmap[h].number]

    # Player 1's best target: the user's hex with the most damage that
    # player 1's own settlements don't touch
    opp_hexes = {h for s in opp for h in imap[s].hex_ids}
    target = max((h for h in user_pips if h not in opp_hexes), key=lambda h: user_pips[h], default=None)
    expected = 0.0 if target is None else (user_pips[target] / sum(user_pips.values())) / 2

    loss = compute_robber_expected_loss(hexes, intersections, placements, user_player=0, num_players=2)
    assert loss == pytest.approx(expected, abs=1e-4)
    # This board/draft is chosen so the opponent does have a target; a 0
    # here would mean the test isn't exercising the model
    assert loss > 0
