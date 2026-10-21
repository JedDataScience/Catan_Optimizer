/**
 * AnalysisPanel.jsx — Final settlement analysis view.
 *
 * Shows combined stats, bar chart, per-settlement breakdown, and
 * board scarcity context from the analyze endpoint.
 */

import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, ReferenceLine,
} from 'recharts';
import { RESOURCE_MAP, ALL_RESOURCES, SCARCITY_COLORS } from '../utils/constants';

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const { name, value } = payload[0];
  const info = RESOURCE_MAP[name];
  return (
    <div style={{
      background: '#1c2128',
      border: '1px solid rgba(255,255,255,0.1)',
      borderRadius: 8,
      padding: '8px 12px',
      fontSize: 12,
      color: '#e6edf3',
      boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
    }}>
      <span style={{ fontWeight: 800 }}>{info?.emoji} {info?.label}</span>
      <br />
      <span style={{ color: '#8b949e' }}>
        {(value * 36).toFixed(2)} pips · {value.toFixed(3)}/roll
      </span>
    </div>
  );
}

export default function AnalysisPanel({ analysis, onRestart }) {
  if (!analysis) return null;

  const {
    combined_pip_total,
    diversity,
    expected_resources,
    cards_per_roll,
    robber_expected_loss,
    explanation,
    board_analysis,
    s1,
    s2,
  } = analysis;

  const chartData = ALL_RESOURCES
    .filter((r) => (expected_resources?.[r] || 0) > 0)
    .map((res) => ({ name: res, value: expected_resources[res] }));

  const avgPerResource = chartData.length > 0
    ? chartData.reduce((s, d) => s + d.value, 0) / chartData.length
    : 0;

  // Same cutoffs as the backend explanation (scorer.explain): >15% elevated, >8% moderate
  const robberPct = Math.round(robber_expected_loss * 100);
  const robberColor = robberPct > 15 ? 'var(--red)' : robberPct > 8 ? 'var(--orange)' : 'var(--green)';

  return (
    <div>
      <div className="section-heading" style={{ marginBottom: 4 }}>Settlement Analysis</div>
      <div className="section-sub">
        Full breakdown of both your starting placements: {cards_per_roll.toFixed(2)} resource cards per roll.
      </div>

      {/* Key stats */}
      <div className="analysis-stat-grid">
        <div className="stat-card" style={{ '--stat-color': 'var(--accent)' }}>
          <div className="stat-value">{combined_pip_total}</div>
          <div className="stat-label">Total Pips</div>
        </div>
        <div className="stat-card" style={{ '--stat-color': 'var(--green)' }}>
          <div className="stat-value" style={{ color: 'var(--green)' }}>{diversity}</div>
          <div className="stat-label">Resources</div>
        </div>
        <div
          className="stat-card"
          style={{ '--stat-color': robberColor }}
          title={
            'Long-run share of your production the robber blocks. On each 7, any player is ' +
            'equally likely to roll; they move the robber to the hex that hurts the others most, ' +
            'never their own.'
          }
        >
          <div className="stat-value" style={{ color: robberColor }}>{robberPct}%</div>
          <div className="stat-label">Robber Risk</div>
        </div>
      </div>

      {/* Board scarcity context */}
      {board_analysis?.label && (
        <div className="card" style={{ marginBottom: 12, padding: '10px 14px' }}>
          <div className="label-xs" style={{ marginBottom: 7 }}>Board Resource Scarcity</div>
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
            {ALL_RESOURCES.map((res) => {
              const info   = RESOURCE_MAP[res];
              const lvl    = board_analysis.label[res] || 'moderate';
              const colors = SCARCITY_COLORS[lvl] || SCARCITY_COLORS.moderate;
              return (
                <div
                  key={res}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 4,
                    padding: '3px 8px', borderRadius: 99,
                    background: colors.bg, color: colors.text, border: `1px solid ${colors.border}`,
                    fontSize: 11, fontWeight: 600,
                  }}
                >
                  {info?.emoji} {lvl}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Explanation */}
      {explanation && (
        <div className="card" style={{ marginBottom: 12, background: '#fffbeb', borderColor: 'var(--accent-border)' }}>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.65, fontWeight: 500 }}>
            {explanation}
          </div>
        </div>
      )}

      {/* Resource chart */}
      <div className="label-xs" style={{ marginBottom: 8 }}>Expected Resources per Roll</div>
      <div style={{ height: 130, marginBottom: 14 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 6, right: 4, bottom: 4, left: -22 }}>
            <XAxis
              dataKey="name"
              tick={{ fontSize: 14 }}
              tickFormatter={(v) => RESOURCE_MAP[v]?.emoji || v}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 9, fill: 'var(--text-muted)' }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => v.toFixed(2)}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(0,0,0,0.04)' }} />
            {/* Board average reference line */}
            {avgPerResource > 0 && (
              <ReferenceLine
                y={avgPerResource}
                stroke="var(--border-strong)"
                strokeDasharray="3 3"
                label={{ value: 'avg', position: 'insideTopRight', fontSize: 9, fill: 'var(--text-muted)' }}
              />
            )}
            <Bar dataKey="value" radius={[4, 4, 0, 0]}>
              {chartData.map((entry) => (
                <Cell key={entry.name} fill={RESOURCE_MAP[entry.name]?.chartColor || '#888'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Per-settlement breakdown */}
      <div className="label-xs" style={{ marginBottom: 8 }}>Per-Settlement Breakdown</div>
      {[s1, s2].map((s, idx) => s && (
        <div key={idx} className="card" style={{ marginBottom: 8, padding: '11px 14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{ fontWeight: 700, fontSize: 13 }}>Settlement {idx + 1}</span>
            <span className="chip chip-accent" style={{ marginLeft: 'auto' }}>
              {s.pip_total} pips
            </span>
          </div>
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
            {Object.entries(s.expected_resources || {}).map(([res, val]) => {
              const info = RESOURCE_MAP[res];
              return (
                <div
                  key={res}
                  style={{
                    background: info?.light || '#f0f0f0',
                    border: `1px solid ${info?.color}30`,
                    borderRadius: 6,
                    padding: '3px 8px',
                    fontSize: 11,
                    color: info?.color || 'var(--text-primary)',
                    fontWeight: 700,
                  }}
                >
                  {info?.emoji} {val.toFixed(3)}/roll
                </div>
              );
            })}
          </div>
        </div>
      ))}

      <div style={{ display: 'flex', gap: 7, marginTop: 16 }}>
        <button className="btn btn-primary btn-lg" style={{ flex: 1 }} onClick={onRestart}>
          New Game
        </button>
      </div>
    </div>
  );
}
