import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  formatApiError,
  listLaunchVehicles,
  runLaunchCompat,
  uploadLaunchLoads,
} from '../api/client'
import type { LaunchCompatResult, LaunchVehicleMeta, PartAnnotation } from '../api/types'
import type { SatelliteProfile } from '../lib/satelliteProfile'
import { missingFields } from '../lib/satelliteProfile'
import { missionReadinessHint } from '../lib/annotations'
import { LaunchStressMap } from './LaunchStressMap'
import { LaunchTestMatrix } from './LaunchTestMatrix'
import { LaunchLoadCurves } from './LaunchLoadCurves'
import { LoadingIndicator } from './LoadingIndicator'

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
  const [selectedTestId, setSelectedTestId] = useState<string | null>(null)
  const [stressMode, setStressMode] = useState<'stress' | 'power'>('stress')
  const fileRef = useRef<HTMLInputElement>(null)
  const [uploadKind, setUploadKind] = useState<'psd' | 'srs'>('psd')

  const missing = useMemo(() => missingFields(profile, 'launch'), [profile])
  const massHint = missionReadinessHint(annotations)
  const tests = result?.tests ?? result?.checks ?? []
  const selectedTest = tests.find((t) => t.id === selectedTestId) ?? null

  const psdArtifact = tests.find((t) => t.id === 'random_vibration')?.artifacts?.psd as
    | { freq_hz: number; asd_g2_hz: number }[]
    | undefined
  const srsArtifact = tests.find((t) => t.id === 'shock_srs')?.artifacts?.srs as
    | { freq_hz: number; pv_in_s: number }[]
    | undefined

  useEffect(() => {
    void listLaunchVehicles()
      .then(setVehicles)
      .catch(() => {})
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
      setSelectedTestId(null)
    } catch (e) {
      setErr(formatApiError(e))
      setResult(null)
    } finally {
      setBusy(false)
    }
  }, [projectId, selected, orbit, profile])

  useEffect(() => {
    const t = setTimeout(() => void runSim(), 500)
    return () => clearTimeout(t)
  }, [runSim])

  const vehicleList =
    vehicles.length > 0
      ? vehicles
      : [
          {
            id: 'f9',
            name: 'Falcon 9',
            provider: 'SpaceX',
            leo_capacity_kg: 22800,
            gto_capacity_kg: 8300,
            fairing_diameter_m: 5.2,
          },
        ]

  const onUploadLoads = async (files: FileList | null) => {
    const f = files?.[0]
    if (!f || !projectId) return
    try {
      await uploadLaunchLoads(projectId, uploadKind, f)
      await runSim()
    } catch (e) {
      setErr(formatApiError(e))
    }
  }

  return (
    <div className={`launch-panel ${compact ? 'launch-panel-compact' : ''}`}>
      {!hideHeader ? (
        <div className="panel-head">
          <h3 className="panel-title">
            <span className="panel-icon">◉</span> Launch Physics Engine
          </h3>
          <span
            className={`hud-chip ${
              result?.verdict === 'GO' ? 'hud-chip-cyan' : 'hud-chip-orange'
            }`}
          >
            {busy ? 'RUNNING…' : result?.verdict ?? 'SIM'}
          </span>
        </div>
      ) : null}

      {result?.disclaimer ? (
        <p className="launch-disclaimer muted">{result.disclaimer}</p>
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
        <label className="launch-orbit-label">
          Override loads
          <select
            className="input-text launch-orbit-select"
            value={uploadKind}
            onChange={(e) => setUploadKind(e.target.value as 'psd' | 'srs')}
          >
            <option value="psd">PSD CSV</option>
            <option value="srs">SRS CSV</option>
          </select>
        </label>
        <button type="button" className="btn btn-ghost" onClick={() => fileRef.current?.click()}>
          Upload MPE
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".csv,.json"
          hidden
          onChange={(e) => void onUploadLoads(e.target.files)}
        />
        <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => void runSim()}>
          Re-run suite
        </button>
      </div>

      {(missing.length > 0 || massHint) && (
        <p className="launch-readiness muted">
          {missing.length > 0 ? `Recommended fields: ${missing.map((f) => f.label).join(', ')}. ` : ''}
          {massHint ?? ''}
        </p>
      )}

      {err ? <p className="error">{err}</p> : null}

      <div className="rocket-grid">
        {vehicleList.map((r) => {
          const active = selected === r.id
          const score = result?.vehicle_id === r.id ? result.overall_score : null
          return (
            <button
              key={r.id}
              type="button"
              className={`rocket-card ${active ? 'rocket-card-active' : ''}`}
              onClick={() => setSelected(r.id)}
            >
              <span className="rocket-name">{r.name}</span>
              <span className="rocket-provider muted">{r.provider}</span>
              {score != null ? (
                <span className="mono compat-score">{score}%</span>
              ) : (
                <span className="mono compat-score muted">—</span>
              )}
            </button>
          )
        })}
      </div>

      {busy && !result ? <LoadingIndicator label="Running physics test suite…" /> : null}

      {result ? (
        <>
          <div className="launch-metrics">
            <div className="metric-tile">
              <span className="metric-label">Verdict</span>
              <span className={`metric-value ${result.verdict === 'GO' ? 'glow-cyan' : 'glow-orange'}`}>
                {result.verdict ?? result.overall_status}
              </span>
            </div>
            <div className="metric-tile">
              <span className="metric-label">Payload</span>
              <span className="metric-value mono">{result.payload_mass_kg.toFixed(0)} kg</span>
            </div>
            <div className="metric-tile">
              <span className="metric-label">Mass margin</span>
              <span className="metric-value mono">{result.mass_margin_pct.toFixed(1)}%</span>
            </div>
            <div className="metric-tile">
              <span className="metric-label">Engine</span>
              <span className="metric-value mono" style={{ fontSize: '0.65rem' }}>
                {result.engine_version ?? 'v2'}
              </span>
            </div>
          </div>

          {result.blockers && result.blockers.length > 0 ? (
            <ul className="launch-blockers">
              {result.blockers.map((b) => (
                <li key={b.id} className="launch-blocker">
                  <span className="warning-tag mono">{b.status.toUpperCase()}</span>
                  <strong>{b.title}</strong>
                  <span className="muted">{b.detail}</span>
                </li>
              ))}
            </ul>
          ) : null}

          <LaunchTestMatrix
            tests={tests}
            selectedId={selectedTestId}
            onSelect={setSelectedTestId}
          />

          {selectedTest ? (
            <div className="launch-test-detail card">
              <h4>{selectedTest.title}</h4>
              <p className="mono">
                {selectedTest.value} / {selectedTest.limit}
              </p>
              <p className="muted">{selectedTest.detail}</p>
              {selectedTest.assumptions?.length ? (
                <ul className="launch-assumptions">
                  {selectedTest.assumptions.map((a, i) => (
                    <li key={i}>{a}</li>
                  ))}
                </ul>
              ) : null}
              {selectedTest.references?.length ? (
                <p className="muted mono" style={{ fontSize: '0.68rem' }}>
                  Ref: {selectedTest.references.join('; ')}
                </p>
              ) : null}
            </div>
          ) : null}

          <LaunchLoadCurves psd={psdArtifact} srs={srsArtifact} />

          {result.stress_field?.fea_mode && result.stress_field.fea_mode !== 'none' ? (
            <LaunchStressMap result={result} mode={stressMode} onModeChange={setStressMode} />
          ) : (
            <p className="muted" style={{ fontSize: '0.78rem' }}>
              Structural FEA map requires annotated parts with mass and L×W×H dimensions.
            </p>
          )}

          <p className="muted launch-sim-note">{result.simulation?.notes}</p>
        </>
      ) : null}
    </div>
  )
}
