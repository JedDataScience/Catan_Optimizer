/**
 * ResourceIcon.jsx — Flat SVG glyphs for each terrain, drawn on a 24×24 grid.
 *
 *   <ResourceGlyph>  for use inside an existing <svg> (tiles, docks, charts)
 *   <ResourceIcon>   a standalone inline <svg> for HTML (panel, popovers)
 *
 * One glyph set everywhere keeps the board and the panel speaking the same
 * visual language (and replaces the emoji, which render differently per OS).
 */

import { RESOURCE_MAP } from '../../utils/constants';

function Forest() {
  const { deep, slab } = RESOURCE_MAP.forest;
  return (
    <>
      <rect x="6.3" y="16" width="1.6" height="4" rx="0.5" fill="#6B4A2B" />
      <polygon points="7.1,3 12,10.5 2.2,10.5" fill={slab} />
      <polygon points="7.1,7 13,16.5 1.2,16.5" fill={deep} />
      <rect x="16.2" y="17" width="1.5" height="3" rx="0.5" fill="#6B4A2B" />
      <polygon points="17,7 21.2,13 12.8,13" fill={slab} />
      <polygon points="17,10 22,17.5 12,17.5" fill={deep} />
    </>
  );
}

function Fields() {
  const { deep, slab } = RESOURCE_MAP.fields;
  // Three wheat stalks: a stem with grains alternating left and right
  return (
    <>
      {[6, 12, 18].map((x, i) => (
        <g key={x} transform={`translate(${x} ${i === 1 ? 0 : 2})`}>
          <line x1="0" y1="7" x2="0" y2="21" stroke={deep} strokeWidth="1.4" strokeLinecap="round" />
          {[0, 1, 2, 3].map((k) => (
            <ellipse
              key={k}
              cx={k % 2 ? 1.7 : -1.7}
              cy={5 + k * 2.6}
              rx="1.3" ry="2.2"
              transform={`rotate(${k % 2 ? 25 : -25} ${k % 2 ? 1.7 : -1.7} ${5 + k * 2.6})`}
              fill={slab}
            />
          ))}
        </g>
      ))}
    </>
  );
}

function Pasture() {
  const { deep } = RESOURCE_MAP.pasture;
  return (
    <>
      <line x1="8" y1="15" x2="8" y2="20" stroke="#2F3A2F" strokeWidth="1.6" strokeLinecap="round" />
      <line x1="15" y1="15" x2="15" y2="20" stroke="#2F3A2F" strokeWidth="1.6" strokeLinecap="round" />
      {/* Fleece: overlapping circles read as wool at small sizes */}
      <g fill="#FFFFFF" stroke={deep} strokeWidth="1">
        <circle cx="7" cy="12" r="3.6" />
        <circle cx="11.5" cy="10" r="3.8" />
        <circle cx="15.5" cy="12.5" r="3.4" />
        <circle cx="10.5" cy="14" r="3.4" />
      </g>
      <g fill="#FFFFFF">
        <circle cx="7" cy="12" r="2.8" />
        <circle cx="11.5" cy="10.2" r="3" />
        <circle cx="15.5" cy="12.5" r="2.6" />
        <circle cx="10.5" cy="13.6" r="2.7" />
      </g>
      <ellipse cx="19.5" cy="10.5" rx="2.6" ry="2.2" fill="#2F3A2F" />
    </>
  );
}

function Hills() {
  const { deep, slab } = RESOURCE_MAP.hills;
  // A small stack of bricks
  const bricks = [
    [3, 14], [12, 14],
    [7.5, 9],
  ];
  return (
    <>
      {bricks.map(([x, y]) => (
        <rect key={`${x}-${y}`} x={x} y={y} width="9" height="5" rx="0.8" fill={slab} stroke={deep} strokeWidth="1.1" />
      ))}
      <rect x="3" y="19" width="18" height="1.6" rx="0.8" fill={deep} />
    </>
  );
}

function Mountains() {
  const { deep, slab } = RESOURCE_MAP.mountains;
  return (
    <>
      <polygon points="1.5,20 9.5,5 13.5,12 16.5,8.5 22.5,20" fill={slab} />
      <polygon points="9.5,5 13.5,12 12,20 1.5,20" fill={deep} opacity="0.55" />
      <polygon points="9.5,5 12.2,10 10.8,10.6 9.4,9.4 7.6,10.4" fill="#FFFFFF" />
      <polygon points="16.5,8.5 18.4,11.6 17.2,12 16.2,11.2 15,11.8" fill="#FFFFFF" />
    </>
  );
}

function Desert() {
  const { deep, slab } = RESOURCE_MAP.desert;
  return (
    <>
      <path d="M1.5 19 Q8 9.5 14.5 19 Z" fill={slab} />
      <path d="M9.5 19 Q16 12 22.5 19 Z" fill={deep} opacity="0.7" />
      <rect x="1.5" y="18.6" width="21" height="1.6" rx="0.8" fill={deep} />
    </>
  );
}

const GLYPHS = {
  forest: Forest,
  fields: Fields,
  pasture: Pasture,
  hills: Hills,
  mountains: Mountains,
  desert: Desert,
};

/** Glyph centred on (x, y), `size` SVG units wide. Renders nothing for unknown types. */
export function ResourceGlyph({ type, x = 0, y = 0, size = 24 }) {
  const Glyph = GLYPHS[type];
  if (!Glyph) return null;
  const s = size / 24;
  return (
    <g transform={`translate(${x - size / 2} ${y - size / 2}) scale(${s})`} aria-hidden="true">
      <Glyph />
    </g>
  );
}

/** Standalone inline icon for HTML. Decorative: pair it with a visible text label. */
export function ResourceIcon({ type, size = 20, className }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      style={{ flexShrink: 0 }}
    >
      <ResourceGlyph type={type} x={12} y={12} size={24} />
    </svg>
  );
}
