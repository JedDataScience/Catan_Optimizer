# Seat 0 investigation

_Full run: 800 paired games per arm, test player always placing first (seat 0), 8 arms. Same AlphaBeta play everywhere except the test player's two setup settlements._

## Win rates from seat 0

`diff` is the paired difference from the control (AlphaBeta's own picks) on the same seeds, with a bootstrap 95% CI. `p_holm` is the two-sided p-value adjusted for comparing every arm with the control (Holm).

| arm | tests | games | win_rate | ci_low | ci_high | diff | diff_ci_low | diff_ci_high | p_holm |
|---|---|---|---|---|---|---|---|---|---|
| alphabeta | Control: AlphaBeta's own picks | 800 | 0.079 | 0.062 | 0.099 | 0.000 | 0.000 | 0.000 | nan |
| recommender | H0: current recommender | 800 | 0.114 | 0.094 | 0.138 | 0.035 | 0.009 | 0.061 | 0.062 |
| follow_up_0.00 | H1: no follow-up term | 800 | 0.107 | 0.088 | 0.131 | 0.029 | 0.001 | 0.055 | 0.128 |
| follow_up_0.15 | H1: half the follow-up weight | 800 | 0.114 | 0.094 | 0.138 | 0.035 | 0.009 | 0.061 | 0.062 |
| greedy_opp_4 | H2: greedier simulated opponents | 800 | 0.120 | 0.099 | 0.144 | 0.041 | 0.014 | 0.070 | 0.038 |
| rec_s1_only | H3: recommender S1, AlphaBeta S2 | 800 | 0.102 | 0.083 | 0.125 | 0.024 | -0.003 | 0.050 | 0.165 |
| rec_s2_only | H3: AlphaBeta S1, recommender S2 | 800 | 0.117 | 0.097 | 0.142 | 0.039 | 0.011 | 0.066 | 0.038 |
| raw_production | H4: no resource weighting (slider at 0) | 800 | 0.085 | 0.068 | 0.106 | 0.006 | -0.021 | 0.033 | 0.684 |

Arms that differ from the control after adjustment: `greedy_opp_4`, `rec_s2_only`.

## What each arm picks

Pips are raw dice pips (a 6 or 8 is 5). `s1_top_pip_share` is how often the first settlement was the open spot with the most pips; `s1_pips_below_best` is how many pips it gave up versus that spot. `predicted_s2_pips` is what the recommender's follow-up expected the second settlement to have; compare it with `s2_pips`. Resource columns are the average pips of each resource across both settlements.

| arm | s1_pips | s1_top_pip_share | s1_pips_below_best | s2_pips | total_pips | s1+s2_fields | s1+s2_mountains | s1+s2_hills | s1+s2_forest | s1+s2_pasture | predicted_s2_pips |
|---|---|---|---|---|---|---|---|---|---|---|---|
| alphabeta | 11.758 | 0.705 | 0.341 | 8.501 | 20.259 | 4.296 | 3.583 | 3.553 | 4.435 | 4.393 | nan |
| recommender | 11.328 | 0.465 | 0.771 | 8.664 | 19.991 | 5.772 | 5.359 | 3.425 | 3.460 | 1.975 | 10.687 |
| follow_up_0.00 | 11.120 | 0.400 | 0.979 | 8.695 | 19.815 | 5.638 | 5.316 | 3.368 | 3.522 | 1.971 | 10.735 |
| follow_up_0.15 | 11.235 | 0.434 | 0.864 | 8.678 | 19.913 | 5.692 | 5.367 | 3.388 | 3.509 | 1.956 | 10.708 |
| greedy_opp_4 | 11.322 | 0.459 | 0.776 | 8.675 | 19.997 | 5.812 | 5.327 | 3.438 | 3.495 | 1.925 | 10.199 |
| rec_s1_only | 11.319 | 0.463 | 0.780 | 8.553 | 19.871 | 4.992 | 4.157 | 3.301 | 3.837 | 3.583 | 10.687 |
| rec_s2_only | 11.758 | 0.705 | 0.341 | 8.590 | 20.348 | 4.984 | 4.576 | 3.393 | 4.071 | 3.324 | nan |
| raw_production | 11.841 | 0.744 | 0.258 | 9.059 | 20.900 | 4.619 | 3.536 | 3.430 | 4.794 | 4.521 | 11.158 |

## Runtime

- 28.0 minutes on 10 workers.
## Findings (written after the run)

- **H0 — it was noise.** With 800 games, the recommender *beats* AlphaBeta's own picks from seat 0: 11.4% vs 7.9%,
  +3.5 points (95% CI +0.9 to +6.1). Replaying the first benchmark's 319 seat-0 games gave the control 9.1% instead of
  the original 14.1%, so the original deficit came from a lucky high draw for the control (and from looking at the
  worst of four seats, which tends to pick out noise).
- **H1 — not the follow-up weight.** Turning the follow-up term off changes the first pick very little and does
  slightly worse (+2.9 points vs +3.5).
- **H2 — greedier simulated opponents help a little.** Opponent greediness 4.0 is the best arm (+4.1 points, Holm
  p = 0.038), but its edge over the current setting (+0.6 points) is well within noise. The follow-up is still
  optimistic either way: it predicts a second spot with about 10.2–10.7 pips, and the real second spot averages 8.7.
- **H3 — the second pick carries the most value.** AlphaBeta's first pick plus our second pick (+3.9) beats our first
  pick plus AlphaBeta's second (+2.4, not significant).
- **H4 — the resource weighting is the edge, not the problem.** With raw production (slider at 0) the recommender is
  no better than AlphaBeta (+0.6 points). The current first pick gives up about 0.8 pips versus the highest-pip spot
  in exchange for more ore and wheat, and that trade wins.

**Caveat:** Catanatron games aren't fully reproducible across runs (82–86% of replayed seeds had the same winner),
most likely because Python's per-process hash randomization changes the order in which bots consider tied moves. The
comparisons remain unbiased, and the confidence intervals reflect the real variation, but the pairing is less tight
than designed.
