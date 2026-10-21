/**
 * SettingsControls.jsx — Strategy slider and simulation-count control,
 * shared by the Game Setup and Draft panels.
 */

const SIM_OPTIONS = [500, 1000, 2000, 5000, 10000];
const SIM_LABELS  = ['500', '1k', '2k', '5k', '10k'];

export function StrategySlider({ value, onChange, showDescription = false }) {
  return (
    <div className="strategy-slider-wrap">
      <div className="strategy-track">
        <span>Raw Production</span>
        <span>Win-Path</span>
      </div>
      <input
        type="range"
        className="strategy-slider"
        aria-label="Optimization strategy"
        min={0} max={1} step={0.1}
        value={value}
        style={{ '--val': value * 100 }}
        onChange={(e) => onChange(parseFloat(e.target.value))}
      />
      {showDescription && (
        <div style={{ textAlign: 'center', fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
          {value <= 0.1 ? 'Pure pip maximization'
            : value >= 0.9 ? 'Win-path: Ore/Wheat prioritized, synergy bonuses active'
            : `Blend: ${Math.round(value * 100)}% strategic weighting`}
        </div>
      )}
    </div>
  );
}

export function SimCountControl({ value, onChange, style }) {
  return (
    <div className="seg-control" style={style}>
      {SIM_OPTIONS.map((n, i) => (
        <button
          key={n}
          className={`seg-btn ${value === n ? 'active' : ''}`}
          onClick={() => onChange(n)}
        >
          {SIM_LABELS[i]}
        </button>
      ))}
    </div>
  );
}
