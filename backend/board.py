"""
board.py — Hex and Intersection data models for the Catan board.

Computes the 54 unique intersections from the hex grid geometry (pointy-top,
3-4-5-4-3 row layout). Tracks which hexes each intersection touches and which
intersections are adjacent (for the distance rule).
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RESOURCE_TYPES = {"forest", "hills", "fields", "pasture", "mountains", "desert"}

# Number of each number token available
TOKEN_COUNTS = {2: 1, 3: 2, 4: 2, 5: 2, 6: 2, 8: 2, 9: 2, 10: 2, 11: 2, 12: 1}

PIP_VALUES = {2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 8: 5, 9: 4, 10: 3, 11: 2, 12: 1}

# Axial (q, r) coordinates for the 19 hexes in left-to-right, top-to-bottom order
# This produces the standard Catan 3-4-5-4-3 layout
HEX_AXIAL_COORDS = [
    # Row 0 — top 3
    (0, -2), (1, -2), (2, -2),
    # Row 1 — 4 hexes
    (-1, -1), (0, -1), (1, -1), (2, -1),
    # Row 2 — middle 5
    (-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0),
    # Row 3 — 4 hexes
    (-2, 1), (-1, 1), (0, 1), (1, 1),
    # Row 4 — bottom 3
    (-2, 2), (-1, 2), (0, 2),
]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Hex:
    id: int
    resource: Optional[str] = None   # None = unassigned
    number: Optional[int] = None      # None = desert or unassigned
    cx: float = 0.0
    cy: float = 0.0


@dataclass
class Intersection:
    id: int
    x: float
    y: float
    hex_ids: List[int] = field(default_factory=list)         # up to 3 hexes
    adjacent_ids: List[int] = field(default_factory=list)    # distance-rule neighbours


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

HEX_SIZE = 1.0  # unit radius; frontend scales to pixels


def _axial_to_xy(q: int, r: int, size: float = HEX_SIZE):
    """Convert axial hex coordinates to Cartesian (pointy-top)."""
    x = size * (math.sqrt(3) * q + math.sqrt(3) / 2 * r)
    y = size * (3 / 2 * r)
    return x, y


def _hex_corner(cx: float, cy: float, size: float, i: int):
    """Return the i-th corner of a pointy-top hex (0 = top-right, going clockwise)."""
    angle_rad = math.pi / 180 * (60 * i + 30)
    return (
        round(cx + size * math.cos(angle_rad), 6),
        round(cy + size * math.sin(angle_rad), 6),
    )


def _corners_are_equal(a, b, tol: float = 1e-3) -> bool:
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol


# ---------------------------------------------------------------------------
# Board construction
# ---------------------------------------------------------------------------

def build_hex_grid() -> List[Hex]:
    """Return the 19 Hex objects with computed unit-scale center coordinates."""
    hexes = []
    for hex_id, (q, r) in enumerate(HEX_AXIAL_COORDS):
        cx, cy = _axial_to_xy(q, r, HEX_SIZE)
        hexes.append(Hex(id=hex_id, cx=cx, cy=cy))
    return hexes


def build_intersection_map(hexes: List[Hex]) -> List[Intersection]:
    """
    Compute the 54 unique intersections from the 19 hex corners.

    Algorithm:
      1. For every hex, compute its 6 corners.
      2. Deduplicate corners across all hexes (within tolerance).
      3. Mark each unique corner with which hexes it belongs to.
      4. Two intersections are adjacent if they are consecutive corners
         of any shared hex (distance rule).
    """
    # Step 1 & 2: collect all corners, deduplicate
    unique: List[tuple] = []       # (x, y)
    corner_to_id: List[int] = []   # corner_instances → intersection id
    hex_corner_ids: List[List[int]] = [[] for _ in hexes]  # hex → 6 corner ids

    for h in hexes:
        for i in range(6):
            cx, cy = _hex_corner(h.cx, h.cy, HEX_SIZE, i)
            # Find existing unique corner
            found = -1
            for uid, (ux, uy) in enumerate(unique):
                if _corners_are_equal((cx, cy), (ux, uy)):
                    found = uid
                    break
            if found == -1:
                found = len(unique)
                unique.append((cx, cy))
            hex_corner_ids[h.id].append(found)

    # Step 3: build Intersection objects, noting which hexes touch each one
    intersections = [Intersection(id=uid, x=x, y=y) for uid, (x, y) in enumerate(unique)]

    for h in hexes:
        for cid in hex_corner_ids[h.id]:
            if h.id not in intersections[cid].hex_ids:
                intersections[cid].hex_ids.append(h.id)

    # Step 4: mark adjacency — consecutive corners of the same hex
    adj_set = [set() for _ in intersections]
    for h in hexes:
        corners = hex_corner_ids[h.id]
        n = len(corners)
        for i in range(n):
            a = corners[i]
            b = corners[(i + 1) % n]
            adj_set[a].add(b)
            adj_set[b].add(a)

    for iid, neighbours in enumerate(adj_set):
        intersections[iid].adjacent_ids = sorted(neighbours)

    # Sanity check: the standard Catan board always has exactly 54 intersections.
    # If this fails, there is a floating-point deduplication issue in _corners_are_equal.
    assert len(intersections) == 54, (
        f"[board.py] Expected 54 intersections, got {len(intersections)}. "
        "Check _corners_are_equal tolerance."
    )

    return intersections


def apply_board_state(hexes: List[Hex], board_data: list) -> List[Hex]:
    """
    Merge frontend board JSON (list of {id, resource, number}) into hex objects.
    Returns the updated list.
    """
    board_map = {h.id: h for h in hexes}
    for entry in board_data:
        h = board_map[entry["id"]]
        h.resource = entry.get("resource")
        h.number = entry.get("number")
    return hexes
