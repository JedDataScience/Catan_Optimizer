/**
 * RecommendationList.jsx — The top 5 spots as a ranked list.
 *
 * Each row's summary (rank, cards per roll, pips, score) is a button; the
 * open row shows the detail: stat cells, the production bar, and the
 * explanation. The best spot starts open. Hovering or focusing a row
 * highlights its pin on the board.
 */

import { useState } from 'react';
import ProductionBar from './ProductionBar';

function StatCell({ value, label }) {
  return (
    <div className="stat-cell">
      <strong className="num">{value}</strong>
      <span>{label}</span>
    </div>
  );
}

export default function RecommendationList({ recommendations = [], onHighlight, highlightedId }) {
  const [openId, setOpenId] = useState(recommendations[0]?.intersection_id ?? null);
  if (!recommendations.length) return null;

  return (
    <ol className="rank-list" onMouseLeave={() => onHighlight?.(null)}>
      {recommendations.map((rec) => {
        const isOpen = rec.intersection_id === openId;
        const detailId = `rec-detail-${rec.intersection_id}`;
        const classes = ['rank-row'];
        if (isOpen) classes.push('is-open');
        if (rec.intersection_id === highlightedId) classes.push('is-highlighted');

        return (
          <li key={rec.intersection_id} className={classes.join(' ')} onMouseEnter={() => onHighlight?.(rec.intersection_id)}>
            <button
              type="button"
              className="rank-summary"
              aria-expanded={isOpen}
              aria-controls={detailId}
              onClick={() => setOpenId(isOpen ? null : rec.intersection_id)}
              onFocus={() => onHighlight?.(rec.intersection_id)}
            >
              <span className={`rank-pin${rec.rank === 1 ? ' is-best' : ''}`} aria-label={`Rank ${rec.rank}`}>
                {rec.rank}
              </span>
              <span className="rank-headline">
                <span><strong className="num">{rec.cards_per_roll.toFixed(2)}</strong>cards per roll</span>
                <span><strong className="num">{rec.pip_total}</strong>pips</span>
              </span>
              <span className="rank-score" title="Compared with every open spot on this board (100 = best)">
                <strong className="num">{rec.score}</strong>
                <span>score</span>
              </span>
            </button>

            {isOpen && (
              <div className="rank-detail" id={detailId}>
                <div className="stat-cells">
                  <StatCell value={rec.diversity} label={rec.diversity === 1 ? 'resource type' : 'resource types'} />
                  {rec.follow_up_pips != null && (
                    <StatCell value={rec.follow_up_pips} label="pips at best 2nd spot" />
                  )}
                  <StatCell value={rec.expansion_pips} label="pips two roads away" />
                </div>
                <ProductionBar expected={rec.expected_resources} />
                {rec.explanation && <p className="rank-why">{rec.explanation}</p>}
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
