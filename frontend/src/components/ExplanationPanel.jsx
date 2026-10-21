/**
 * ExplanationPanel.jsx
 *
 * Shows top 5 recommended intersections with rank card, resource bars, and explanation.
 * Uses shared constants from utils/constants.js.
 */

import { RESOURCE_MAP, ALL_RESOURCES, RANK_COLORS } from '../utils/constants';

const MAX_EXPECTED = 5 / 36; // 6 or 8 = 5 pips → 5/36 per roll

function ResourceBars({ expectedResources }) {
  return (
    <div className="resource-bars">
      {ALL_RESOURCES.map((res) => {
        const info   = RESOURCE_MAP[res];
        const val    = expectedResources?.[res] || 0;
        const height = Math.max(Math.round((val / MAX_EXPECTED) * 28), val > 0 ? 3 : 0);
        return (
          <div key={res} className="resource-bar-wrap">
            <div
              className="resource-bar"
              style={{
                height: Math.max(height, 2),
                background: info?.chartColor || '#888',
                opacity: val > 0 ? 1 : 0.12,
              }}
            />
            <span className="resource-label-mini" title={info?.label}>{info?.emoji}</span>
          </div>
        );
      })}
    </div>
  );
}

export default function ExplanationPanel({ recommendations = [], onSelectNode, highlightedId, title }) {
  if (!recommendations.length) return null;

  return (
    <div>
      <div className="label-xs" style={{ marginBottom: 12, marginTop: 16 }}>{title || 'Top Recommendations'}</div>

      {recommendations.map((rec) => {
        const color       = RANK_COLORS[rec.rank - 1] || RANK_COLORS[4];
        const isHighlight = rec.intersection_id === highlightedId;
        // Expected pips of the best 2nd settlement still open (only sent for S1)
        const followUp    = rec.follow_up_pips != null ? rec.follow_up_pips : null;
        const scoreDisp   = (rec.score * 100).toFixed(0);

        return (
          <div
            key={rec.intersection_id}
            className={`rank-item ${isHighlight ? 'highlighted' : ''}`}
            style={{ '--rank-color': color }}
            onClick={() => onSelectNode?.(rec.intersection_id)}
            onMouseEnter={() => onSelectNode?.(rec.intersection_id)}
          >
            {/* Header row */}
            <div className="rank-item-header">
              <div
                className="rank-badge-inline"
                style={{ color, background: color + '18', borderColor: color }}
              >
                {rec.rank}
              </div>

              <div className="rank-meta">
                <span className="rank-stat">
                  <strong>{rec.pip_total}</strong>&nbsp;pips
                </span>
                <span className="rank-stat">
                  <strong>{rec.diversity}</strong>&nbsp;types
                </span>
                {followUp != null && (
                  <span className="rank-stat" title="Expected pips of the best 2nd settlement still open on your next turn">
                    2nd spot&nbsp;<strong>{followUp}</strong>&nbsp;pips
                  </span>
                )}
              </div>

              <span className="rank-score" style={{ color }}>
                {scoreDisp}
              </span>
            </div>

            {/* Resource production bars */}
            <ResourceBars expectedResources={rec.expected_resources} />

            {/* Explanation text */}
            {rec.explanation && (
              <div className="explanation-text">{rec.explanation}</div>
            )}
          </div>
        );
      })}
    </div>
  );
}
