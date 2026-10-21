"""
test_calibration_fit.py — The fitting code recovers effects we planted in
synthetic data. If this fails, the pipeline is mis-wired (not the game).

Skipped when the calibration dependencies aren't installed:
    uv run --group calibration pytest tests/test_calibration_fit.py
"""

import pytest

np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")
pytest.importorskip("statsmodels")

from calibration.fit import fit_glm, within_board_spearman  # noqa: E402


def _synthetic(n_boards=600, games=20, seed=1):
    """Wins drawn from a known logistic model: ore pips matter twice as much as wood pips."""
    rng = np.random.default_rng(seed)
    rows = []
    for b in range(n_boards):
        for seat in range(4):
            ore, wood = rng.integers(0, 9), rng.integers(0, 9)
            logit = -1.6 + 0.12 * ore + 0.06 * wood + 0.1 * (seat == 0)
            wins = rng.binomial(games, 1 / (1 + np.exp(-logit)))
            rows.append({"board_id": b, "seat": seat, "wins": wins, "games": games,
                         "pips_mountains": ore, "pips_forest": wood})
    return pd.DataFrame(rows)


def test_glm_recovers_planted_coefficients():
    df = _synthetic()
    res = fit_glm(df, ["pips_mountains", "pips_forest"])
    assert res.params["pips_mountains"] == pytest.approx(0.12, abs=0.02)
    assert res.params["pips_forest"] == pytest.approx(0.06, abs=0.02)
    # And their ratio, which is what becomes a resource value
    ratio = res.params["pips_mountains"] / res.params["pips_forest"]
    assert 1.5 < ratio < 2.8


def test_within_board_spearman_is_one_for_perfect_ordering():
    df = pd.DataFrame({"board_id": [0] * 4 + [1] * 4, "wins": [1, 2, 3, 4, 4, 3, 2, 1]})
    assert within_board_spearman(df, np.array([1, 2, 3, 4, 4, 3, 2, 1])) == pytest.approx(1.0)
    assert within_board_spearman(df, np.array([4, 3, 2, 1, 1, 2, 3, 4])) == pytest.approx(-1.0)
