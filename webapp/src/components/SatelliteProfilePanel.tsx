import type { PendingQuestion, SatelliteProfile } from '../lib/satelliteProfile'
import { PROFILE_FIELDS } from '../lib/satelliteProfile'
import type { Subsystem } from '../lib/subsystems'
import { subsystemCounts, SUBSYSTEMS } from '../lib/subsystems'
import type { DiagramNode } from '../api/types'

type Props = {
  profile: SatelliteProfile
  pendingQuestions: PendingQuestion[]
  nodes: DiagramNode[]
  activeSubsystem: Subsystem
  onChange: (key: string, value: string) => void
  onAnswerPending: (questionId: string, value: string) => void
}

export function SatelliteProfilePanel({
  profile,
  pendingQuestions,
  nodes,
  activeSubsystem,
  onChange,
  onAnswerPending,
}: Props) {
  const counts = subsystemCounts(nodes)

  return (
    <div className="satellite-profile-panel">
      <p className="muted" style={{ marginTop: 0, fontSize: '0.82rem', lineHeight: 1.55 }}>
        Mission parameters used for launch compatibility and simulation accuracy. Values you
        enter here are shared across all engineering tabs.
      </p>

      {pendingQuestions.length > 0 ? (
        <section className="satellite-profile-section">
          <h4 className="satellite-profile-heading">Follow-up required</h4>
          <p className="muted" style={{ fontSize: '0.78rem' }}>
            The terminal requested additional data before running calculations.
          </p>
          <ul className="satellite-followup-list">
            {pendingQuestions.map((q) => (
              <li key={q.id} className="satellite-followup-item">
                <p className="satellite-followup-q">{q.question}</p>
                <p className="muted mono" style={{ fontSize: '0.68rem' }}>
                  {q.reason}
                </p>
                <input
                  type="text"
                  className="input-text"
                  placeholder="Enter value…"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      const v = (e.target as HTMLInputElement).value.trim()
                      if (v) onAnswerPending(q.id, v)
                    }
                  }}
                />
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="satellite-profile-section">
        <h4 className="satellite-profile-heading">Mission parameters</h4>
        <div className="satellite-profile-grid">
          {PROFILE_FIELDS.map((f) => (
            <label key={f.key} className="satellite-profile-field">
              <span>
                {f.label}
                {f.unit ? <span className="muted"> ({f.unit})</span> : null}
              </span>
              <input
                type="text"
                className="input-text"
                value={profile[f.key] ?? ''}
                onChange={(e) => onChange(f.key, e.target.value)}
              />
            </label>
          ))}
        </div>
      </section>

      <section className="satellite-profile-section">
        <h4 className="satellite-profile-heading">Subsystem inventory</h4>
        <p className="muted" style={{ fontSize: '0.78rem' }}>
          Components classified under <strong>{activeSubsystem}</strong> from the schematic IR.
        </p>
        <div className="satellite-inventory">
          {SUBSYSTEMS.map((s) => (
            <div
              key={s}
              className={`satellite-inventory-row ${s === activeSubsystem ? 'satellite-inventory-row-active' : ''}`}
            >
              <span>{s}</span>
              <span className="mono">{counts[s]}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
