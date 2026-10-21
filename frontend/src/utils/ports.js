/**
 * ports.js — The 9 port slots on the standard board frame.
 *
 * Each slot is one coastal edge, i.e. two adjacent intersections on the same
 * outer hex, listed clockwise from the top. The port *types* are the user's
 * to set; positions are fixed like the physical frame.
 *
 * SYNC: must match PORT_SLOTS / DEFAULT_PORT_TYPES in backend/board.py
 * (both are checked against shared/board_geometry.json by tests).
 */

import { INTERSECTIONS } from './intersectionMap';
import { SVG_CX, SVG_CY } from './hexGeometry';
import { shuffle } from './boardRandomizer';

export const PORT_SLOTS = [
  [8, 9],    // top
  [10, 13],  // upper right
  [22, 37],  // right
  [45, 46],  // lower right
  [50, 53],  // bottom
  [47, 48],  // lower left
  [26, 40],  // left, lower
  [16, 28],  // left, upper
  [2, 3],    // upper left
];

// 4 generic 3:1 ports + one 2:1 port per resource
export const DEFAULT_PORT_TYPES = ['any', 'fields', 'mountains', 'any', 'hills', 'any', 'forest', 'pasture', 'any'];

export const PORT_TYPE_OPTIONS = ['any', 'forest', 'hills', 'fields', 'pasture', 'mountains'];

// How far (SVG units) the port dock sits outside the coastline: long enough
// for a short plank bridge from each coastal corner
const MARKER_OFFSET = 36;

/**
 * SVG position for a slot's badge: the midpoint of its edge, pushed outward
 * (away from the board centre) so it sits in the sea.
 */
export function portMarkerPosition(slotIdx) {
  const [a, b] = PORT_SLOTS[slotIdx].map((id) => INTERSECTIONS[id]);
  const mx = (a.x + b.x) / 2;
  const my = (a.y + b.y) / 2;
  const dx = mx - SVG_CX;
  const dy = my - SVG_CY;
  const len = Math.hypot(dx, dy) || 1;
  return { x: mx + (dx / len) * MARKER_OFFSET, y: my + (dy / len) * MARKER_OFFSET };
}

/**
 * Set slot `slotIdx` to `newType` by swapping with another slot that has
 * that type. Swapping (rather than overwriting) keeps the standard set of
 * 4 generic + 5 resource ports intact, so the board is always valid.
 */
export function swapPortType(ports, slotIdx, newType) {
  if (ports[slotIdx] === newType) return ports;
  const other = ports.findIndex((t, i) => i !== slotIdx && t === newType);
  if (other === -1) return ports; // not part of the standard set: ignore
  const next = [...ports];
  [next[slotIdx], next[other]] = [next[other], next[slotIdx]];
  return next;
}

/** A random arrangement of the standard port set. */
export function shufflePorts() {
  return shuffle(DEFAULT_PORT_TYPES);
}
