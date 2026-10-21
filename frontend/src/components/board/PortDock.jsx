/**
 * PortDock.jsx — Ports drawn as wooden docks reached by small plank bridges,
 * plus the popover to change a port's type.
 *
 * Each port slot has two coastal intersections that can trade through it;
 * one bridge runs from each of them out to the dock.
 */

import { INTERSECTIONS } from '../../utils/intersectionMap';
import { RESOURCE_MAP, INK } from '../../utils/constants';
import { PORT_SLOTS, PORT_TYPE_OPTIONS, portMarkerPosition } from '../../utils/ports';
import { placePopover } from '../../utils/popover';
import { ResourceGlyph, ResourceIcon } from './ResourceIcon';

const DOCK_R      = 16;
const BRIDGE_HALF = 3.6;   // half the bridge width
const PLANK_GAP   = 3.4;
const WOOD        = '#C98F58';
const WOOD_DARK   = '#7E5230';
const WOOD_LIGHT  = '#E2B07C';

function portLabel(type) {
  return type === 'any' ? '3:1 any resource' : `2:1 ${RESOURCE_MAP[type].label}`;
}

/** A plank bridge from `from` to `to`, drawn along +x then rotated into place. */
function Bridge({ from, to }) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const length = Math.hypot(dx, dy);
  const angle = (Math.atan2(dy, dx) * 180) / Math.PI;
  const planks = Math.floor(length / PLANK_GAP);

  return (
    <g transform={`translate(${from.x} ${from.y}) rotate(${angle})`}>
      <rect x="0" y={-BRIDGE_HALF} width={length} height={BRIDGE_HALF * 2} fill={WOOD} />
      {Array.from({ length: planks }, (_, i) => (
        <line
          key={i}
          x1={(i + 0.5) * PLANK_GAP} y1={-BRIDGE_HALF}
          x2={(i + 0.5) * PLANK_GAP} y2={BRIDGE_HALF}
          stroke={WOOD_DARK} strokeOpacity="0.45" strokeWidth="0.9"
        />
      ))}
      {/* Rails */}
      <line x1="0" y1={-BRIDGE_HALF} x2={length} y2={-BRIDGE_HALF} stroke={WOOD_DARK} strokeWidth="1.4" />
      <line x1="0" y1={BRIDGE_HALF}  x2={length} y2={BRIDGE_HALF}  stroke={WOOD_DARK} strokeWidth="1.4" />
    </g>
  );
}

export function PortDocks({ ports, editable, onSelect }) {
  return (
    <g className="ports">
      {PORT_SLOTS.map((slot, idx) => {
        const dock = portMarkerPosition(idx);
        const type = ports[idx];
        const label = `Port ${idx + 1}: ${portLabel(type)}`;
        const select = () => onSelect(idx, dock);

        return (
          <g
            key={idx}
            className={`port${editable ? ' is-editable' : ''}`}
            onClick={editable ? select : undefined}
            onKeyDown={editable ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(); }
            } : undefined}
            tabIndex={editable ? 0 : undefined}
            data-port-slot={idx}
            role={editable ? 'button' : 'img'}
            aria-label={editable ? `${label} (change type)` : label}
          >
            <title>{portLabel(type)}</title>

            {slot.map((id) => {
              const corner = INTERSECTIONS[id];
              // Stop each bridge at the dock's rim rather than its centre
              const len = Math.hypot(dock.x - corner.x, dock.y - corner.y);
              const t = (len - DOCK_R + 2) / len;
              const end = { x: corner.x + (dock.x - corner.x) * t, y: corner.y + (dock.y - corner.y) * t };
              return <Bridge key={id} from={corner} to={end} />;
            })}

            {/* Dock: wooden ring with a paper face */}
            <circle cx={dock.x} cy={dock.y + 2.5} r={DOCK_R} fill={WOOD_DARK} />
            <circle className="port-disc" cx={dock.x} cy={dock.y} r={DOCK_R} fill={WOOD_LIGHT} stroke={WOOD_DARK} strokeWidth="1.5" />
            <circle cx={dock.x} cy={dock.y} r={DOCK_R - 4} fill="#FFFFFF" />

            {type === 'any' ? (
              <text
                x={dock.x} y={dock.y + 0.5}
                textAnchor="middle" dominantBaseline="middle"
                fontFamily="var(--font-display)" fontWeight="800" fontSize="10" fill={INK}
                style={{ pointerEvents: 'none' }}
              >
                3:1
              </text>
            ) : (
              <>
                <ResourceGlyph type={type} x={dock.x} y={dock.y - 3} size={13} />
                <text
                  x={dock.x} y={dock.y + 7}
                  textAnchor="middle" dominantBaseline="middle"
                  fontFamily="var(--font-display)" fontWeight="800" fontSize="6.5" fill={INK}
                  style={{ pointerEvents: 'none' }}
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

const PORT_POPOVER_HEIGHT = 230;

export function PortConfigPopover({ slotIdx, ports, onChange, onClose, anchor }) {
  const pos = placePopover(anchor, PORT_POPOVER_HEIGHT);

  return (
    <div className="popover-backdrop" onMouseDown={onClose}>
      <div
        className="popover"
        role="dialog"
        aria-label={`Port ${slotIdx + 1} type`}
        style={pos}
        onMouseDown={(e) => e.stopPropagation()}
        onKeyDown={(e) => { if (e.key === 'Escape') onClose(); }}
      >
        <div className="popover-title">Port {slotIdx + 1}</div>
        <div className="choice-grid" style={{ '--cols': 3 }}>
          {PORT_TYPE_OPTIONS.map((type) => (
            <button
              key={type}
              className={`choice${ports[slotIdx] === type ? ' is-active' : ''}`}
              onClick={() => { onChange(slotIdx, type); onClose(); }}
              autoFocus={ports[slotIdx] === type}
            >
              {type === 'any'
                ? <span className="choice-big" style={{ fontSize: 'var(--t-sm)' }}>3:1</span>
                : <ResourceIcon type={type} size={22} />}
              {type === 'any' ? 'Any' : RESOURCE_MAP[type].label}
            </button>
          ))}
        </div>
        <p className="hint">
          Swaps with the port that has this type now, so the board keeps 4 generic and 5 resource ports.
        </p>
      </div>
    </div>
  );
}
