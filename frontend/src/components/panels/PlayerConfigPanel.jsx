/**
 * PlayerConfigPanel.jsx — Step 2: players, turn order, and settings.
 */

import { Fragment } from 'react';
import { PHASES, buildDraftOrder } from '../../state/reducer';
import { PLAYER_COLORS, PLAYER_LABELS, PLAYER_NAMES } from '../../utils/constants';
import { StrategySlider, SimCountControl } from '../SettingsControls';
import ScarcityPanel from './ScarcityPanel';

export default function PlayerConfigPanel({ state, dispatch }) {
  const draftOrder = buildDraftOrder(state.numPlayers);

  return (
    <div>
      <h1 className="panel-title">Players and turn order</h1>
      <p className="panel-intro">
        Recommendations are for you. Choose how many people are playing and
        when you place your first settlement.
      </p>

      {state.boardAnalysis && (
        <section className="section">
          <ScarcityPanel boardAnalysis={state.boardAnalysis} />
        </section>
      )}

      <section className="section">
        <span className="field-label" id="players-label">Players</span>
        <div className="choice-grid" role="radiogroup" aria-labelledby="players-label" style={{ '--cols': 3 }}>
          {[2, 3, 4].map((n) => (
            <button
              key={n}
              type="button"
              role="radio"
              aria-checked={state.numPlayers === n}
              className={`choice${state.numPlayers === n ? ' is-active' : ''}`}
              onClick={() => dispatch({ type: 'SET_NUM_PLAYERS', n })}
            >
              <span className="choice-big num">{n}</span>
              players
            </button>
          ))}
        </div>
      </section>

      <section className="section">
        <span className="field-label" id="turn-label">You place</span>
        <div className="choice-grid" role="radiogroup" aria-labelledby="turn-label" style={{ '--cols': state.numPlayers }}>
          {Array.from({ length: state.numPlayers }, (_, pos) => (
            <button
              key={pos}
              type="button"
              role="radio"
              aria-checked={state.userPosition === pos}
              className={`choice${state.userPosition === pos ? ' is-active' : ''}`}
              onClick={() => dispatch({ type: 'SET_USER_POSITION', position: pos })}
            >
              <span className="choice-big">{PLAYER_LABELS[pos]}</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <span className="player-dot" style={{ background: PLAYER_COLORS[pos] }} />
                {PLAYER_NAMES[pos]}
              </span>
            </button>
          ))}
        </div>

        <span className="field-label" style={{ marginTop: 14 }}>Draft order</span>
        <div className="draft-order" aria-label="Snake draft order">
          {draftOrder.map((player, step) => (
            <Fragment key={step}>
              {step === state.numPlayers && <span className="draft-divider" aria-hidden="true" />}
              <span
                className={`draft-pip${player === state.userPosition ? ' is-user' : ''}`}
                title={`Pick ${step + 1}: ${PLAYER_NAMES[player]}, settlement ${step < state.numPlayers ? 1 : 2}`}
              >
                {player + 1}
              </span>
            </Fragment>
          ))}
        </div>
        <p className="hint">Your picks are highlighted. First settlements are left of the line, second settlements right.</p>
      </section>

      <section className="section">
        <StrategySlider
          value={state.strategyWeight}
          onChange={(w) => dispatch({ type: 'SET_STRATEGY_WEIGHT', w })}
          showCaption
        />
      </section>

      <section className="section">
        <SimCountControl value={state.nSimulations} onChange={(n) => dispatch({ type: 'SET_N_SIMS', n })} showHint />
      </section>

      <section className="section">
        <div className="btn-row">
          <button className="btn btn-secondary" style={{ flex: '0 0 auto' }} onClick={() => dispatch({ type: 'SET_PHASE', phase: PHASES.BOARD_SETUP })}>
            Back
          </button>
          <button className="btn btn-primary btn-lg" onClick={() => dispatch({ type: 'SET_PHASE', phase: PHASES.SNAKE_DRAFT })}>
            Start draft
          </button>
        </div>
      </section>
    </div>
  );
}
