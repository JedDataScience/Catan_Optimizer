"""
test_game_sim.py — Rules of the calibration game simulator (calibration/game.py).
"""

import pytest

from board import DEFAULT_PORT_TYPES
from calibration.game import COSTS, DISCARD_LIMIT, RESOURCES, WIN_VP, BoardInfo, Game
from calibration.policy import GreedyPolicy
from tests.helpers import build_board, greedy_draft


@pytest.fixture
def info():
    hexes, inters = build_board()
    return BoardInfo(hexes, inters, DEFAULT_PORT_TYPES)


@pytest.fixture
def placements():
    return [(p["player"], p["intersection_id"]) for p in greedy_draft(4)]


def new_game(info, placements, seed=0):
    return Game(info, placements, 4, GreedyPolicy(), seed=seed)


def empty_hands(game):
    for p in game.players:
        p.hand = {r: 0 for r in RESOURCES}


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def test_starting_cards_come_from_second_settlement(info, placements):
    game = new_game(info, placements)
    for pid in range(4):
        second = [n for p, n in placements if p == pid][1]
        expected = {r: 0 for r in RESOURCES}
        for hid in info.node_hexes[second]:
            if info.hex_resource[hid] != "desert":
                expected[info.hex_resource[hid]] += 1
        assert game.players[pid].hand == expected


def test_setup_gives_each_settlement_a_road(info, placements):
    game = new_game(info, placements)
    for pid in range(4):
        assert len(game.players[pid].roads) == 2
        assert len(game.players[pid].settlements) == 2


# ---------------------------------------------------------------------------
# Production and the robber
# ---------------------------------------------------------------------------

def _hex_with_one_owner(game):
    """A numbered hex touched by exactly one building, and that building."""
    for hid, corners in game.info.hex_corners.items():
        owned = [n for n in corners if n in game.owner]
        if game.info.hex_number[hid] and len(owned) == 1:
            return hid, owned[0]
    raise AssertionError("test board has no such hex")


def test_settlement_produces_one_city_two(info, placements):
    game = new_game(info, placements)
    hid, node = _hex_with_one_owner(game)
    pid, res, roll = game.owner[node], info.hex_resource[hid], info.hex_number[hid]
    game.robber = info.desert
    before = game.players[pid].hand[res]
    game._produce(roll)
    after_settlement = game.players[pid].hand[res]

    game.players[pid].settlements.remove(node)
    game.players[pid].cities.add(node)
    game._produce(roll)
    after_city = game.players[pid].hand[res]
    # Other buildings may sit on another hex with the same number, so compare deltas on this hex only
    other = sum(1 for h in info.hexes_by_roll[roll] if h != hid
                for n in info.hex_corners[h] if game.owner.get(n) == pid and info.hex_resource[h] == res)
    assert after_settlement - before == 1 + other
    assert after_city - after_settlement == 2 + other


def test_robber_hex_produces_nothing(info, placements):
    game = new_game(info, placements)
    hid, node = _hex_with_one_owner(game)
    pid, roll = game.owner[node], info.hex_number[hid]
    empty_hands(game)
    game.robber = hid
    game._produce(roll)
    from_this_hex = game.players[pid].hand[info.hex_resource[hid]]
    others = sum(1 for h in info.hexes_by_roll[roll] if h != hid
                 for n in info.hex_corners[h] if game.owner.get(n) == pid
                 and info.hex_resource[h] == info.hex_resource[hid])
    assert from_this_hex == others


def test_seven_makes_big_hands_discard_half(info, placements):
    game = new_game(info, placements)
    empty_hands(game)
    game.players[1].hand.update({"forest": 5, "hills": 4})      # 9 cards → discard 4
    game.players[2].hand.update({"fields": DISCARD_LIMIT})      # exactly 7 → keeps all
    game._roll_seven(roller=0)
    # The roller may also have stolen one card from someone on the robber's hex
    assert game.players[1].hand_size() in (5, 4)
    assert game.players[2].hand_size() in (DISCARD_LIMIT, DISCARD_LIMIT - 1)
    assert sum(p.hand_size() for p in game.players) == 5 + DISCARD_LIMIT


# ---------------------------------------------------------------------------
# Building rules
# ---------------------------------------------------------------------------

def test_building_pays_the_cost(info, placements):
    game = new_game(info, placements)
    empty_hands(game)
    pid = 0
    game.players[pid].hand.update(COSTS["city"])
    node = next(iter(game.players[pid].settlements))
    game.build_city(pid, node)
    assert game.players[pid].hand_size() == 0
    assert node in game.players[pid].cities


def test_settlement_needs_a_connected_road(info, placements):
    game = new_game(info, placements)
    pid = 0
    game.players[pid].hand.update({r: 5 for r in RESOURCES})
    connected = set(game.legal_settlements(pid))
    unconnected = next(n for n in range(len(info.intersections))
                       if game.spot_is_free(n) and n not in connected)
    with pytest.raises(AssertionError):
        game.build_settlement(pid, unconnected)


def test_distance_rule_blocks_neighbours_of_buildings(info, placements):
    game = new_game(info, placements)
    for node in game.owner:
        for nb in info.adj[node]:
            assert not game.spot_is_free(nb)
    for pid in range(4):
        for spot in game.legal_settlements(pid):
            assert all(nb not in game.owner for nb in info.adj[spot])


def test_roads_cannot_pass_through_opponent_buildings(info, placements):
    game = new_game(info, placements)
    for pid in range(4):
        for a, _ in game.legal_roads(pid):
            assert game.owner.get(a) in (None, pid)


# ---------------------------------------------------------------------------
# Trading and dev cards
# ---------------------------------------------------------------------------

def test_trade_rates_follow_ports(info, placements):
    game = new_game(info, placements)
    p = game.players[0]
    p.ports = set()
    assert game.trade_rate(0, "forest") == 4
    p.ports = {"any"}
    assert game.trade_rate(0, "forest") == 3
    p.ports = {"any", "forest"}
    assert game.trade_rate(0, "forest") == 2
    assert game.trade_rate(0, "hills") == 3


def test_bank_trade_moves_cards(info, placements):
    game = new_game(info, placements)
    empty_hands(game)
    game.players[0].ports = set()
    game.players[0].hand["fields"] = 4
    game.bank_trade(0, "fields", "mountains")
    assert game.players[0].hand["fields"] == 0 and game.players[0].hand["mountains"] == 1


def test_largest_army_needs_three_knights(info, placements):
    game = new_game(info, placements)
    p = game.players[2]
    p.dev_cards = ["knight"] * 3
    for k in range(3):
        p.played_dev_this_turn = False   # each knight on a new turn (one dev card per turn)
        game.play_knight(2)
        assert (game.army_holder == 2) == (k == 2)


# ---------------------------------------------------------------------------
# Whole games
# ---------------------------------------------------------------------------

def test_games_end_when_someone_reaches_ten(info, placements):
    for seed in range(40):
        result = new_game(info, placements, seed).run()
        assert result.winner is not None
        assert result.vp[result.winner] >= WIN_VP
        assert all(v < WIN_VP for i, v in enumerate(result.vp) if i != result.winner)


def test_same_seed_same_game(info, placements):
    a = new_game(info, placements, seed=11).run()
    b = new_game(info, placements, seed=11).run()
    c = new_game(info, placements, seed=12).run()
    assert a == b
    assert (a.winner, a.rounds, a.vp) != (c.winner, c.rounds, c.vp)


# ---------------------------------------------------------------------------
# Progress cards
# ---------------------------------------------------------------------------

def test_year_of_plenty_gives_two_cards(info, placements):
    game = new_game(info, placements)
    empty_hands(game)
    game.players[0].dev_cards = ["year_of_plenty"]
    game.play_year_of_plenty(0, ["mountains", "fields"])
    assert game.players[0].hand["mountains"] == 1 and game.players[0].hand["fields"] == 1


def test_monopoly_takes_every_opponent_card_of_that_type(info, placements):
    game = new_game(info, placements)
    empty_hands(game)
    for pid, n in ((1, 2), (2, 3), (3, 0)):
        game.players[pid].hand["pasture"] = n
    game.players[0].dev_cards = ["monopoly"]
    assert game.play_monopoly(0, "pasture") == 5
    assert game.players[0].hand["pasture"] == 5
    assert all(game.players[p].hand["pasture"] == 0 for p in (1, 2, 3))


def test_road_building_places_two_free_connected_roads(info, placements):
    game = new_game(info, placements)
    empty_hands(game)
    p = game.players[0]
    p.dev_cards = ["road_building"]
    before = len(p.roads)
    policy = GreedyPolicy()
    placed = game.play_road_building(0, lambda: policy.road_toward_best_spot(game, 0))
    assert placed == 2 and len(p.roads) == before + 2
    assert p.hand_size() == 0  # free


def test_only_one_dev_card_per_turn(info, placements):
    game = new_game(info, placements)
    p = game.players[0]
    p.dev_cards = ["year_of_plenty", "knight"]
    game.play_year_of_plenty(0, ["forest", "hills"])
    with pytest.raises(AssertionError):
        game.play_knight(0)


def test_cards_bought_this_turn_cannot_be_played(info, placements):
    game = new_game(info, placements)
    p = game.players[0]
    p.hand.update({"fields": 1, "pasture": 1, "mountains": 1})
    game.deck = ["monopoly"]
    game.buy_dev(0)
    assert p.new_dev_cards == ["monopoly"] and "monopoly" not in p.dev_cards
    with pytest.raises(ValueError):
        game.play_monopoly(0, "forest")


# ---------------------------------------------------------------------------
# Player-to-player trades
# ---------------------------------------------------------------------------

def test_player_trade_swaps_one_card_each(info, placements):
    game = new_game(info, placements)
    empty_hands(game)
    game.players[0].hand["forest"] = 1
    game.players[1].hand["mountains"] = 1
    game.player_trade(0, "forest", 1, "mountains")
    assert game.players[0].hand == {**{r: 0 for r in RESOURCES}, "mountains": 1}
    assert game.players[1].hand == {**{r: 0 for r in RESOURCES}, "forest": 1}


def test_nobody_trades_with_a_near_winner(info, placements):
    game = new_game(info, placements)
    empty_hands(game)
    game.players[1].vp_cards = 6            # 2 settlements + 6 = 8 VP
    game.players[0].hand["forest"] = 1
    game.players[1].hand["mountains"] = 1
    with pytest.raises(AssertionError):
        game.player_trade(0, "forest", 1, "mountains")
    # And the policy never proposes it
    policy = GreedyPolicy()
    others = {o.pid: dict(o.hand) for o in game.players if o.pid != 0}
    deal = policy._player_deal(game, 0, "mountains", dict(game.players[0].hand), others, {"mountains": 1})
    assert deal is None or deal[0] != 1


def test_trade_partner_must_need_the_offered_card(info, placements):
    game = new_game(info, placements)
    empty_hands(game)
    policy = GreedyPolicy()
    me = {**{r: 0 for r in RESOURCES}, "forest": 3}
    # Player 1 is saving for a city (needs fields 2 + mountains 3) and has spare sheep
    others = {1: {**{r: 0 for r in RESOURCES}, "pasture": 2}, 2: {r: 0 for r in RESOURCES},
              3: {r: 0 for r in RESOURCES}}
    # They don't need wood, so no deal for sheep
    assert policy._player_deal(game, 0, "pasture", me, others, {"pasture": 1}) is None
    me["fields"] = 2
    deal = policy._player_deal(game, 0, "pasture", me, others, {"pasture": 1})
    assert deal == (1, "fields")
