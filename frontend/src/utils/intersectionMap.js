/**
 * intersectionMap.js
 *
 * Computes the 54 unique intersection positions from the 19 hex corners and
 * builds the adjacency graph (which intersections are connected by an edge —
 * the "distance rule" in Catan).
 *
 * Algorithm:
 *  1. Iterate every hex → every corner → deduplicate within TOLERANCE pixels.
 *  2. Each unique corner becomes one Intersection { id, x, y, hexIds[] }.
 *  3. Two intersections are adjacent if they are consecutive corners of any
 *     shared hex (i.e., connected by a single road edge).
 *
 * This module exports pre-built singletons so the intersection map is only
 * computed once per page load.
 */

import { buildHexGrid, hexCorner, HEX_SIZE } from './hexGeometry';

const TOLERANCE = 0.5; // pixels

function cornersEqual(a, b) {
  return Math.abs(a.x - b.x) < TOLERANCE && Math.abs(a.y - b.y) < TOLERANCE;
}

/**
 * Build and return:
 *   intersections — array of 54 Intersection objects
 *   adjacencyMap  — Map<id, Set<adjacentId>>
 */
function buildIntersectionData(hexes) {
  const unique = [];          // { x, y }
  const hexCornerIds = [];    // hexCornerIds[hexId][cornerIdx] = intersection id

  for (const hex of hexes) {
    const cids = [];
    for (let ci = 0; ci < 6; ci++) {
      const corner = hexCorner(hex.cx, hex.cy, HEX_SIZE, ci);
      let found = -1;
      for (let uid = 0; uid < unique.length; uid++) {
        if (cornersEqual(corner, unique[uid])) {
          found = uid;
          break;
        }
      }
      if (found === -1) {
        found = unique.length;
        unique.push({ x: corner.x, y: corner.y });
      }
      cids.push(found);
    }
    hexCornerIds.push(cids);
  }

  // Build Intersection objects
  const intersections = unique.map((pt, id) => ({
    id,
    x: pt.x,
    y: pt.y,
    hexIds: [],
    adjacentIds: [],
  }));

  // Attach hex memberships
  for (const hex of hexes) {
    for (const cid of hexCornerIds[hex.id]) {
      if (!intersections[cid].hexIds.includes(hex.id)) {
        intersections[cid].hexIds.push(hex.id);
      }
    }
  }

  // Build adjacency: consecutive corners of the same hex are adjacent
  const adjSets = intersections.map(() => new Set());
  for (const hex of hexes) {
    const cids = hexCornerIds[hex.id];
    const n = cids.length;
    for (let i = 0; i < n; i++) {
      const a = cids[i];
      const b = cids[(i + 1) % n];
      adjSets[a].add(b);
      adjSets[b].add(a);
    }
  }

  for (let id = 0; id < intersections.length; id++) {
    intersections[id].adjacentIds = [...adjSets[id]].sort((a, b) => a - b);
  }

  // Build lookupMap for O(1) access
  const adjacencyMap = new Map(intersections.map((i) => [i.id, adjSets[i.id]]));

  return { intersections, adjacencyMap };
}

// ---------------------------------------------------------------------------
// Singletons (computed once)
// ---------------------------------------------------------------------------

const _hexes = buildHexGrid();
const { intersections: INTERSECTIONS, adjacencyMap: ADJACENCY_MAP } =
  buildIntersectionData(_hexes);

// Sanity check: standard Catan board must have exactly 54 intersections.
// If this fails, there is a floating-point deduplication issue in cornersEqual.
console.assert(
  INTERSECTIONS.length === 54,
  `[intersectionMap] Expected 54 intersections, got ${INTERSECTIONS.length}`,
);

export { INTERSECTIONS, ADJACENCY_MAP };

/**
 * Given a set of occupied intersection IDs, return the full exclusion zone
 * (occupied + their immediate neighbours) — the distance rule.
 */
export function getExclusionZone(occupiedIds) {
  const blocked = new Set(occupiedIds);
  for (const oid of occupiedIds) {
    const neighbours = ADJACENCY_MAP.get(oid);
    if (neighbours) {
      for (const nid of neighbours) blocked.add(nid);
    }
  }
  return blocked;
}
