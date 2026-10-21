/**
 * MethodDiagram.jsx — The calibration method as four steps: random boards →
 * simulated games → statistics on who won → a test on new boards.
 *
 * Pictograms are drawn in SVG (so they scale cleanly); the captions are HTML
 * underneath so they wrap and stay readable on small screens.
 */

import { RESOURCE_MAP, INK, GOLD } from '../utils/constants';

const R = 30;          // pictogram circle radius
const XS = [50, 150, 250, 350];
const Y = 40;

function hexPoints(cx, cy, r) {
  return Array.from({ length: 6 }, (_, i) => {
    const a = (Math.PI / 180) * (60 * i + 30);
    return `${cx + r * Math.cos(a)},${cy + r * Math.sin(a)}`;
  }).join(' ');
}

function Boards({ x }) {
  const tiles = [[-10, -6, 'fields'], [10, -6, 'forest'], [0, 11, 'mountains']];
  return (
    <g>
      {tiles.map(([dx, dy, res]) => (
        <polygon key={res} points={hexPoints(x + dx, Y + dy, 10.5)} fill={RESOURCE_MAP[res].top} stroke={RESOURCE_MAP[res].slab} strokeWidth="1.5" />
      ))}
    </g>
  );
}

function Dice({ x }) {
  const die = (cx, cy, pips, rot) => (
    <g transform={`rotate(${rot} ${cx} ${cy})`}>
      <rect x={cx - 10} y={cy - 10} width="20" height="20" rx="4" fill="#FFFFFF" stroke={INK} strokeWidth="1.8" />
      {pips.map(([px, py], i) => <circle key={i} cx={cx + px} cy={cy + py} r="1.9" fill={INK} />)}
    </g>
  );
  return (
    <g>
      {die(x - 8, Y + 4, [[-4.5, -4.5], [0, 0], [4.5, 4.5]], -10)}
      {die(x + 9, Y - 5, [[-4.5, -4.5], [4.5, -4.5], [-4.5, 4.5], [4.5, 4.5]], 12)}
    </g>
  );
}

function Stats({ x }) {
  const bars = [[-14, 8], [-5, 14], [4, 20], [13, 26]];
  return (
    <g>
      {bars.map(([dx, h]) => (
        <rect key={dx} x={x + dx - 3.5} y={Y + 15 - h} width="7" height={h} rx="1.5" fill="var(--sea-deep)" />
      ))}
      <path d={`M ${x - 18} ${Y + 6} L ${x - 5} ${Y - 2} L ${x + 4} ${Y - 6} L ${x + 17} ${Y - 15}`}
            fill="none" stroke={INK} strokeWidth="2" strokeLinecap="round" />
      <line x1={x - 20} y1={Y + 16} x2={x + 20} y2={Y + 16} stroke={INK} strokeWidth="1.5" />
    </g>
  );
}

function Tested({ x }) {
  return (
    <g>
      <circle cx={x} cy={Y} r="16" fill={GOLD} stroke={INK} strokeWidth="1.8" />
      <path d={`M ${x - 7} ${Y} L ${x - 2} ${Y + 6} L ${x + 8} ${Y - 6}`} fill="none" stroke={INK} strokeWidth="2.6"
            strokeLinecap="round" strokeLinejoin="round" />
    </g>
  );
}

const PICTOGRAMS = [Boards, Dice, Stats, Tested];

export default function MethodDiagram({ games, boards, heldout }) {
  const steps = [
    { title: 'Random boards', text: `${boards.toLocaleString()} legal boards, each with a varied draft of starting spots.` },
    { title: 'Simulated games', text: `${games.toLocaleString()} full games: dice, robber, building, trades and dev cards.` },
    { title: 'Who won, and why', text: 'Statistics measure which starting features lead to wins, adjusted for turn order.' },
    { title: 'Tested on new boards', text: `New values vs old on ${heldout} boards the model never saw.` },
  ];

  return (
    <figure className="method">
      <svg viewBox="0 0 400 80" role="img" aria-label="Four steps: random boards, simulated games, statistics on who won, test on new boards">
        <defs>
          <marker id="method-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M0,0 L8,4 L0,8 z" fill={INK} opacity="0.5" />
          </marker>
        </defs>
        {XS.slice(0, -1).map((x) => (
          <line key={x} x1={x + R + 6} y1={Y} x2={x + 100 - R - 8} y2={Y}
                stroke={INK} strokeOpacity="0.5" strokeWidth="1.6" markerEnd="url(#method-arrow)" />
        ))}
        {XS.map((x, i) => {
          const Picto = PICTOGRAMS[i];
          return (
            <g key={x}>
              <circle cx={x} cy={Y} r={R} fill="var(--paper-2)" />
              <Picto x={x} />
            </g>
          );
        })}
      </svg>
      <ol className="method-steps">
        {steps.map((s) => (
          <li key={s.title}>
            <strong>{s.title}</strong>
            <span>{s.text}</span>
          </li>
        ))}
      </ol>
    </figure>
  );
}
