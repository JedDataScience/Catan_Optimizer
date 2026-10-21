"""
test_geometry.py — Board geometry, port slots, and the shared fixture.
"""

import json

from board import DEFAULT_PORT_TYPES, PORT_SLOTS
from scripts.export_geometry import FIXTURE_PATH, build_geometry_fixture


def test_standard_board_has_54_intersections(intersections):
    assert len(intersections) == 54
    assert all(1 <= len(i.hex_ids) <= 3 for i in intersections)


def test_adjacency_is_symmetric(imap):
    for i in imap.values():
        for n in i.adjacent_ids:
            assert i.id in imap[n].adjacent_ids


def test_port_slots_are_real_coastal_edges(imap):
    assert len(PORT_SLOTS) == 9
    used = set()
    for a, b in PORT_SLOTS:
        ia, ib = imap[a], imap[b]
        # The two ends of a port are joined by one edge...
        assert b in ia.adjacent_ids, f"port {a}-{b}: not adjacent"
        # ...on the coast: both corners touch fewer than 3 hexes...
        assert len(ia.hex_ids) < 3 and len(ib.hex_ids) < 3, f"port {a}-{b}: not coastal"
        # ...and the edge borders exactly one land hex (the other side is sea)
        assert len(set(ia.hex_ids) & set(ib.hex_ids)) == 1, f"port {a}-{b}: not an outer edge"
        # No intersection serves two ports
        assert not ({a, b} & used), f"port {a}-{b}: overlaps another port"
        used |= {a, b}


def test_default_port_types_are_the_standard_set():
    assert DEFAULT_PORT_TYPES.count("any") == 4
    assert sorted(t for t in DEFAULT_PORT_TYPES if t != "any") == sorted(
        ["forest", "hills", "fields", "pasture", "mountains"]
    )


def test_geometry_matches_shared_fixture():
    # If this fails after an intentional geometry change, regenerate with
    #   uv run python -m scripts.export_geometry
    committed = json.loads(FIXTURE_PATH.read_text())
    assert build_geometry_fixture() == committed
