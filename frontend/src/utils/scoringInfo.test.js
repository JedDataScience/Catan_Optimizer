import { describe, expect, it } from 'vitest';
import { resourceRows, scoringRows } from './scoringInfo';

describe('scoringRows', () => {
  it('labels and sorts components from biggest to smallest share', () => {
    const rows = scoringRows({ synergy: 0.07, pip: 0.39, follow_up: 0.27, mystery: 0.5 });
    expect(rows.map((r) => r.key)).toEqual(['pip', 'follow_up', 'synergy']);
    expect(rows[0].label).toBe('Production');
    expect(rows[1].label).toBe('Your second spot');
  });
});

describe('resourceRows', () => {
  it('sorts by value and pairs each resource with its earlier value', () => {
    const rows = resourceRows({ pasture: 0.75, mountains: 1.21, desert: 0 }, { mountains: 1.25 });
    expect(rows.map((r) => r.label)).toEqual(['Ore', 'Sheep', 'Desert']);
    expect(rows[0].previous).toBe(1.25);
    expect(rows[1].previous).toBeNull();
  });
});
