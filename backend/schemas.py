"""
schemas.py — Request models and validation for the API.

Every request is checked against the rules of a standard Catan board before
any simulation runs. A request that breaks a rule is rejected by FastAPI with
HTTP 422 (Unprocessable Content) and a `detail` list saying what was wrong,
instead of crashing deep inside the simulation with a 500.

What is enforced:
  - Board: 19 unique hexes, standard resource counts, standard number tokens,
    desert has no number. (The "6 and 8 not adjacent" rule is NOT enforced:
    it's a setup guideline, and people may enter real boards that break it.)
  - Ports: one type per slot, 4 generic + one 2:1 port per resource.
  - Placements: legal intersection ids, distance rule, and the snake-draft
    order (who places at which step).
"""

from collections import Counter
from typing import Annotated, List, Literal, Optional

from pydantic import AfterValidator, BaseModel, Field, model_validator

from board import (
    DEFAULT_PORT_TYPES,
    RESOURCE_COUNTS,
    TOKEN_COUNTS,
    build_hex_grid,
    build_intersection_map,
)
from simulation import build_snake_draft

ResourceName = Literal["forest", "hills", "fields", "pasture", "mountains", "desert"]
PortType     = Literal["any", "forest", "hills", "fields", "pasture", "mountains"]

# Board geometry never changes, so the adjacency used for the distance rule
# is computed once at import time
_ADJACENT = {i.id: set(i.adjacent_ids) for i in build_intersection_map(build_hex_grid())}
_N_INTERSECTIONS = len(_ADJACENT)


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

class HexData(BaseModel):
    id: int = Field(ge=0, le=18)
    resource: ResourceName
    number: Optional[int] = None

    @model_validator(mode="after")
    def _check_number(self):
        if self.resource == "desert":
            if self.number is not None:
                raise ValueError(f"hex {self.id}: the desert can't have a number token")
        elif self.number not in TOKEN_COUNTS:
            raise ValueError(f"hex {self.id}: number must be 2-6 or 8-12, got {self.number}")
        return self


def _validate_board(board: List[HexData]) -> List[HexData]:
    """Check the board as a whole: every hex once, standard counts."""
    ids = sorted(h.id for h in board)
    if ids != list(range(19)):
        raise ValueError("board must contain each hex id 0-18 exactly once")

    resources = Counter(h.resource for h in board)
    if resources != Counter(RESOURCE_COUNTS):
        raise ValueError(
            f"resource counts must be {RESOURCE_COUNTS}, got {dict(resources)}"
        )

    tokens = Counter(h.number for h in board if h.number is not None)
    if tokens != Counter(TOKEN_COUNTS):
        raise ValueError(f"number tokens must be {TOKEN_COUNTS}, got {dict(tokens)}")
    return board


def _validate_ports(ports: List[str]) -> List[str]:
    """One type per slot: 4 generic 3:1 ports and one 2:1 port per resource."""
    expected = Counter(DEFAULT_PORT_TYPES)
    if len(ports) != len(DEFAULT_PORT_TYPES) or Counter(ports) != expected:
        raise ValueError(
            f"ports must list {len(DEFAULT_PORT_TYPES)} slot types: "
            "4 x 'any' plus one of each resource"
        )
    return ports


# Annotated types attach the whole-list checks to the field itself
Board = Annotated[List[HexData], AfterValidator(_validate_board)]
Ports = Annotated[List[PortType], AfterValidator(_validate_ports)]


def _default_ports() -> List[str]:
    return list(DEFAULT_PORT_TYPES)


class PlacedSettlement(BaseModel):
    intersection_id: int = Field(ge=0, lt=_N_INTERSECTIONS)
    player: int = Field(ge=0, le=3)  # 0-indexed


def _validate_draft(placements: List[PlacedSettlement], num_players: int, expected_len: int) -> None:
    """
    Check placements against the snake draft: right length, right player at
    each step, and the distance rule (no settlement on or next to another).
    """
    if len(placements) != expected_len:
        raise ValueError(f"expected {expected_len} placements so far, got {len(placements)}")

    snake = build_snake_draft(num_players)
    blocked: set = set()
    for step, p in enumerate(placements):
        if p.player != snake[step]:
            raise ValueError(
                f"placement {step}: player {p.player} placed, but it was player {snake[step]}'s turn"
            )
        if p.intersection_id in blocked:
            raise ValueError(
                f"placement {step}: intersection {p.intersection_id} breaks the distance rule"
            )
        blocked.add(p.intersection_id)
        blocked.update(_ADJACENT[p.intersection_id])


def _user_picks(placements: List[PlacedSettlement], user_position: int) -> List[int]:
    return [p.intersection_id for p in placements if p.player == user_position]


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class RecommendRequest(BaseModel):
    board: Board
    ports: Ports = Field(default_factory=_default_ports)
    placed_settlements: List[PlacedSettlement] = Field(default_factory=list)
    user_position: int = Field(default=0, ge=0, le=3)
    num_players: int = Field(default=4, ge=2, le=4)
    draft_step: int = Field(default=0, ge=0)
    s1_id: Optional[int] = None
    n_simulations: int = Field(default=5000, ge=500, le=10000)
    strategy_weight: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check_draft_state(self):
        if self.user_position >= self.num_players:
            raise ValueError("user_position must be less than num_players")

        snake = build_snake_draft(self.num_players)
        if self.draft_step >= len(snake):
            raise ValueError("the draft is already complete")
        if snake[self.draft_step] != self.user_position:
            raise ValueError(f"draft step {self.draft_step} is not the user's turn")

        # Everything placed so far must be a legal draft up to this step
        _validate_draft(self.placed_settlements, self.num_players, self.draft_step)

        # s1_id is given exactly when this is the user's second pick
        earlier = _user_picks(self.placed_settlements, self.user_position)
        if not earlier and self.s1_id is not None:
            raise ValueError("s1_id must be null for the user's first settlement")
        if earlier and self.s1_id != earlier[0]:
            raise ValueError("s1_id must be the user's first placed settlement")
        return self


class AnalyzeRequest(BaseModel):
    board: Board
    ports: Ports = Field(default_factory=_default_ports)
    s1_id: int
    s2_id: int
    all_placements: List[PlacedSettlement]
    num_players: int = Field(default=4, ge=2, le=4)
    user_position: int = Field(default=0, ge=0, le=3)
    strategy_weight: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check_complete_draft(self):
        if self.user_position >= self.num_players:
            raise ValueError("user_position must be less than num_players")
        # Analysis needs the whole draft: every player's two settlements
        _validate_draft(self.all_placements, self.num_players, 2 * self.num_players)
        if _user_picks(self.all_placements, self.user_position) != [self.s1_id, self.s2_id]:
            raise ValueError("s1_id and s2_id must be the user's two placements, in order")
        return self


class BoardAnalysisRequest(BaseModel):
    board: Board
