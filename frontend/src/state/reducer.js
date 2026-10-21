/**
 * reducer.js — App state and the reducer that updates it.
 *
 * The reducer is a pure function: same state + action in, same state out.
 * Anything random (like Randomise) is computed by the caller and passed in
 * on the action, so React's StrictMode double-invocation can't produce two
 * different boards.
 */

import { buildHexGrid } from '../utils/hexGeometry';
import { DEFAULT_PORT_TYPES, swapPortType } from '../utils/ports';

export const PHASES = { BOARD_SETUP: 0, PLAYER_CONFIG: 1, SNAKE_DRAFT: 2, ANALYSIS: 3 };

/** Snake order, e.g. 3 players → [0, 1, 2, 2, 1, 0]. Matches build_snake_draft() in the backend. */
export function buildDraftOrder(numPlayers) {
  const fwd = Array.from({ length: numPlayers }, (_, i) => i);
  return [...fwd, ...[...fwd].reverse()];
}

export function makeInitialState() {
  return {
    phase:           PHASES.BOARD_SETUP,
    hexes:           buildHexGrid(),
    ports:           [...DEFAULT_PORT_TYPES], // port type per slot in PORT_SLOTS
    boardVersion:    0,  // bumps on Randomise so the board replays its drop-in animation
    numPlayers:      4,
    userPosition:    0,
    nSimulations:    5000,
    strategyWeight:  1.0,
    draftStep:       0,
    placements:      [],
    userS1:          null,
    userS2:          null,
    recommendations: [],
    isLoading:       false,
    analysis:        null,
    boardAnalysis:   null,
    error:           null,
  };
}

export function reducer(state, action) {
  switch (action.type) {
    case 'UPDATE_HEX':
      return {
        ...state,
        hexes: state.hexes.map((h) =>
          h.id === action.hexId ? { ...h, ...action.patch } : h
        ),
        boardAnalysis: null, // invalidate on board change
      };

    case 'SET_PORT_TYPE':
      return { ...state, ports: swapPortType(state.ports, action.slot, action.portType) };

    case 'CLEAR_BOARD':
      return { ...state, hexes: buildHexGrid(), ports: [...DEFAULT_PORT_TYPES], boardAnalysis: null };

    case 'RANDOMISE_BOARD':
      // action.patches / action.ports come from randomiseBoard() / shufflePorts()
      return {
        ...state,
        hexes: state.hexes.map((h, i) => ({ ...h, ...action.patches[i] })),
        ports: action.ports,
        boardVersion: state.boardVersion + 1,
        boardAnalysis: null,
      };

    case 'SET_NUM_PLAYERS': {
      const n   = action.n;
      const pos = Math.min(state.userPosition, n - 1);
      return { ...state, numPlayers: n, userPosition: pos };
    }

    case 'SET_USER_POSITION':
      return { ...state, userPosition: action.position };

    // Changing either setting invalidates the current recommendations; the
    // app refetches them automatically if it's the user's turn
    case 'SET_N_SIMS':
      return { ...state, nSimulations: action.n, recommendations: [] };

    case 'SET_STRATEGY_WEIGHT':
      return { ...state, strategyWeight: action.w, recommendations: [] };

    case 'SET_PHASE':
      return { ...state, phase: action.phase };

    case 'FETCH_START':
      return { ...state, isLoading: true, error: null };

    case 'SET_RECOMMENDATIONS':
      return { ...state, recommendations: action.data, isLoading: false, error: null };

    case 'SET_BOARD_ANALYSIS':
      return { ...state, boardAnalysis: action.data };

    case 'PLACE_SETTLEMENT': {
      const isUserTurn = action.player === state.userPosition;
      const isS1Step   = state.draftStep < state.numPlayers;
      const nextStep   = state.draftStep + 1;
      return {
        ...state,
        placements:      [...state.placements, { intersection_id: action.intersectionId, player: action.player }],
        draftStep:       nextStep,
        userS1:          isUserTurn && isS1Step  ? action.intersectionId : state.userS1,
        userS2:          isUserTurn && !isS1Step ? action.intersectionId : state.userS2,
        recommendations: [],
        // Any in-flight fetch for the old step is cancelled. If that was the
        // last pick, the final analysis starts loading straight away.
        isLoading:       nextStep >= 2 * state.numPlayers,
        error:           null,
      };
    }

    case 'UNDO_PLACEMENT': {
      if (!state.placements.length) return state;
      const last       = state.placements[state.placements.length - 1];
      const prevStep   = state.draftStep - 1;
      const wasUser    = last.player === state.userPosition;
      const wasS1Step  = prevStep < state.numPlayers;
      return {
        ...state,
        placements:      state.placements.slice(0, -1),
        draftStep:       prevStep,
        userS1:          (wasUser && wasS1Step) ? null : state.userS1,
        userS2:          (wasUser && !wasS1Step) ? null : state.userS2,
        recommendations: [],
        isLoading:       false,
        error:           null,
      };
    }

    case 'SET_ANALYSIS':
      return { ...state, analysis: action.data, phase: PHASES.ANALYSIS, isLoading: false };

    case 'SET_ERROR':
      return { ...state, error: action.msg, isLoading: false };

    case 'RESET':
      return makeInitialState();

    default:
      return state;
  }
}
