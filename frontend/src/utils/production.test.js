import { describe, expect, it } from 'vitest';
import { productionSegments } from './production';

describe('productionSegments', () => {
  it('keeps only produced resources, in a fixed order, with shares summing to 1', () => {
    const segs = productionSegments({ mountains: 0.1, forest: 0.3, desert: 0.5, fields: 0 });
    expect(segs.map((s) => s.resource)).toEqual(['forest', 'mountains']);
    expect(segs.reduce((sum, s) => sum + s.share, 0)).toBeCloseTo(1);
    expect(segs[0].share).toBeCloseTo(0.75);
  });

  it('returns nothing for an empty map', () => {
    expect(productionSegments({})).toEqual([]);
    expect(productionSegments()).toEqual([]);
  });
});
