/**
 * BoardSetupPanel.jsx — Side panel for phase 1: fill the board and ports.
 */

import { PHASES } from '../../state/reducer';
import { fetchBoardAnalysis } from '../../api/client';
import { randomiseBoard } from '../../utils/boardRandomizer';
import { shufflePorts } from '../../utils/ports';
import { getBoardIssues } from '../../utils/boardValidation';

export default function BoardSetupPanel({ state, dispatch }) {
  const issues = getBoardIssues(state.hexes);
  const valid  = issues.length === 0;
  const filled = state.hexes.filter((h) => h.resource).length;

  function handleRandomise() {
    // Randomness happens here, not in the reducer, so the reducer stays pure
    dispatch({ type: 'RANDOMISE_BOARD', patches: randomiseBoard(), ports: shufflePorts() });
  }

  function handleContinue() {
    // Scarcity is a nice-to-have: if it fails, the panel just doesn't show
    fetchBoardAnalysis(state)
      .then((data) => dispatch({ type: 'SET_BOARD_ANALYSIS', data }))
      .catch((e) => console.warn('[board-analysis]', e.message));
    dispatch({ type: 'SET_PHASE', phase: PHASES.PLAYER_CONFIG });
  }

  return (
    <div>
      <div className="section-heading">Configure the Board</div>
      <div className="section-sub">
        Click each hex to assign a resource and number token, and each port
        badge to set its type. All 19 hexes must be filled before continuing.
      </div>

      {/* Board actions */}
      <div style={{ display: 'flex', gap: 7, marginBottom: 14 }}>
        <button className="btn btn-ghost btn-sm" style={{ flex: 1 }} onClick={() => dispatch({ type: 'CLEAR_BOARD' })}>
          Clear Board
        </button>
        <button className="btn btn-primary btn-sm" style={{ flex: 1 }} onClick={handleRandomise}>
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
      {!valid && filled > 0 && (
        <div style={{
          background: '#fffbeb', border: '1px solid #fde68a',
          borderRadius: 'var(--radius-md)', padding: '8px 12px', marginBottom: 12,
        }}>
          {issues.map((issue) => (
            <div key={issue} style={{ fontSize: 12, color: '#92400e', fontWeight: 500 }}>⚠ {issue}</div>
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
