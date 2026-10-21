"""
conftest.py — pytest fixtures shared by every test file.
"""

import pytest

from scorer import compute_board_scarcity
from tests.helpers import build_board


@pytest.fixture
def board():
    """(hexes, intersections) for the fixed test board."""
    return build_board()


@pytest.fixture
def hexes(board):
    return board[0]


@pytest.fixture
def intersections(board):
    return board[1]


@pytest.fixture
def hmap(hexes):
    return {h.id: h for h in hexes}


@pytest.fixture
def imap(intersections):
    return {i.id: i for i in intersections}


@pytest.fixture
def scarcity(hexes):
    return compute_board_scarcity(hexes)
