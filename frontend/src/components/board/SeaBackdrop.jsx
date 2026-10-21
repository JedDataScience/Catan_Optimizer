/**
 * SeaBackdrop.jsx — The water the island sits in.
 *
 *   SeaRing  — a rounded, flat-topped hexagon of deeper water framing the
 *              board (the outline of the standard 3-4-5-4-3 island), with a
 *              few wave strokes.
 *   Shallows — a pale halo hugging the coast, made by drawing every tile
 *              enlarged; overlaps merge into one shoreline.
 */

import { hexPoints, HEX_SIZE, SVG_CX, SVG_CY } from '../../utils/hexGeometry';

const RING_RADIUS = 318;

function flatTopHexPoints(cx, cy, r) {
  return Array.from({ length: 6 }, (_, i) => {
    const a = (Math.PI / 180) * (60 * i);
    return `${cx + r * Math.cos(a)},${cy + r * Math.sin(a)}`;
  }).join(' ');
}

// Short wave strokes placed in open water between the island and the ring
// (all inside the ring: |y| ≤ 0.866·R and |x| ≤ R − |y|/√3)
const WAVES = [
  [-276, -12], [272, 30], [-170, 236], [168, -236], [-40, 266],
];

export function SeaRing() {
  return (
    <g aria-hidden="true">
      <polygon
        points={flatTopHexPoints(SVG_CX, SVG_CY, RING_RADIUS)}
        fill="var(--sea-deep)"
        fillOpacity="0.32"
        stroke="var(--sea-deep)"
        strokeOpacity="0.32"
        strokeWidth="36"
        strokeLinejoin="round"
      />
      {WAVES.map(([dx, dy]) => (
        <path
          key={`${dx},${dy}`}
          d={`M ${SVG_CX + dx - 14} ${SVG_CY + dy} q 7 -6 14 0 t 14 0`}
          fill="none"
          stroke="#FFFFFF"
          strokeOpacity="0.55"
          strokeWidth="2.2"
          strokeLinecap="round"
        />
      ))}
    </g>
  );
}

export function Shallows({ hexes }) {
  return (
    <g aria-hidden="true">
      {hexes.map((h) => (
        <polygon
          key={h.id}
          points={hexPoints(h.cx, h.cy + 3, HEX_SIZE + 16)}
          fill="var(--shallows)"
          stroke="var(--shallows)"
          strokeWidth="10"
          strokeLinejoin="round"
        />
      ))}
    </g>
  );
}
