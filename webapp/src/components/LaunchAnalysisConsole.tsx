import { useEffect, useMemo, useState } from 'react'
import type { LaunchCompatCheck, LaunchCompatResult, LaunchVehicleMeta, PartAnnotation } from '../api/types'
import { buildCheckProgramLogs } from '../lib/launchReport'
import type { SatelliteProfile } from '../lib/satelliteProfile'

type Props = {
  result: LaunchCompatResult | null
  busy: boolean
  orbit: string
  profile: SatelliteProfile
  annotations: PartAnnotation[]
  vehicle?: LaunchVehicleMeta
  selectedTest?: LaunchCompatCheck | null
}

const LIVE_PROGRAM = [
  'bootstrap AEGIS-LV run context',
  'normalize SI units and mission profile',
  'load vehicle MPE, fairing, modal, and CG constraint tables',
  'assemble mass properties and annotated component graph',
  'evaluate payload mass, CG offset, MOI ratio, and orbit proxy',
  'integrate PSD/SRS curves and quasi-static load cases',
  'solve beam-network structural surrogate and modal floors',
  'propagate blocked gates into mission verdict',
]

export function LaunchAnalysisConsole({
  result,
  busy,
  orbit,
  profile,
  annotations,
  vehicle,
  selectedTest,
}: Props) {
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (!busy) {
      setTick(0)
      return
    }
    const id = window.setInterval(() => setTick((n) => n + 1), 420)
    return () => window.clearInterval(id)
  }, [busy])

  const checks = useMemo(() => result?.tests ?? result?.checks ?? [], [result])
  const logs = useMemo(
    () => (busy ? liveLogs(tick) : resultLogs(result, checks, orbit, vehicle)),
    [busy, checks, orbit, result, tick, vehicle],
  )
  const traces = useMemo(() => parameterTrace(result, profile, annotations, orbit, vehicle), [
    annotations,
    orbit,
    profile,
    result,
    vehicle,
  ])
  const selectedProgramLogs = useMemo(
    () => buildCheckProgramLogs(selectedTest ?? null, result),
    [result, selectedTest],
  )
  const curves = useMemo(() => compactCurves(result, checks, profile, orbit, vehicle), [
    checks,
    orbit,
    profile,
    result,
    vehicle,
  ])

  return (
    <section className="analysis-console">
      <div className="launch-section-head">
        <span className="launch-section-title">Analysis Console</span>
        <span className="mono muted">
          {busy ? 'streaming solver trace' : result ? 'trace frozen at verdict' : 'waiting for run'}
        </span>
      </div>

      <div className="analysis-console-grid">
        <div className="analysis-log-panel">
          <div className="analysis-log-title mono">ENGINEERING LOG STREAM</div>
          <div className="analysis-log-lines" role="log" aria-live="polite">
            {logs.map((line) => (
              <div
                key={line.key}
                className={`analysis-log-line analysis-log-${line.level}`}
                title={`${line.time} ${line.code} ${line.text}`}
              >
                <span className="analysis-log-time">{line.time}</span>
                <span className="analysis-log-code">{line.code}</span>
                <span className="analysis-log-text">{line.text}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="analysis-trace-panel">
          <div className="analysis-log-title mono">
            {selectedTest ? `${selectedTest.id} PROGRAM LOG` : 'SELECTED TEST PROGRAM LOG'}
          </div>
          <div className="analysis-program-lines">
            {selectedProgramLogs.map((line, i) => (
              <div key={`${line}-${i}`} className="analysis-program-line mono">
                <span>{String(i + 1).padStart(2, '0')}</span>
                <code>{line}</code>
              </div>
            ))}
          </div>
          <div className="analysis-log-title mono">PARAMETER TRACEABILITY</div>
          <dl className="analysis-trace-list">
            {traces.map((item) => (
              <div
                key={item.label}
                className={item.level === 'warn' ? 'analysis-trace-warn' : ''}
                title={`${item.label}: ${item.value}`}
              >
                <dt>{item.label}</dt>
                <dd>{item.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      <div className="analysis-curve-strip" aria-label="Compact simulation curve visualizations">
        {curves.map((curve) => (
          <div key={curve.label} className="analysis-curve-card">
            <span className="analysis-curve-label">{curve.label}</span>
            <svg viewBox="0 0 120 34" role="img" aria-label={curve.label}>
              <polyline points={curve.points} fill="none" stroke={curve.color} strokeWidth="1.6" />
              <line x1="4" y1="28" x2="116" y2="28" stroke="rgba(130,160,178,0.22)" />
              {curve.limitX != null ? (
                <line x1={curve.limitX} y1="5" x2={curve.limitX} y2="30" stroke="var(--accent-orange)" strokeDasharray="2 2" />
              ) : null}
            </svg>
            <span className="analysis-curve-value mono">{curve.value}</span>
          </div>
        ))}
      </div>
    </section>
  )
}

function liveLogs(tick: number) {
  const count = Math.min(LIVE_PROGRAM.length, Math.max(3, tick + 3))
  return LIVE_PROGRAM.slice(0, count).map((text, i) => ({
    key: `live-${i}`,
    time: `T+${(i * 0.18).toFixed(2)}s`,
    code: i < count - 1 ? 'RUN' : 'ITER',
    level: 'info' as const,
    text,
  }))
}

function resultLogs(
  result: LaunchCompatResult | null,
  checks: LaunchCompatCheck[],
  orbit: string,
  vehicle?: LaunchVehicleMeta,
) {
  if (!result) {
    return [
      {
        key: 'idle-0',
        time: 'T+0.00s',
        code: 'IDLE',
        level: 'info' as const,
        text: `select vehicle and run AEGIS-LV for ${orbit.toUpperCase()} trace`,
      },
    ]
  }

  const priority = [...checks].sort((a, b) => statusRank(b) - statusRank(a))
  return [
    {
      key: 'ctx',
      time: 'T+0.00s',
      code: 'INIT',
      level: 'info' as const,
      text: `${result.engine_name ?? 'AEGIS-LV'} / ${result.engine_version ?? 'launch_physics_v2'} vehicle=${result.vehicle_name ?? vehicle?.name ?? result.vehicle_id}`,
    },
    {
      key: 'mass',
      time: 'T+0.11s',
      code: 'MASS',
      level: result.payload_mass_kg > 0 ? 'info' as const : 'warn' as const,
      text: `payload=${result.payload_mass_kg.toFixed(2)} kg source=${result.mass_source || 'missing'} capacity=${result.capacity_kg.toFixed(0)} kg margin=${result.mass_margin_pct.toFixed(2)}%`,
    },
    ...priority.map((check, i) => {
      const status = check.test_status ?? check.status
      return {
        key: check.id,
        time: `T+${(0.24 + i * 0.09).toFixed(2)}s`,
        code: status.toUpperCase(),
        level: status === 'pass' ? 'info' as const : status === 'warn' ? 'warn' as const : 'crit' as const,
        text: `${check.id}: ${check.value} <= ${check.limit}; MS=${check.margin_of_safety?.toFixed(3) ?? 'n/a'}; ${check.detail}`,
      }
    }),
    {
      key: 'verdict',
      time: 'T+1.18s',
      code: result.verdict ?? result.overall_status,
      level: result.verdict === 'GO' ? 'info' as const : 'crit' as const,
      text: `verdict=${result.verdict ?? result.overall_status}; blocked=${checks.filter((c) => (c.test_status ?? c.status) === 'blocked').length}; score=${result.overall_score}%`,
    },
  ]
}

function parameterTrace(
  result: LaunchCompatResult | null,
  profile: SatelliteProfile,
  annotations: PartAnnotation[],
  orbit: string,
  vehicle?: LaunchVehicleMeta,
) {
  const mass = result?.payload_mass_kg || profile.mass_kg
  const massAnnotated = annotations.filter((a) => typeof a.mass_kg === 'number' && a.mass_kg > 0).length
  return [
    { label: 'Target orbit', value: orbit.toUpperCase() },
    { label: 'Launch vehicle', value: result?.vehicle_name ?? vehicle?.name ?? 'not selected' },
    { label: 'Vehicle data rev', value: result?.vehicle_data_rev ?? 'pending run' },
    { label: 'Mass input', value: mass ? `${Number(mass).toFixed(2)} kg` : 'DATA REQUIRED', level: mass ? 'info' : 'warn' },
    { label: 'Annotated masses', value: `${massAnnotated}/${annotations.length || 0} parts` },
    { label: 'CG lateral X/Y/Z', value: `${profile.cg_x_mm ?? '—'} / ${profile.cg_y_mm ?? '—'} / ${profile.cg_z_mm ?? '—'} mm` },
    { label: 'MOI Ixx/Iyy/Izz', value: `${profile.moi_ixx_kgm2 ?? '—'} / ${profile.moi_iyy_kgm2 ?? '—'} / ${profile.moi_izz_kgm2 ?? '—'} kgm2` },
    { label: 'Loads provenance', value: 'bundled MPE + uploaded PSD/SRS overrides' },
    { label: 'Penalty model', value: 'BLOCKED gates score 0 and force NO-GO' },
  ]
}

function compactCurves(
  result: LaunchCompatResult | null,
  checks: LaunchCompatCheck[],
  profile: SatelliteProfile,
  orbit: string,
  vehicle?: LaunchVehicleMeta,
) {
  const capacity = result?.capacity_kg ?? (orbit === 'gto' ? vehicle?.gto_capacity_kg : vehicle?.leo_capacity_kg) ?? 1
  const mass = result?.payload_mass_kg ?? Number(profile.mass_kg || 0)
  const modal = checks.find((c) => c.id === 'modal_lateral' || c.id === 'modal_axial')
  const stress = result?.stress_field?.min_margin_of_safety
  const thermal = checks.find((c) => c.category === 'thermal')
  return [
    {
      label: 'payload/orbit',
      points: spark([capacity * 1.0, capacity * 0.82, capacity * 0.55, capacity * 0.32], 4),
      value: `${mass.toFixed(0)} / ${capacity.toFixed(0)} kg`,
      color: '#82a6b8',
      limitX: Math.min(116, 4 + (mass / Math.max(capacity, 1)) * 112),
    },
    {
      label: 'modal floor',
      points: spark([0.3, 0.5, 0.42, Number(modal?.margin_of_safety ?? 0.2) + 0.5], 0),
      value: modal ? `MS ${modal.margin_of_safety?.toFixed(2) ?? 'n/a'}` : 'blocked',
      color: 'var(--cyan)',
    },
    {
      label: 'structural MS',
      points: spark([0.12, 0.32, 0.27, Number(stress ?? -0.2) + 0.5], 0),
      value: stress == null ? 'data required' : stress.toFixed(2),
      color: stress == null || stress < 0 ? 'var(--accent-orange)' : '#82a6b8',
    },
    {
      label: 'thermal response',
      points: spark([0.18, 0.45, 0.61, Number(thermal?.margin_of_safety ?? 0.1) + 0.5], 0),
      value: thermal ? `MS ${thermal.margin_of_safety?.toFixed(2) ?? 'n/a'}` : 'pending',
      color: 'var(--accent-orange)',
    },
  ]
}

function spark(values: number[], floor: number) {
  const min = Math.min(...values, floor)
  const max = Math.max(...values, min + 1)
  return values
    .map((v, i) => {
      const x = 4 + (i / Math.max(values.length - 1, 1)) * 112
      const y = 28 - ((v - min) / (max - min || 1)) * 22
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}

function statusRank(check: LaunchCompatCheck) {
  const status = check.test_status ?? check.status
  if (status === 'fail' || status === 'blocked') return 3
  if (status === 'warn') return 2
  return 1
}
