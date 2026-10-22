"""
test_catanatron_bench.py — The Catanatron benchmark's board translation and
players (benchmarks/catanatron/).

Skipped when Catanatron isn't installed:
    uv run --group benchmark pytest tests/test_catanatron_bench.py
"""

import random

import pytest

pytest.importorskip("catanatron.players.minimax")

from catanatron import Color, Game  # noqa: E402
from catanatron.models.map import build_map  # noqa: E402

from benchmarks.catanatron.mapping import RESOURCE_NAMES, translate  # noqa: E402
from benchmarks.catanatron.players import (  # noqa: E402
    MostPipsPlayer,
    RecommenderPlayer,
    draft_so_far,
    make_alphabeta,
)
from board import PIP_VALUES  # noqa: E402
from simulation import build_snake_draft  # noqa: E402

COLORS = (Color.RED, Color.BLUE, Color.ORANGE, Color.WHITE)


@pytest.fixture(params=[0, 1, 2])
def catan_map(request):
    random.seed(request.param)
    return build_map("BASE")


# ---------------------------------------------------------------------------
# Board translation
# ---------------------------------------------------------------------------

def test_nodes_map_one_to_one(catan_map):
    t = translate(catan_map)
    assert sorted(t.node_to_ours) == list(range(54))
    assert sorted(t.node_to_ours.values()) == list(range(54))
    assert all(t.ours_to_node[o] == n for n, o in t.node_to_ours.items())


def test_catanatron_edges_are_our_roads(catan_map):
    t = translate(catan_map)
    edges = {frozenset(e) for tile in catan_map.land_tiles.values() for e in tile.edges.values()}
    ours = {frozenset((i.id, n)) for i in t.intersections for n in i.adjacent_ids}
    assert {frozenset(t.node_to_ours[n] for n in e) for e in edges} == ours


def test_production_carries_over(catan_map):
    # Catanatron's own per-node production (dice probability per resource)
    # must equal what our translated board produces at the matching corner
    t = translate(catan_map)
    hmap = {h.id: h for h in t.hexes}
    for node, counter in catan_map.node_production.items():
        ours = {}
        for hid in t.intersections[t.node_to_ours[node]].hex_ids:
            h = hmap[hid]
            if h.number:
                ours[h.resource] = ours.get(h.resource, 0) + PIP_VALUES[h.number] / 36
        theirs = {RESOURCE_NAMES[r]: p for r, p in counter.items() if p}
        assert ours == pytest.approx(theirs)


def test_ports_are_coastal_edges(catan_map):
    t = translate(catan_map)
    assert len(t.port_edges) == 9
    assert sorted(t.port_types) == sorted(["any"] * 4 + ["fields", "forest", "hills", "mountains", "pasture"])
    for a, b in t.port_edges:
        ia, ib = t.intersections[a], t.intersections[b]
        assert b in ia.adjacent_ids
        assert len(set(ia.hex_ids) & set(ib.hex_ids)) == 1


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------

def _game(test_player, seed):
    players = [test_player] + [make_alphabeta(c) for c in COLORS[1:]]
    return Game(players, seed=seed)


def test_setup_order_is_a_snake_draft():
    game = _game(make_alphabeta(COLORS[0]), seed=4)
    while game.state.is_initial_build_phase:
        game.play_tick()
    board = translate(game.state.board.map)
    placed = draft_so_far(game, board)   # raises if the order isn't a snake
    assert [p["player"] for p in placed] == build_snake_draft(4)


def test_recommender_plays_our_top_pick():
    player = RecommenderPlayer(COLORS[0], n_simulations=300)
    game = _game(player, seed=5)
    # Play until our player has made its first setup pick
    while not any(r.action.color == COLORS[0] for r in game.state.action_records):
        game.play_tick()
    first = next(r.action for r in game.state.action_records if r.action.color == COLORS[0])
    board = translate(game.state.board.map)
    # The settlement actually played is the recommender's #1, translated back
    assert board.node_to_ours[first.value] == player.last_recommendation[0]["intersection_id"]
    assert first.action_type.name == "BUILD_SETTLEMENT"


@pytest.mark.parametrize("make", [RecommenderPlayer, MostPipsPlayer])
def test_custom_players_finish_games(make):
    game = _game(make(COLORS[0]) if make is MostPipsPlayer else make(COLORS[0], n_simulations=200), seed=6)
    winner = game.play()
    assert winner in COLORS


def test_recommender_does_not_disturb_game_randomness():
    """Two arms with the same seed see the same board, seats and dice sequence source."""
    rec = _game(RecommenderPlayer(COLORS[0], n_simulations=200), seed=9)
    ctl = _game(make_alphabeta(COLORS[0]), seed=9)
    assert rec.state.colors == ctl.state.colors
    assert {c: (t.resource, t.number) for c, t in rec.state.board.map.land_tiles.items()} == \
           {c: (t.resource, t.number) for c, t in ctl.state.board.map.land_tiles.items()}
    # The game's own generator is untouched by our player's Monte Carlo
    while rec.state.is_initial_build_phase:
        rec.play_tick()
    while ctl.state.is_initial_build_phase:
        ctl.play_tick()
    assert rec.state.random.random() == ctl.state.random.random()


# ---------------------------------------------------------------------------
# Seat-0 investigation helpers
# ---------------------------------------------------------------------------

def test_seat0_seeds_really_seat_the_test_player_first():
    from benchmarks.catanatron.seat0 import OPPONENTS, TEST, seat0_seeds
    for seed in seat0_seeds(5):
        game = Game([make_alphabeta(TEST)] + [make_alphabeta(c) for c in OPPONENTS], seed=seed)
        assert list(game.state.colors).index(TEST) == 0


@pytest.mark.parametrize("use_for", [("s1",), ("s2",)])
def test_hybrid_uses_the_recommender_for_exactly_one_pick(use_for):
    player = RecommenderPlayer(COLORS[0], n_simulations=200, use_for=use_for)
    game = _game(player, seed=12)
    while game.state.is_initial_build_phase:
        game.play_tick()
    assert [p["pick"] for p in player.picks] == ["s1", "s2"]
    assert [p["chosen_by"] for p in player.picks] == ["ours" if k in use_for else "alphabeta" for k in ("s1", "s2")]


def test_control_logs_alphabeta_picks():
    from benchmarks.catanatron.players import AlphaBetaLogged
    player = AlphaBetaLogged(COLORS[0])
    game = _game(player, seed=13)
    while game.state.is_initial_build_phase:
        game.play_tick()
    assert [p["chosen_by"] for p in player.picks] == ["alphabeta", "alphabeta"]
    assert all(1 <= p["pip_rank"] and p["pips"] <= p["best_open_pips"] for p in player.picks)
