/**
 * App.jsx — Catan Settlement Optimizer (v2)
 *
 * New features:
 *   - strategy_weight slider (0 = raw production, 1 = win-path)
 *   - auto-fetch recommendations on user's turn
 *   - undo last placement
 *   - segmented simulation count control
 *   - board scarcity analysis panel (fetched after board is complete)
 *   - board toolbar moved into side panel
 */

import { useReducer, useCallback, useEffect, useRef, useState } from 'react';
import BoardSetup from './components/BoardSetup';
import ResultsOverlay from './components/ResultsOverlay';
import ExplanationPanel from './components/ExplanationPanel';
import AnalysisPanel from './components/AnalysisPanel';
import { buildHexGrid } from './utils/hexGeometry';
import { INTERSECTIONS, getExclusionZone } from './utils/intersectionMap';
import { randomiseBoard } from './utils/boardRandomizer';
import { RESOURCE_MAP, ALL_RESOURCES, SCARCITY_COLORS } from './utils/constants';

// ── Constants ─────────────────────────────────────────────────────────────────

const PHASES   = { BOARD_SETUP: 0, PLAYER_CONFIG: 1, SNAKE_DRAFT: 2, ANALYSIS: 3 };
const API_BASE = 'http://localhost:8000';
const PLAYER_COLORS = ['#f59e0b', '#ef4444', '#22c55e', '#6366f1'];
const PLAYER_LABELS = ['1st', '2nd', '3rd', '4th'];

const SIM_OPTIONS = [500, 1000, 2000, 5000, 10000];
const SIM_LABELS  = ['500', '1k', '2k', '5k', '10k'];

function buildDraftOrder(numPlayers) {
  const fwd = Array.from({ length: numPlayers }, (_, i) => i);
  return [...fwd, ...[...fwd].reverse()];
}

// ── Initial state ─────────────────────────────────────────────────────────────

function makeInitialState() {
  return {
    phase:           PHASES.BOARD_SETUP,
    hexes:           buildHexGrid(),
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

// ── Reducer ───────────────────────────────────────────────────────────────────

function reducer(state, action) {
  switch (action.type) {
    case 'UPDATE_HEX':
      return {
        ...state,
        hexes: state.hexes.map((h) =>
          h.id === action.hexId ? { ...h, ...action.patch } : h
        ),
        boardAnalysis: null, // invalidate on board change
      };

    case 'CLEAR_BOARD':
      return { ...state, hexes: buildHexGrid(), boardAnalysis: null };

    case 'RANDOMISE_BOARD': {
      const patches = randomiseBoard();
      return {
        ...state,
        hexes: state.hexes.map((h, i) => ({ ...h, ...patches[i] })),
        boardAnalysis: null,
      };
    }

    case 'SET_NUM_PLAYERS': {
      const n   = action.n;
      const pos = Math.min(state.userPosition, n - 1);
      return { ...state, numPlayers: n, userPosition: pos };
    }

    case 'SET_USER_POSITION':
      return { ...state, userPosition: action.position };

    case 'SET_N_SIMS':
      return { ...state, nSimulations: action.n };

    case 'SET_STRATEGY_WEIGHT':
      return { ...state, strategyWeight: action.w, recommendations: [] };

    case 'SET_PHASE':
      return { ...state, phase: action.phase };

    case 'SET_LOADING':
      return { ...state, isLoading: action.loading };

    case 'SET_RECOMMENDATIONS':
      return { ...state, recommendations: action.data, isLoading: false, error: null };

    case 'SET_BOARD_ANALYSIS':
      return { ...state, boardAnalysis: action.data };

    case 'PLACE_SETTLEMENT': {
      const newPlacements = [
        ...state.placements,
        { intersection_id: action.intersectionId, player: action.player },
      ];
      return {
        ...state,
        placements:      newPlacements,
        draftStep:       state.draftStep + 1,
        userS1:          action.isUserS1 ? action.intersectionId : state.userS1,
        userS2:          action.isUserS2 ? action.intersectionId : state.userS2,
        recommendations: [],
        error:           null,
      };
    }

    case 'UNDO_PLACEMENT': {
      if (!state.placements.length) return state;
      const last         = state.placements[state.placements.length - 1];
      const newPlacements = state.placements.slice(0, -1);
      const prevStep      = state.draftStep - 1;
      const draftOrder    = buildDraftOrder(state.numPlayers);
      const wasUser       = last.player === state.userPosition;
      const wasS1Phase    = (state.draftStep - 1) < state.numPlayers;
      return {
        ...state,
        placements:      newPlacements,
        draftStep:       prevStep,
        userS1:          (wasUser && wasS1Phase) ? null : state.userS1,
        userS2:          (wasUser && !wasS1Phase) ? null : state.userS2,
        recommendations: [],
        error:           null,
      };
    }

    case 'SET_ANALYSIS':
      return { ...state, analysis: action.data, phase: PHASES.ANALYSIS, isLoading: false };

    case 'SET_ERROR':
      return { ...state, error: action.msg, isLoading: false };

    case 'CLEAR_ERROR':
      return { ...state, error: null };

    case 'RESET':
      return makeInitialState();

    default:
      return state;
  }
}

// ── API helpers ───────────────────────────────────────────────────────────────

async function fetchRecommendations(state, dispatch) {
  dispatch({ type: 'SET_LOADING', loading: true });
  dispatch({ type: 'CLEAR_ERROR' });
  try {
    const resp = await fetch(`${API_BASE}/recommend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        board:              state.hexes.map((h) => ({ id: h.id, resource: h.resource, number: h.number })),
        placed_settlements: state.placements,
        user_position:      state.userPosition,
        num_players:        state.numPlayers,
        draft_step:         state.draftStep,
        s1_id:              state.userS1,
        n_simulations:      state.nSimulations,
        strategy_weight:    state.strategyWeight,
      }),
    });
    if (!resp.ok) throw new Error(`Server error ${resp.status}`);
    const data = await resp.json();
    dispatch({ type: 'SET_RECOMMENDATIONS', data: data.rankings });
  } catch (e) {
    dispatch({ type: 'SET_ERROR', msg: e.message });
  }
}

async function fetchBoardAnalysis(state, dispatch) {
  try {
    const resp = await fetch(`${API_BASE}/board-analysis`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        board: state.hexes.map((h) => ({ id: h.id, resource: h.resource, number: h.number })),
      }),
    });
    if (!resp.ok) return;
    const data = await resp.json();
    dispatch({ type: 'SET_BOARD_ANALYSIS', data });
  } catch (_) {}
}

async function fetchAnalysis(state, dispatch) {
  dispatch({ type: 'SET_LOADING', loading: true });
  try {
    const resp = await fetch(`${API_BASE}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        board:           state.hexes.map((h) => ({ id: h.id, resource: h.resource, number: h.number })),
        s1_id:           state.userS1,
        s2_id:           state.userS2,
        all_placements:  state.placements,
        strategy_weight: state.strategyWeight,
      }),
    });
    if (!resp.ok) throw new Error(`Server error ${resp.status}`);
    const data = await resp.json();
    dispatch({ type: 'SET_ANALYSIS', data });
  } catch (e) {
    dispatch({ type: 'SET_ERROR', msg: e.message });
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function isBoardValid(hexes) {
  return hexes.every((h) => h.resource && (h.resource === 'desert' || h.number != null));
}

function getBoardIssues(hexes) {
  const issues = [];
  const noResource = hexes.filter((h) => !h.resource).length;
  const noNumber   = hexes.filter((h) => h.resource && h.resource !== 'desert' && !h.number).length;
  if (noResource > 0) issues.push(`${noResource} hex${noResource > 1 ? 'es' : ''} need a resource type`);
  if (noNumber   > 0) issues.push(`${noNumber} hex${noNumber > 1 ? 'es' : ''} need a number token`);
  return issues;
}

function currentExclusionZone(placements) {
  return getExclusionZone(placements.map((p) => p.intersection_id));
}

const STEP_LABELS = ['Board Setup', 'Game Setup', 'Draft', 'Analysis'];

// ── Progress Bar ──────────────────────────────────────────────────────────────

function ProgressBar({ phase }) {
  return (
    <div className="progress-bar">
      {STEP_LABELS.map((label, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center' }}>
          {i > 0 && <div className="progress-separator" />}
          <div className={`progress-step ${i === phase ? 'active' : ''} ${i < phase ? 'done' : ''}`}>
            <div className="progress-step-num">{i < phase ? '✓' : i + 1}</div>
            {label}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Scarcity Panel ────────────────────────────────────────────────────────────

function ScarcityPanel({ boardAnalysis, hideTitle }) {
  if (!boardAnalysis) return null;
  const { scarcity, label, pip_by_resource } = boardAnalysis;

  return (
    <div style={{ marginBottom: 12 }}>
      {!hideTitle && <div className="label-xs" style={{ marginBottom: 8 }}>Board Resource Scarcity</div>}
      {hideTitle && <div className="label-xs" style={{ marginBottom: 12 }}>Resource scarcity analysis</div>}
      <div className="scarcity-grid">
        {ALL_RESOURCES.map((res) => {
          const info   = RESOURCE_MAP[res];
          const lvl    = label[res] || 'moderate';
          const colors = SCARCITY_COLORS[lvl] || SCARCITY_COLORS.moderate;
          const pct    = Math.round((scarcity[res] || 0) * 100);
          return (
            <div key={res} style={{ display: 'flex', flexDirection: 'column', width: '48px', alignItems: 'center' }}>
              <div
                className="scarcity-pill"
                style={{ background: 'var(--bg-subtle)', color: 'var(--text-primary)', borderColor: 'transparent', flexDirection: 'column', alignItems: 'center', padding: '4px 6px', gap: '2px', width: '100%' }}
                title={`${info?.label}: ${lvl} (${pip_by_resource[res] || 0} pips)`}
              >
                <span style={{ fontSize: 11, fontWeight: 700 }}>{info?.label}</span>
                <span style={{ fontWeight: 500, fontSize: 9, color: 'var(--text-secondary)' }}>{lvl}</span>
              </div>
              <div className="scarcity-bar-wrap" style={{ height: '3px', width: '36px', marginTop: '4px', background: 'var(--border)' }}>
                <div className="scarcity-bar" style={{ width: `${Math.min(100, Math.max(10, pct))}%`, background: colors.text, borderRadius: '2px' }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Board Setup Panel ─────────────────────────────────────────────────────────

function BoardSetupPanel({ state, dispatch, onClearBoard, onRandomise }) {
  const valid  = isBoardValid(state.hexes);
  const filled = state.hexes.filter((h) => h.resource).length;
  const issues = getBoardIssues(state.hexes);

  function handleContinue() {
    fetchBoardAnalysis(state, dispatch);
    dispatch({ type: 'SET_PHASE', phase: PHASES.PLAYER_CONFIG });
  }

  return (
    <div>
      <div className="section-heading">Configure the Board</div>
      <div className="section-sub">
        Click each hex to assign a resource and number token.
        All 19 hexes must be filled before continuing.
      </div>

      {/* Board actions */}
      <div style={{ display: 'flex', gap: 7, marginBottom: 14 }}>
        <button className="btn btn-ghost btn-sm" style={{ flex: 1 }} onClick={onClearBoard}>
          Clear Board
        </button>
        <button className="btn btn-primary btn-sm" style={{ flex: 1 }} onClick={onRandomise}>
          🎲 Randomise
        </button>
      </div>

      {/* Hex progress */}
      <div className="card" style={{ padding: '10px 14px', marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 500 }}>Hexes configured</span>
          <span style={{
            fontSize: 13, fontWeight: 800,
            color: filled === 19 ? 'var(--green)' : 'var(--accent)',
          }}>
            {filled} / 19
          </span>
        </div>
        <div style={{ background: 'var(--border)', borderRadius: 4, height: 4, overflow: 'hidden' }}>
          <div style={{
            height: 4, borderRadius: 4,
            width: `${(filled / 19) * 100}%`,
            background: filled === 19 ? 'var(--green)' : 'var(--accent)',
            transition: 'width 0.3s ease',
          }} />
        </div>
      </div>

      {/* Validation warnings */}
      {!valid && filled > 0 && issues.length > 0 && (
        <div style={{
          background: '#fffbeb', border: '1px solid #fde68a',
          borderRadius: 'var(--radius-md)', padding: '8px 12px', marginBottom: 12,
        }}>
          {issues.map((issue, i) => (
            <div key={i} style={{ fontSize: 12, color: '#92400e', fontWeight: 500 }}>⚠ {issue}</div>
          ))}
        </div>
      )}

      <button
        className="btn btn-primary btn-lg"
        style={{ width: '100%' }}
        disabled={!valid}
        onClick={handleContinue}
      >
        Continue →
      </button>
    </div>
  );
}

// ── Player Config Panel ───────────────────────────────────────────────────────

function PlayerConfigPanel({ state, dispatch }) {
  const draftOrder = buildDraftOrder(state.numPlayers);
  const sw         = state.strategyWeight;

  return (
    <div>
      <div className="section-heading">Game Setup</div>
      <div className="section-sub">
        Configure players, turn order, and how the optimizer weights its recommendations.
      </div>

      {/* Board scarcity (fetched when entering player config) */}
      <ScarcityPanel boardAnalysis={state.boardAnalysis} />

      {/* Number of players */}
      <div style={{ marginBottom: 14 }}>
        <div className="label-xs" style={{ marginBottom: 7 }}>Number of Players</div>
        <div style={{ display: 'flex', gap: 7 }}>
          {[2, 3, 4].map((n) => (
            <button
              key={n}
              className={`position-btn ${state.numPlayers === n ? 'active' : ''}`}
              style={{ flex: 1 }}
              onClick={() => dispatch({ type: 'SET_NUM_PLAYERS', n })}
            >
              <span className="position-btn-num">{n}</span>
              players
            </button>
          ))}
        </div>
      </div>

      {/* Turn position */}
      <div style={{ marginBottom: 14 }}>
        <div className="label-xs" style={{ marginBottom: 7 }}>Your Turn Position</div>
        <div className="position-grid">
          {Array.from({ length: state.numPlayers }, (_, pos) => (
            <button
              key={pos}
              className={`position-btn ${state.userPosition === pos ? 'active' : ''}`}
              onClick={() => dispatch({ type: 'SET_USER_POSITION', position: pos })}
            >
              <span className="position-btn-num" style={{ color: PLAYER_COLORS[pos] }}>{pos + 1}</span>
              {PLAYER_LABELS[pos]}
            </button>
          ))}
        </div>
      </div>

      {/* Simulations segmented control */}
      <div style={{ marginBottom: 14 }}>
        <div className="label-xs" style={{ marginBottom: 7 }}>Simulations</div>
        <div className="seg-control">
          {SIM_OPTIONS.map((n, i) => (
            <button
              key={n}
              className={`seg-btn ${state.nSimulations === n ? 'active' : ''}`}
              onClick={() => dispatch({ type: 'SET_N_SIMS', n })}
            >
              {SIM_LABELS[i]}
            </button>
          ))}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>
          More = better accuracy, slower. 5k recommended.
        </div>
      </div>

      {/* Strategy weight */}
      <div style={{ marginBottom: 16 }}>
        <div className="label-xs" style={{ marginBottom: 7 }}>Optimization Strategy</div>
        <div className="strategy-slider-wrap">
          <div className="strategy-track">
            <span>Raw Production</span>
            <span>Win-Path</span>
          </div>
          <input
            type="range"
            className="strategy-slider"
            min={0} max={1} step={0.1}
            value={sw}
            style={{ '--val': sw * 100 }}
            onChange={(e) => dispatch({ type: 'SET_STRATEGY_WEIGHT', w: parseFloat(e.target.value) })}
          />
          <div style={{ textAlign: 'center', fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
            {sw <= 0.1 ? 'Pure pip maximization'
              : sw >= 0.9 ? 'Win-path: Ore/Wheat prioritized, synergy bonuses active'
              : `Blend: ${Math.round(sw * 100)}% strategic weighting`}
          </div>
        </div>
      </div>

      {/* Draft preview */}
      <div className="card" style={{ padding: '10px 14px', marginBottom: 14 }}>
        <div className="label-xs" style={{ marginBottom: 7 }}>Draft Order Preview</div>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
          {draftOrder.map((player, step) => {
            const isUser   = player === state.userPosition;
            const isPhase2 = step >= state.numPlayers;
            return (
              <>
                {step === state.numPlayers && (
                  <div
                    key="sep"
                    style={{ width: 1, height: 24, background: 'var(--border-med)', margin: '0 3px' }}
                  />
                )}
                <div
                  key={step}
                  style={{
                    width: 26, height: 26, borderRadius: '50%',
                    background: isUser ? PLAYER_COLORS[state.userPosition] + '22' : 'var(--bg-hover)',
                    border: `2px solid ${isUser ? PLAYER_COLORS[state.userPosition] : 'var(--border-med)'}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 9, fontWeight: 700,
                    color: isUser ? PLAYER_COLORS[state.userPosition] : 'var(--text-muted)',
                  }}
                  title={`Step ${step + 1}: P${player + 1} — Settlement ${isPhase2 ? 2 : 1}`}
                >
                  {player + 1}
                </div>
              </>
            );
          })}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 7 }}>
          Highlighted = your picks. Left of divider = S1, right = S2.
        </div>
      </div>

      <div style={{ display: 'flex', gap: 7 }}>
        <button className="btn btn-ghost" onClick={() => dispatch({ type: 'SET_PHASE', phase: PHASES.BOARD_SETUP })}>
          ← Back
        </button>
        <button
          className="btn btn-primary"
          style={{ flex: 1 }}
          onClick={() => dispatch({ type: 'SET_PHASE', phase: PHASES.SNAKE_DRAFT })}
        >
          Start Draft →
        </button>
      </div>
    </div>
  );
}

// ── Snake Draft Panel ─────────────────────────────────────────────────────────

function SnakeDraftPanel({ state, dispatch, onFetchRec, onUndo, highlightedId, setHighlightedId }) {
  const { draftStep, numPlayers, userPosition, recommendations, isLoading, error, boardAnalysis, nSimulations, strategyWeight } = state;
  const draftOrder = buildDraftOrder(numPlayers);
  const totalSteps = draftOrder.length;
  const finished   = draftStep >= totalSteps;
  const sw = strategyWeight;

  if (finished) {
    return (
      <div>
        <div className="section-heading">Draft Complete</div>
        <div className="section-sub">Fetching your analysis…</div>
        {isLoading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-secondary)', fontSize: 13 }}>
            <div className="spinner" /> Running analysis…
          </div>
        )}
      </div>
    );
  }

  const currentPlayer = draftOrder[draftStep];
  const isUserTurn    = currentPlayer === userPosition;
  const isS1Phase     = draftStep < numPlayers;
  const settleNum     = isS1Phase ? 1 : 2;
  const playerColor   = PLAYER_COLORS[currentPlayer];

  return (
    <>
      <div className="optimizer-card" style={{ marginBottom: 12 }}>
        <div className="optimizer-title">Settlement Optimizer</div>
        
        <ScarcityPanel boardAnalysis={boardAnalysis} hideTitle />
        
        <div style={{ marginTop: 16 }}>
          <div className="label-xs" style={{ marginBottom: 12 }}>Strategy</div>
          <div className="strategy-slider-wrap">
            <div className="strategy-track">
              <span>Raw Production</span>
              <span>Win Path</span>
            </div>
            <input
              type="range"
              className="strategy-slider"
              min={0} max={1} step={0.1}
              value={sw}
              style={{ '--val': sw * 100 }}
              onChange={(e) => dispatch({ type: 'SET_STRATEGY_WEIGHT', w: parseFloat(e.target.value) })}
            />
          </div>
        </div>

        <div className="seg-control" style={{ marginTop: 24 }}>
          {SIM_OPTIONS.map((n, i) => (
            <button
              key={n}
              className={`seg-btn ${nSimulations === n ? 'active' : ''}`}
              onClick={() => dispatch({ type: 'SET_N_SIMS', n })}
            >
              {SIM_LABELS[i]}
            </button>
          ))}
        </div>
      </div>

      {/* Undo */}
      {state.placements.length > 0 && (
        <button
          className="btn btn-ghost btn-sm"
          style={{ marginBottom: 10, width: '100%' }}
          onClick={onUndo}
        >
          ↩ Undo Last Placement
        </button>
      )}

      {/* Turn banner */}
      {!isUserTurn && (
        <div className={`turn-banner`}>
          <div className="turn-banner-title" style={{ color: playerColor }}>
            Player {currentPlayer + 1}'s Turn — Settlement {settleNum}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
            Click any valid intersection to set Player {currentPlayer + 1}'s placement.
          </div>
        </div>
      )}

      {/* Error */}
      {isUserTurn && error && !isLoading && (
        <div className="error-box">
          ⚠ {error}
          <button className="btn btn-ghost btn-sm" style={{ marginTop: 6, width: '100%' }} onClick={onFetchRec}>
            Retry
          </button>
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14, color: 'var(--text-secondary)', fontSize: 13, fontWeight: 500 }}>
          <div className="spinner" />
          Running {nSimulations.toLocaleString()} simulations…
        </div>
      )}

      {/* Recommendations */}
      {isUserTurn && recommendations.length > 0 && (
        <div className="recommendations-list">
          <ExplanationPanel
            recommendations={recommendations}
            onSelectNode={(id) => setHighlightedId(id)}
            highlightedId={highlightedId}
          />
        </div>
      )}
    </>
  );
}

// ── Main App ──────────────────────────────────────────────────────────────────

export default function App() {
  const [state, dispatch]                 = useReducer(reducer, makeInitialState());
  const [highlightedId, setHighlightedId] = useState(null);
  const autoFetchedForStep                = useRef(null);

  const {
    phase, hexes, numPlayers, draftStep, userPosition,
    placements, recommendations, isLoading, analysis,
  } = state;

  const draftOrder  = buildDraftOrder(numPlayers);
  const totalSteps  = draftOrder.length;
  const exclusionZone = currentExclusionZone(placements);
  const boardInteractive = phase === PHASES.BOARD_SETUP;

  // ── Auto-fetch recommendations when it becomes the user's turn ───────────
  useEffect(() => {
    if (phase !== PHASES.SNAKE_DRAFT) return;
    if (draftStep >= totalSteps) return;
    const currentPlayer = draftOrder[draftStep];
    if (currentPlayer !== userPosition) return;
    if (recommendations.length > 0) return;
    if (isLoading) return;
    if (autoFetchedForStep.current === draftStep) return;

    autoFetchedForStep.current = draftStep;
    fetchRecommendations(state, dispatch);
  }, [phase, draftStep, userPosition, isLoading, recommendations.length]);

  const handleFetchRec = useCallback(() => {
    autoFetchedForStep.current = draftStep;
    fetchRecommendations(state, dispatch);
  }, [state]);

  // Handle board intersection click during draft
  function handleNodeClick(intersectionId) {
    if (phase !== PHASES.SNAKE_DRAFT) return;
    if (draftStep >= totalSteps) return;
    if (exclusionZone.has(intersectionId)) return;

    const currentPlayer = draftOrder[draftStep];
    const isUserTurn    = currentPlayer === userPosition;
    const isUserS1      = isUserTurn && draftStep < numPlayers;
    const isUserS2      = isUserTurn && draftStep >= numPlayers;

    const newDraftStep  = draftStep + 1;
    const newPlacements = [...placements, { intersection_id: intersectionId, player: currentPlayer }];
    const newUserS1     = isUserS1 ? intersectionId : state.userS1;
    const newUserS2     = isUserS2 ? intersectionId : state.userS2;

    dispatch({ type: 'PLACE_SETTLEMENT', intersectionId, player: currentPlayer, isUserS1, isUserS2 });
    setHighlightedId(null);

    if (newDraftStep >= totalSteps) {
      const finalState = {
        ...state,
        placements:      newPlacements,
        userS1:          newUserS1,
        userS2:          newUserS2,
        draftStep:       newDraftStep,
        recommendations: [],
      };
      fetchAnalysis(finalState, dispatch);
    }
  }

  function handleUndo() {
    autoFetchedForStep.current = null;
    dispatch({ type: 'UNDO_PLACEMENT' });
    setHighlightedId(null);
  }

  // Overlay visibility
  const currentPlayer  = draftStep < totalSteps ? draftOrder[draftStep] : null;
  const showRecs       = phase === PHASES.SNAKE_DRAFT && recommendations.length > 0;
  const showAnyDots    = phase === PHASES.SNAKE_DRAFT && currentPlayer !== null && currentPlayer !== userPosition;
  const showUserDot    = phase === PHASES.SNAKE_DRAFT && currentPlayer === userPosition && !recommendations.length;
  const overlayClickable = phase === PHASES.SNAKE_DRAFT && draftStep < totalSteps;

  function renderSidePanel() {
    switch (phase) {
      case PHASES.BOARD_SETUP:
        return (
          <BoardSetupPanel
            state={state}
            dispatch={dispatch}
            onClearBoard={() => dispatch({ type: 'CLEAR_BOARD' })}
            onRandomise={() => dispatch({ type: 'RANDOMISE_BOARD' })}
          />
        );
      case PHASES.PLAYER_CONFIG:
        return <PlayerConfigPanel state={state} dispatch={dispatch} />;
      case PHASES.SNAKE_DRAFT:
        return (
          <SnakeDraftPanel
            state={state}
            dispatch={dispatch}
            onFetchRec={handleFetchRec}
            onUndo={handleUndo}
            highlightedId={highlightedId}
            setHighlightedId={setHighlightedId}
          />
        );
      case PHASES.ANALYSIS:
        return <AnalysisPanel analysis={analysis} onRestart={() => dispatch({ type: 'RESET' })} />;
      default:
        return null;
    }
  }

  return (
    <div className="app-shell">
      {/* Header */}
      <header className="app-header">
        <div className="app-logo">
          <svg className="app-logo-hex" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <polygon points="16,2 27,8.5 27,23.5 16,30 5,23.5 5,8.5" fill="none" stroke="#000" strokeWidth="2" />
            <polygon points="16,8 23,12 23,20 16,24 9,20 9,12" fill="#000" />
            <circle cx="16" cy="16" r="1.5" fill="#fff" />
          </svg>
          <div className="app-title">
            <span className="app-title-bold">CATAN</span><br/>
            <span className="app-title-light">OPTIMIZER</span>
          </div>
        </div>

        <nav className="top-nav">
          <button className="nav-link active">Dashboard</button>
          <button className="nav-link" onClick={() => dispatch({ type: 'RESET' })}>New Simulation</button>
          <button className="nav-link">My Games</button>
          <button className="nav-link">Analytics</button>
          <button className="nav-link">Help</button>
        </nav>
      </header>

      {/* Main */}
      <div className="main-layout">
        <div className="board-area">
          <BoardSetup
            hexes={hexes}
            onHexUpdate={(id, patch) => dispatch({ type: 'UPDATE_HEX', hexId: id, patch })}
            onClearBoard={() => dispatch({ type: 'CLEAR_BOARD' })}
            onRandomise={() => dispatch({ type: 'RANDOMISE_BOARD' })}
            interactive={boardInteractive}
          >
            {(phase === PHASES.SNAKE_DRAFT || phase === PHASES.ANALYSIS) && (
              <ResultsOverlay
                intersections={INTERSECTIONS}
                recommendations={showRecs ? recommendations : []}
                placements={placements}
                userPosition={userPosition}
                exclusionZone={exclusionZone}
                onNodeClick={overlayClickable ? handleNodeClick : undefined}
                highlightTop5={showRecs}
                allowAnyClick={showAnyDots || showUserDot}
              />
            )}
          </BoardSetup>
        </div>

        <aside className="side-panel">
          <div className="side-panel-inner">
            {renderSidePanel()}
          </div>
        </aside>
      </div>
    </div>
  );
}
