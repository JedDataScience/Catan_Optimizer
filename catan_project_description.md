# Catan Settlement Optimizer — Project Description

## Overview

Build a web application that lets a user configure a Catan board (resources + number tokens per hex), select their settlement placement turn order, and run a Monte Carlo simulation across thousands of games to recommend the optimal two starting settlement placements. The app explains each recommendation using probabilistic reasoning and expected resource output.

---

## Scope & Constraints

- **No ports.** Treat all coastal intersections as normal intersections. Port mechanics are excluded entirely from this iteration.
- **Starting settlements only.** The simulation covers only the 2 starting settlements per player. No roads, cities, development cards, or mid-game settlement placement.
- **Robber is active.** When a 7 is rolled, the robber is placed by the rolling player on the hex that deals maximum damage to opponents (highest combined pip value among opponent-occupied hexes), and cannot be placed on any hex the rolling player's own settlements touch.
- **No trading.** Resource accumulation is tracked but trading is not simulated.
- **Player count is configurable** (2–4 players), but the optimization output is always from the perspective of Player 1 (the user).

---

## Tech Stack

```
Frontend:   React (Vite)
Simulation: Python (FastAPI)
State:      React useState / useReducer (no backend persistence needed)
Styling:    Tailwind CSS
Charts:     Recharts
HTTP:       Axios or fetch
```

Run the simulation server locally. No database required for v1.

---

## Application Flow

```
1. Board Setup
   └── User places resources + number tokens on all 19 hexes

2. Player Configuration
   └── User sets number of players (2–4)
   └── User sets their turn position (1st, 2nd, 3rd, 4th)

3. Run Simulation
   └── POST /simulate with board state + config
   └── Backend runs N Monte Carlo games (default: 10,000)
   └── Returns ranked intersection scores + explanation data

4. Results View
   └── Board highlights top 5 intersections for settlement 1
   └── User selects settlement 1 → board updates
   └── Board highlights top 5 intersections for settlement 2 (conditioned on settlement 1)
   └── Explanation panel shows probabilistic breakdown
```

---

## Frontend

### Components

**`BoardSetup`**
- Renders the 19-hex Catan board as an SVG hex grid (pointy-top hexagons, 3-4-5-4-3 row layout)
- Each hex is clickable; clicking opens a small config panel to assign:
  - Resource type: Wood, Brick, Wheat, Sheep, Ore, Desert
  - Number token: 2–12 (excluding 7); tokens grey out once their allowed count is exhausted
  - Desert hex gets no number token
- Valid number token counts: `{2:1, 3:2, 4:2, 5:2, 6:2, 8:2, 9:2, 10:2, 11:2, 12:1}`
- Board displays pip dots on number tokens (6 and 8 shown in red)
- "Clear Board" and "Randomize" buttons

**`PlayerConfig`**
- Slider or dropdown: number of players (2–4)
- Radio: user's turn position (1st / 2nd / 3rd / 4th)
- Input: number of simulations to run (default 10,000; max 50,000)

**`SimulationRunner`**
- "Run Simulation" button; triggers POST to backend
- Loading state with progress indicator

**`ResultsOverlay`**
- Renders on top of the board SVG
- Intersection nodes drawn at all valid hex corners
- Top 5 candidate intersections highlighted with ranked badges (1–5)
- Clicking an intersection selects it as settlement 1 and re-queries for settlement 2 candidates
- Color gradient from best (dark green) to acceptable (yellow)

**`ExplanationPanel`**
- For each recommended intersection, shows:
  - Expected resources per roll (each resource type separately)
  - Total weighted pip score
  - Resource diversity score (number of distinct resource types)
  - Robber-adjusted expected output (how much the robber discounts this spot)
  - Win rate across simulations when this intersection is chosen
- Bar chart of resource production per intersection (Recharts `BarChart`)

---

## Board Data Model

```javascript
// Hex
{
  id: 0–18,          // integer, left-to-right, top-to-bottom
  resource: string,  // 'forest' | 'hills' | 'fields' | 'pasture' | 'mountains' | 'desert'
  number: number,    // 2–12 | null (desert)
  cx: number,        // SVG center x
  cy: number         // SVG center y
}

// Intersection (vertex shared by up to 3 hexes)
{
  id: 0–53,          // 54 total intersections on standard board
  hexIds: number[],  // 1–3 hex ids this intersection touches
  x: number,         // SVG x
  y: number          // SVG y
}
```

Precompute the intersection-to-hex adjacency map on the frontend at startup. Each intersection touches 1–3 hexes. The 54 intersections are fixed by the board geometry regardless of resource assignment.

---

## Backend — Simulation Engine

### Endpoint

```
POST /simulate
Content-Type: application/json

{
  "board": [
    { "id": 0, "resource": "forest", "number": 6 },
    ...
  ],
  "players": 3,
  "user_position": 0,       // 0-indexed turn order
  "n_simulations": 10000,
  "locked_settlement_1": null | intersection_id
}

Response:
{
  "rankings": [
    {
      "intersection_id": 12,
      "score": 0.847,
      "win_rate": 0.312,
      "expected_resources": { "wood": 0.83, "brick": 0.55, "wheat": 0.69, "sheep": 0.0, "ore": 0.42 },
      "pip_total": 12,
      "diversity": 3,
      "robber_discount": 0.08,
      "explanation": "Strong wood + wheat production with solid pip coverage. Robber risk is low as no adjacent hex exceeds 9 pip weight."
    },
    ...
  ]
}
```

### Simulation Logic (Python)

```python
def run_simulation(board, players, user_position, n_simulations, locked_s1=None):
    intersections = build_intersection_map(board)   # precompute adjacency
    scores = defaultdict(list)

    for _ in range(n_simulations):
        # 1. Place opponent settlements (random valid intersections, no adjacency violations)
        opponent_placements = place_opponent_settlements(intersections, players, user_position)

        # 2. Place user settlement 1
        if locked_s1 is not None:
            s1 = locked_s1
        else:
            s1 = sample_candidate(intersections, exclude=get_exclusion_zone(opponent_placements))

        # 3. Place user settlement 2 (after all other players place their 2nd, snake draft)
        s2_candidates = get_valid_intersections(intersections, exclude=get_exclusion_zone([s1] + opponent_placements))
        s2 = sample_candidate(s2_candidates)

        # 4. Simulate N rounds of dice rolls
        resources = simulate_rounds(board, [s1, s2], opponent_placements, rounds=50)

        # 5. Score = weighted resource value (all resources equal weight in v1)
        score = sum(resources.values())
        scores[s1].append(score)

    return rank_intersections(scores)
```

### Dice Roll Simulation

```python
def simulate_rounds(board, user_settlements, opponent_settlements, rounds=50):
    resources = defaultdict(float)
    robber_hex = get_desert_hex(board)   # robber starts on desert

    for _ in range(rounds):
        roll = random.randint(1, 6) + random.randint(1, 6)

        if roll == 7:
            # Rolling player: pick opponent at random to simulate "someone rolls 7"
            # Robber goes to the hex with the highest pip value adjacent to any opponent
            # settlement, excluding any hex adjacent to the user's settlements
            robber_hex = place_robber_optimally(
                board,
                user_settlements=user_settlements,
                opponent_settlements=opponent_settlements
            )
            continue

        # Produce resources for each user settlement
        for settlement in user_settlements:
            for hex_id in settlement.adjacent_hexes:
                hex = board[hex_id]
                if hex.number == roll and hex_id != robber_hex:
                    resources[hex.resource] += 1

    return resources
```

### Robber Placement Logic

```python
def place_robber_optimally(board, user_settlements, opponent_settlements):
    """
    Places robber on the hex that maximizes damage to opponents
    while not touching any hex adjacent to user's own settlements.
    """
    user_hex_ids = {h for s in user_settlements for h in s.adjacent_hexes}

    best_hex = None
    best_damage = -1

    for hex in board:
        if hex.resource == 'desert':
            continue
        if hex.id in user_hex_ids:
            continue   # cannot block own production
        if hex.number is None:
            continue

        # Damage = pip value of this hex * number of opponent settlements adjacent
        pip_value = PIP_VALUES[hex.number]
        opponent_count = sum(
            1 for s in opponent_settlements if hex.id in s.adjacent_hexes
        )
        damage = pip_value * opponent_count

        if damage > best_damage:
            best_damage = damage
            best_hex = hex.id

    return best_hex  # returns None if no valid hex found (robber stays put)

PIP_VALUES = {2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 8: 5, 9: 4, 10: 3, 11: 2, 12: 1}
```

### Intersection Adjacency Map

The 54 intersections on a standard Catan board are fixed. Precompute the map once at server startup from the hex layout. Each intersection stores which hex IDs it touches (1–3). Two intersections are "adjacent" if they share a hex edge — settlements cannot be placed on adjacent intersections (the distance rule).

```python
def build_intersection_map(board):
    """
    Returns list of Intersection objects, each with:
      - id
      - adjacent_hex_ids: list of hex ids (1–3)
      - adjacent_intersection_ids: for distance rule enforcement
    """
    ...
```

---

## Explanation Generation

For each top-ranked intersection, generate a plain-English explanation using these rules:

```python
def explain(intersection, expected_resources, pip_total, diversity, robber_discount, win_rate):
    parts = []

    # Pip strength
    if pip_total >= 13:
        parts.append("Excellent pip coverage with high expected roll frequency.")
    elif pip_total >= 10:
        parts.append("Solid pip total with reliable production.")
    else:
        parts.append("Lower pip total — compensated by resource diversity.")

    # Best resources
    top = sorted(expected_resources.items(), key=lambda x: -x[1])[:2]
    parts.append(f"Strongest production: {top[0][0]} and {top[1][0]}.")

    # Diversity
    if diversity == 3:
        parts.append("Touches 3 distinct resources — strong flexibility.")
    elif diversity == 2:
        parts.append("Covers 2 resource types.")
    else:
        parts.append("Single resource — highly specialized.")

    # Robber risk
    if robber_discount > 0.15:
        parts.append(f"Note: robber risk is elevated ({robber_discount:.0%} expected output loss) due to high-value adjacent hexes.")
    else:
        parts.append("Low robber risk.")

    return " ".join(parts)
```

---

## Settlement Placement Turn Order (Snake Draft)

Standard Catan uses a snake draft for starting placements:

```
4 players: P1 → P2 → P3 → P4 → P4 → P3 → P2 → P1
3 players: P1 → P2 → P3 → P3 → P2 → P1
2 players: P1 → P2 → P2 → P1
```

The simulation must account for this when modeling which intersections opponents will block before the user places their second settlement. Opponent placement is randomized in each simulation run (uniform random over valid intersections).

---

## Scoring Formula

```
final_score(intersection) =
    0.50 * normalized_win_rate
  + 0.30 * normalized_pip_total
  + 0.15 * normalized_diversity
  - 0.05 * robber_discount
```

All components normalized to [0, 1] across all intersections before combining. Weights can be exposed as user-adjustable sliders in a future iteration.

---

## File Structure

```
catan-optimizer/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── BoardSetup.jsx        # Hex grid SVG + resource/number assignment
│   │   │   ├── PlayerConfig.jsx      # Players, turn order, sim count
│   │   │   ├── ResultsOverlay.jsx    # Intersection ranking overlaid on board
│   │   │   └── ExplanationPanel.jsx  # Text + chart breakdown
│   │   ├── utils/
│   │   │   ├── hexGeometry.js        # Hex/intersection coordinate math
│   │   │   └── intersectionMap.js    # Precomputed adjacency for 54 intersections
│   │   ├── App.jsx
│   │   └── main.jsx
│   └── package.json
│
├── backend/
│   ├── main.py              # FastAPI app, /simulate endpoint
│   ├── simulation.py        # Monte Carlo engine
│   ├── board.py             # Board + intersection data model
│   ├── robber.py            # Robber placement logic
│   └── scorer.py            # Scoring + explanation generation
│
└── README.md
```

---

## Implementation Order

1. **Hex board SVG** — render 19 hexes, click to assign resource + number, validate token counts
2. **Intersection overlay** — compute and render 54 intersections over the board SVG
3. **FastAPI skeleton** — `/simulate` endpoint accepts board JSON, returns dummy data
4. **Board data model** — hex + intersection adjacency map in Python
5. **Dice roll simulation** — resource accumulation over N rounds
6. **Robber logic** — optimal robber placement on 7s
7. **Snake draft modeling** — opponent placement order
8. **Scoring + ranking** — rank intersections, normalize scores
9. **Explanation generation** — plain-English output per intersection
10. **Results UI** — highlight top 5, click to lock settlement 1, re-query for settlement 2
11. **Explanation panel** — bar chart + text for each candidate

---

## Key Edge Cases to Handle

- Desert hex: no number token, never produces resources, robber starts here
- Intersections touching the desert: pip contribution from desert side is 0
- Distance rule: no two settlements within 1 edge of each other (enforced during both simulated opponent placement and candidate generation)
- Robber has no valid target (e.g., all non-desert hexes touch the user): robber stays on current hex
- Duplicate numbers: 3, 4, 5, 6, 8, 9, 10, 11 each appear twice — both tokens are independent
- Settlement 2 candidates must exclude intersections adjacent to settlement 1 (distance rule)
