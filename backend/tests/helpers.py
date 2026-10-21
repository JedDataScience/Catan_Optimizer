"""
helpers.py — Shared test data: a fixed legal board and a legal draft.
"""

from board import apply_board_state, build_hex_grid, build_intersection_map
from scorer import compute_pip_total
from simulation import build_snake_draft, get_exclusion_zone

# A fixed, legal board (4 forest, 3 hills, 4 fields, 4 pasture, 3 mountains,
# 1 desert; standard number tokens), listed by hex id
RESOURCES = [
    "mountains", "pasture", "forest",
    "fields", "hills", "pasture", "hills",
    "fields", "forest", "desert", "forest", "mountains",
    "forest", "mountains", "fields", "pasture",
    "hills", "fields", "pasture",
]
NUMBERS = [10, 2, 9, 12, 6, 4, 10, 9, 11, None, 3, 8, 8, 3, 4, 5, 5, 6, 11]

BOARD = [{"id": i, "resource": r, "number": n} for i, (r, n) in enumerate(zip(RESOURCES, NUMBERS))]


def build_board():
    """(hexes, intersections) for BOARD."""
    hexes = apply_board_state(build_hex_grid(), BOARD)
    return hexes, build_intersection_map(hexes)


def greedy_draft(num_players: int, steps: int = None) -> list:
    """
    A legal snake draft where every player greedily takes the highest-pip
    open spot. Deterministic, so tests can rely on exact placements.
    `steps` stops the draft early (default: the full draft).
    """
    hexes, intersections = build_board()
    hmap = {h.id: h for h in hexes}
    snake = build_snake_draft(num_players)
    steps = len(snake) if steps is None else steps

    placements = []
    for step in range(steps):
        blocked = get_exclusion_zone([p["intersection_id"] for p in placements], intersections)
        best = max(
            (i for i in intersections if i.id not in blocked),
            key=lambda i: (compute_pip_total(i.hex_ids, hmap), -i.id),
        )
        placements.append({"intersection_id": best.id, "player": snake[step]})
    return placements
