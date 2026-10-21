/**
 * PortMarkers.jsx — Port badges around the coast, and the popover to change one.
 *
 * PortMarkers renders inside the board <svg>; PortConfigPopover is plain HTML
 * positioned over the board (same pattern as the hex config popover).
 */

import { INTERSECTIONS } from '../utils/intersectionMap';
import { SVG_WIDTH, SVG_HEIGHT } from '../utils/hexGeometry';
import { RESOURCE_MAP } from '../utils/constants';
import { PORT_SLOTS, PORT_TYPE_OPTIONS, portMarkerPosition } from '../utils/ports';

function portLabel(type) {
  return type === 'any' ? '3:1 any' : `2:1 ${RESOURCE_MAP[type].label}`;
}

export function PortMarkers({ ports, interactive, onSelect }) {
  return (
    <g className="port-markers">
      {PORT_SLOTS.map((slot, idx) => {
        const pos  = portMarkerPosition(idx);
        const type = ports[idx];
        const res  = RESOURCE_MAP[type];
        const edge = slot.map((id) => INTERSECTIONS[id]);
        const select = () => onSelect(idx, pos);

        return (
          <g
            key={idx}
            onClick={interactive ? select : undefined}
            onKeyDown={interactive ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(); }
            } : undefined}
            tabIndex={interactive ? 0 : undefined}
            role={interactive ? 'button' : undefined}
            aria-label={`Port ${idx + 1}: ${portLabel(type)}${interactive ? ' (change type)' : ''}`}
            style={{ cursor: interactive ? 'pointer' : 'default' }}
          >
            <title>{portLabel(type)}</title>
            {/* Piers to the two intersections that can use this port */}
            {edge.map((corner) => (
              <line
                key={corner.id}
                x1={pos.x} y1={pos.y} x2={corner.x} y2={corner.y}
                stroke="#a8a29e" strokeWidth={2} strokeLinecap="round"
              />
            ))}
            <circle cx={pos.x} cy={pos.y} r={13} fill="#f5f0df" stroke={res?.color ?? '#57534e'} strokeWidth={2} />
            {type === 'any' ? (
              <text
                x={pos.x} y={pos.y}
                textAnchor="middle" dominantBaseline="middle"
                fontSize={9} fontWeight={800} fill="#1c1917"
                fontFamily="Inter, system-ui, sans-serif"
                style={{ pointerEvents: 'none', userSelect: 'none' }}
              >
                3:1
              </text>
            ) : (
              <>
                <text
                  x={pos.x} y={pos.y - 3}
                  textAnchor="middle" dominantBaseline="middle" fontSize={10}
                  style={{ pointerEvents: 'none', userSelect: 'none' }}
                >
                  {res.emoji}
                </text>
                <text
                  x={pos.x} y={pos.y + 7}
                  textAnchor="middle" dominantBaseline="middle"
                  fontSize={6.5} fontWeight={800} fill="#1c1917"
                  fontFamily="Inter, system-ui, sans-serif"
                  style={{ pointerEvents: 'none', userSelect: 'none' }}
                >
                  2:1
                </text>
              </>
            )}
          </g>
        );
      })}
    </g>
  );
}

export function PortConfigPopover({ slotIdx, ports, onChange, onClose, anchorPos }) {
  const POPOVER_W = 234;
  const POPOVER_H = 150;
  const left      = Math.max(4, Math.min(anchorPos.x, SVG_WIDTH - POPOVER_W - 10));
  const wouldClip = anchorPos.y + 14 + POPOVER_H > SVG_HEIGHT;
  const top       = wouldClip ? Math.max(4, anchorPos.y - POPOVER_H - 6) : anchorPos.y + 14;

  return (
    <div className="hex-config-overlay" onMouseDown={onClose}>
      <div
        className="hex-config-popover"
        style={{ left, top }}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="hex-config-title">Port #{slotIdx + 1}</div>
        <div className="resource-grid">
          {PORT_TYPE_OPTIONS.map((type) => (
            <button
              key={type}
              className={`resource-btn ${ports[slotIdx] === type ? 'active' : ''}`}
              onClick={() => { onChange(slotIdx, type); onClose(); }}
            >
              <span className="resource-btn-emoji">{type === 'any' ? '⚓' : RESOURCE_MAP[type].emoji}</span>
              {portLabel(type)}
            </button>
          ))}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          Swaps with the port that currently has this type, so the board keeps 4 generic + 5 resource ports.
        </div>
      </div>
    </div>
  );
}
