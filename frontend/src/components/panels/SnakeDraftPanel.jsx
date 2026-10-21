/**
 * SnakeDraftPanel.jsx — Step 3: the snake draft.
 *
 * On the user's turn: the ranked recommendations. On anyone else's turn: a
 * note asking where they built. Settings sit below so they're at hand but
 * don't compete with the recommendations.
 */

import { buildDraftOrder } from '../../state/reducer';
import { PLAYER_COLORS, PLAYER_NAMES } from '../../utils/constants';
import { StrategySlider, SimCountControl } from '../SettingsControls';
import RecommendationList from '../RecommendationList';

function ErrorNotice({ message, onRetry }) {
  return (
    <div className="notice-error" role="alert">
      {message}
      <button className="btn btn-secondary btn-block" onClick={onRetry}>Try again</button>
    </div>
  );
}

export default function SnakeDraftPanel({ state, dispatch, onRetry, onUndo, highlightedId, setHighlightedId }) {
  const { draftStep, numPlayers, userPosition, recommendations, isLoading, error, nSimulations, strategyWeight } = state;
  const draftOrder = buildDraftOrder(numPlayers);

  if (draftStep >= draftOrder.length) {
    return (
      <div>
        <h1 className="panel-title">Draft complete</h1>
        {error
          ? <ErrorNotice message={error} onRetry={onRetry} />
          : <div className="loading-line"><span className="spinner" /> Scoring your settlements…</div>}
      </div>
    );
  }

  const currentPlayer = draftOrder[draftStep];
  const isUserTurn    = currentPlayer === userPosition;
  const settlementNum = draftStep < numPlayers ? 1 : 2;

  return (
    <div>
      <h1 className="panel-title">
        {isUserTurn ? `Your turn: settlement ${settlementNum}` : `${PLAYER_NAMES[currentPlayer]} places settlement ${settlementNum}`}
      </h1>
      <p className="panel-intro">
        {isUserTurn
          ? 'Pick a numbered spot on the board, or any open spot if you prefer your own.'
          : `Click the spot on the board where ${PLAYER_NAMES[currentPlayer]} built.`}
      </p>

      {!isUserTurn && (
        <div className="turn-note">
          <span className="player-dot" style={{ background: PLAYER_COLORS[currentPlayer] }} />
          <div>
            <div className="turn-note-title">Pick {draftStep + 1} of {draftOrder.length}</div>
            <div className="turn-note-body">Open spots are shown as white dots. Faint dots are too close to another settlement.</div>
          </div>
        </div>
      )}

      {isUserTurn && (
        <section className="section" aria-live="polite" aria-busy={isLoading}>
          {isLoading && (
            <div className="loading-line">
              <span className="spinner" />
              Running {nSimulations.toLocaleString()} simulations…
            </div>
          )}
          {error && !isLoading && <ErrorNotice message={error} onRetry={onRetry} />}
          {!isLoading && recommendations.length > 0 && (
            <>
              <span className="field-label">Best open spots</span>
              <RecommendationList
                key={recommendations.map((r) => r.intersection_id).join('-')}
                recommendations={recommendations}
                onHighlight={setHighlightedId}
                highlightedId={highlightedId}
              />
            </>
          )}
        </section>
      )}

      {state.placements.length > 0 && (
        <section className="section">
          <button className="btn btn-quiet" onClick={onUndo}>Undo last placement</button>
        </section>
      )}

      <section className="section">
        <StrategySlider value={strategyWeight} onChange={(w) => dispatch({ type: 'SET_STRATEGY_WEIGHT', w })} />
      </section>
      <section className="section">
        <SimCountControl value={nSimulations} onChange={(n) => dispatch({ type: 'SET_N_SIMS', n })} />
      </section>
    </div>
  );
}
