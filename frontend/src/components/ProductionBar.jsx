/**
 * ProductionBar.jsx — One horizontal bar split by resource (widths are each
 * resource's share of expected cards), with an icon legend underneath.
 * Everything is in normal flow, so it can't overlap the text around it.
 */

import { RESOURCE_MAP } from '../utils/constants';
import { productionSegments } from '../utils/production';
import { ResourceIcon } from './board/ResourceIcon';

export default function ProductionBar({ expected }) {
  const segments = productionSegments(expected);
  if (!segments.length) return null;

  return (
    <div>
      <div
        className="prod-bar"
        role="img"
        aria-label={segments.map((s) => `${RESOURCE_MAP[s.resource].label} ${Math.round(s.share * 100)}%`).join(', ')}
      >
        {segments.map((s) => (
          <div
            key={s.resource}
            className="prod-seg"
            style={{ flexBasis: `${s.share * 100}%`, background: RESOURCE_MAP[s.resource].top }}
          />
        ))}
      </div>
      <ul className="prod-legend">
        {segments.map((s) => (
          <li key={s.resource}>
            <ResourceIcon type={s.resource} size={16} />
            {RESOURCE_MAP[s.resource].label}
            <strong className="num">{s.value.toFixed(2)}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}
