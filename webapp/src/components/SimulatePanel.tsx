import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { runSimulate, runSweep } from '../api/client'
import type { Diagram, Quantity } from '../api/types'
import { CHART } from '../theme/charts'

type Props = {
  projectId: string
  diagram: Diagram
  embedded?: boolean
}

function qValue(q: Quantity | null | undefined): number | null {
  if (!q) return null
  return q.value
}

export function SimulatePanel({ projectId, diagram, embedded }: Props) {
  const params = diagram.parameters ?? []
  const [overrides, setOverrides] = useState<Record<string, number>>({})
  const [engine, setEngine] = useState('analytic_rc')
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [sweepData, setSweepData] = useState<Record<string, unknown>[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    const init: Record<string, number> = {}
    for (const p of params) {
      const v = qValue(p.default ?? undefined)
      if (v != null) init[p.name] = v
    }
    setOverrides(init)
  }, [params])

  const debouncedRun = useMemo(() => {
    let t: ReturnType<typeof setTimeout> | undefined
    return (body: Record<string, unknown>) => {
      if (t) clearTimeout(t)
      t = setTimeout(async () => {
        setBusy(true)
        setErr(null)
        try {
          const r = await runSimulate(projectId, engine, body)
          setResult(r as unknown as Record<string, unknown>)
        } catch (e) {
          setErr(e instanceof Error ? e.message : String(e))
        } finally {
          setBusy(false)
        }
      }, 250)
    }
  }, [projectId, engine])

  useEffect(() => {
    if (!params.length) return
    if (!Object.keys(overrides).length) return
    debouncedRun(overrides)
  }, [overrides, debouncedRun, params])

  const chartFromResult = useCallback(() => {
    interface SeriesShape {
      name: string
      values: number[]
    }
    interface DS {
      series?: SeriesShape[]
      axes?: string[]
    }
    if (!result) return null
    const datasets = result.datasets as DS[] | undefined
    const ds = datasets?.[0]
    if (!ds?.series?.length) return null
    const series = ds.series
    const n = Math.max(...series.map((s) => s.values.length), 0)
    const rows: Record<string, number | string>[] = []
    for (let i = 0; i < n; i++) {
      const row: Record<string, number | string> = { i }
      for (const s of series) {
        row[s.name] = s.values[i] ?? NaN
      }
      rows.push(row)
    }
    return { rows, names: series.map((s) => s.name) }
  }, [result])

  const simChart = chartFromResult()
  const firstParam = params[0]?.name

  return (
    <div className={embedded ? '' : 'card'}>
      {!embedded && (
        <p className="muted" style={{ marginTop: 0 }}>
          Real-time parameter tuning · analytic &amp; SPICE engines
        </p>
      )}
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <label className="muted mono" style={{ fontSize: '0.72rem' }}>
          ENGINE
        </label>
        <select
          value={engine}
          onChange={(e) => setEngine(e.target.value)}
          className="select-glass"
        >
          <option value="analytic_rc">analytic_rc</option>
          <option value="ngspice">ngspice</option>
        </select>
        {busy ? <span className="gpu-indicator">computing</span> : null}
      </div>
      {params.length ? (
        params.map((p) => {
          const v = overrides[p.name] ?? qValue(p.default ?? undefined) ?? 0
          const [lo, hi] = p.bounds ?? [v * 0.1, v * 10 + 1]
          return (
            <div key={p.id} style={{ marginBottom: 10 }}>
              <label>
                <span className="mono glow-cyan">{p.name}</span>{' '}
                <span className="muted">{p.default?.unit ?? ''}</span>
              </label>
              <input
                type="range"
                min={lo}
                max={hi}
                step={(hi - lo) / 200 || 0.001}
                value={v}
                onChange={(e) =>
                  setOverrides((o) => ({ ...o, [p.name]: Number.parseFloat(e.target.value) }))
                }
                style={{ width: '100%' }}
              />
              <span className="mono">{v}</span>
            </div>
          )
        })
      ) : (
        <p className="muted">No parameters — use an annotated electrical diagram.</p>
      )}
      {err ? <p className="error">{err}</p> : null}
      {simChart ? (
        <div className="chart-box" style={{ height: embedded ? 160 : 240 }}>
          <ResponsiveContainer>
            <LineChart data={simChart.rows}>
              <CartesianGrid stroke={CHART.grid} strokeDasharray="3 3" />
              <XAxis dataKey="i" stroke={CHART.axis} tick={{ fontSize: 10 }} />
              <YAxis stroke={CHART.axis} tick={{ fontSize: 10 }} />
              <Tooltip
                contentStyle={{
                  background: CHART.tooltipBg,
                  border: `1px solid ${CHART.tooltipBorder}`,
                  borderRadius: 4,
                  fontFamily: 'var(--mono)',
                  fontSize: 11,
                }}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {simChart.names.map((name, idx) => (
                <Line
                  key={name}
                  type="monotone"
                  dataKey={name}
                  dot={false}
                  strokeWidth={2}
                  stroke={CHART.series[idx % CHART.series.length]}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : null}

      {firstParam ? (
        <div className="footer-actions">
          <button
            type="button"
            className="btn"
            onClick={async () => {
              setBusy(true)
              setErr(null)
              try {
                const cur = overrides[firstParam] ?? 1
                const pts = [cur * 0.5, cur, cur * 2, cur * 4].filter((x) => Number.isFinite(x))
                const sw = await runSweep(projectId, engine, { [firstParam]: pts })
                setSweepData(sw as Record<string, unknown>[])
              } catch (e) {
                setErr(e instanceof Error ? e.message : String(e))
              } finally {
                setBusy(false)
              }
            }}
          >
            Sweep {firstParam}
          </button>
        </div>
      ) : null}

      {sweepData?.length ? (
        <div className="chart-box" style={{ height: 160, marginTop: 12 }}>
          <ResponsiveContainer>
            <LineChart
              data={sweepData.map((row, i) => {
                const ov = row.overrides as Record<string, number> | undefined
                const res = row.result as {
                  datasets?: { series?: { name: string; values: number[] }[] }[]
                }
                const v0 = res?.datasets?.[0]?.series
                  ?.find((s) => s.values.length)
                  ?.values.slice(-1)[0]
                return {
                  x: ov?.[firstParam!] ?? i,
                  y: v0,
                }
              })}
            >
              <CartesianGrid stroke={CHART.grid} strokeDasharray="3 3" />
              <XAxis dataKey="x" stroke={CHART.axis} tick={{ fontSize: 10 }} />
              <YAxis stroke={CHART.axis} tick={{ fontSize: 10 }} />
              <Tooltip
                contentStyle={{
                  background: CHART.tooltipBg,
                  border: `1px solid ${CHART.tooltipBorder}`,
                  borderRadius: 4,
                }}
              />
              <Line type="monotone" dataKey="y" stroke={CHART.series[2]} dot strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : null}
    </div>
  )
}
