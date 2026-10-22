"""
mapping.py — Translate a Catanatron board into this project's board model.

Catanatron describes tiles by cube coordinates and numbers the 54 corners
("nodes") itself; it has no screen positions. This module works out the
geometry instead of assuming it:

  1. Place each Catanatron tile at a 2D point using one of the standard
     cube → pointy-top-hex conventions, and each node at its tile's centre plus
     the offset for its NodeRef (NORTH, NORTHEAST, ...).
  2. Keep the first convention under which every node lands on one point,
     no matter which of its 2-3 tiles it's computed from. (A wrong convention
     scatters shared corners, so this check is decisive.)
  3. Match tile centres to our 19 hexes and node points to our 54
     intersections by nearest point.

Any rotation or reflection between the two boards is harmless: resources,
numbers and ports are all carried over through the same mapping.
"""

import math
from dataclasses import dataclass
from itertools import permutations, product
from typing import Dict, List, Tuple

from board import Hex, Intersection, apply_board_state, build_hex_grid, build_intersection_map

from catanatron.models.enums import NodeRef
from catanatron.models.map import PORT_DIRECTION_TO_NODEREFS, CatanMap

SQRT3 = math.sqrt(3)
TOLERANCE = 1e-6

# Catanatron resource names → ours. None is the desert (tiles) or a 3:1 port.
RESOURCE_NAMES = {"WOOD": "forest", "BRICK": "hills", "WHEAT": "fields", "SHEEP": "pasture", "ORE": "mountains"}

# Pointy-top hex corner offsets in a y-down frame (unit circumradius)
CORNER_OFFSET = {
    NodeRef.NORTH:     (0.0, -1.0),
    NodeRef.NORTHEAST: (SQRT3 / 2, -0.5),
    NodeRef.SOUTHEAST: (SQRT3 / 2, 0.5),
    NodeRef.SOUTH:     (0.0, 1.0),
    NodeRef.SOUTHWEST: (-SQRT3 / 2, 0.5),
    NodeRef.NORTHWEST: (-SQRT3 / 2, -0.5),
}


def _axial_to_point(q: float, r: float) -> Tuple[float, float]:
    """Same formula as board._axial_to_xy (pointy-top, unit size)."""
    return SQRT3 * q + SQRT3 / 2 * r, 1.5 * r


def _conventions():
    """Every (q, r) choice of two signed cube components."""
    for (i, j), (si, sj) in product(permutations(range(3), 2), product((1, -1), repeat=2)):
        yield lambda c, i=i, j=j, si=si, sj=sj: (si * c[i], sj * c[j])


def _node_points(catan_map: CatanMap, to_axial) -> Dict[int, Tuple[float, float]]:
    """Node id → point, or raise if any node lands on two different points."""
    points: Dict[int, Tuple[float, float]] = {}
    for coord, tile in catan_map.land_tiles.items():
        cx, cy = _axial_to_point(*to_axial(coord))
        for ref, node_id in tile.nodes.items():
            dx, dy = CORNER_OFFSET[ref]
            p = (cx + dx, cy + dy)
            if node_id in points and math.dist(points[node_id], p) > TOLERANCE:
                raise ValueError("inconsistent convention")
            points[node_id] = p
    return points


def _nearest(point, candidates: Dict[int, Tuple[float, float]]) -> int:
    best = min(candidates, key=lambda k: math.dist(point, candidates[k]))
    if math.dist(point, candidates[best]) > 1e-3:
        raise ValueError(f"no counterpart for point {point}")
    return best


@dataclass
class TranslatedBoard:
    hexes: List[Hex]
    intersections: List[Intersection]
    node_to_ours: Dict[int, int]          # Catanatron node id → our intersection id
    ours_to_node: Dict[int, int]
    port_edges: List[Tuple[int, int]]     # our intersection ids
    port_types: List[str]                 # "any" or our resource name, aligned with port_edges


def translate(catan_map: CatanMap) -> TranslatedBoard:
    # Our board geometry, in the same unit frame (board.HEX_SIZE == 1)
    base = build_hex_grid()
    our_centres = {h.id: (h.cx, h.cy) for h in base}
    our_nodes = {i.id: (i.x, i.y) for i in build_intersection_map(base)}

    for to_axial in _conventions():
        try:
            points = _node_points(catan_map, to_axial)
        except ValueError:
            continue
        if len(points) != 54:
            continue
        # 1. Tiles: Catanatron coordinate → our hex id (copy resource and number)
        board_state = []
        for coord, tile in catan_map.land_tiles.items():
            our_id = _nearest(_axial_to_point(*to_axial(coord)), our_centres)
            resource = RESOURCE_NAMES.get(tile.resource, "desert")
            board_state.append({"id": our_id, "resource": resource,
                                "number": None if resource == "desert" else tile.number})
        if len({b["id"] for b in board_state}) != 19:
            continue
        # 2. Nodes
        node_to_ours = {n: _nearest(p, our_nodes) for n, p in points.items()}
        if len(set(node_to_ours.values())) != 54:
            continue
        hexes = apply_board_state(build_hex_grid(), board_state)
        intersections = build_intersection_map(hexes)
        # 3. Ports: each Port tile's two coastal corners
        port_edges, port_types = [], []
        for port in catan_map.ports_by_id.values():
            a_ref, b_ref = PORT_DIRECTION_TO_NODEREFS[port.direction]
            port_edges.append((node_to_ours[port.nodes[a_ref]], node_to_ours[port.nodes[b_ref]]))
            port_types.append(RESOURCE_NAMES.get(port.resource, "any"))
        return TranslatedBoard(hexes, intersections, node_to_ours,
                               {v: k for k, v in node_to_ours.items()}, port_edges, port_types)

    raise RuntimeError("Could not match Catanatron's board geometry to ours under any convention")
