/**
 * ScarcityPanel.jsx — How rare each resource is on this board (/board-analysis).
 */

import { RESOURCE_MAP, ALL_RESOURCES, SCARCITY_COLORS } from '../../utils/constants';
import { ResourceIcon } from '../board/ResourceIcon';

export default function ScarcityPanel({ boardAnalysis, title = 'How rare each resource is' }) {
  if (!boardAnalysis) return null;
  const { scarcity, label, pip_by_resource } = boardAnalysis;

  return (
    <div>
      <span className="field-label">{title}</span>
      <ul className="scarcity-row" style={{ listStyle: 'none' }}>
        {ALL_RESOURCES.map((res) => {
          const level = label[res] || 'moderate';
          // Show at least a sliver so "abundant" still reads as a meter
          const pct = Math.max(8, Math.round((scarcity[res] || 0) * 100));
          return (
            <li
              key={res}
              className="scarcity-item"
              title={`${RESOURCE_MAP[res].label}: ${level}, ${pip_by_resource[res] || 0} pips on the board`}
            >
              <ResourceIcon type={res} size={24} />
              <span className="name">{RESOURCE_MAP[res].label}</span>
              <span className="level">{level}</span>
              <div className="meter" aria-hidden="true">
                <div className="meter-fill" style={{ width: `${pct}%`, background: SCARCITY_COLORS[level] }} />
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
