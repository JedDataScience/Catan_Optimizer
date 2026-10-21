/**
 * scoringInfo.js — Turn the /scoring-info response into rows for the
 * "How scoring works" panel, with plain-language names.
 */

import { RESOURCE_MAP } from './constants';

// Component keys from the backend (scorer.SCORE_WEIGHTS) → what players call them
export const COMPONENT_LABELS = {
  pip:       { label: 'Production',       hint: 'Pips on the spot, weighted by what each resource is worth and how rare it is' },
  follow_up: { label: 'Your second spot', hint: 'How good a second settlement will still be open on your next turn' },
  expansion: { label: 'Room to grow',     hint: 'The best open spots two roads away' },
  diversity: { label: 'Resource variety', hint: 'How many different resources you collect' },
  synergy:   { label: 'Resource pairs',   hint: 'Resources that work together, like ore and wheat for cities' },
};

/** Weight shares → rows sorted from biggest to smallest. Unknown keys are skipped. */
export function scoringRows(shares = {}) {
  return Object.entries(shares)
    .filter(([key]) => COMPONENT_LABELS[key])
    .map(([key, share]) => ({ key, share, ...COMPONENT_LABELS[key] }))
    .sort((a, b) => b.share - a.share);
}

/** Resource values (+ the earlier hand-picked values, if known) → rows sorted by value. */
export function resourceRows(values = {}, previous = {}) {
  return Object.entries(values)
    .filter(([id]) => RESOURCE_MAP[id])
    .map(([id, value]) => ({ id, label: RESOURCE_MAP[id].label, value, previous: previous[id] ?? null }))
    .sort((a, b) => b.value - a.value);
}
