/**
 * constants.js — Single source of truth for resource metadata shared across all components.
 */

export const RESOURCES = [
  { id: 'forest',    label: 'Wood',   emoji: '🌲', color: '#2d6a4f', chartColor: '#40916c', light: '#d8f3dc' },
  { id: 'hills',     label: 'Brick',  emoji: '🧱', color: '#9b2226', chartColor: '#ae2012', light: '#ffddd2' },
  { id: 'fields',    label: 'Wheat',  emoji: '🌾', color: '#b5840a', chartColor: '#e9a000', light: '#fff3b0' },
  { id: 'pasture',   label: 'Sheep',  emoji: '🐑', color: '#457b3b', chartColor: '#70a85e', light: '#d9f0d3' },
  { id: 'mountains', label: 'Ore',    emoji: '⛏️',  color: '#4a5568', chartColor: '#718096', light: '#e2e8f0' },
  { id: 'desert',    label: 'Desert', emoji: '🏜️', color: '#c2820a', chartColor: '#d4a017', light: '#fef9c3' },
];

export const RESOURCE_MAP = Object.fromEntries(RESOURCES.map(r => [r.id, r]));

export const ALL_RESOURCES = ['forest', 'hills', 'fields', 'pasture', 'mountains'];

export const PLAYER_COLORS = ['#f59e0b', '#ef4444', '#22c55e', '#6366f1'];
export const PLAYER_LABELS = ['1st', '2nd', '3rd', '4th'];

export const TOKEN_COUNTS = { 2: 1, 3: 2, 4: 2, 5: 2, 6: 2, 8: 2, 9: 2, 10: 2, 11: 2, 12: 1 };
export const ALL_NUMBERS  = [2, 3, 4, 5, 6, 8, 9, 10, 11, 12];
export const HOT_NUMBERS  = new Set([6, 8]);
export const PIPS         = { 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 8: 5, 9: 4, 10: 3, 11: 2, 12: 1 };

export const RANK_COLORS = ['#16a34a', '#65a30d', '#ca8a04', '#ea580c', '#dc2626'];

export const SCARCITY_COLORS = {
  abundant:     { bg: '#f0fdf4', text: '#15803d', border: '#bbf7d0' },
  moderate:     { bg: '#fefce8', text: '#854d0e', border: '#fde68a' },
  scarce:       { bg: '#fff7ed', text: '#c2410c', border: '#fed7aa' },
  'very scarce':{ bg: '#fef2f2', text: '#b91c1c', border: '#fecaca' },
};
