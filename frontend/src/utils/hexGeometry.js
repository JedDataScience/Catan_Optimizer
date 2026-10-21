/**
 * hexGeometry.js
 *
 * Pointy-top hex grid math for the standard Catan board (3-4-5-4-3 rows).
 * All coordinates are in SVG pixels. HEX_SIZE is the circumradius (center → corner).
 *
 * Axial (q, r) coords for 19 hexes, left-to-right top-to-bottom:
 *   Row r=-2 (top 3):   q = 0,1,2
 *   Row r=-1 (4 hexes): q = -1,0,1,2
 *   Row r=0  (middle 5): q = -2,-1,0,1,2
 *   Row r=1  (4 hexes): q = -2,-1,0,1
 *   Row r=2  (bottom 3): q = -2,-1,0
 */

export const HEX_SIZE = 55;          // circumradius in pixels
export const SVG_WIDTH  = 620;
export const SVG_HEIGHT = 580;
export const SVG_CX = SVG_WIDTH  / 2;  // 310
export const SVG_CY = SVG_HEIGHT / 2;  // 290

const SQRT3 = Math.sqrt(3);

// Axial coords for each of the 19 hexes (id = array index, left→right, top→bottom)
const HEX_AXIAL = [
  // Row r=-2 (3 hexes)
  [0, -2], [1, -2], [2, -2],
  // Row r=-1 (4 hexes)
  [-1, -1], [0, -1], [1, -1], [2, -1],
  // Row r=0 (5 hexes)
  [-2, 0], [-1, 0], [0, 0], [1, 0], [2, 0],
  // Row r=1 (4 hexes)
  [-2, 1], [-1, 1], [0, 1], [1, 1],
  // Row r=2 (3 hexes)
  [-2, 2], [-1, 2], [0, 2],
];

/** Convert axial (q, r) to SVG pixel (cx, cy) for pointy-top hexes. */
function axialToPixel(q, r) {
  const x = HEX_SIZE * (SQRT3 * q + SQRT3 / 2 * r) + SVG_CX;
  const y = HEX_SIZE * (3 / 2 * r) + SVG_CY;
  return { x, y };
}

/**
 * Return the SVG coordinate of the i-th corner of a pointy-top hex.
 * Corners go clockwise starting from the top-right (30°).
 */
export function hexCorner(cx, cy, size, i) {
  const angleDeg = 60 * i + 30;
  const angleRad = (Math.PI / 180) * angleDeg;
  return {
    x: cx + size * Math.cos(angleRad),
    y: cy + size * Math.sin(angleRad),
  };
}

/**
 * Build the array of 19 Hex objects with pixel centers and corner arrays.
 * hex.id matches array index.
 */
export function buildHexGrid() {
  return HEX_AXIAL.map(([q, r], id) => {
    const { x: cx, y: cy } = axialToPixel(q, r);
    const corners = Array.from({ length: 6 }, (_, i) => hexCorner(cx, cy, HEX_SIZE, i));
    return { id, cx, cy, corners, resource: null, number: null };
  });
}

/** SVG polygon points string for a hex. */
export function hexPoints(cx, cy, size = HEX_SIZE) {
  return Array.from({ length: 6 }, (_, i) => {
    const { x, y } = hexCorner(cx, cy, size, i);
    return `${x},${y}`;
  }).join(' ');
}
