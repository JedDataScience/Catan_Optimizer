/**
 * TerrainTile.jsx — One hex tile drawn as a little slab:
 *   side edge (darker, offset down) → flat top face → inner highlight →
 *   terrain glyph → number token.
 *
 * Tiles are drawn slightly smaller than the true hex so there's a gap
 * between them, like real cardboard tiles. Intersections still sit on the
 * true corners, so settlements land in the gaps.
 */

import { hexPoints, HEX_SIZE } from '../../utils/hexGeometry';
import { RESOURCE_MAP, HOT_NUMBERS, PIPS, INK, HOT } from '../../utils/constants';
import { ResourceGlyph } from './ResourceIcon';

const TILE_SIZE  = HEX_SIZE - 3;  // visual gap between tiles
const SLAB_DEPTH = 7;             // how thick the tile looks

const EMPTY_TOP  = '#E3F4EF';
const EMPTY_SLAB = '#B6DDD3';

function NumberToken({ cx, cy, number }) {
  const hot  = HOT_NUMBERS.has(number);
  const pips = PIPS[number];
  const colour = hot ? HOT : INK;
  const spacing = 4;
  const startX = -((pips - 1) * spacing) / 2;
  return (
    <g transform={`translate(${cx} ${cy})`} style={{ pointerEvents: 'none' }}>
      <circle r="17" cy="1.5" fill="rgba(23,59,58,0.18)" />
      <circle r="17" fill="#FFFFFF" />
      <text
        y="-2"
        textAnchor="middle"
        dominantBaseline="middle"
        fontFamily="var(--font-display)"
        fontWeight="800"
        fontSize={hot ? 15 : 14}
        fill={colour}
      >
        {number}
      </text>
      {Array.from({ length: pips }, (_, i) => (
        <circle key={i} cx={startX + i * spacing} cy="9" r="1.4" fill={colour} />
      ))}
    </g>
  );
}

export default function TerrainTile({ hex, editable, selected, onActivate, dropDelay }) {
  const res   = RESOURCE_MAP[hex.resource];
  const top   = res?.top ?? EMPTY_TOP;
  const slab  = res?.slab ?? EMPTY_SLAB;
  const label = res
    ? `Tile ${hex.id + 1}: ${res.label}${hex.number ? ` ${hex.number}` : ''}`
    : `Tile ${hex.id + 1}: empty`;

  const classes = ['hex-tile'];
  if (editable) classes.push('is-editable');
  if (selected) classes.push('is-selected');
  if (dropDelay != null) classes.push('tile-drop');

  return (
    <g
      className={classes.join(' ')}
      style={dropDelay != null ? { '--delay': `${dropDelay}ms` } : undefined}
      onClick={editable ? (e) => onActivate(hex, e) : undefined}
      onKeyDown={editable ? (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onActivate(hex, null); }
      } : undefined}
      tabIndex={editable ? 0 : undefined}
      role={editable ? 'button' : undefined}
      aria-label={editable ? `${label} (edit)` : label}
    >
      {/* Side edge */}
      <polygon points={hexPoints(hex.cx, hex.cy + SLAB_DEPTH, TILE_SIZE)} fill={slab} />
      {/* Top face */}
      <polygon
        className="hex-top"
        points={hexPoints(hex.cx, hex.cy, TILE_SIZE)}
        fill={top}
        stroke={res ? 'none' : EMPTY_SLAB}
        strokeWidth={res ? 0 : 1.5}
        strokeDasharray={res ? undefined : '5 4'}
      />
      {/* Soft inner highlight along the edge */}
      {res && (
        <polygon
          points={hexPoints(hex.cx, hex.cy, TILE_SIZE - 3)}
          fill="none"
          stroke="rgba(255,255,255,0.35)"
          strokeWidth="2"
          style={{ pointerEvents: 'none' }}
        />
      )}

      {res ? (
        <ResourceGlyph
          type={hex.resource}
          x={hex.cx}
          y={hex.number ? hex.cy - 19 : hex.cy}
          size={hex.number ? 30 : 42}
        />
      ) : (
        <text
          x={hex.cx} y={hex.cy}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize="11"
          fontWeight="600"
          fill="#5E8F86"
          style={{ pointerEvents: 'none', userSelect: 'none' }}
        >
          {editable ? 'Set tile' : ''}
        </text>
      )}

      {hex.number && <NumberToken cx={hex.cx} cy={hex.cy + 16} number={hex.number} />}
    </g>
  );
}
