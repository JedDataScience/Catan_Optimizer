/**
 * Steps.jsx — Where you are in the four-step flow. The steps really are a
 * sequence, so they're numbered.
 */

import { PHASES } from '../../state/reducer';

const STEPS = [
  { phase: PHASES.BOARD_SETUP,   label: 'Board' },
  { phase: PHASES.PLAYER_CONFIG, label: 'Players' },
  { phase: PHASES.SNAKE_DRAFT,   label: 'Draft' },
  { phase: PHASES.ANALYSIS,      label: 'Results' },
];

export default function Steps({ phase }) {
  return (
    <ol className="steps" aria-label="Progress">
      {STEPS.map((s, i) => {
        const state = s.phase < phase ? 'is-done' : s.phase === phase ? 'is-active' : '';
        return (
          <li key={s.label} className={`step ${state}`} aria-current={s.phase === phase ? 'step' : undefined}>
            <span className="step-num">{s.phase < phase ? '✓' : i + 1}</span>
            <span className="step-label">{s.label}</span>
          </li>
        );
      })}
    </ol>
  );
}
