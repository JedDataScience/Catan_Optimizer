/**
 * popover.js — Place a fixed-position popover next to an on-screen point,
 * flipping above it or nudging it sideways so it stays inside the window.
 */

const MARGIN = 12;
export const POPOVER_WIDTH = 272; // keep in sync with .popover in index.css

export function placePopover(anchor, height, width = POPOVER_WIDTH) {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const left = Math.max(MARGIN, Math.min(anchor.x - width / 2, vw - width - MARGIN));
  const below = anchor.y + 18;
  const top = below + height + MARGIN <= vh
    ? below
    : Math.max(MARGIN, anchor.y - height - 18);
  return { left, top };
}

/** Screen point for an SVG-unit point inside `svgEl`, whose viewBox is `vbWidth` wide. */
export function svgToScreen(svgEl, point, vbWidth) {
  const rect = svgEl.getBoundingClientRect();
  const scale = rect.width / vbWidth;
  return { x: rect.left + point.x * scale, y: rect.top + point.y * scale };
}
