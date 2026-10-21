/**
 * BoardSetup.jsx — The island: sea, shallows, docks and bridges, tiles, and
 * whatever overlay is passed as children (settlements, recommendation pins).
 *
 * The SVG scales to fit its container via viewBox, so popovers convert SVG
 * coordinates to screen coordinates before placing themselves.
 *
 * Props:
 *   hexes          — array of 19 hex objects { id, cx, cy, resource, number }
 *   ports          — port type per slot (see utils/ports.js)
 *   onHexUpdate    — (hexId, { resource, number }) => void
 *   onPortChange   — (slotIdx, portType) => void
 *   dropKey        — changes when the board is randomised; tiles replay their drop-in
 *   children       — optional overlay content (ResultsOverlay)
 *   interactive    — bool, if false tiles and ports are not editable
 */

import { useRef, useState } from 'react';
import { SVG_WIDTH, SVG_HEIGHT } from '../utils/hexGeometry';
import { RESOURCES, RESOURCE_MAP, RESOURCE_COUNTS, TOKEN_COUNTS, ALL_NUMBERS, HOT_NUMBERS } from '../utils/constants';
import { placePopover, svgToScreen } from '../utils/popover';
import TerrainTile from './board/TerrainTile';
import { SeaRing, Shallows } from './board/SeaBackdrop';
import { PortDocks, PortConfigPopover } from './board/PortDock';
import { ResourceIcon } from './board/ResourceIcon';

// ── Tile popover ─────────────────────────────────────────────────────────────

// Measured height with terrain counts and numbers showing; used to decide
// whether the popover fits below the tile or should open above it
const HEX_POPOVER_HEIGHT = 440;

/** How many other tiles already use each value of `field` ('number' or 'resource'). */
function usedCounts(hexes, excludeId, field) {
  const counts = {};
  for (const h of hexes) {
    if (h.id === excludeId || !h[field]) continue;
    counts[h[field]] = (counts[h[field]] || 0) + 1;
  }
  return counts;
}

function HexConfigPopover({ hex, hexes, onUpdate, onClose, anchor }) {
  const used     = usedCounts(hexes, hex.id, 'number');
  const usedRes  = usedCounts(hexes, hex.id, 'resource');
  const isDesert = hex.resource === 'desert';
  // Like number tokens, a terrain is unavailable once the standard board has all of them
  const resLeft  = (id) => RESOURCE_COUNTS[id] - (usedRes[id] || 0);
  const firstOpen = RESOURCES.find((r) => resLeft(r.id) > 0)?.id;
  const pos      = placePopover(anchor, HEX_POPOVER_HEIGHT);
  const title    = hex.resource ? `${RESOURCE_MAP[hex.resource].label} tile` : `Tile ${hex.id + 1}`;

  function setResource(resId) {
    onUpdate(hex.id, { resource: resId, number: resId === 'desert' ? null : hex.number });
  }
  function toggleNumber(n) {
    onUpdate(hex.id, { resource: hex.resource, number: n === hex.number ? null : n });
  }

  return (
    <div className="popover-backdrop" onMouseDown={onClose}>
      <div
        className="popover"
        role="dialog"
        aria-label={`Edit ${title}`}
        style={pos}
        onMouseDown={(e) => e.stopPropagation()}
        onKeyDown={(e) => { if (e.key === 'Escape') onClose(); }}
      >
        <div className="popover-title">{title}</div>

        <span className="field-label">Terrain</span>
        <div className="choice-grid" style={{ '--cols': 3 }}>
          {RESOURCES.map((r) => {
            const left = resLeft(r.id);
            const free = left > 0 || hex.resource === r.id;
            return (
              <button
                key={r.id}
                className={`choice${hex.resource === r.id ? ' is-active' : ''}`}
                disabled={!free}
                onClick={() => setResource(r.id)}
                autoFocus={hex.resource ? hex.resource === r.id : r.id === firstOpen}
                aria-label={`${r.label}, ${free ? `${Math.max(left, 0)} left` : 'all placed'}`}
              >
                <ResourceIcon type={r.id} size={22} />
                {r.label}
                <span className="choice-sub num">{free ? `${Math.max(left, 0)} left` : 'all placed'}</span>
              </button>
            );
          })}
        </div>

        {hex.resource && !isDesert && (
          <>
            <span className="field-label">Number</span>
            <div className="token-grid">
              {ALL_NUMBERS.map((n) => {
                const count = used[n] || 0;
                const max   = TOKEN_COUNTS[n];
                const free  = count < max || hex.number === n;
                return (
                  <button
                    key={n}
                    className={`token-btn num${hex.number === n ? ' is-active' : ''}${HOT_NUMBERS.has(n) ? ' is-hot' : ''}`}
                    disabled={!free}
                    onClick={() => toggleNumber(n)}
                    title={free ? `${max - count} left` : 'All used'}
                    aria-label={`${n}, ${free ? `${max - count} left` : 'all used'}`}
                  >
                    {n}
                  </button>
                );
              })}
            </div>
          </>
        )}

        <div className="popover-actions">
          <button
            className="btn btn-secondary"
            onClick={() => { onUpdate(hex.id, { resource: null, number: null }); onClose(); }}
          >
            Clear tile
          </button>
          <button className="btn btn-primary" onClick={onClose}>Done</button>
        </div>
      </div>
    </div>
  );
}

// ── Board ────────────────────────────────────────────────────────────────────

export default function BoardSetup({ hexes, ports, onHexUpdate, onPortChange, dropKey = 0, children, interactive = true }) {
  // Store ids, not objects, so the popover always shows the latest tile state
  const [selectedHexId, setSelectedHexId] = useState(null);
  const [selectedPort, setSelectedPort]   = useState(null);
  const [anchor, setAnchor]               = useState({ x: 0, y: 0 });
  const svgRef = useRef(null);

  const selectedHex = selectedHexId === null ? null : hexes[selectedHexId];

  function handleTile(hex, event) {
    // Mouse: open at the pointer. Keyboard: open at the tile's centre.
    setAnchor(event ? { x: event.clientX, y: event.clientY } : svgToScreen(svgRef.current, { x: hex.cx, y: hex.cy }, SVG_WIDTH));
    setSelectedPort(null);
    setSelectedHexId(hex.id);
  }

  function handlePort(slotIdx, dockPos) {
    setAnchor(svgToScreen(svgRef.current, dockPos, SVG_WIDTH));
    setSelectedHexId(null);
    setSelectedPort(slotIdx);
  }

  // Closing a popover hands keyboard focus back to the tile/dock that opened
  // it, instead of dropping it at the top of the page
  function returnFocus(selector) {
    svgRef.current?.querySelector(selector)?.focus();
  }

  function closeHex() {
    const id = selectedHexId;
    setSelectedHexId(null);
    returnFocus(`[data-tile-id="${id}"]`);
  }

  function closePort() {
    const slot = selectedPort;
    setSelectedPort(null);
    returnFocus(`[data-port-slot="${slot}"]`);
  }

  return (
    <div className="board-frame">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
        role="group"
        aria-label="Catan board"
      >
        <SeaRing />
        <Shallows hexes={hexes} />
        <PortDocks ports={ports} editable={interactive} onSelect={handlePort} />

        {/* Keyed by dropKey so a new random board replays the settle-in */}
        <g key={dropKey}>
          {hexes.map((hex, i) => (
            <TerrainTile
              key={hex.id}
              hex={hex}
              editable={interactive}
              selected={hex.id === selectedHexId}
              onActivate={handleTile}
              dropDelay={dropKey > 0 ? i * 28 : null}
            />
          ))}
        </g>

        {children}
      </svg>

      {selectedHex && interactive && (
        <HexConfigPopover
          hex={selectedHex}
          hexes={hexes}
          onUpdate={onHexUpdate}
          onClose={closeHex}
          anchor={anchor}
        />
      )}

      {selectedPort !== null && interactive && (
        <PortConfigPopover
          slotIdx={selectedPort}
          ports={ports}
          onChange={onPortChange}
          onClose={closePort}
          anchor={anchor}
        />
      )}
    </div>
  );
}
