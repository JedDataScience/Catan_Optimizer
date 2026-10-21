"""
fit.py — Turn the simulated dataset into scoring values.

Method (all models are binomial GLMs, i.e. logistic regression on
"wins out of N games"):

  Model 1  resource values
      logit P(win) = seat effects + Σ_r β_r · pips_r + γ · Σ_r pips_r · scarcity_r
      A resource's value is β_r relative to the average β (so the five
      values average 1, like the app's STRATEGIC_VALUE). γ / mean(β) is the
      scarcity boost.

  Model 2  components
      logit P(win) = seat effects + β_w · weighted_pips_new + β_d · resource_types
                     + Σ_pairs β_p · pair_strength + β_e · expansion + port flags
      Each pair's synergy multiplier is 1 + β_p / (β_w · mean weighted pips):
      the bonus that adds the same win odds as that pair, at a typical position.

  Model 3  component weights
      Same idea on standardised (z-scored) versions of the app's combined
      components; the positive coefficients, rescaled, become score_weights.

Statistical care:
  - "Seat effects" are indicator variables for turn order, so going first or
    last isn't credited to the spot.
  - Standard errors are cluster-robust by board: the four players on a board
    compete with each other, so their results aren't independent.
  - Confidence intervals for the resource values come from a bootstrap over
    boards (refit on resampled boards, take the 2.5% / 97.5% quantiles).
  - Everything is fitted on the training boards; held-out boards are only
    used for validation.
  - Coefficients that come out negative or not significant (p > 0.05) are
    reported and set to "no bonus", never used silently.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import statsmodels.api as sm

from scorer import DEFAULT_PARAMS, NON_DESERT, SYNERGY_PAIRS, ScoringParams
from .dataset import PAIR_NAMES

FOLLOW_UP_WEIGHT = 0.20   # not learnable from final positions; tuned head-to-head in evaluate.py
BOOTSTRAP_REPS   = 300
ALPHA            = 0.05


# ---------------------------------------------------------------------------
# GLM helpers
# ---------------------------------------------------------------------------

def _design(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    X = pd.get_dummies(df["seat"], prefix="seat", drop_first=True, dtype=float)
    X = pd.concat([X.reset_index(drop=True), df[cols].reset_index(drop=True).astype(float)], axis=1)
    return sm.add_constant(X, has_constant="add")


def fit_glm(df: pd.DataFrame, cols: List[str], cluster: bool = True):
    """Binomial GLM of wins out of games on seat dummies + `cols`."""
    y = np.column_stack([df["wins"].to_numpy(), (df["games"] - df["wins"]).to_numpy()])
    model = sm.GLM(y, _design(df, cols), family=sm.families.Binomial())
    if cluster:
        return model.fit(cov_type="cluster", cov_kwds={"groups": df["board_id"].to_numpy()})
    return model.fit()


def predict_prob(result, df: pd.DataFrame, cols: List[str]) -> np.ndarray:
    return np.asarray(result.predict(_design(df, cols)))


def log_loss(df: pd.DataFrame, p: np.ndarray) -> float:
    """Average binomial log-loss per game (lower is better)."""
    p = np.clip(p, 1e-9, 1 - 1e-9)
    w, n = df["wins"].to_numpy(), df["games"].to_numpy()
    return float(-(w * np.log(p) + (n - w) * np.log(1 - p)).sum() / n.sum())


def within_board_spearman(df: pd.DataFrame, score: np.ndarray) -> float:
    """Average rank correlation between a score and win rate among a board's players."""
    tmp = df[["board_id", "wins"]].copy()
    tmp["score"] = score
    corrs = [
        g["score"].rank().corr(g["wins"].rank())
        for _, g in tmp.groupby("board_id")
        if g["wins"].nunique() > 1 and g["score"].nunique() > 1
    ]
    return float(np.nanmean(corrs))


# ---------------------------------------------------------------------------
# Feature construction under a given set of values
# ---------------------------------------------------------------------------

def weighted_pips(df: pd.DataFrame, values: Dict[str, float], scarcity_boost: float) -> pd.Series:
    return sum(df[f"pips_{r}"] * values[r] * (1 + scarcity_boost * df[f"scar_{r}"]) for r in NON_DESERT)


def diversity_quality(df: pd.DataFrame, values: Dict[str, float]) -> pd.Series:
    return sum((df[f"pips_{r}"] > 0) * values[r] for r in NON_DESERT)


def synergy_bonus(df: pd.DataFrame, pairs: Tuple[Tuple[str, str, float], ...]) -> pd.Series:
    bonus = pd.Series(1.0, index=df.index)
    for (a, b, mult), name in zip(pairs, PAIR_NAMES):
        bonus *= 1 + (mult - 1) * df[name]
    return bonus


def combined_score(df: pd.DataFrame, comps: Dict[str, pd.Series], weights: Dict[str, float],
                   ref: Dict[str, Tuple[float, float]]) -> np.ndarray:
    """Σ weight · z(component), z-scored with the training means/SDs in `ref`."""
    total = np.zeros(len(df))
    for k, w in weights.items():
        mean, sd = ref[k]
        total += w * ((comps[k].to_numpy() - mean) / (sd or 1.0))
    return total


def components(df: pd.DataFrame, params: ScoringParams) -> Dict[str, pd.Series]:
    """The app's (non-follow-up) components, computed from the dataset columns."""
    return {
        "pip":       weighted_pips(df, params.strategic_value, params.scarcity_boost),
        "diversity": diversity_quality(df, params.strategic_value),
        "synergy":   synergy_bonus(df, params.synergy_pairs),
        "expansion": df["expansion_pips"],
        "port":      df["port_any"] + df["port_2to1"],
    }


def app_weights(params: ScoringParams) -> Dict[str, float]:
    """The app's static component weights (follow-up excluded), with ports at their share."""
    base = {k: v for k, v in params.score_weights.items() if k != "follow_up"}
    total = sum(base.values())
    w = {k: (1 - params.port_weight) * v / total for k, v in base.items()}
    w["port"] = params.port_weight
    return w


# ---------------------------------------------------------------------------
# The fit
# ---------------------------------------------------------------------------

@dataclass
class FitReport:
    params: ScoringParams
    resource_table: pd.DataFrame
    scarcity_boost: Tuple[float, float, float]           # estimate, CI low, CI high
    pair_table: pd.DataFrame
    component_table: pd.DataFrame
    weights_table: pd.DataFrame
    validation: pd.DataFrame
    notes: List[str] = field(default_factory=list)


def _resource_values(df: pd.DataFrame) -> Tuple[Dict[str, float], float]:
    cols = [f"pips_{r}" for r in NON_DESERT] + ["pips_x_scarcity"]
    res = fit_glm(df, cols, cluster=False)
    betas = np.array([res.params[f"pips_{r}"] for r in NON_DESERT])
    mean = betas.mean()
    values = {r: float(b / mean) for r, b in zip(NON_DESERT, betas)}
    return values, float(res.params["pips_x_scarcity"] / mean)


def fit_all(df: pd.DataFrame, seed: int = 0, bootstrap_reps: int = BOOTSTRAP_REPS) -> FitReport:
    train = df[df["test"] == 0].reset_index(drop=True)
    test = df[df["test"] == 1].reset_index(drop=True)
    notes: List[str] = []

    # ── Model 1: resource values + scarcity, bootstrap CIs over boards ─────
    values, scar_boost = _resource_values(train)
    rng = np.random.default_rng(seed)
    boards = train["board_id"].unique()
    by_board = {b: g for b, g in train.groupby("board_id")}
    boot_vals, boot_scar = [], []
    for _ in range(bootstrap_reps):
        sample = rng.choice(boards, size=len(boards), replace=True)
        boot = pd.concat([by_board[b].assign(board_id=i) for i, b in enumerate(sample)], ignore_index=True)
        v, s = _resource_values(boot)
        boot_vals.append(v)
        boot_scar.append(s)
    resource_table = pd.DataFrame({
        "resource": NON_DESERT,
        "current": [DEFAULT_PARAMS.strategic_value[r] for r in NON_DESERT],
        "fitted": [values[r] for r in NON_DESERT],
        "ci_low": [np.quantile([b[r] for b in boot_vals], 0.025) for r in NON_DESERT],
        "ci_high": [np.quantile([b[r] for b in boot_vals], 0.975) for r in NON_DESERT],
    })
    scar_ci = (float(np.quantile(boot_scar, 0.025)), float(np.quantile(boot_scar, 0.975)))
    if scar_boost < 0 or scar_ci[0] <= 0:
        notes.append(f"Scarcity boost estimate {scar_boost:.2f} (95% CI {scar_ci[0]:.2f} to {scar_ci[1]:.2f}) "
                     "is not clearly positive, so it is set to 0.")
        scar_used = 0.0
    else:
        scar_used = scar_boost

    # ── Model 2: components with the new values → pair multipliers ─────────
    train = train.assign(wpip_new=weighted_pips(train, values, scar_used))
    m2_cols = ["wpip_new", "n_types", *PAIR_NAMES, "expansion_pips", "port_any", "port_2to1"]
    m2 = fit_glm(train, m2_cols)
    beta_w = m2.params["wpip_new"]
    mean_w = train["wpip_new"].mean()
    pair_rows, new_pairs = [], []
    for (a, b, cur_mult), name in zip(SYNERGY_PAIRS, PAIR_NAMES):
        beta, p = m2.params[name], m2.pvalues[name]
        implied = 1 + beta / (beta_w * mean_w)
        use = implied if (beta > 0 and p <= ALPHA) else 1.0
        pair_rows.append({"pair": f"{a} + {b}", "current": cur_mult, "implied": implied,
                          "p_value": p, "used": use})
        new_pairs.append((a, b, float(use)))
    pair_table = pd.DataFrame(pair_rows)
    component_table = pd.DataFrame({
        "coef": m2.params, "se": m2.bse, "p_value": m2.pvalues,
    }).drop(index="const")

    # ── Model 3: component weights on z-scored components ──────────────────
    draft_params = ScoringParams(
        strategic_value={**{r: values[r] for r in NON_DESERT}, "desert": 0.0},
        synergy_pairs=tuple(new_pairs),
        scarcity_boost=scar_used,
    )
    comps = components(train, draft_params)
    ref = {k: (float(s.mean()), float(s.std())) for k, s in comps.items()}
    ztrain = pd.DataFrame({f"z_{k}": (s - ref[k][0]) / (ref[k][1] or 1.0) for k, s in comps.items()})
    m3 = fit_glm(pd.concat([train, ztrain], axis=1), list(ztrain.columns))
    raw = {k: m3.params[f"z_{k}"] for k in comps}
    pv = {k: m3.pvalues[f"z_{k}"] for k in comps}
    kept = {k: (v if (v > 0 and pv[k] <= ALPHA) else 0.0) for k, v in raw.items()}
    for k in comps:
        if kept[k] == 0.0:
            notes.append(f"Component '{k}' coefficient {raw[k]:.3f} (p={pv[k]:.3f}) is not a clear positive effect; weight set to 0.")
    total = sum(kept.values()) or 1.0
    share = {k: v / total for k, v in kept.items()}
    # The app's weights cover pip/diversity/synergy/expansion (+ follow-up); ports are separate
    static = 1.0 - FOLLOW_UP_WEIGHT
    non_port = 1.0 - share["port"]
    new_score_weights = {k: static * share[k] / (non_port or 1.0) for k in ("pip", "diversity", "synergy", "expansion")}
    new_score_weights["follow_up"] = FOLLOW_UP_WEIGHT
    weights_table = pd.DataFrame({
        "component": list(raw),
        "z_coef": [raw[k] for k in raw],
        "p_value": [pv[k] for k in raw],
        "current_weight": [app_weights(DEFAULT_PARAMS)[k] for k in raw],
        "fitted_share": [share[k] for k in raw],
    })

    params = ScoringParams(
        strategic_value=draft_params.strategic_value,
        score_weights=new_score_weights,
        synergy_pairs=tuple(new_pairs),
        synergy_full_pips=DEFAULT_PARAMS.synergy_full_pips,
        port_weight=float(share["port"]),
        port_boost=dict(DEFAULT_PARAMS.port_boost),
        expansion_top_n=DEFAULT_PARAMS.expansion_top_n,
        scarcity_boost=scar_used,
    )

    # ── Validation on held-out boards ──────────────────────────────────────
    validation = validate(train, test, params)
    return FitReport(params, resource_table, (scar_boost, *scar_ci), pair_table,
                     component_table, weights_table, validation, notes)


def validate(train: pd.DataFrame, test: pd.DataFrame, new: ScoringParams) -> pd.DataFrame:
    """Does each score predict held-out winners? Log-loss and within-board rank correlation."""
    rows = []
    seat_only = fit_glm(train, [], cluster=False)
    p0 = predict_prob(seat_only, test, [])
    rows.append({"model": "Seat order only", "log_loss": log_loss(test, p0), "spearman": float("nan")})

    for label, params in (("Current values", DEFAULT_PARAMS), ("Calibrated values", new)):
        comps_tr, comps_te = components(train, params), components(test, params)
        ref = {k: (float(s.mean()), float(s.std())) for k, s in comps_tr.items()}
        w = app_weights(params)
        tr = train.assign(score=combined_score(train, comps_tr, w, ref))
        te = test.assign(score=combined_score(test, comps_te, w, ref))
        res = fit_glm(tr, ["score"], cluster=False)
        rows.append({
            "model": label,
            "log_loss": log_loss(test, predict_prob(res, te, ["score"])),
            "spearman": within_board_spearman(te, te["score"].to_numpy()),
        })
    return pd.DataFrame(rows)
