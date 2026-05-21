import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  formatApiError,
  getLaunchReadiness,
  importLaunchReadiness,
  listLaunchVehicles,
  runLaunchCompat,
  uploadLaunchLoads,
} from '../api/client'
import type { LaunchCompatResult, LaunchVehicleMeta, PartAnnotation } from '../api/types'
import type { SatelliteProfile } from '../lib/satelliteProfile'
import {
  applyVehicleToMissionConfig,
  configFromLaunchReadinessDoc,
  defaultLaunchMissionConfig,
  missionConfigToJson,
  parseMissionConfigJson,
  validateLaunchInputs,
  type LaunchMissionConfig,
  type LaunchOrbit,
} from '../lib/launchReadiness'
import { BUNDLED_LAUNCH_VEHICLES } from '../lib/launchVehicles'
import {
  buildCheckProgramLogs,
  buildLaunchSuiteLogLines,
  downloadLaunchReportPdf,
} from '../lib/launchReport'
import { LaunchStressMap } from './LaunchStressMap'
import { LaunchTestMatrix } from './LaunchTestMatrix'
import { LaunchLoadCurves } from './LaunchLoadCurves'
import { LoadingIndicator } from './LoadingIndicator'
import { LaunchAnalysisConsole } from './LaunchAnalysisConsole'

const ENGINE_NAME = 'AEGIS-LV'
const ENGINE_FULL_NAME = 'AEGIS-LV Mission Assurance Engine'

const ORBITS: { id: LaunchOrbit; label: string }[] = [
  { id: 'leo', label: 'LEO' },
  { id: 'gto', label: 'GTO' },
  { id: 'sso', label: 'SSO' },
]

const LOAD_KINDS = [
  { id: 'psd' as const, label: 'PSD' },
  { id: 'srs' as const, label: 'SRS' },
]

type Props = {
  projectId: string
  profile: SatelliteProfile
  annotations: PartAnnotation[]
  compact?: boolean
  hideHeader?: boolean
  onTerminalLog?: (lines: string[]) => void
}

export function LaunchCompatPanel({
  projectId,
  profile,
  annotations,
  compact,
  hideHeader,
  onTerminalLog,
}: Props) {
  const [vehicles, setVehicles] = useState<LaunchVehicleMeta[]>(BUNDLED_LAUNCH_VEHICLES)
  const [selected, setSelected] = useState('f9')
  const [orbit, setOrbit] = useState<LaunchOrbit>('leo')
  const [missionConfig, setMissionConfig] = useState<LaunchMissionConfig>(() =>
    defaultLaunchMissionConfig('f9', 'leo'),
  )
  const [configText, setConfigText] = useState(() => missionConfigToJson(defaultLaunchMissionConfig()))
  const [configParseErr, setConfigParseErr] = useState<string | null>(null)
  const [result, setResult] = useState<LaunchCompatResult | null>(null)
  const [hasRun, setHasRun] = useState(false)
  const [showConfig, setShowConfig] = useState(true)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [selectedTestId, setSelectedTestId] = useState<string | null>(null)
  const [stressMode, setStressMode] = useState<'stress' | 'power'>('stress')
  const fileRef = useRef<HTMLInputElement>(null)
  const missionFileRef = useRef<HTMLInputElement>(null)
  const [uploadKind, setUploadKind] = useState<'psd' | 'srs'>('psd')
  const [missionDropOver, setMissionDropOver] = useState(false)

  const mergedMission = useMemo(() => ({ ...profile, ...missionConfig.mission }), [profile, missionConfig.mission])

  const validationAnnotations =
    missionConfig.components && missionConfig.components.length > 0 ? missionConfig.components : annotations
  const validation = useMemo(
    () => validateLaunchInputs(mergedMission, validationAnnotations),
    [mergedMission, validationAnnotations],
  )

  const tests = result?.tests ?? result?.checks ?? []
  const selectedTest = tests.find((t) => t.id === selectedTestId) ?? null
  const blockedCount = tests.filter((t) => (t.test_status ?? t.status) === 'blocked').length
  const failCount = tests.filter((t) => (t.test_status ?? t.status) === 'fail').length
  const warnCount = tests.filter((t) => (t.test_status ?? t.status) === 'warn').length
  const verdictLabel = busy ? 'RUNNING' : (result?.verdict ?? '—')
  const assuranceState =
    blockedCount > 0 ? 'BLOCKED' : failCount > 0 ? 'NO-GO' : warnCount > 0 ? 'CONDITIONAL' : hasRun ? 'GO' : '—'

  const psdArtifact = tests.find((t) => t.id === 'random_vibration')?.artifacts?.psd as
    | { freq_hz: number; asd_g2_hz: number }[]
    | undefined
  const srsArtifact = tests.find((t) => t.id === 'shock_srs')?.artifacts?.srs as
    | { freq_hz: number; pv_in_s: number }[]
    | undefined

  const syncConfigText = useCallback((cfg: LaunchMissionConfig) => {
    setMissionConfig(cfg)
    setConfigText(missionConfigToJson(cfg))
    setConfigParseErr(null)
  }, [])

  useEffect(() => {
    void listLaunchVehicles()
      .then((fromApi) => {
        if (fromApi.length > 0) setVehicles(fromApi)
      })
      .catch(() => {
        /* keep bundled catalog */
      })
  }, [])

  useEffect(() => {
    if (!projectId) return
    void getLaunchReadiness(projectId).then((doc) => {
      if (!doc?.mission) return
      const cfg = configFromLaunchReadinessDoc(
        doc as {
          mission?: SatelliteProfile
          components?: LaunchMissionConfig['components']
          launch_vehicle_preferences?: { preferred_vehicle_id?: string; target_orbit?: string }
        },
      )
      syncConfigText(cfg)
      setSelected(cfg.launch_vehicle_preferences.preferred_vehicle_id)
      setOrbit(cfg.launch_vehicle_preferences.target_orbit)
    })
  }, [projectId, syncConfigText])

  const selectedVehicle = vehicles.find((v) => v.id === selected)

  const logValidationErrors = useCallback(() => {
    if (validation.errors.length) onTerminalLog?.(validation.errors)
  }, [validation.errors, onTerminalLog])

  const runSim = useCallback(async () => {
    if (!projectId || !validation.ready) return
    setShowConfig(false)
    setBusy(true)
    setErr(null)
    onTerminalLog?.([
      `[AEGIS-LV] RUN START vehicle=${selected} orbit=${orbit.toUpperCase()}`,
      '[AEGIS-LV] mission config + annotated spacecraft → launch_physics_v2',
    ])
    try {
      const r = await runLaunchCompat(projectId, {
        vehicle_id: selected,
        orbit,
        profile: mergedMission as Record<string, string | number>,
      })
      setResult(r)
      setHasRun(true)
      const suite = r.tests ?? r.checks ?? []
      setSelectedTestId(suite[0]?.id ?? null)
      onTerminalLog?.(buildLaunchSuiteLogLines(r, suite))
    } catch (e) {
      setErr(formatApiError(e))
      setResult(null)
      setShowConfig(true)
      onTerminalLog?.([`[AEGIS-LV] ERROR ${formatApiError(e)}`])
    } finally {
      setBusy(false)
    }
  }, [projectId, validation.ready, selected, orbit, mergedMission, onTerminalLog])

  const onSelectTest = (id: string) => {
    setSelectedTestId(id)
    const check = tests.find((t) => t.id === id) ?? null
    if (check) {
      onTerminalLog?.([
        `[AEGIS-LV] TRACE ${check.id}`,
        ...buildCheckProgramLogs(check, result).map((line) => `[AEGIS-LV] TRACE ${check.id}: ${line}`),
      ])
    }
  }

  const onDownloadPdf = () => {
    if (!result) return
    downloadLaunchReportPdf({
      result,
      tests,
      orbit,
      profile: mergedMission,
      vehicle: selectedVehicle,
    })
  }

  const onTryRun = () => {
    if (!validation.ready) {
      logValidationErrors()
      return
    }
    void runSim()
  }

  const onSelectVehicle = (vehicle: LaunchVehicleMeta) => {
    setSelected(vehicle.id)
    const next = applyVehicleToMissionConfig(missionConfig, vehicle, orbit)
    syncConfigText(next)
    onTerminalLog?.([
      `[AEGIS-LV] CONFIG vehicle=${vehicle.name} (${vehicle.id})`,
      `[AEGIS-LV] CONFIG fairing_diameter_m=${vehicle.fairing_diameter_m} LEO cap=${vehicle.leo_capacity_kg} kg`,
    ])
  }

  const onOrbitChange = (next: LaunchOrbit) => {
    setOrbit(next)
    syncConfigText({
      ...missionConfig,
      launch_vehicle_preferences: {
        preferred_vehicle_id: selected,
        target_orbit: next,
      },
    })
  }

  const onConfigBlur = () => {
    try {
      const parsed = parseMissionConfigJson(configText)
      syncConfigText(parsed)
      setSelected(parsed.launch_vehicle_preferences.preferred_vehicle_id)
      setOrbit(parsed.launch_vehicle_preferences.target_orbit)
    } catch (e) {
      setConfigParseErr(e instanceof Error ? e.message : 'Invalid JSON')
    }
  }

  const onUploadLoads = async (files: FileList | null) => {
    const f = files?.[0]
    if (!f || !projectId) return
    try {
      await uploadLaunchLoads(projectId, uploadKind, f)
      onTerminalLog?.([`[AEGIS-LV] CONFIG uploaded ${uploadKind.toUpperCase()} loads for project`])
    } catch (e) {
      setErr(formatApiError(e))
    }
  }

  const isMissionJson = (f: File) => {
    const n = f.name.toLowerCase()
    return n.endsWith('.json') || f.type.includes('json')
  }

  const onImportMission = async (files: FileList | null) => {
    const f = files?.[0]
    if (!f || !projectId) return
    if (!isMissionJson(f)) {
      setErr('Mission config must be a .json launch readiness file.')
      return
    }
    setErr(null)
    try {
      const text = await f.text()
      const parsed = parseMissionConfigJson(text)
      await importLaunchReadiness(projectId, f)
      syncConfigText(parsed)
      setSelected(parsed.launch_vehicle_preferences.preferred_vehicle_id)
      setOrbit(parsed.launch_vehicle_preferences.target_orbit)
      onTerminalLog?.(['[AEGIS-LV] CONFIG imported mission JSON from disk'])
      const importedAnnotations =
        parsed.components && parsed.components.length > 0 ? parsed.components : annotations
      const importValidation = validateLaunchInputs({ ...profile, ...parsed.mission }, importedAnnotations)
      if (!importValidation.ready) {
        onTerminalLog?.(importValidation.errors)
      }
    } catch (e) {
      setErr(formatApiError(e))
    }
  }

  const onMissionDragOver = (e: React.DragEvent) => {
    if (!e.dataTransfer.types.includes('Files')) return
    e.preventDefault()
    e.stopPropagation()
    e.dataTransfer.dropEffect = 'copy'
    setMissionDropOver(true)
  }

  const onMissionDrop = (e: React.DragEvent) => {
    if (!e.dataTransfer.files?.length) return
    e.preventDefault()
    e.stopPropagation()
    setMissionDropOver(false)
    void onImportMission(e.dataTransfer.files)
  }

  return (
    <div
      className={`launch-panel ${compact ? 'launch-panel-compact' : ''}${missionDropOver ? ' launch-panel-drop-active' : ''}`}
      onDragOver={onMissionDragOver}
      onDragLeave={() => setMissionDropOver(false)}
      onDrop={onMissionDrop}
    >
      {!hideHeader ? (
        <div className="panel-head launch-assurance-head">
          <div className="launch-assurance-main">
            <h3 className="panel-title launch-title">{ENGINE_FULL_NAME}</h3>
            {hasRun && result ? (
              <div className="launch-report-actions launch-report-actions-head">
                <button type="button" className="launch-action-btn" onClick={() => setShowConfig(true)}>
                  Back to config
                </button>
                <button type="button" className="launch-action-btn" onClick={onDownloadPdf}>
                  Download PDF report
                </button>
              </div>
            ) : null}
          </div>
          {busy || hasRun ? (
            <span
              className={`hud-chip ${
                result?.verdict === 'GO' ? 'hud-chip-cyan' : 'hud-chip-orange'
              }`}
            >
              {verdictLabel}
            </span>
          ) : null}
        </div>
      ) : null}

      {showConfig ? (
      <section className="launch-config-frame">
        <div className="launch-section-head">
          <span className="launch-section-title">Launch vehicle</span>
          <span className="mono muted">select to apply MPE defaults to mission JSON</span>
        </div>
        <div className="rocket-grid">
          {vehicles.map((r) => {
            const active = selected === r.id
            const score = result?.vehicle_id === r.id ? result.overall_score : null
            return (
              <button
                key={r.id}
                type="button"
                className={`rocket-card ${active ? 'rocket-card-active' : ''}`}
                onClick={() => onSelectVehicle(r)}
              >
                <span className="rocket-name">{r.name}</span>
                <span className="rocket-provider muted">{r.provider}</span>
                <span className="rocket-mass mono">
                  {r.leo_capacity_kg.toLocaleString()} kg LEO
                </span>
                {score != null ? (
                  <span className="mono compat-score">{score}%</span>
                ) : (
                  <span className="mono compat-score muted">—</span>
                )}
              </button>
            )
          })}
        </div>

        <div className="launch-config-toolbar">
          <div className="launch-segment-block">
            <span className="launch-segment-label mono">Target orbit</span>
            <div className="launch-segment-group" role="group" aria-label="Target orbit">
              {ORBITS.map((o) => (
                <button
                  key={o.id}
                  type="button"
                  className={`launch-segment-btn${orbit === o.id ? ' launch-segment-btn-active' : ''}`}
                  onClick={() => onOrbitChange(o.id)}
                >
                  {o.label}
                </button>
              ))}
            </div>
          </div>
          <div className="launch-segment-block">
            <span className="launch-segment-label mono">MPE override</span>
            <div className="launch-segment-group" role="group" aria-label="Load file type">
              {LOAD_KINDS.map((k) => (
                <button
                  key={k.id}
                  type="button"
                  className={`launch-segment-btn${uploadKind === k.id ? ' launch-segment-btn-active' : ''}`}
                  onClick={() => setUploadKind(k.id)}
                >
                  {k.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="launch-section-head">
          <span className="launch-section-title">Mission specification</span>
          <span className="mono muted">JSON · paired with annotated spacecraft at run</span>
        </div>
        <textarea
          className="launch-config-editor mono"
          spellCheck={false}
          value={configText}
          onChange={(e) => setConfigText(e.target.value)}
          onBlur={onConfigBlur}
          aria-label="Mission specification JSON"
        />
        {configParseErr ? <p className="error launch-config-err">{configParseErr}</p> : null}

        <div className="launch-action-rail">
          <button
            type="button"
            className="launch-action-btn"
            onClick={() => missionFileRef.current?.click()}
          >
            <span className="launch-action-icon">⎘</span>
            Import JSON
          </button>
          <input
            ref={missionFileRef}
            type="file"
            accept=".json,application/json,text/json"
            hidden
            onChange={(e) => void onImportMission(e.target.files)}
          />
          <button type="button" className="launch-action-btn" onClick={() => fileRef.current?.click()}>
            <span className="launch-action-icon">↑</span>
            Upload {uploadKind.toUpperCase()}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.json"
            hidden
            onChange={(e) => void onUploadLoads(e.target.files)}
          />
          <button
            type="button"
            className="launch-run-btn"
            disabled={busy || !validation.ready || !!configParseErr}
            onClick={onTryRun}
            title={
              validation.ready
                ? 'Run full physics assurance suite'
                : 'Complete mission JSON and annotations first — errors in terminal'
            }
          >
            {busy ? 'Running suite…' : 'Run assurance suite'}
          </button>
          {!validation.ready ? (
            <button
              type="button"
              className="launch-action-btn launch-action-btn-muted"
              onClick={logValidationErrors}
            >
              Log gaps to terminal
            </button>
          ) : null}
        </div>
      </section>
      ) : null}

      {err ? <p className="error">{err}</p> : null}

      {hasRun || busy ? (
        <LaunchAnalysisConsole
          result={result}
          busy={busy}
          orbit={orbit}
          profile={mergedMission}
          annotations={annotations}
          vehicle={selectedVehicle}
          selectedTest={selectedTest}
        />
      ) : (
        <p className="muted launch-idle-hint mono">
          Configure vehicle + mission JSON, satisfy all required fields, then run the suite.
          Missing inputs are reported in the integration terminal.
        </p>
      )}

      {busy && !result ? <LoadingIndicator label="Running physics test suite…" /> : null}

      {hasRun && result ? (
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
                {result.engine_name ?? ENGINE_NAME}
              </span>
            </div>
            <div className="metric-tile">
              <span className="metric-label">Gates</span>
              <span className={`metric-value mono ${blockedCount > 0 ? 'glow-orange' : 'glow-cyan'}`}>
                {assuranceState}
              </span>
            </div>
          </div>

          {result.blockers && result.blockers.length > 0 ? (
            <div className="launch-blocker-frame">
              <div className="launch-section-head">
                <span className="launch-section-title">Critical blockers</span>
              </div>
              <ul className="launch-blockers">
                {result.blockers.map((b) => (
                  <li key={b.id} className="launch-blocker">
                    <span className="warning-tag mono">{b.status.toUpperCase()}</span>
                    <strong>{b.title}</strong>
                    <span className="muted">{b.detail}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="launch-section-head">
            <span className="launch-section-title">Physics simulation outputs</span>
            <span className="mono muted">
              {result.engine_version ?? 'launch_physics_v2'} / rev {result.vehicle_data_rev ?? 'untracked'}
            </span>
          </div>
          <LaunchTestMatrix tests={tests} selectedId={selectedTestId} onSelect={onSelectTest} />

          {selectedTest ? (
            <div className="launch-test-detail card">
              <h4>{selectedTest.title}</h4>
              <p className="mono">
                {selectedTest.value} / {selectedTest.limit}
              </p>
              <p className="muted">{selectedTest.detail}</p>
            </div>
          ) : null}

          <LaunchLoadCurves psd={psdArtifact} srs={srsArtifact} />

          {result.stress_field?.fea_mode && result.stress_field.fea_mode !== 'none' ? (
            <LaunchStressMap result={result} mode={stressMode} onModeChange={setStressMode} />
          ) : null}

          <p className="muted launch-sim-note">{result.simulation?.notes}</p>
        </>
      ) : null}
    </div>
  )
}
