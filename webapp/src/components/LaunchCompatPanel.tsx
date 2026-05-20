import { useState } from 'react'

const ROCKETS = [
  { id: 'f9', name: 'Falcon 9', provider: 'SpaceX', mass: '22,800 kg', score: 94, status: 'nominal' },
  { id: 'elec', name: 'Electron', provider: 'Rocket Lab', mass: '300 kg', score: 72, status: 'review' },
  { id: 'starship', name: 'Starship', provider: 'SpaceX', mass: '100,000+ kg', score: 88, status: 'nominal' },
  { id: 'vulcan', name: 'Vulcan', provider: 'ULA', mass: '27,200 kg', score: 81, status: 'review' },
  { id: 'a6', name: 'Ariane 6', provider: 'Arianespace', mass: '21,650 kg', score: 79, status: 'caution' },
] as const

const WARNINGS = [
  { level: 'warn', text: 'Fairing clearance margin +2.1% at max deployment angle' },
  { level: 'info', text: 'CoM within envelope — lateral offset 4.2 mm' },
  { level: 'crit', text: 'Vibration mode coupling near 42 Hz — review isolators' },
] as const

type Props = { compact?: boolean; hideHeader?: boolean }

export function LaunchCompatPanel({ compact, hideHeader }: Props) {
  const [selected, setSelected] = useState('f9')

  return (
    <div className={`launch-panel ${compact ? 'launch-panel-compact' : ''}`}>
      {!hideHeader ? (
        <div className="panel-head">
          <h3 className="panel-title">
            <span className="panel-icon">◉</span> Launch Compatibility Engine
          </h3>
          <span className="hud-chip hud-chip-orange">SIM ACTIVE</span>
        </div>
      ) : null}

      <div className="rocket-grid">
        {ROCKETS.map((r) => (
          <button
            key={r.id}
            type="button"
            className={`rocket-card ${selected === r.id ? 'rocket-card-active' : ''}`}
            onClick={() => setSelected(r.id)}
          >
            <span className="rocket-name">{r.name}</span>
            <span className="rocket-provider muted">{r.provider}</span>
            <div className="compat-bar">
              <div
                className="compat-fill"
                style={{ width: `${r.score}%` }}
                data-status={r.status}
              />
            </div>
            <span className="mono compat-score">{r.score}%</span>
            <span className="mono rocket-mass">{r.mass}</span>
          </button>
        ))}
      </div>

      <div className="launch-metrics">
        <div className="metric-tile">
          <span className="metric-label">Envelope fit</span>
          <span className="metric-value glow-cyan">OK</span>
        </div>
        <div className="metric-tile">
          <span className="metric-label">Payload mass</span>
          <span className="metric-value mono">847 kg</span>
        </div>
        <div className="metric-tile">
          <span className="metric-label">CoM stability</span>
          <span className="metric-value glow-orange">0.94</span>
        </div>
      </div>

      <ul className="warning-list">
        {WARNINGS.map((w, i) => (
          <li key={i} className={`warning-item warning-${w.level}`}>
            <span className="warning-tag mono">{w.level.toUpperCase()}</span>
            {w.text}
          </li>
        ))}
      </ul>
    </div>
  )
}
