/**
 * App.jsx — Catan Settlement Optimizer (v3)
 *
 * Owns the app state (see state/reducer.js) and the calls to the backend;
 * the side panels and board components only render it.
 *
 * Fetching:
 *   - Recommendations load automatically on the user's turn, and reload
 *     (debounced) when the strategy or simulation count changes.
 *   - The final analysis loads as soon as the draft is complete.
 *   - Every request is cancelled when its inputs change, so a slow, outdated
 *     response can never overwrite a newer one.
 */

import { useEffect, useMemo, useReducer, useState } from 'react';
import BoardSetup from './components/BoardSetup';
import ResultsOverlay from './components/ResultsOverlay';
import AnalysisPanel from './components/AnalysisPanel';
import BoardSetupPanel from './components/panels/BoardSetupPanel';
import PlayerConfigPanel from './components/panels/PlayerConfigPanel';
import SnakeDraftPanel from './components/panels/SnakeDraftPanel';
import { INTERSECTIONS, getExclusionZone } from './utils/intersectionMap';
import { PHASES, buildDraftOrder, makeInitialState, reducer } from './state/reducer';
import { fetchAnalysis, fetchRecommendations } from './api/client';

// Wait this long after the last settings change before refetching
const REFETCH_DEBOUNCE_MS = 300;

export default function App() {
  const [state, dispatch]                 = useReducer(reducer, undefined, makeInitialState);
  const [highlightedId, setHighlightedId] = useState(null);
  const [retryToken, setRetryToken]       = useState(0);

  const {
    phase, hexes, ports, numPlayers, draftStep, userPosition, placements,
    userS1, userS2, nSimulations, strategyWeight, recommendations, analysis,
  } = state;

  const draftOrder    = buildDraftOrder(numPlayers);
  const totalSteps    = draftOrder.length;
  const inDraft       = phase === PHASES.SNAKE_DRAFT;
  const currentPlayer = draftStep < totalSteps ? draftOrder[draftStep] : null;
  const isUserTurn    = inDraft && currentPlayer === userPosition;
  const draftDone     = inDraft && draftStep >= totalSteps;

  const exclusionZone = useMemo(
    () => getExclusionZone(placements.map((p) => p.intersection_id)),
    [placements],
  );

  // Everything the API calls need, rebuilt only when one of these changes
  const request = useMemo(
    () => ({ hexes, ports, placements, userPosition, numPlayers, draftStep, userS1, userS2, nSimulations, strategyWeight }),
    [hexes, ports, placements, userPosition, numPlayers, draftStep, userS1, userS2, nSimulations, strategyWeight],
  );

  // ── Recommendations on the user's turn ───────────────────────────────────
  useEffect(() => {
    if (!isUserTurn) return undefined;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      dispatch({ type: 'FETCH_START' });
      fetchRecommendations(request, controller.signal)
        .then((data) => dispatch({ type: 'SET_RECOMMENDATIONS', data }))
        .catch((e) => {
          if (e.name !== 'AbortError') dispatch({ type: 'SET_ERROR', msg: e.message });
        });
    }, REFETCH_DEBOUNCE_MS);
    // Runs when the inputs change or the turn ends: drop the pending request
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [isUserTurn, request, retryToken]);

  // ── Final analysis once the draft is complete ────────────────────────────
  useEffect(() => {
    if (!draftDone) return undefined;
    const controller = new AbortController();
    fetchAnalysis(request, controller.signal)
      .then((data) => dispatch({ type: 'SET_ANALYSIS', data }))
      .catch((e) => {
        if (e.name !== 'AbortError') dispatch({ type: 'SET_ERROR', msg: e.message });
      });
    return () => controller.abort();
  }, [draftDone, request, retryToken]);

  function handleRetry() {
    dispatch({ type: 'FETCH_START' });
    setRetryToken((t) => t + 1);
  }

  // Board intersection click during the draft
  function handleNodeClick(intersectionId) {
    if (!inDraft || currentPlayer === null) return;
    if (exclusionZone.has(intersectionId)) return;
    dispatch({ type: 'PLACE_SETTLEMENT', intersectionId, player: currentPlayer });
    setHighlightedId(null);
  }

  function handleUndo() {
    dispatch({ type: 'UNDO_PLACEMENT' });
    setHighlightedId(null);
  }

  // Overlay visibility
  const showRecs         = inDraft && recommendations.length > 0;
  const showAnyDots      = inDraft && currentPlayer !== null && !isUserTurn;
  const showUserDot      = isUserTurn && !recommendations.length;
  const overlayClickable = inDraft && currentPlayer !== null;

  function renderSidePanel() {
    switch (phase) {
      case PHASES.BOARD_SETUP:
        return <BoardSetupPanel state={state} dispatch={dispatch} />;
      case PHASES.PLAYER_CONFIG:
        return <PlayerConfigPanel state={state} dispatch={dispatch} />;
      case PHASES.SNAKE_DRAFT:
        return (
          <SnakeDraftPanel
            state={state}
            dispatch={dispatch}
            onRetry={handleRetry}
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
          <span className="nav-link active" aria-current="page">Dashboard</span>
          <button className="nav-link" onClick={() => dispatch({ type: 'RESET' })}>New Simulation</button>
        </nav>
      </header>

      {/* Main */}
      <div className="main-layout">
        <div className="board-area">
          <BoardSetup
            hexes={hexes}
            ports={ports}
            onHexUpdate={(id, patch) => dispatch({ type: 'UPDATE_HEX', hexId: id, patch })}
            onPortChange={(slot, portType) => dispatch({ type: 'SET_PORT_TYPE', slot, portType })}
            interactive={phase === PHASES.BOARD_SETUP}
          >
            {(inDraft || phase === PHASES.ANALYSIS) && (
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
