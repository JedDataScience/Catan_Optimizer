/**
 * ScoringInfo.jsx — The "How scoring works" button and the panel it opens.
 *
 * The panel is a native <dialog> opened with showModal(): the browser moves
 * focus into it, closes it on Escape, dims the page behind it, and returns
 * focus to the button afterwards. Its numbers come from GET /scoring-info,
 * so they always match what the backend actually scores with.
 */

import { useRef, useState } from 'react';
import { fetchScoringInfo } from '../api/client';
import { RESOURCE_MAP } from '../utils/constants';
import { resourceRows, scoringRows } from '../utils/scoringInfo';
import { ResourceIcon } from './board/ResourceIcon';
import MethodDiagram from './MethodDiagram';

const VALUE_SCALE_MAX = 1.4; // resource bars run from 0 to this value

const pct = (x, digits = 0) => `${(x * 100).toFixed(digits)}%`;

function WeightBars({ shares }) {
  return (
    <ul className="bar-list">
      {scoringRows(shares).map((row) => (
        <li key={row.key}>
          <div className="bar-text">
            <span className="bar-label">{row.label}</span>
            <span className="bar-hint">{row.hint}</span>
          </div>
          <div className="bar-track" aria-hidden="true">
            <div className="bar-fill" style={{ width: pct(row.share) }} />
          </div>
          <span className="bar-value num">{pct(row.share)}</span>
        </li>
      ))}
    </ul>
  );
}

function ResourceValues({ values, previous }) {
  const pos = (v) => `${Math.min(100, (v / VALUE_SCALE_MAX) * 100)}%`;
  return (
    <>
      <ul className="bar-list">
        {resourceRows(values, previous).map((row) => (
          <li key={row.id}>
            <div className="bar-text bar-text-icon">
              <ResourceIcon type={row.id} size={20} />
              <span className="bar-label">{row.label}</span>
            </div>
            <div
              className="bar-track"
              role="img"
              aria-label={`${row.label}: ${row.value.toFixed(2)} times average${row.previous != null ? `, previously ${row.previous.toFixed(2)}` : ''}`}
            >
              <div className="bar-fill" style={{ width: pos(row.value), background: RESOURCE_MAP[row.id].top }} />
              <span className="bar-average" style={{ left: pos(1) }} />
              {row.previous != null && <span className="bar-previous" style={{ left: pos(row.previous) }} />}
            </div>
            <span className="bar-value num">{row.value.toFixed(2)}×</span>
          </li>
        ))}
      </ul>
      <p className="legend">
        <span className="legend-key legend-average" /> average resource (1.00)
        {previous && <><span className="legend-key legend-previous" /> earlier hand-picked value</>}
      </p>
    </>
  );
}

function PairList({ pairs }) {
  const shown = pairs.filter((p) => p.multiplier > 1.0).sort((x, y) => y.multiplier - x.multiplier);
  return (
    <ul className="pair-list">
      {shown.map((p) => (
        <li key={`${p.a}-${p.b}`}>
          <ResourceIcon type={p.a} size={18} />
          <ResourceIcon type={p.b} size={18} />
          <span>{RESOURCE_MAP[p.a].label} + {RESOURCE_MAP[p.b].label}</span>
          <strong className="num">{p.multiplier.toFixed(2)}×</strong>
        </li>
      ))}
    </ul>
  );
}

function PanelBody({ data }) {
  const cal = data.calibration;
  return (
    <>
      <section className="section">
        <h3 className="info-heading">What a spot is scored on</h3>
        <p className="info-text">
          Every open spot gets a score from these parts. The bigger the share, the more it moves the ranking.
        </p>
        <WeightBars shares={data.weights.first_settlement} />
        <p className="info-text">
          Being on a port adds a small bonus ({pct(data.port_weight)} of the score). For your second settlement
          there's no "second spot" part, so the others share its weight.
        </p>
      </section>

      <section className="section">
        <h3 className="info-heading">What each resource is worth</h3>
        <p className="info-text">
          One pip of each resource, compared with the average resource. A resource that's rare on your board
          is worth up to {pct(data.scarcity_boost)} more.
        </p>
        <ResourceValues values={data.resource_values} previous={cal?.previous_values} />
        <p className="info-text">
          The strategy slider decides how much these values count: at "Raw production" every resource is
          worth the same.
        </p>
      </section>

      <section className="section">
        <h3 className="info-heading">Resources that work together</h3>
        <p className="info-text">
          Spots whose resources pair up get a bonus, but only in proportion to how much of both you produce.
        </p>
        <PairList pairs={data.pairs} />
      </section>

      {cal && (
        <section className="section">
          <h3 className="info-heading">Where these numbers come from</h3>
          <p className="info-text">
            They were measured, not guessed: a simulator played out {cal.games_simulated.toLocaleString()} games
            and statistics worked out which starting positions win most.
          </p>
          <MethodDiagram games={cal.games_simulated} boards={cal.boards} heldout={cal.heldout_boards} />
          <div className="result-callout">
            On {cal.heldout_boards} boards the model never saw, these values won{' '}
            <strong className="num">{pct(cal.win_rate_calibrated, 1)}</strong> of games, compared with{' '}
            <strong className="num">{pct(cal.win_rate_previous, 1)}</strong> for the earlier hand-picked values: about{' '}
            <strong className="num">{(cal.difference * 100).toFixed(1)}</strong> more wins per 100 games
            (95% range {(cal.ci_low * 100).toFixed(1)} to {(cal.ci_high * 100).toFixed(1)}).
          </div>
          <p className="hint">
            Simulated players follow one simple strategy and the simulator skips Longest Road, so treat these as
            strong defaults rather than exact truths. Full method and results: backend/calibration/REPORT.md.
          </p>
        </section>
      )}
    </>
  );
}

export default function ScoringInfo() {
  const dialogRef = useRef(null);
  const [state, setState] = useState({ status: 'idle' });

  function load() {
    setState({ status: 'loading' });
    fetchScoringInfo()
      .then((data) => setState({ status: 'ready', data }))
      .catch((e) => setState({ status: 'error', message: e.message }));
  }

  function open() {
    dialogRef.current?.showModal();
    if (state.status === 'idle' || state.status === 'error') load();
  }

  function close() {
    dialogRef.current?.close();
  }

  return (
    <>
      <button className="btn btn-secondary btn-on-sea" onClick={open} aria-haspopup="dialog" aria-label="How scoring works">
        {/* The short label is swapped in on phones, where the header is tight */}
        <span className="label-long">How scoring works</span>
        <span className="label-short" aria-hidden="true">Scoring</span>
      </button>

      <dialog
        ref={dialogRef}
        className="info-dialog"
        aria-labelledby="scoring-info-title"
        // A click on the dimmed area outside the panel lands on the <dialog> itself
        onClick={(e) => { if (e.target === dialogRef.current) close(); }}
      >
        <div className="info-panel">
          <header className="info-header">
            <h2 id="scoring-info-title" className="panel-title">How spots are scored</h2>
            <button className="btn btn-quiet info-close" onClick={close} aria-label="Close">✕</button>
          </header>

          {state.status === 'loading' && (
            <div className="loading-line"><span className="spinner" /> Loading the scoring values…</div>
          )}
          {state.status === 'error' && (
            <div className="notice-error" role="alert">
              {state.message}
              <button className="btn btn-secondary btn-block" onClick={load}>Try again</button>
            </div>
          )}
          {state.status === 'ready' && <PanelBody data={state.data} />}
        </div>
      </dialog>
    </>
  );
}
