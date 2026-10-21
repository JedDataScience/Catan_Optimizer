/**
 * ResultsOverlay.jsx — SVG overlay for the board.
 *
 * Light theme: dots are dark-on-light, rank badges are solid colored,
 * user settlements are amber house, opponents get player-colored houses.
 */

import { RANK_COLORS, PLAYER_COLORS } from '../utils/constants';

/** Simple SVG house shape centered at (0,0). */
function House({ color, scale = 1, labelText = null }) {
  const s = scale;
  return (
    <g>
      {/* Drop shadow */}
      <polygon
        points={`${-7*s},${-2*s} 0,${-10*s} ${7*s},${-2*s}`}
        fill="rgba(0,0,0,0.15)"
        transform="translate(0.5,1.5)"
      />
      <rect
        x={-6*s} y={-2*s} width={12*s} height={9*s}
        fill="rgba(0,0,0,0.15)" rx={1} transform="translate(0.5,1.5)"
      />
      {/* Roof */}
      <polygon
        points={`${-7*s},${-2*s} 0,${-10*s} ${7*s},${-2*s}`}
        fill={color}
        stroke="rgba(255,255,255,0.6)"
        strokeWidth={0.8}
        strokeLinejoin="round"
      />
      {/* Body */}
      <rect
        x={-6*s} y={-2*s} width={12*s} height={9*s}
        fill={color}
        stroke="rgba(255,255,255,0.6)"
        strokeWidth={0.8}
        rx={1}
      />
      {/* Door */}
      <rect
        x={-2.2*s} y={1.5*s} width={4.4*s} height={5.5*s}
        fill="rgba(0,0,0,0.22)"
        rx={0.5}
      />
      {/* Label (S1 / S2) */}
      {labelText && (
        <text
          y={-14*s}
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize={8}
          fontWeight={800}
          fontFamily="Inter, system-ui, sans-serif"
          fill={color}
          style={{ userSelect: 'none', pointerEvents: 'none' }}
        >
          {labelText}
        </text>
      )}
    </g>
  );
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
}) {
  const rankMap = {};
  for (const r of recommendations) rankMap[r.intersection_id] = r;

  const placementMap = {};
  // The user's first placement is S1; any other user placement is S2
  let userS1id = null;
  for (const p of placements) {
    placementMap[p.intersection_id] = p.player;
    if (p.player === userPosition && userS1id === null) userS1id = p.intersection_id;
  }

  return (
    <g className="results-overlay">
      {intersections.map((node) => {
        const ranked   = rankMap[node.id];
        const placed   = placementMap[node.id];
        const excluded = exclusionZone.has(node.id);
        const isTopN   = highlightTop5 && ranked;
        const isPlaced = placed !== undefined;

        // ── Placed settlement ─────────────────────────────────────────────────
        if (isPlaced) {
          const isUser = placed === userPosition;
          if (isUser) {
            const lbl = node.id === userS1id ? 'S1' : 'S2';
            const col = node.id === userS1id ? '#e8930a' : '#2563eb';
            return (
              <g key={node.id} transform={`translate(${node.x}, ${node.y})`}>
                <circle r={18} fill={col + '16'} stroke={col} strokeWidth={1.5} />
                <House color={col} scale={1} labelText={lbl} />
              </g>
            );
          } else {
            const color = PLAYER_COLORS[placed] ?? '#9ca3af';
            return (
              <g key={node.id} transform={`translate(${node.x}, ${node.y})`}>
                <circle r={14} fill={color + '18'} stroke={color} strokeWidth={1.5} />
                <House color={color} scale={0.78} />
              </g>
            );
          }
        }

        // ── Top 5 ranked node ─────────────────────────────────────────────────
        if (isTopN) {
          const rank   = ranked.rank;
          const colour = RANK_COLORS[rank - 1];
          return (
            <g
              key={node.id}
              transform={`translate(${node.x}, ${node.y})`}
              onClick={() => onNodeClick?.(node.id)}
              style={{ cursor: 'pointer' }}
            >
              <circle r={22} fill="transparent" />
              {/* Pulsing outer ring */}
              <circle r={17} fill={colour + '14'} stroke={colour} strokeWidth={1.5} opacity={0.85}>
                <animate attributeName="r"       values="14;19;14" dur="2.4s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.5;1;0.5" dur="2.4s" repeatCount="indefinite" />
              </circle>
              {/* Solid badge */}
              <circle r={13} fill={colour} stroke="#fff" strokeWidth={1.5} />
              {/* Rank number */}
              <text
                textAnchor="middle"
                dominantBaseline="middle"
                fontSize={10}
                fontWeight={900}
                fontFamily="Inter, system-ui, sans-serif"
                fill="#fff"
                style={{ userSelect: 'none', pointerEvents: 'none' }}
              >
                {rank}
              </text>
            </g>
          );
        }

        // ── Excluded — faint blocked indicator ────────────────────────────────
        if (excluded && (allowAnyClick || highlightTop5)) {
          return (
            <g key={node.id} transform={`translate(${node.x}, ${node.y})`}>
              <circle
                r={6}
                fill="rgba(0,0,0,0.04)"
                stroke="rgba(0,0,0,0.12)"
                strokeWidth={1}
                strokeDasharray="2 2"
              />
            </g>
          );
        }

        // ── Available — clickable dot ─────────────────────────────────────────
        if (!excluded && allowAnyClick) {
          return (
            <g
              key={node.id}
              transform={`translate(${node.x}, ${node.y})`}
              onClick={() => onNodeClick?.(node.id)}
              style={{ cursor: 'pointer' }}
              className="intersection-node"
            >
              <circle r={16} fill="transparent" />
              <circle
                r={5}
                fill="rgba(0,0,0,0.08)"
                stroke="rgba(0,0,0,0.25)"
                strokeWidth={1}
              >
                <animate
                  attributeName="r"
                  values="4;6;4"
                  dur="3s"
                  repeatCount="indefinite"
                  begin={`${(node.id % 12) * 0.25}s`}
                />
              </circle>
            </g>
          );
        }

        return null;
      })}
    </g>
  );
}
