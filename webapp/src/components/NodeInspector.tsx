import { useEffect, useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { fetchSheetRows, fetchSheetSummary, getDiagram, uploadSheetCsv } from '../api/client'
import type { DiagramNode } from '../api/types'
import { CHART } from '../theme/charts'
import { SheetUploader } from './SheetUploader'
import { useSelectionStore } from '../state/project'

type Props = {
  projectId: string
  node: DiagramNode | null
}

function firstNumericColumn(rows: Record<string, unknown>[]): string | null {
  if (!rows.length) return null
  for (const k of Object.keys(rows[0])) {
    const v = rows[0][k]
    if (typeof v === 'number') return k
  }
  return null
}

export function NodeInspector({ projectId, node }: Props) {
  const [rows, setRows] = useState<Record<string, unknown>[]>([])
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    if (!node) {
      setRows([])
      setSummary(null)
      return
    }
    let cancelled = false
    void (async () => {
      try {
        const [r, s] = await Promise.all([
          fetchSheetRows(projectId, node.id, 50),
          fetchSheetSummary(projectId, node.id),
        ])
        if (!cancelled) {
          setRows(r)
          setSummary(s)
          setErr(null)
        }
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e))
      }
    })()
    return () => {
      cancelled = true
    }
  }, [projectId, node])

  if (!node) {
    return (
      <div className="card glass-panel" style={{ height: '100%' }}>
        <div className="panel-head">
          <h3 className="panel-title">
            <span className="panel-icon">◎</span> Telemetry
          </h3>
        </div>
        <p className="muted mono" style={{ fontSize: '0.78rem' }}>
          Hover or select a subsystem on the canvas to view mass, power, thermal, and sheet
          telemetry.
        </p>
      </div>
    )
  }

  const props = node.properties as Record<string, unknown>
  const schema = props.telemetry_schema as
    | { name?: string; unit?: string; dtype?: string }[]
    | undefined
  const chartKey = firstNumericColumn(rows)
  const chartData = chartKey
    ? rows.map((row, i) => ({ i, v: row[chartKey] as number }))
    : []

  const refresh = async () => {
    const [r, s] = await Promise.all([
      fetchSheetRows(projectId, node.id, 50),
      fetchSheetSummary(projectId, node.id),
    ])
    setRows(r)
    setSummary(s)
  }

  const displayName =
    typeof props.display_name === 'string' ? props.display_name : node.label || node.kind

  return (
    <div className="card glass-panel" style={{ height: '100%' }}>
      <div className="panel-head">
        <h3 className="panel-title">
          <span className="panel-icon">◎</span> Component telemetry
        </h3>
        <span className="hud-chip hud-chip-cyan">LIVE</span>
      </div>
      <h3 style={{ margin: '0 0 0.25rem', fontFamily: 'var(--font-display)', fontSize: '1rem' }}>
        {displayName}
      </h3>
      <p className="muted mono" style={{ marginBottom: '0.85rem' }}>
        {node.id}
      </p>

      <h4>Properties</h4>
      <table className="inspector-table">
        <tbody>
          {Object.entries(props)
            .filter(([k]) => k !== 'telemetry_schema')
            .map(([k, v]) => (
              <tr key={k}>
                <th>{k}</th>
                <td className="mono">{JSON.stringify(v)}</td>
              </tr>
            ))}
        </tbody>
      </table>

      {schema?.length ? (
        <>
          <h4>Telemetry schema</h4>
          <table className="inspector-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Unit</th>
                <th>Type</th>
              </tr>
            </thead>
            <tbody>
              {schema.map((c, i) => (
                <tr key={i}>
                  <td>{c.name}</td>
                  <td>{c.unit}</td>
                  <td>{c.dtype}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : null}

      <h4>Data sheet</h4>
      {summary && typeof summary.rows === 'number' ? (
        <p className="muted mono">{summary.rows as number} rows ingested</p>
      ) : null}
      {err ? <p className="error">{err}</p> : null}

      <SheetUploader
        label="Attach CSV telemetry"
        onFile={async (file) => {
          await uploadSheetCsv(projectId, node.id, file)
          await refresh()
          const d = await getDiagram(projectId)
          useSelectionStore.getState().setDiagram(d)
        }}
      />

      {chartKey && chartData.length ? (
        <div className="chart-box">
          <ResponsiveContainer>
            <LineChart data={chartData}>
              <CartesianGrid stroke={CHART.grid} strokeDasharray="3 3" />
              <XAxis dataKey="i" stroke={CHART.axis} tick={{ fontSize: 10 }} />
              <YAxis stroke={CHART.axis} tick={{ fontSize: 10 }} />
              <Tooltip
                contentStyle={{
                  background: CHART.tooltipBg,
                  border: `1px solid ${CHART.tooltipBorder}`,
                  borderRadius: 4,
                }}
              />
              <Line
                type="monotone"
                dataKey="v"
                stroke={CHART.series[0]}
                strokeWidth={2}
                dot={false}
                name={chartKey}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : null}

      {rows.length ? (
        <>
          <h4>Recent samples</h4>
          <div style={{ overflowX: 'auto', maxHeight: 200 }}>
            <table className="inspector-table">
              <thead>
                <tr>
                  {Object.keys(rows[0]).map((k) => (
                    <th key={k}>{k}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 12).map((r, i) => (
                  <tr key={i}>
                    {Object.values(r).map((v, j) => (
                      <td key={j}>{String(v)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <p className="muted">No telemetry rows.</p>
      )}
    </div>
  )
}
