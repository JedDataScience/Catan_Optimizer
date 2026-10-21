# Scoring calibration report

_Full run: 3,000 boards × 20 games (60,000 games) for fitting; 300 held-out boards × 4 seats × 30 games per picker for the head-to-head._

## Summary

- Best calibrated picker (**calibrated_fu0.3**) wins **55.8%** of games from its seat, vs **52.0%** with the current values: a difference of **+3.8%** (95% CI +2.5% to +5.0%).
- The interval excludes zero, so the improvement is unlikely to be luck.

## Sanity checks

- ✅ Most-pips beats a random pick
- ✅ Current values beat most-pips
- ✅ Every seat wins 15-35% of dataset games
- ✅ Games finishing within 250 rounds

## Head-to-head (held-out boards)

| arm | win_rate | diff_vs_current | ci_low | ci_high |
|---|---|---|---|---|
| calibrated_fu0.3 | 0.558 | 0.038 | 0.025 | 0.050 |
| calibrated_fu0.2 | 0.554 | 0.034 | 0.021 | 0.046 |
| calibrated_fu0.1 | 0.550 | 0.030 | 0.018 | 0.042 |
| current | 0.520 | 0.000 | 0.000 | 0.000 |
| most_pips | 0.445 | -0.075 | -0.092 | -0.057 |
| random | 0.078 | -0.442 | -0.457 | -0.428 |

Win rate by seat (rows) and picker (columns):

| seat | calibrated_fu0.1 | calibrated_fu0.2 | calibrated_fu0.3 | current | most_pips | random |
|---|---|---|---|---|---|---|
| 0 | 0.609 | 0.613 | 0.619 | 0.574 | 0.493 | 0.094 |
| 1 | 0.573 | 0.578 | 0.581 | 0.543 | 0.475 | 0.075 |
| 2 | 0.513 | 0.516 | 0.523 | 0.493 | 0.402 | 0.074 |
| 3 | 0.504 | 0.508 | 0.508 | 0.470 | 0.412 | 0.069 |

![Head-to-head](output/head_to_head.png)

## Resource values

Value of one pip of each resource relative to the average resource, from Model 1.

| resource | current | fitted | ci_low | ci_high |
|---|---|---|---|---|
| forest | 0.900 | 0.913 | 0.883 | 0.939 |
| hills | 0.900 | 0.969 | 0.940 | 0.999 |
| fields | 1.350 | 1.164 | 1.132 | 1.192 |
| pasture | 1.100 | 0.748 | 0.726 | 0.781 |
| mountains | 1.250 | 1.206 | 1.175 | 1.238 |

Scarcity boost: **0.52** (95% CI 0.44 to 0.60); current value 0.60.

![Resource values](output/resource_values.png)

## Resource pairs (synergy multipliers)

| pair | current | implied | p_value | used |
|---|---|---|---|---|
| mountains + fields | 1.400 | 1.143 | 0.000 | 1.143 |
| mountains + pasture | 1.200 | 1.029 | 0.086 | 1.000 |
| fields + pasture | 1.150 | 1.046 | 0.001 | 1.046 |
| forest + hills | 1.100 | 1.077 | 0.000 | 1.077 |
| forest + fields | 1.050 | 1.044 | 0.002 | 1.044 |
| hills + fields | 1.050 | 1.043 | 0.003 | 1.043 |

## Component weights

| component | z_coef | p_value | current_weight | fitted_share |
|---|---|---|---|---|
| pip | 0.907 | 0.000 | 0.475 | 0.489 |
| diversity | 0.232 | 0.000 | 0.178 | 0.125 |
| synergy | 0.157 | 0.000 | 0.178 | 0.085 |
| expansion | 0.398 | 0.000 | 0.119 | 0.215 |
| port | 0.160 | 0.000 | 0.050 | 0.086 |

Calibrated `score_weights`: pip 0.43, diversity 0.11, synergy 0.07, expansion 0.19, follow_up 0.20; port weight 0.09. Follow-up weight is chosen head-to-head (see above).

## Does the score predict held-out winners?

Log-loss: how well predicted win chances match what happened (lower is better). Spearman: average rank correlation between score and win rate among a board's four players (1 = perfect ordering).

| model | log_loss | spearman |
|---|---|---|
| Seat order only | 0.562 | nan |
| Current values | 0.460 | 0.719 |
| Calibrated values | 0.449 | 0.740 |

## Notes from the fit

- None.

## Full Model 2 coefficients

| term | coef | se | p_value |
|---|---|---|---|
| seat_1 | -0.162 | 0.035 | 0.000 |
| seat_2 | -0.263 | 0.036 | 0.000 |
| seat_3 | -0.366 | 0.036 | 0.000 |
| wpip_new | 0.194 | 0.004 | 0.000 |
| n_types | 0.240 | 0.023 | 0.000 |
| pair_mountains_fields | 0.432 | 0.043 | 0.000 |
| pair_mountains_pasture | 0.087 | 0.051 | 0.086 |
| pair_fields_pasture | 0.140 | 0.041 | 0.001 |
| pair_forest_hills | 0.233 | 0.051 | 0.000 |
| pair_forest_fields | 0.132 | 0.042 | 0.002 |
| pair_hills_fields | 0.131 | 0.045 | 0.003 |
| expansion_pips | 0.097 | 0.003 | 0.000 |
| port_any | 0.348 | 0.032 | 0.000 |
| port_2to1 | 0.225 | 0.029 | 0.000 |

## Method

1. **Dataset.** Random legal boards (6s and 8s never adjacent, ports shuffled). Four players draft with deliberate randomness so the data covers strong and weak positions. Every starting position is played out many times by identical greedy players (`policy.py`).
2. **Models.** Binomial GLMs (logistic regression on wins out of games) with seat indicators so turn order isn't credited to the spot. Standard errors are cluster-robust by board, because players on the same board compete with each other. Resource-value intervals come from a bootstrap over boards.
3. **Validation.** Fitted on 80% of boards; scored on the held-out 20%.
4. **Head-to-head.** On held-out boards one seat drafts with each picker while the others use the app's opponent model at a high greediness (4; the app assumes 1.5 for casual players). Opponent draws and dice use the same seeds across pickers (a paired comparison). Win rates well above 25% for the recommender arms mean it out-drafts these opponents, as intended.

## Limitations

- Results are only as realistic as the simulated play: one greedy strategy for everyone, no Longest Road, and the bank never runs out. Progress cards (Road Building, Year of Plenty, Monopoly) are played by simple rules, and player trades are one-for-one only, accepted when both sides need what they get (never with a player on 8+ VP). Real tables negotiate more freely.
- The follow-up variants differ from each other by about a point, which is within noise; only their difference from the current values is clearly established.
- Model 2's pair multipliers are a linear approximation around a typical position.
- The follow-up weight and the opponent model can't be learned from final positions; the follow-up weight is chosen from the head-to-head grid instead.

## Runtime

- Simulate dataset: 37s
- Fit models: 82s
- Head-to-head: 133s
- Workers: 10
