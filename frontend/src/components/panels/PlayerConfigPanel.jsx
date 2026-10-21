/**
 * PlayerConfigPanel.jsx — Side panel for phase 2: players, turn order, settings.
 */

import { Fragment } from 'react';
import { PHASES, buildDraftOrder } from '../../state/reducer';
import { PLAYER_COLORS, PLAYER_LABELS } from '../../utils/constants';
import { StrategySlider, SimCountControl } from '../SettingsControls';
import ScarcityPanel from './ScarcityPanel';

export default function PlayerConfigPanel({ state, dispatch }) {
  const draftOrder = buildDraftOrder(state.numPlayers);

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

      {/* Simulations */}
      <div style={{ marginBottom: 14 }}>
        <div className="label-xs" style={{ marginBottom: 7 }}>Simulations</div>
        <SimCountControl value={state.nSimulations} onChange={(n) => dispatch({ type: 'SET_N_SIMS', n })} />
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>
          More = better accuracy, slower. 5k recommended.
        </div>
      </div>

      {/* Strategy weight */}
      <div style={{ marginBottom: 16 }}>
        <div className="label-xs" style={{ marginBottom: 7 }}>Optimization Strategy</div>
        <StrategySlider
          value={state.strategyWeight}
          onChange={(w) => dispatch({ type: 'SET_STRATEGY_WEIGHT', w })}
          showDescription
        />
      </div>

      {/* Draft preview */}
      <div className="card" style={{ padding: '10px 14px', marginBottom: 14 }}>
        <div className="label-xs" style={{ marginBottom: 7 }}>Draft Order Preview</div>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
          {draftOrder.map((player, step) => {
            const isUser   = player === state.userPosition;
            const isPhase2 = step >= state.numPlayers;
            return (
              <Fragment key={step}>
                {step === state.numPlayers && (
                  <div style={{ width: 1, height: 24, background: 'var(--border-med)', margin: '0 3px' }} />
                )}
                <div
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
              </Fragment>
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
