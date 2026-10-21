/**
 * SnakeDraftPanel.jsx — Side panel for phase 3: the snake draft.
 */

import { buildDraftOrder } from '../../state/reducer';
import { PLAYER_COLORS } from '../../utils/constants';
import { StrategySlider, SimCountControl } from '../SettingsControls';
import ExplanationPanel from '../ExplanationPanel';
import ScarcityPanel from './ScarcityPanel';

export default function SnakeDraftPanel({ state, dispatch, onRetry, onUndo, highlightedId, setHighlightedId }) {
  const { draftStep, numPlayers, userPosition, recommendations, isLoading, error, boardAnalysis, nSimulations, strategyWeight } = state;
  const draftOrder = buildDraftOrder(numPlayers);
  const finished   = draftStep >= draftOrder.length;

  if (finished) {
    return (
      <div>
        <div className="section-heading">Draft Complete</div>
        {error ? (
          <div className="error-box">
            ⚠ {error}
            <button className="btn btn-ghost btn-sm" style={{ marginTop: 6, width: '100%' }} onClick={onRetry}>
              Retry
            </button>
          </div>
        ) : (
          <>
            <div className="section-sub">Fetching your analysis…</div>
            {isLoading && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-secondary)', fontSize: 13 }}>
                <div className="spinner" /> Running analysis…
              </div>
            )}
          </>
        )}
      </div>
    );
  }

  const currentPlayer = draftOrder[draftStep];
  const isUserTurn    = currentPlayer === userPosition;
  const settleNum     = draftStep < numPlayers ? 1 : 2;
  const playerColor   = PLAYER_COLORS[currentPlayer];

  return (
    <>
      <div className="optimizer-card" style={{ marginBottom: 12 }}>
        <div className="optimizer-title">Settlement Optimizer</div>

        <ScarcityPanel boardAnalysis={boardAnalysis} title="Resource scarcity analysis" />

        <div style={{ marginTop: 16 }}>
          <div className="label-xs" style={{ marginBottom: 12 }}>Strategy</div>
          <StrategySlider value={strategyWeight} onChange={(w) => dispatch({ type: 'SET_STRATEGY_WEIGHT', w })} />
        </div>

        <SimCountControl
          value={nSimulations}
          onChange={(n) => dispatch({ type: 'SET_N_SIMS', n })}
          style={{ marginTop: 24 }}
        />
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
        <div className="turn-banner">
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
          <button className="btn btn-ghost btn-sm" style={{ marginTop: 6, width: '100%' }} onClick={onRetry}>
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
            onSelectNode={setHighlightedId}
            highlightedId={highlightedId}
          />
        </div>
      )}
    </>
  );
}
