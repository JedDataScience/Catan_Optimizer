/**
 * SettingsControls.jsx — Strategy slider and simulation-count control,
 * shared by the Players and Draft steps.
 */

const SIM_OPTIONS = [500, 1000, 2000, 5000, 10000];
const SIM_LABELS  = ['500', '1k', '2k', '5k', '10k'];

function strategyCaption(value) {
  if (value <= 0.1) return 'Ranks spots by raw production only.';
  if (value >= 0.9) return 'Favours ore and wheat, resource pairs that work together, and good ports.';
  return `A ${Math.round(value * 100)}% blend of raw production and long-game value.`;
}

export function StrategySlider({ id = 'strategy', value, onChange, showCaption = false }) {
  return (
    <div>
      <label className="field-label" htmlFor={id}>Strategy</label>
      <div className="slider-ends" aria-hidden="true">
        <span>Raw production</span>
        <span>Long game</span>
      </div>
      <input
        id={id}
        type="range"
        className="slider"
        min={0} max={1} step={0.1}
        value={value}
        aria-valuetext={strategyCaption(value)}
        style={{ '--val': value * 100 }}
        onChange={(e) => onChange(parseFloat(e.target.value))}
      />
      {showCaption && <p className="slider-caption">{strategyCaption(value)}</p>}
    </div>
  );
}

export function SimCountControl({ value, onChange, showHint = false }) {
  return (
    <div>
      <span className="field-label" id="sims-label">Simulations</span>
      <div className="seg" role="radiogroup" aria-labelledby="sims-label">
        {SIM_OPTIONS.map((n, i) => (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={value === n}
            className={`seg-btn${value === n ? ' is-active' : ''}`}
            onClick={() => onChange(n)}
          >
            {SIM_LABELS[i]}
          </button>
        ))}
      </div>
      {showHint && <p className="hint">More simulations give steadier rankings but take longer. 5k is a good default.</p>}
    </div>
  );
}
