import { describe, expect, it } from 'vitest';
import { randomiseBoard } from './boardRandomizer';
import { getBoardIssues } from './boardValidation';
import { INTERSECTIONS } from './intersectionMap';
import { buildHexGrid } from './hexGeometry';

// Hexes are adjacent when some intersection touches both
const hexNeighbours = new Map();
for (const { hexIds } of INTERSECTIONS) {
  for (const a of hexIds) {
    for (const b of hexIds) {
      if (a !== b) {
        if (!hexNeighbours.has(a)) hexNeighbours.set(a, new Set());
        hexNeighbours.get(a).add(b);
      }
    }
  }
}

function boardFrom(patches) {
  return buildHexGrid().map((h, i) => ({ ...h, ...patches[i] }));
}

describe('randomiseBoard', () => {
  it('always produces a valid board with no adjacent 6s and 8s', () => {
    for (let run = 0; run < 200; run++) {
      const patches = randomiseBoard();
      expect(getBoardIssues(boardFrom(patches))).toEqual([]);

      const hot = patches.flatMap((p, id) => (p.number === 6 || p.number === 8 ? [id] : []));
      for (const id of hot) {
        for (const other of hot) {
          expect(hexNeighbours.get(id).has(other)).toBe(false);
        }
      }
    }
  });
});

describe('getBoardIssues', () => {
  it('flags wrong resource counts once the board is filled', () => {
    const patches = randomiseBoard();
    const firstHills = patches.findIndex((p) => p.resource === 'hills');
    patches[firstHills] = { ...patches[firstHills], resource: 'forest' };
    const issues = getBoardIssues(boardFrom(patches));
    expect(issues.some((i) => i.includes('Wood'))).toBe(true);
    expect(issues.some((i) => i.includes('Brick'))).toBe(true);
  });

  it('only asks for missing tiles on a partial board', () => {
    expect(getBoardIssues(buildHexGrid())).toEqual(['19 tiles need terrain']);
  });
});
