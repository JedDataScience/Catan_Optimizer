/**
 * boardRandomizer.js
 *
 * Properly randomises the 19-hex Catan board using a Fisher-Yates shuffle.
 *
 * Rules enforced:
 *  - Canonical resource counts: 4 forest, 3 hills, 4 fields, 4 pasture,
 *    3 mountains, 1 desert  (total = 19)
 *  - Canonical token counts:
 *    {2:1, 3:2, 4:2, 5:2, 6:2, 8:2, 9:2, 10:2, 11:2, 12:1}  (total = 18)
 *  - Desert hex receives no number token (null)
 *  - 6 and 8 tokens may NOT be placed on adjacent hexes (official Catan rule)
 *
 * Uses rejection-sampling (up to MAX_ATTEMPTS) to enforce the 6/8 constraint.
 * Falls back to the static balanced layout if all attempts are exhausted.
 *
 * The hex adjacency map is derived from INTERSECTIONS: two hexes are adjacent
 * iff they both appear in the hexIds of the same intersection (they share an edge).
 */

import { INTERSECTIONS } from './intersectionMap';

// ── Canonical Catan resource + token sets ─────────────────────────────────────

// 4 forest, 3 hills, 4 fields, 4 pasture, 3 mountains, 1 desert = 19
const CANONICAL_RESOURCES = [
  'forest', 'forest', 'forest', 'forest',
  'hills',  'hills',  'hills',
  'fields', 'fields', 'fields', 'fields',
  'pasture','pasture','pasture','pasture',
  'mountains','mountains','mountains',
  'desert',
];

// 2:1, 3:2, 4:2, 5:2, 6:2, 8:2, 9:2, 10:2, 11:2, 12:1 = 18 tokens
const CANONICAL_TOKENS = [2, 3, 3, 4, 4, 5, 5, 6, 6, 8, 8, 9, 9, 10, 10, 11, 11, 12];

const MAX_ATTEMPTS = 100;

// ── Fisher-Yates shuffle ──────────────────────────────────────────────────────

/**
 * Return a new shuffled copy of arr using the Fisher-Yates algorithm.
 * NOTE: Do NOT use Array.sort(() => Math.random() - 0.5) — it is biased.
 */
export function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// ── Hex adjacency from intersection data ──────────────────────────────────────

/**
 * Build a Map<hexId, Set<hexId>> of adjacent hex pairs.
 * Two hexes are adjacent (share an edge) iff they both appear in the
 * hexIds[] of any single intersection.
 * Computed once at module load time.
 */
function buildHexAdjacency() {
  const adj = new Map();
  for (let i = 0; i < 19; i++) adj.set(i, new Set());

  for (const intersection of INTERSECTIONS) {
    const { hexIds } = intersection;
    for (let a = 0; a < hexIds.length; a++) {
      for (let b = a + 1; b < hexIds.length; b++) {
        adj.get(hexIds[a]).add(hexIds[b]);
        adj.get(hexIds[b]).add(hexIds[a]);
      }
    }
  }
  return adj;
}

const HEX_ADJACENCY = buildHexAdjacency();

// ── 6/8 adjacency constraint ──────────────────────────────────────────────────

/**
 * Returns true if no two hexes with number 6 or 8 are adjacent.
 * hexNumbers[hexId] = number token assigned to that hex (null for desert).
 */
function isValid68(hexNumbers) {
  const hotIds = hexNumbers
    .map((n, id) => ({ n, id }))
    .filter(({ n }) => n === 6 || n === 8)
    .map(({ id }) => id);

  for (const id of hotIds) {
    const neighbours = HEX_ADJACENCY.get(id) ?? new Set();
    for (const neighbour of neighbours) {
      if (hotIds.includes(neighbour)) return false;
    }
  }
  return true;
}

// ── Static fallback board ─────────────────────────────────────────────────────
// Used only when all MAX_ATTEMPTS fail (should be extremely rare).

const FALLBACK_RESOURCES = [
  'mountains','pasture','forest',
  'fields','hills','pasture','hills',
  'fields','forest','desert','forest','mountains',
  'forest','mountains','fields','pasture',
  'hills','fields','pasture',
];
const FALLBACK_NUMBERS = [
  10, 2, 9,
  12, 6, 4, 10,
  9, 11, null, 3, 8,
  8, 3, 4, 5,
  5, 6, 11,
];

// ── Main export ───────────────────────────────────────────────────────────────

/**
 * Produce a fully randomised board layout that obeys all Catan placement rules.
 *
 * Returns an array of 19 patch objects { resource, number } indexed by hex id
 * (same order as buildHexGrid() — left-to-right, top-to-bottom in the 3-4-5-4-3 layout).
 */
export function randomiseBoard() {
  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
    const resources = shuffle(CANONICAL_RESOURCES);
    const tokens    = shuffle(CANONICAL_TOKENS);

    // Assign tokens to non-desert hexes only; desert receives null
    const hexNumbers = new Array(19).fill(null);
    let tokenIdx = 0;
    for (let i = 0; i < 19; i++) {
      if (resources[i] !== 'desert') {
        hexNumbers[i] = tokens[tokenIdx++];
      }
    }

    if (isValid68(hexNumbers)) {
      return resources.map((resource, i) => ({ resource, number: hexNumbers[i] }));
    }
  }

  // Should not reach here in practice — logged for debugging
  console.warn(
    `[boardRandomizer] All ${MAX_ATTEMPTS} attempts failed the 6/8 constraint.`,
    'Falling back to static layout.',
  );
  return FALLBACK_RESOURCES.map((resource, i) => ({ resource, number: FALLBACK_NUMBERS[i] }));
}
