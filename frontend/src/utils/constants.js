/**
 * constants.js — Single source of truth for resource metadata and palette.
 *
 * Terrain colours come in three shades:
 *   top  — the tile's flat face
 *   slab — the tile's visible side edge (darker, gives the tile thickness)
 *   deep — a dark shade readable as text/icon colour on the light panel
 */

export const RESOURCES = [
  { id: 'forest',    label: 'Wood',   top: '#6FA83E', slab: '#4E7F2A', deep: '#3D6B22' },
  { id: 'hills',     label: 'Brick',  top: '#E5874A', slab: '#B9622E', deep: '#9A4A1E' },
  { id: 'fields',    label: 'Wheat',  top: '#F3CF4A', slab: '#C9A42C', deep: '#7D620A' },
  { id: 'pasture',   label: 'Sheep',  top: '#B5D84C', slab: '#8DAF2E', deep: '#56700F' },
  { id: 'mountains', label: 'Ore',    top: '#A3AEB1', slab: '#7A8689', deep: '#4F5B5E' },
  { id: 'desert',    label: 'Desert', top: '#EAD39C', slab: '#C6AC70', deep: '#7E6838' },
];

export const RESOURCE_MAP = Object.fromEntries(RESOURCES.map((r) => [r.id, r]));

export const ALL_RESOURCES = ['forest', 'hills', 'fields', 'pasture', 'mountains'];

// Classic Catan player pieces. PLAYER_INK is a darker version that stays
// readable as text on the light panel (white pieces read as ink).
export const PLAYER_COLORS = ['#D8503F', '#3F7FD6', '#F08A2C', '#F2F4F3'];
export const PLAYER_INK    = ['#B23A2B', '#2C62AE', '#A9570E', '#173B3A'];
export const PLAYER_NAMES  = ['Red', 'Blue', 'Orange', 'White'];
export const PLAYER_LABELS = ['1st', '2nd', '3rd', '4th'];

// Hexes of each resource on the standard board (19 total). Matches RESOURCE_COUNTS in backend/board.py.
export const RESOURCE_COUNTS = { forest: 4, hills: 3, fields: 4, pasture: 4, mountains: 3, desert: 1 };

export const TOKEN_COUNTS = { 2: 1, 3: 2, 4: 2, 5: 2, 6: 2, 8: 2, 9: 2, 10: 2, 11: 2, 12: 1 };
export const ALL_NUMBERS  = [2, 3, 4, 5, 6, 8, 9, 10, 11, 12];
export const HOT_NUMBERS  = new Set([6, 8]);
export const PIPS         = { 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 8: 5, 9: 4, 10: 3, 11: 2, 12: 1 };

// UI palette used inside SVG (CSS uses the matching custom properties in index.css)
export const INK  = '#173B3A';
export const GOLD = '#F2B33D';
export const HOT  = '#C2412D'; // 6 and 8 numerals

// Rank pins: gold for the best spot, ink for the rest
export const RANK_COLORS = [GOLD, INK, INK, INK, INK];

// Scarcity meter colour per level (from /board-analysis labels)
export const SCARCITY_COLORS = {
  abundant:      '#4FB3A9',
  moderate:      '#9BB56A',
  scarce:        '#E0A13A',
  'very scarce': '#C2412D',
};
