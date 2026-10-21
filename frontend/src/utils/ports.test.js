import { describe, expect, it } from 'vitest';
import { DEFAULT_PORT_TYPES, PORT_SLOTS, PORT_TYPE_OPTIONS, portMarkerPosition, shufflePorts, swapPortType } from './ports';
import { INTERSECTIONS } from './intersectionMap';
import { SVG_CX, SVG_CY } from './hexGeometry';

function counts(ports) {
  return ports.reduce((acc, t) => ({ ...acc, [t]: (acc[t] ?? 0) + 1 }), {});
}

const STANDARD = counts(DEFAULT_PORT_TYPES);

describe('swapPortType', () => {
  it('keeps the standard set of port types for every possible change', () => {
    for (let slot = 0; slot < PORT_SLOTS.length; slot++) {
      for (const type of PORT_TYPE_OPTIONS) {
        const next = swapPortType(DEFAULT_PORT_TYPES, slot, type);
        expect(next[slot]).toBe(type);
        expect(counts(next)).toEqual(STANDARD);
      }
    }
  });

  it('returns the same array when nothing changes', () => {
    expect(swapPortType(DEFAULT_PORT_TYPES, 0, DEFAULT_PORT_TYPES[0])).toBe(DEFAULT_PORT_TYPES);
  });

  it('does not mutate its input', () => {
    const before = [...DEFAULT_PORT_TYPES];
    swapPortType(DEFAULT_PORT_TYPES, 0, 'mountains');
    expect(DEFAULT_PORT_TYPES).toEqual(before);
  });
});

describe('shufflePorts', () => {
  it('always produces the standard set', () => {
    for (let i = 0; i < 50; i++) expect(counts(shufflePorts())).toEqual(STANDARD);
  });
});

describe('portMarkerPosition', () => {
  it('puts every badge outside its coastal edge', () => {
    PORT_SLOTS.forEach(([a, b], slot) => {
      const mid = { x: (INTERSECTIONS[a].x + INTERSECTIONS[b].x) / 2, y: (INTERSECTIONS[a].y + INTERSECTIONS[b].y) / 2 };
      const pos = portMarkerPosition(slot);
      expect(Math.hypot(pos.x - SVG_CX, pos.y - SVG_CY)).toBeGreaterThan(Math.hypot(mid.x - SVG_CX, mid.y - SVG_CY));
    });
  });
});
