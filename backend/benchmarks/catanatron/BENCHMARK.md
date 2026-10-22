# Catanatron benchmark

_Full run: 1,200 paired games per arm, 4 arms (4,800 games), in [Catanatron](https://github.com/bcollazo/catanatron), an independent Catan engine._

## Question

When a strong search player (Catanatron's AlphaBeta) lets our recommender choose its two starting settlements, does it win more than when it chooses them itself?

## Answer

- With the recommender's picks, the player won **28.5%** of games vs **23.9%** with AlphaBeta's own picks: **+4.6%** (95% CI +1.4% to +7.8%).
- The interval is above zero, so the recommender's starting spots measurably help a strong player.
- Earlier hand-picked values: 21.0% (-2.9% vs AlphaBeta). Most-pips baseline: 15.0%.

## Results

Win rate = share of games won by the player under test (fair share with 4 equal players: 25%). `diff_vs_alphabeta` is the paired difference from the control on the same seeds, with a bootstrap 95% CI.

| arm | games | win_rate | ci_low | ci_high | diff_vs_alphabeta | diff_ci_low | diff_ci_high | mean_vp | mean_turns |
|---|---|---|---|---|---|---|---|---|---|
| alphabeta | 1200 | 0.239 | 0.216 | 0.264 | 0.000 | 0.000 | 0.000 | 6.575 | 83.698 |
| recommender | 1200 | 0.285 | 0.260 | 0.311 | 0.046 | 0.014 | 0.078 | 6.881 | 85.324 |
| recommender_handpicked | 1200 | 0.210 | 0.188 | 0.234 | -0.029 | -0.058 | 0.001 | 6.560 | 85.076 |
| most_pips | 1200 | 0.150 | 0.131 | 0.171 | -0.089 | -0.118 | -0.060 | 5.768 | 84.500 |

Win rate by seat (0 = first to place):

| seat | alphabeta | most_pips | recommender | recommender_handpicked |
|---|---|---|---|---|
| 0 | 0.141 | 0.053 | 0.094 | 0.072 |
| 1 | 0.229 | 0.184 | 0.270 | 0.229 |
| 2 | 0.306 | 0.165 | 0.404 | 0.293 |
| 3 | 0.289 | 0.206 | 0.388 | 0.258 |

## Method

- **Players.** Every game has the player under test plus three plain AlphaBeta opponents (depth 2, pruning on). The arms differ *only* in the test player's two setup settlements; setup roads and the whole rest of the game are identical AlphaBeta play.
- **Arms.** `alphabeta` (control: its own setup picks), `recommender` (our current values), `recommender_handpicked` (the values used before calibration), `most_pips` (highest-pip legal spot).
- **Recommender settings.** Long-game strategy (slider at 1.0), 1,000 Monte Carlo runs per pick, #1 recommendation played. The Catanatron board, ports and draft so far are translated into this project's board model (`mapping.py`, verified by tests: one-to-one corners, identical roads, identical production).
- **Paired design.** All arms play the same seeds, so they see the same boards and seats, and the game's own random-number generator (dice, cards) is untouched by our players.

## Limitations

- Still simulated play, not human games, though from a different engine and much stronger players than this project's own simulator.
- Catanatron's bots don't make player-to-player trades.
- Opponents are all the same AlphaBeta bot; results against human or mixed opponents may differ.

## Runtime

- 20.1 minutes on 10 workers; games with no winner: 0.
