/**
 * BoardSetup.jsx — Light-theme SVG board with clean hex tiles.
 *
 * Props:
 *   hexes          — array of 19 hex objects { id, cx, cy, resource, number }
 *   ports          — port type per slot (see utils/ports.js)
 *   onHexUpdate    — (hexId, { resource, number }) => void
 *   onPortChange   — (slotIdx, portType) => void
 *   children       — optional overlay content (ResultsOverlay, settlements)
 *   interactive    — bool, if false hexes and ports are not clickable
 */

import { useState, useRef } from 'react';
import { hexPoints, SVG_WIDTH, SVG_HEIGHT } from '../utils/hexGeometry';
import { RESOURCES, RESOURCE_MAP, TOKEN_COUNTS, ALL_NUMBERS, HOT_NUMBERS, PIPS } from '../utils/constants';
import { PortMarkers, PortConfigPopover } from './PortMarkers';

// ── Pip dots ─────────────────────────────────────────────────────────────────

function PipDots({ pip, isHot }) {
  const colour  = isHot ? '#991b1b' : '#44403c';
  const spacing = 4.5;
  const total   = (pip - 1) * spacing;
  const startX  = -total / 2;
  return (
    <g>
      {Array.from({ length: pip }, (_, i) => (
        <circle key={i} cx={startX + i * spacing} cy={0} r={1.6} fill={colour} />
      ))}
    </g>
  );
}

// ── Hex Config Popover ───────────────────────────────────────────────────────

function getUsedTokenCounts(hexes, excludeId = null) {
  const counts = {};
  for (const h of hexes) {
    if (h.id === excludeId || !h.number) continue;
    counts[h.number] = (counts[h.number] || 0) + 1;
  }
  return counts;
}

function HexConfigPopover({ hex, hexes, onUpdate, onClose, anchorPos }) {
  const usedTokens = getUsedTokenCounts(hexes, hex.id);
  const isDesert   = hex.resource === 'desert';

  const POPOVER_H  = 295;
  const left       = Math.min(anchorPos.x, SVG_WIDTH - 244);
  const wouldClip  = anchorPos.y + 14 + POPOVER_H > SVG_HEIGHT;
  const top        = wouldClip ? Math.max(4, anchorPos.y - POPOVER_H - 6) : anchorPos.y + 14;

  function setResource(resId) {
    onUpdate(hex.id, { resource: resId, number: resId === 'desert' ? null : hex.number });
  }
  function toggleNumber(n) {
    onUpdate(hex.id, { resource: hex.resource, number: n === hex.number ? null : n });
  }

  return (
    <div className="hex-config-overlay" onMouseDown={onClose}>
      <div
        className="hex-config-popover"
        style={{ left, top }}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="hex-config-title">Hex #{hex.id + 1}</div>

        <div className="resource-grid">
          {RESOURCES.map((r) => (
            <button
              key={r.id}
              className={`resource-btn ${hex.resource === r.id ? 'active' : ''}`}
              onClick={() => setResource(r.id)}
            >
              <span className="resource-btn-emoji">{r.emoji}</span>
              {r.label}
            </button>
          ))}
        </div>

        {!isDesert && (
          <>
            <div className="label-xs" style={{ marginBottom: 7 }}>Number Token</div>
            <div className="token-grid">
              {ALL_NUMBERS.map((n) => {
                const used  = usedTokens[n] || 0;
                const max   = TOKEN_COUNTS[n];
                const avail = used < max || hex.number === n;
                const isHot = HOT_NUMBERS.has(n);
                return (
                  <button
                    key={n}
                    className={`token-btn ${hex.number === n ? 'active' : ''} ${isHot ? 'hot' : ''}`}
                    disabled={!avail}
                    onClick={() => toggleNumber(n)}
                    title={`${used}/${max} used`}
                  >
                    {n}
                  </button>
                );
              })}
            </div>
          </>
        )}

        <div style={{ marginTop: 11, display: 'flex', gap: 5 }}>
          <button
            className="btn btn-ghost btn-sm"
            style={{ flex: 1 }}
            onClick={() => { onUpdate(hex.id, { resource: null, number: null }); onClose(); }}
          >
            Clear
          </button>
          <button className="btn btn-primary btn-sm" style={{ flex: 1 }} onClick={onClose}>
            Done ✓
          </button>
        </div>
      </div>
    </div>
  );
}

// ── HEX FILL GRADIENTS ───────────────────────────────────────────────────────

const HEX_FILLS = {
  forest:    { base: '#2d6a4f', light: '#52b788' },
  hills:     { base: '#9b2226', light: '#d4504a' },
  fields:    { base: '#b5840a', light: '#e9a000' },
  pasture:   { base: '#457b3b', light: '#70a85e' },
  mountains: { base: '#4a5568', light: '#718096' },
  desert:    { base: '#c2820a', light: '#e9a000' },
};

// ── Main BoardSetup Component ────────────────────────────────────────────────

export default function BoardSetup({ hexes, ports, onHexUpdate, onPortChange, children, interactive = true }) {
  const [selectedHex, setSelectedHex]   = useState(null);
  const [selectedPort, setSelectedPort] = useState(null);
  const [popoverPos, setPopoverPos]     = useState({ x: 0, y: 0 });
  const svgRef = useRef(null);

  function handleHexClick(e, hex) {
    if (!interactive) return;
    const rect = svgRef.current.getBoundingClientRect();
    setPopoverPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
    setSelectedPort(null);
    setSelectedHex(hex);
  }

  // Anchored at the badge itself (SVG coords), so it works for keyboard too
  function handlePortSelect(slotIdx, markerPos) {
    setPopoverPos(markerPos);
    setSelectedHex(null);
    setSelectedPort(slotIdx);
  }

  const selectedId = selectedHex?.id ?? null;

  return (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      <div className="board-svg-wrapper" ref={svgRef}>
        <svg
          width={SVG_WIDTH}
          height={SVG_HEIGHT}
          viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
          style={{ display: 'block' }}
        >
          <defs>
            {/* Light neutral board background */}
            <radialGradient id="bgGrad" cx="50%" cy="50%" r="70%">
              <stop offset="0%"   stopColor="#dde3ea" />
              <stop offset="100%" stopColor="#c5cdd8" />
            </radialGradient>

            {/* Per-terrain radial gradients for depth */}
            {Object.entries(HEX_FILLS).map(([res, { base, light }]) => (
              <radialGradient key={res} id={`hg-${res}`} cx="35%" cy="30%" r="75%">
                <stop offset="0%"   stopColor={light} stopOpacity="0.95" />
                <stop offset="100%" stopColor={base}  stopOpacity="1" />
              </radialGradient>
            ))}

            {/* Token drop shadow */}
            <filter id="tokenShadow" x="-30%" y="-30%" width="160%" height="160%">
              <feDropShadow dx="0" dy="1.5" stdDeviation="2.5" floodColor="rgba(0,0,0,0.35)" />
            </filter>
          </defs>

          {/* Background removed */}

          {/* Hex tiles */}
          {hexes.map((hex) => {
            const res        = RESOURCE_MAP[hex.resource];
            const fillId     = res ? `url(#hg-${hex.resource})` : '#c5cdd8';
            const isSelected = hex.id === selectedId;
            const pips       = hex.number ? PIPS[hex.number] : 0;
            const isHot      = HOT_NUMBERS.has(hex.number);

            return (
              <g
                key={hex.id}
                className={`hex-tile ${!hex.resource ? 'unassigned' : ''} ${isSelected ? 'selected' : ''}`}
                onClick={(e) => handleHexClick(e, hex)}
              >
                {/* Hex fill */}
                <polygon
                  points={hexPoints(hex.cx, hex.cy)}
                  fill={fillId}
                  stroke="rgba(255,255,255,0.35)"
                  strokeWidth={1.5}
                />

                {/* Edge highlight for depth */}
                <polygon
                  points={hexPoints(hex.cx, hex.cy)}
                  fill="none"
                  stroke="rgba(0,0,0,0.14)"
                  strokeWidth={2}
                />

                {/* Resource emoji */}
                {res && (
                  <text
                    x={hex.cx}
                    y={hex.cy - (hex.number ? 13 : 0)}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fontSize={hex.number ? 22 : 30}
                    style={{ pointerEvents: 'none', userSelect: 'none' }}
                  >
                    {res.emoji}
                  </text>
                )}

                {/* Parchment number token */}
                {hex.number && (
                  <g
                    transform={`translate(${hex.cx}, ${hex.cy + 15})`}
                    filter="url(#tokenShadow)"
                    className="token-circle"
                  >
                    <circle r={16} fill="#f5f0df" />
                    <circle r={13.5} fill="#ede8d5" />
                    <text
                      x={0} y={-1}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      fontSize={isHot ? 12 : 11}
                      fontWeight={900}
                      fill={isHot ? '#991b1b' : '#1c1917'}
                      fontFamily="Inter, system-ui, sans-serif"
                      style={{ pointerEvents: 'none', userSelect: 'none' }}
                    >
                      {hex.number}
                    </text>
                    <g transform="translate(0, 7.5)">
                      <PipDots pip={pips} isHot={isHot} />
                    </g>
                  </g>
                )}

                {/* Unassigned placeholder */}
                {!hex.resource && (
                  <text
                    x={hex.cx} y={hex.cy}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fontSize={9}
                    fontWeight={600}
                    fill="rgba(0,0,0,0.22)"
                    fontFamily="Inter, system-ui, sans-serif"
                    style={{ pointerEvents: 'none', userSelect: 'none' }}
                  >
                    click
                  </text>
                )}
              </g>
            );
          })}

          {/* Ports around the coast */}
          <PortMarkers ports={ports} interactive={interactive} onSelect={handlePortSelect} />

          {/* Overlay children (intersections, settlements, etc.) */}
          {children}
        </svg>
      </div>

      {selectedHex && (
        <HexConfigPopover
          hex={selectedHex}
          hexes={hexes}
          onUpdate={(id, patch) => onHexUpdate(id, patch)}
          onClose={() => setSelectedHex(null)}
          anchorPos={popoverPos}
        />
      )}

      {selectedPort !== null && (
        <PortConfigPopover
          slotIdx={selectedPort}
          ports={ports}
          onChange={onPortChange}
          onClose={() => setSelectedPort(null)}
          anchorPos={popoverPos}
        />
      )}
    </div>
  );
}
