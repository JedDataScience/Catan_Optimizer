/**
 * ScarcityPanel.jsx — Per-resource scarcity pills from /board-analysis.
 */

import { RESOURCE_MAP, ALL_RESOURCES, SCARCITY_COLORS } from '../../utils/constants';

export default function ScarcityPanel({ boardAnalysis, title = 'Board Resource Scarcity' }) {
  if (!boardAnalysis) return null;
  const { scarcity, label, pip_by_resource } = boardAnalysis;

  return (
    <div style={{ marginBottom: 12 }}>
      <div className="label-xs" style={{ marginBottom: 8 }}>{title}</div>
      <div className="scarcity-grid">
        {ALL_RESOURCES.map((res) => {
          const info   = RESOURCE_MAP[res];
          const lvl    = label[res] || 'moderate';
          const colors = SCARCITY_COLORS[lvl] || SCARCITY_COLORS.moderate;
          const pct    = Math.round((scarcity[res] || 0) * 100);
          return (
            <div key={res} style={{ display: 'flex', flexDirection: 'column', width: '48px', alignItems: 'center' }}>
              <div
                className="scarcity-pill"
                style={{ background: 'var(--bg-subtle)', color: 'var(--text-primary)', borderColor: 'transparent', flexDirection: 'column', alignItems: 'center', padding: '4px 6px', gap: '2px', width: '100%' }}
                title={`${info?.label}: ${lvl} (${pip_by_resource[res] || 0} pips)`}
              >
                <span style={{ fontSize: 11, fontWeight: 700 }}>{info?.label}</span>
                <span style={{ fontWeight: 500, fontSize: 9, color: 'var(--text-secondary)' }}>{lvl}</span>
              </div>
              <div className="scarcity-bar-wrap" style={{ height: '3px', width: '36px', marginTop: '4px', background: 'var(--border)' }}>
                <div className="scarcity-bar" style={{ width: `${Math.min(100, Math.max(10, pct))}%`, background: colors.text, borderRadius: '2px' }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
