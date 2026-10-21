/**
 * ResultsOverlay.jsx — What sits on the intersections during the draft:
 *   placed settlements (houses in player colours),
 *   recommendation pins (gold for the best spot, ink for the rest),
 *   open spots you can click, and faint marks where building is blocked.
 */

import { INK, GOLD, PLAYER_COLORS, PLAYER_NAMES, RANK_COLORS } from '../utils/constants';

// The white player's piece needs dark text on it
const WHITE_PLAYER = PLAYER_NAMES.indexOf('White');

/**
 * A settlement piece centred on (0, 0) with a darker base for thickness.
 * With a `label` (the user's S1/S2) the label replaces the door, so it never
 * collides with the number tokens around the piece.
 */
function House({ color, scale = 1, label = null, labelColor = '#FFFFFF' }) {
  const s = scale;
  const body = `${-7 * s},${-1 * s} 0,${-9 * s} ${7 * s},${-1 * s} ${7 * s},${8 * s} ${-7 * s},${8 * s}`;
  return (
    <g>
      <polygon points={body} transform={`translate(0 ${2.5 * s})`} fill="rgba(23,59,58,0.35)" />
      <polygon points={body} fill={color} stroke={INK} strokeWidth="1.6" strokeLinejoin="round" />
      {label ? (
        <text
          y={3.6 * s}
          textAnchor="middle"
          dominantBaseline="middle"
          fontFamily="var(--font-display)"
          fontWeight="800"
          fontSize={6.2 * s}
          fill={labelColor}
          style={{ pointerEvents: 'none' }}
        >
          {label}
        </text>
      ) : (
        <rect x={-1.8 * s} y={2.5 * s} width={3.6 * s} height={5.5 * s} rx="0.6" fill={INK} opacity="0.55" />
      )}
    </g>
  );
}

function activateOnKey(handler) {
  return (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handler(); }
  };
}

export default function ResultsOverlay({
  intersections,
  recommendations = [],
  placements = [],
  userPosition,
  exclusionZone = new Set(),
  onNodeClick,
  highlightTop5 = false,
  allowAnyClick = false,
  highlightedId = null,
}) {
  const rankMap = {};
  for (const r of recommendations) rankMap[r.intersection_id] = r;

  // The user's first placement is S1; their other one is S2
  const placementMap = {};
  let userS1id = null;
  for (const p of placements) {
    placementMap[p.intersection_id] = p.player;
    if (p.player === userPosition && userS1id === null) userS1id = p.intersection_id;
  }

  return (
    <g className="results-overlay">
      {intersections.map((node) => {
        const ranked   = highlightTop5 ? rankMap[node.id] : undefined;
        const placed   = placementMap[node.id];
        const excluded = exclusionZone.has(node.id);
        const pos      = `translate(${node.x} ${node.y})`;

        // ── Placed settlement ────────────────────────────────────────────
        if (placed !== undefined) {
          const isUser = placed === userPosition;
          return (
            <g key={node.id} transform={pos} role="img" aria-label={`${PLAYER_NAMES[placed]} settlement${isUser ? ' (yours)' : ''}`}>
              <House
                color={PLAYER_COLORS[placed]}
                scale={isUser ? 1.6 : 1.25}
                label={isUser ? (node.id === userS1id ? 'S1' : 'S2') : null}
                labelColor={placed === WHITE_PLAYER ? INK : '#FFFFFF'}
              />
            </g>
          );
        }

        // ── Recommendation pin ───────────────────────────────────────────
        if (ranked) {
          const { rank } = ranked;
          const fill = RANK_COLORS[rank - 1];
          const isHighlighted = node.id === highlightedId;
          const click = () => onNodeClick?.(node.id);
          return (
            <g
              key={node.id}
              transform={pos}
              className="spot"
              onClick={click}
              onKeyDown={activateOnKey(click)}
              tabIndex={0}
              role="button"
              aria-label={`Place your settlement at recommendation ${rank}`}
            >
              <circle r="20" fill="transparent" />
              {(rank === 1 || isHighlighted) && (
                <circle r="19" fill="none" stroke={rank === 1 ? GOLD : INK} strokeWidth="2.5" opacity="0.7" />
              )}
              <circle r="13" cy="2" fill="rgba(23,59,58,0.3)" />
              <circle r={isHighlighted ? 15 : 13} fill={fill} stroke="#FFFFFF" strokeWidth="2.5" />
              <text
                textAnchor="middle"
                dominantBaseline="central"
                fontFamily="var(--font-display)"
                fontWeight="800"
                fontSize="13"
                fill={rank === 1 ? INK : '#FFFFFF'}
                style={{ pointerEvents: 'none' }}
              >
                {rank}
              </text>
            </g>
          );
        }

        // ── Blocked by the distance rule ─────────────────────────────────
        if (excluded) {
          if (!allowAnyClick && !highlightTop5) return null;
          return (
            <circle key={node.id} cx={node.x} cy={node.y} r="2.5" fill={INK} opacity="0.18" aria-hidden="true" />
          );
        }

        // ── Open spot ────────────────────────────────────────────────────
        if (allowAnyClick) {
          const click = () => onNodeClick?.(node.id);
          return (
            <g
              key={node.id}
              transform={pos}
              className="spot"
              onClick={click}
              onKeyDown={activateOnKey(click)}
              tabIndex={0}
              role="button"
              aria-label={`Place settlement at spot ${node.id + 1}`}
            >
              <circle r="14" fill="transparent" />
              {/* Quieter while recommendation pins are showing, so the pins lead */}
              <circle
                className="spot-dot"
                r={highlightTop5 ? 3.5 : 5.5}
                fill="#FFFFFF"
                stroke={INK}
                strokeWidth={highlightTop5 ? 1.2 : 1.8}
                opacity={highlightTop5 ? 0.7 : 1}
              />
            </g>
          );
        }

        return null;
      })}
    </g>
  );
}
