/**
 * production.js — Turn an { resource: cardsPerRoll } map into ordered bar
 * segments, each with its share of the total, for the production bar.
 */

import { ALL_RESOURCES } from './constants';

export function productionSegments(expected = {}) {
  const items = ALL_RESOURCES
    .map((resource) => ({ resource, value: expected[resource] ?? 0 }))
    .filter((s) => s.value > 0);
  const total = items.reduce((sum, s) => sum + s.value, 0);
  return items.map((s) => ({ ...s, share: total > 0 ? s.value / total : 0 }));
}
