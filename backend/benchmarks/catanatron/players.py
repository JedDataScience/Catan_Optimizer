"""
players.py — Catanatron players that differ only in how they pick their two
starting settlements. Everything else (setup roads and the whole rest of the
game) is Catanatron's unmodified AlphaBeta search.

    RecommenderPlayer  starting spots from our recommend(), with any ScoringParams
    MostPipsPlayer     starting spots with the most pips (simple baseline)

Plain AlphaBetaPlayer (Catanatron's own placement) is the control.
"""

import random
from typing import List, Optional

from catanatron.models.enums import ActionType
from catanatron.players.minimax import AlphaBetaPlayer

from board import PIP_VALUES
from scorer import DEFAULT_PARAMS, ScoringParams, compute_pip_total
from simulation import OPPONENT_TEMPERATURE, build_snake_draft, recommend

from .mapping import TranslatedBoard, translate

# Same search settings for every AlphaBeta in the benchmark (pruning for speed)
AB_PARAMS = AlphaBetaPlayer.Params(depth=2, prunning=True)
N_SIMS_PER_PICK = 1000


def make_alphabeta(color) -> AlphaBetaPlayer:
    return AlphaBetaPlayer(color, AB_PARAMS)


def _is_setup_settlement(game, playable_actions) -> bool:
    return (game.state.is_initial_build_phase and bool(playable_actions)
            and all(a.action_type == ActionType.BUILD_SETTLEMENT for a in playable_actions))


def draft_so_far(game, board: TranslatedBoard) -> List[dict]:
    """
    Setup settlements placed so far, in our format, from Catanatron's action
    log. Checks the order is the snake draft our recommender assumes.
    """
    colors = list(game.state.colors)
    snake = build_snake_draft(len(colors))
    placed = []
    for rec in game.state.action_records:
        a = rec.action
        if a.action_type != ActionType.BUILD_SETTLEMENT or len(placed) >= len(snake):
            continue
        seat = colors.index(a.color)
        if seat != snake[len(placed)]:
            raise RuntimeError(f"setup pick {len(placed)} by seat {seat}, expected snake seat {snake[len(placed)]}")
        placed.append({"intersection_id": board.node_to_ours[a.value], "player": seat})
    return placed


class _SetupPicker(AlphaBetaPlayer):
    """
    AlphaBeta, except for the setup settlements listed in `use_for`
    ("s1" = first, "s2" = second), which `pick_node` chooses. Every setup
    pick (ours or AlphaBeta's) is logged in `self.picks` for analysis.
    """

    def __init__(self, color, use_for=("s1", "s2")):
        super().__init__(color, AB_PARAMS)
        self.use_for = tuple(use_for)
        self.picks: List[dict] = []
        self._predicted_follow_up: Optional[float] = None

    def pick_node(self, game, playable_actions, board: TranslatedBoard) -> int:
        raise NotImplementedError

    def decide(self, game, playable_actions):
        if not _is_setup_settlement(game, playable_actions):
            return super().decide(game, playable_actions)
        board = translate(game.state.board.map)
        which = "s2" if self.picks else "s1"
        self._predicted_follow_up = None
        if which in self.use_for:
            node = self.pick_node(game, playable_actions, board)
            action = next((a for a in playable_actions if a.value == node), None)
            if action is None:
                # A pick that isn't legal in Catanatron means the translation is wrong: fail loudly
                raise RuntimeError(f"picked node {node}, which isn't a legal setup spot in Catanatron")
        else:
            action = super().decide(game, playable_actions)   # AlphaBeta's own choice
        self._log(which, action.value, playable_actions, board, chosen_by="ours" if which in self.use_for else "alphabeta")
        return action

    def _log(self, which, node, playable_actions, board, chosen_by):
        hmap = {h.id: h for h in board.hexes}
        pips = lambda n: compute_pip_total(board.intersections[board.node_to_ours[n]].hex_ids, hmap)
        mine = pips(node)
        res: dict = {}
        for hid in board.intersections[board.node_to_ours[node]].hex_ids:
            h = hmap[hid]
            if h.number:
                res[h.resource] = res.get(h.resource, 0) + PIP_VALUES[h.number]
        self.picks.append({
            "pick": which,
            "chosen_by": chosen_by,
            "node": node,
            "pips": mine,
            "pip_rank": 1 + sum(1 for a in playable_actions if pips(a.value) > mine),
            "best_open_pips": max(pips(a.value) for a in playable_actions),
            "resources": res,
            "predicted_follow_up_pips": self._predicted_follow_up,
        })


class AlphaBetaLogged(_SetupPicker):
    """The control: AlphaBeta's own setup picks, logged like the other arms."""

    def __init__(self, color):
        super().__init__(color, use_for=())


class RecommenderPlayer(_SetupPicker):
    """Setup settlements (those in `use_for`) from our recommender's #1 pick."""

    def __init__(self, color, params: ScoringParams = DEFAULT_PARAMS, n_simulations: int = N_SIMS_PER_PICK,
                 opponent_temperature: float = OPPONENT_TEMPERATURE, use_for=("s1", "s2"),
                 strategy_weight: float = 1.0):
        super().__init__(color, use_for=use_for)
        self.scoring = params
        self.strategy_weight = strategy_weight   # the app's slider: 0 = raw production, 1 = long game
        self.n_simulations = n_simulations
        self.opponent_temperature = opponent_temperature
        self.last_recommendation: Optional[List[dict]] = None   # for tests and debugging

    def pick_node(self, game, playable_actions, board):
        placed = draft_so_far(game, board)
        seat = list(game.state.colors).index(self.color)
        mine = [p["intersection_id"] for p in placed if p["player"] == seat]
        # recommend() draws from Python's global random module for its Monte Carlo;
        # save and restore it so this player can't change anything else's randomness
        saved = random.getstate()
        try:
            recs = recommend(
                board.hexes, board.intersections, placed,
                user_position=seat, num_players=len(game.state.colors), draft_step=len(placed),
                s1_id=mine[0] if mine else None, port_types=board.port_types,
                n_simulations=self.n_simulations, strategy_weight=self.strategy_weight,
                params=self.scoring, port_edges=board.port_edges,
                opponent_temperature=self.opponent_temperature,
            )
        finally:
            random.setstate(saved)
        self.last_recommendation = recs
        self._predicted_follow_up = recs[0].get("follow_up_pips")
        return board.ours_to_node[recs[0]["intersection_id"]]


class MostPipsPlayer(_SetupPicker):
    """Starting settlements on the legal spot with the most pips."""

    def pick_node(self, game, playable_actions, board):
        hmap = {h.id: h for h in board.hexes}
        legal = [a.value for a in playable_actions]
        return max(legal, key=lambda n: (compute_pip_total(board.intersections[board.node_to_ours[n]].hex_ids, hmap), -n))
