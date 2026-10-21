/**
 * BoardSetupPanel.jsx — Step 1: lay out the tiles and ports.
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
    // Scarcity is a nice-to-have: if it fails, the panel just doesn't show it
    fetchBoardAnalysis(state)
      .then((data) => dispatch({ type: 'SET_BOARD_ANALYSIS', data }))
      .catch((e) => console.warn('[board-analysis]', e.message));
    dispatch({ type: 'SET_PHASE', phase: PHASES.PLAYER_CONFIG });
  }

  return (
    <div>
      <h1 className="panel-title">Set up your board</h1>
      <p className="panel-intro">
        Match the board on your table: click a tile to choose its terrain and
        number, and a dock to set its port. Or start from a random board.
      </p>

      <section className="section">
        <div className="btn-row">
          <button className="btn btn-secondary" onClick={handleRandomise}>Random board</button>
          <button className="btn btn-quiet" onClick={() => dispatch({ type: 'CLEAR_BOARD' })}>Clear</button>
        </div>
      </section>

      <section className="section">
        <div className="progress-line">
          <span>Tiles placed</span>
          <span><strong className="num">{filled}</strong> of 19</span>
        </div>
        <div className="meter" aria-hidden="true">
          <div className={`meter-fill${filled === 19 ? ' is-complete' : ''}`} style={{ width: `${(filled / 19) * 100}%` }} />
        </div>

        {!valid && filled > 0 && (
          <ul className="issue-list" aria-live="polite">
            {issues.map((issue) => <li key={issue}>{issue}</li>)}
          </ul>
        )}
      </section>

      <section className="section">
        <button className="btn btn-primary btn-lg btn-block" disabled={!valid} onClick={handleContinue}>
          Continue
        </button>
      </section>
    </div>
  );
}
