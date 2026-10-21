/**
 * AnalysisPanel.jsx — Step 4: the result for both of your settlements.
 */

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { RESOURCE_MAP, ALL_RESOURCES, INK } from '../utils/constants';
import { ResourceGlyph } from './board/ResourceIcon';
import ProductionBar from './ProductionBar';
import ScarcityPanel from './panels/ScarcityPanel';

// Same cutoffs as the backend explanation (scorer.explain)
function robberLevel(pct) {
  if (pct > 15) return 'high';
  if (pct > 8) return 'moderate';
  return 'low';
}

function GlyphTick({ x, y, payload }) {
  return <ResourceGlyph type={payload.value} x={x} y={y + 12} size={18} />;
}

function ChartTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const { name, value } = payload[0].payload;
  return (
    <div className="popover" style={{ position: 'static', width: 'auto', padding: '8px 12px', animation: 'none' }}>
      <strong>{RESOURCE_MAP[name].label}</strong>
      <div className="num" style={{ color: 'var(--ink-2)', fontSize: 'var(--t-xs)' }}>
        {value.toFixed(3)} cards per roll ({(value * 36).toFixed(0)} pips)
      </div>
    </div>
  );
}

function StatCell({ value, label, title }) {
  return (
    <div className="stat-cell" title={title}>
      <strong className="num">{value}</strong>
      <span>{label}</span>
    </div>
  );
}

export default function AnalysisPanel({ analysis, onRestart }) {
  if (!analysis) return null;

  const {
    combined_pip_total, diversity, expected_resources, cards_per_roll,
    robber_expected_loss, explanation, board_analysis, s1, s2,
  } = analysis;

  const chartData = ALL_RESOURCES
    .filter((r) => (expected_resources?.[r] || 0) > 0)
    .map((res) => ({ name: res, value: expected_resources[res] }));

  const robberPct = Math.round(robber_expected_loss * 100);

  return (
    <div>
      <h1 className="panel-title">Your starting settlements</h1>
      <p className="panel-intro">
        Together they produce <strong className="num">{cards_per_roll.toFixed(2)}</strong> resource cards per roll.
      </p>

      <section className="section">
        <div className="result-stats">
          <StatCell value={combined_pip_total} label="total pips" />
          <StatCell value={diversity} label={diversity === 1 ? 'resource type' : 'resource types'} />
          <StatCell
            value={`${robberPct}%`}
            label={`robber risk (${robberLevel(robberPct)})`}
            title="Long-run share of your production the robber blocks. On each 7, any player is equally likely to roll; they move the robber to the hex that hurts the others most, never their own."
          />
        </div>
      </section>

      {explanation && (
        <section className="section">
          <p className="why-block">{explanation}</p>
        </section>
      )}

      <section className="section">
        <span className="field-label">Cards per roll by resource</span>
        <div className="chart-box">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 6, right: 4, bottom: 6, left: -18 }}>
              <XAxis dataKey="name" tick={<GlyphTick />} axisLine={false} tickLine={false} interval={0} height={30} />
              <YAxis
                tick={{ fontSize: 11, fill: INK, opacity: 0.6 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => v.toFixed(2)}
              />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(23,59,58,0.05)' }} />
              <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={44}>
                {chartData.map((entry) => (
                  <Cell key={entry.name} fill={RESOURCE_MAP[entry.name].top} stroke={RESOURCE_MAP[entry.name].slab} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="section">
        <span className="field-label">Each settlement</span>
        {[s1, s2].map((s, idx) => s && (
          <div key={s.intersection_id} className="settlement-line" style={{ display: 'block' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <span className="name">Settlement {idx + 1}</span>
              <span className="pips num">{s.pip_total} pips</span>
            </div>
            <ProductionBar expected={s.expected_resources} />
          </div>
        ))}
      </section>

      {board_analysis && (
        <section className="section">
          <ScarcityPanel boardAnalysis={board_analysis} />
        </section>
      )}

      <section className="section">
        <button className="btn btn-primary btn-lg btn-block" onClick={onRestart}>New game</button>
      </section>
    </div>
  );
}
