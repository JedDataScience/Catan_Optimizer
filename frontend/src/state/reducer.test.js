import { describe, expect, it } from 'vitest';
import { PHASES, makeInitialState, reducer } from './reducer';
import { DEFAULT_PORT_TYPES } from '../utils/ports';

function draftState(overrides = {}) {
  return { ...makeInitialState(), phase: PHASES.SNAKE_DRAFT, numPlayers: 2, userPosition: 0, ...overrides };
}

function place(state, intersectionId, player) {
  return reducer(state, { type: 'PLACE_SETTLEMENT', intersectionId, player });
}

describe('placements and undo', () => {
  // 2 players, snake order [0, 1, 1, 0]: the user (player 0) picks at steps 0 and 3
  it("records the user's S1 and S2 from the draft step", () => {
    let s = draftState();
    s = place(s, 10, 0);
    s = place(s, 30, 1);
    s = place(s, 40, 1);
    s = place(s, 50, 0);
    expect(s.userS1).toBe(10);
    expect(s.userS2).toBe(50);
    expect(s.draftStep).toBe(4);
    expect(s.isLoading).toBe(true); // last pick: the final analysis starts loading
  });

  it('undo clears only the settlement it removes', () => {
    let s = draftState();
    for (const [id, player] of [[10, 0], [30, 1], [40, 1], [50, 0]]) s = place(s, id, player);

    s = reducer(s, { type: 'UNDO_PLACEMENT' });
    expect(s.userS2).toBe(null);
    expect(s.userS1).toBe(10);

    s = reducer(s, { type: 'UNDO_PLACEMENT' });
    s = reducer(s, { type: 'UNDO_PLACEMENT' });
    s = reducer(s, { type: 'UNDO_PLACEMENT' });
    expect(s.userS1).toBe(null);
    expect(s.draftStep).toBe(0);
    expect(s.placements).toEqual([]);
  });

  it('undo with nothing placed is a no-op', () => {
    const s = draftState();
    expect(reducer(s, { type: 'UNDO_PLACEMENT' })).toBe(s);
  });
});

describe('ports and board actions', () => {
  it('SET_PORT_TYPE swaps types between slots', () => {
    const s = reducer(makeInitialState(), { type: 'SET_PORT_TYPE', slot: 0, portType: 'mountains' });
    expect(s.ports[0]).toBe('mountains');
    expect(s.ports[DEFAULT_PORT_TYPES.indexOf('mountains')]).toBe(DEFAULT_PORT_TYPES[0]);
  });

  it('RANDOMISE_BOARD uses exactly what the action carries (reducer stays pure)', () => {
    const patches = Array.from({ length: 19 }, () => ({ resource: 'forest', number: 5 }));
    const ports = [...DEFAULT_PORT_TYPES].reverse();
    const action = { type: 'RANDOMISE_BOARD', patches, ports };
    const a = reducer(makeInitialState(), action);
    const b = reducer(makeInitialState(), action);
    expect(a.hexes).toEqual(b.hexes);
    expect(a.ports).toEqual(ports);
  });

  it('CLEAR_BOARD resets ports to the defaults', () => {
    let s = reducer(makeInitialState(), { type: 'SET_PORT_TYPE', slot: 0, portType: 'mountains' });
    s = reducer(s, { type: 'CLEAR_BOARD' });
    expect(s.ports).toEqual(DEFAULT_PORT_TYPES);
  });
});

describe('settings', () => {
  it('changing strategy or sim count clears stale recommendations', () => {
    const s = { ...makeInitialState(), recommendations: [{ rank: 1 }] };
    expect(reducer(s, { type: 'SET_STRATEGY_WEIGHT', w: 0.5 }).recommendations).toEqual([]);
    expect(reducer(s, { type: 'SET_N_SIMS', n: 1000 }).recommendations).toEqual([]);
  });
});
