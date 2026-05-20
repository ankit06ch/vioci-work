import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  formatApiError,
  listLaunchVehicles,
  runLaunchCompat,
} from '../api/client'
import type { LaunchCompatResult, LaunchVehicleMeta, PartAnnotation } from '../api/types'
import type { SatelliteProfile } from '../lib/satelliteProfile'
import { missingFields } from '../lib/satelliteProfile'
import { missionReadinessHint } from '../lib/annotations'
import { LaunchStressMap } from './LaunchStressMap'
import { LoadingIndicator } from './LoadingIndicator'

const CATEGORY_LABELS: Record<string, string> = {
  mass_orbit: '1 · Mass, orbit & performance',
  envelope: '2 · Volumetric fit',
  loads: '3 · Structural & dynamic loads',
  thermal: '4 · Thermal & environment',
}

type Props = {
  projectId: string
  profile: SatelliteProfile
  annotations: PartAnnotation[]
  compact?: boolean
  hideHeader?: boolean
}

export function LaunchCompatPanel({
  projectId,
  profile,
  annotations,
  compact,
  hideHeader,
}: Props) {
  const [vehicles, setVehicles] = useState<LaunchVehicleMeta[]>([])
  const [selected, setSelected] = useState('f9')
  const [orbit, setOrbit] = useState<'leo' | 'gto' | 'sso'>('leo')
  const [result, setResult] = useState<LaunchCompatResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [activeCategory, setActiveCategory] = useState<string>('mass_orbit')
  const [stressMode, setStressMode] = useState<'stress' | 'power'>('stress')

  const missing = useMemo(() => missingFields(profile, 'launch'), [profile])
  const massHint = missionReadinessHint(annotations)

  useEffect(() => {
    void listLaunchVehicles()
      .then(setVehicles)
      .catch(() => {
        /* fallback if offline */
      })
  }, [])

  const runSim = useCallback(async () => {
    if (!projectId) return
    setBusy(true)
    setErr(null)
    try {
      const r = await runLaunchCompat(projectId, {
        vehicle_id: selected,
        orbit,
        profile: profile as Record<string, string | number>,
      })
      setResult(r)
    } catch (e) {
      setErr(formatApiError(e))
      setResult(null)
    } finally {
      setBusy(false)
    }
  }, [projectId, selected, orbit, profile])

  useEffect(() => {
    const t = setTimeout(() => {
      void runSim()
    }, 400)
    return () => clearTimeout(t)
  }, [runSim])

  const vehicleList = vehicles.length
    ? vehicles
    : [
        { id: 'f9', name: 'Falcon 9', provider: 'SpaceX', leo_capacity_kg: 22800, gto_capacity_kg: 8300, fairing_diameter_m: 5.2 },
        { id: 'elec', name: 'Electron', provider: 'Rocket Lab', leo_capacity_kg: 300, gto_capacity_kg: 0, fairing_diameter_m: 1.2 },
        { id: 'starship', name: 'Starship', provider: 'SpaceX', leo_capacity_kg: 100000, gto_capacity_kg: 21000, fairing_diameter_m: 9 },
        { id: 'vulcan', name: 'Vulcan', provider: 'ULA', leo_capacity_kg: 27200, gto_capacity_kg: 14400, fairing_diameter_m: 5.4 },
        { id: 'a6', name: 'Ariane 6', provider: 'Arianespace', leo_capacity_kg: 21650, gto_capacity_kg: 10350, fairing_diameter_m: 5.4 },
      ]

  const checksForCategory = result?.checks.filter((c) => c.category === activeCategory) ?? []

  const scoreForVehicle = (vid: string) =>
    result && result.vehicle_id === vid ? result.overall_score : null

  return (
    <div className={`launch-panel ${compact ? 'launch-panel-compact' : ''}`}>
      {!hideHeader ? (
        <div className="panel-head">
          <h3 className="panel-title">
            <span className="panel-icon">◉</span> Launch Integration
          </h3>
          <span className={`hud-chip hud-chip-${result?.overall_status === 'nominal' ? 'cyan' : 'orange'}`}>
            {busy ? 'RUNNING…' : result ? `${result.overall_score}%` : 'SIM'}
          </span>
        </div>
      ) : null}

      <div className="launch-orbit-row">
        <label className="launch-orbit-label">
          Target orbit
          <select
            className="input-text launch-orbit-select"
            value={orbit}
            onChange={(e) => setOrbit(e.target.value as 'leo' | 'gto' | 'sso')}
          >
            <option value="leo">LEO</option>
            <option value="gto">GTO</option>
            <option value="sso">SSO</option>
          </select>
        </label>
        <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => void runSim()}>
          Re-run integration
        </button>
      </div>

      {(missing.length > 0 || massHint) && (
        <p className="launch-readiness muted">
          {missing.length > 0
            ? `Missing mission fields: ${missing.map((f) => f.label).join(', ')}. `
            : ''}
          {massHint ?? ''}
        </p>
      )}

      {err ? <p className="error">{err}</p> : null}

      <div className="rocket-grid">
        {vehicleList.map((r) => {
          const score = scoreForVehicle(r.id)
          const active = selected === r.id
          const status =
            score == null
              ? 'idle'
              : score >= 85
                ? 'nominal'
                : score >= 70
                  ? 'review'
                  : score >= 50
                    ? 'caution'
                    : 'fail'
          const cap =
            orbit === 'gto' ? r.gto_capacity_kg : orbit === 'sso' ? r.leo_capacity_kg * 0.7 : r.leo_capacity_kg
          return (
            <button
              key={r.id}
              type="button"
              className={`rocket-card ${active ? 'rocket-card-active' : ''}`}
              onClick={() => setSelected(r.id)}
            >
              <span className="rocket-name">{r.name}</span>
              <span className="rocket-provider muted">{r.provider}</span>
              <div className="compat-bar">
                <div
                  className="compat-fill"
                  style={{ width: `${score ?? (active ? 50 : 12)}%` }}
                  data-status={status}
                />
              </div>
              {score != null ? (
                <span className="mono compat-score">{score}%</span>
              ) : (
                <span className="mono compat-score muted">—</span>
              )}
              <span className="mono rocket-mass">{cap.toLocaleString()} kg</span>
            </button>
          )
        })}
      </div>

      {busy && !result ? (
        <LoadingIndicator label="Running launch integration checks…" />
      ) : null}

      {result ? (
        <>
          <div className="launch-metrics">
            <div className="metric-tile">
              <span className="metric-label">Envelope</span>
              <span
                className={`metric-value ${
                  result.category_scores.envelope >= 85 ? 'glow-cyan' : 'glow-orange'
                }`}
              >
                {result.category_scores.envelope}%
              </span>
            </div>
            <div className="metric-tile">
              <span className="metric-label">Payload</span>
              <span className="metric-value mono">{result.payload_mass_kg.toFixed(0)} kg</span>
            </div>
            <div className="metric-tile">
              <span className="metric-label">Mass margin</span>
              <span
                className={`metric-value mono ${
                  result.mass_margin_pct >= 12 ? 'glow-cyan' : 'glow-orange'
                }`}
              >
                {result.mass_margin_pct.toFixed(1)}%
              </span>
            </div>
            <div className="metric-tile">
              <span className="metric-label">CG offset</span>
              <span className="metric-value mono">
                {result.mass_properties.lateral_offset_mm?.toFixed(1) ?? '—'} mm
              </span>
            </div>
          </div>

          <div className="launch-category-tabs">
            {Object.entries(CATEGORY_LABELS).map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={`launch-cat-tab ${activeCategory === id ? 'launch-cat-tab-active' : ''}`}
                onClick={() => setActiveCategory(id)}
              >
                {label}
                <span className="mono launch-cat-score">{result.category_scores[id] ?? '—'}%</span>
              </button>
            ))}
            <button
              type="button"
              className={`launch-cat-tab ${activeCategory === 'stress' ? 'launch-cat-tab-active' : ''}`}
              onClick={() => setActiveCategory('stress')}
            >
              Stress test map
            </button>
          </div>

          {activeCategory === 'stress' ? (
            <LaunchStressMap result={result} mode={stressMode} onModeChange={setStressMode} />
          ) : (
            <ul className="launch-check-list">
              {checksForCategory.map((c) => (
                <li key={c.id} className={`launch-check launch-check-${c.status}`}>
                  <div className="launch-check-head">
                    <span className="warning-tag mono">{c.status.toUpperCase()}</span>
                    <strong>{c.title}</strong>
                  </div>
                  <p className="mono launch-check-values">
                    {c.value} <span className="muted">/ limit {c.limit}</span>
                  </p>
                  <p className="muted launch-check-detail">{c.detail}</p>
                </li>
              ))}
            </ul>
          )}

          <ul className="warning-list">
            {result.warnings.slice(0, 6).map((w, i) => (
              <li key={i} className={`warning-item warning-${w.level}`}>
                <span className="warning-tag mono">{w.level.toUpperCase()}</span>
                {w.text}
              </li>
            ))}
          </ul>

          <p className="muted launch-sim-note" style={{ fontSize: '0.72rem', marginTop: '0.5rem' }}>
            {result.simulation.notes}
          </p>
        </>
      ) : null}
    </div>
  )
}
