import { useCallback, useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  createRegistryRow,
  deleteRegistryRow,
  formatApiError,
  patchRegistryRow,
  querySchemaRegistry,
  runRegistrySql,
  schemaRegistryCsvUrl,
} from '../api/client'
import type { SchemaRegistrySqlResult } from '../api/types'
import { IconEnterFullscreen, IconExitFullscreen } from './FullscreenIcons'

export type RegistryTableKey = 'components' | 'dependencies' | 'properties'

type ViewMode = 'sheet' | 'sql'

type Props = {
  projectId: string
  table: RegistryTableKey
  /** @deprecated Prefer previewMode + fullscreen icon */
  startFullscreen?: boolean
  /** Inline preview in explorer (sheet only, compact) */
  previewMode?: boolean
  /** Label in toolbar / full-screen chrome */
  title?: string
  onTableMutated?: () => void
  onExitFullscreen?: () => void
  /** Injected when SQL is run from the integration terminal */
  terminalSql?: string | null
  terminalSqlResult?: SchemaRegistrySqlResult | null
  terminalSqlError?: string | null
  terminalSqlUpdatedAt?: number
}

const SQL_HINTS = [
  'SELECT * FROM components WHERE mass_kg != ""',
  'SELECT source_name, target_name, kind FROM dependencies',
  'SELECT entity_name, property_key, value FROM properties WHERE entity_type = \'component\'',
  'UPDATE components SET mass_kg = \'10\' WHERE node_id = \'n1\'',
  'DELETE FROM properties WHERE property_key = \'notes\' AND value = \'\'',
]

const TABLE_FILE: Record<RegistryTableKey, string> = {
  components: 'components.csv',
  dependencies: 'dependencies.csv',
  properties: 'properties.csv',
}

export function SchemaSpreadsheet({
  projectId,
  table,
  startFullscreen = false,
  previewMode = false,
  title,
  onTableMutated,
  onExitFullscreen,
  terminalSql,
  terminalSqlResult,
  terminalSqlError,
  terminalSqlUpdatedAt,
}: Props) {
  const [fullscreen, setFullscreen] = useState(startFullscreen && !previewMode)

  const exitFullscreen = useCallback(() => {
    setFullscreen(false)
    onExitFullscreen?.()
  }, [onExitFullscreen])
  const [mode, setMode] = useState<ViewMode>('sheet')
  const [columns, setColumns] = useState<string[]>([])
  const [rows, setRows] = useState<Record<string, unknown>[]>([])
  const [total, setTotal] = useState(0)
  const [filter, setFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [savingCell, setSavingCell] = useState<string | null>(null)
  const [sql, setSql] = useState(() => `SELECT * FROM ${table} LIMIT 100`)
  const [sqlResult, setSqlResult] = useState<SchemaRegistrySqlResult | null>(null)
  const [sqlRunning, setSqlRunning] = useState(false)

  const displayTitle = title ?? TABLE_FILE[table]

  useEffect(() => {
    if (!fullscreen) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') exitFullscreen()
    }
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = prev
      window.removeEventListener('keydown', onKey)
    }
  }, [fullscreen, exitFullscreen])

  const loadSheet = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await querySchemaRegistry(projectId, table, undefined, true)
      setColumns(res.columns)
      setRows(res.rows)
      setTotal(res.total)
    } catch (e) {
      setError(formatApiError(e))
    } finally {
      setLoading(false)
    }
  }, [projectId, table])

  useEffect(() => {
    if (mode === 'sheet') void loadSheet()
  }, [mode, loadSheet])

  useEffect(() => {
    setSql((s) => {
      if (/FROM\s+\w+/i.test(s)) {
        return s.replace(/FROM\s+\w+/i, `FROM ${table}`)
      }
      return `SELECT * FROM ${table} LIMIT 100`
    })
  }, [table])

  useEffect(() => {
    if (!terminalSqlUpdatedAt || !terminalSql) return
    setMode('sql')
    setSql(terminalSql)
    setSqlResult(terminalSqlResult ?? null)
    setError(terminalSqlError ?? null)
  }, [terminalSql, terminalSqlResult, terminalSqlError, terminalSqlUpdatedAt])

  const visibleRows = useMemo(() => {
    const needle = filter.trim().toLowerCase()
    return rows
      .map((row, index) => ({ row, index }))
      .filter(({ row }) => {
        if (!needle) return true
        return Object.values(row).some((v) => String(v ?? '').toLowerCase().includes(needle))
      })
  }, [rows, filter])

  const displayColumns = useMemo(() => {
    const seen = new Set(columns)
    const extra: string[] = []
    for (const row of rows) {
      for (const k of Object.keys(row)) {
        if (!seen.has(k)) {
          seen.add(k)
          extra.push(k)
        }
      }
    }
    return [...columns, ...extra]
  }, [columns, rows])

  const saveCell = async (rowIndex: number, col: string, value: string) => {
    const key = `${rowIndex}:${col}`
    setSavingCell(key)
    try {
      await patchRegistryRow(projectId, table, rowIndex, { [col]: value })
      onTableMutated?.()
    } catch (e) {
      setError(formatApiError(e))
      void loadSheet()
    } finally {
      setSavingCell(null)
    }
  }

  const onDeleteRow = async (rowIndex: number) => {
    if (!confirm(`Delete row ${rowIndex + 1}?`)) return
    try {
      await deleteRegistryRow(projectId, table, rowIndex)
      await loadSheet()
      onTableMutated?.()
    } catch (e) {
      setError(formatApiError(e))
    }
  }

  const onAddRow = async () => {
    const values: Record<string, string> = {}
    for (const c of displayColumns) values[c] = ''
    try {
      await createRegistryRow(projectId, table, values)
      await loadSheet()
      onTableMutated?.()
    } catch (e) {
      setError(formatApiError(e))
    }
  }

  const onRunSql = async () => {
    setSqlRunning(true)
    setError(null)
    setSqlResult(null)
    try {
      const res = await runRegistrySql(projectId, sql)
      setSqlResult(res)
      if (res.mutated) {
        await loadSheet()
        onTableMutated?.()
      }
    } catch (e) {
      setError(formatApiError(e))
    } finally {
      setSqlRunning(false)
    }
  }

  const downloadUrl = schemaRegistryCsvUrl(projectId, table)

  const panel = (
    <div
      className={`schema-spreadsheet ${fullscreen ? 'schema-spreadsheet--fullscreen' : ''}${previewMode ? ' schema-spreadsheet--preview' : ''}`}
    >
      <div className="schema-spreadsheet-toolbar">
        {previewMode && title ? (
          <span className="schema-spreadsheet-preview-title mono">{title}</span>
        ) : null}
        <div className="schema-spreadsheet-modes" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'sheet'}
            className={mode === 'sheet' ? 'active' : ''}
            onClick={() => setMode('sheet')}
          >
            Sheet
          </button>
          {!previewMode ? (
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'sql'}
              className={mode === 'sql' ? 'active' : ''}
              onClick={() => setMode('sql')}
            >
              SQL
            </button>
          ) : null}
        </div>
        {mode === 'sheet' ? (
          <label className="schema-spreadsheet-filter">
            <span className="sr-only">Filter rows</span>
            <input
              type="search"
              placeholder="Filter…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </label>
        ) : null}
        <div className="schema-spreadsheet-actions">
          {!fullscreen ? (
            <button
              type="button"
              className="btn btn-icon btn-ghost"
              onClick={() => setFullscreen(true)}
              title="Full screen"
              aria-label="Full screen"
            >
              <IconEnterFullscreen />
            </button>
          ) : null}
          <a className="btn btn-ghost btn-sm" href={downloadUrl} download>
            Download CSV
          </a>
          {mode === 'sheet' ? (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => void onAddRow()}>
              + Row
            </button>
          ) : null}
        </div>
      </div>

      {terminalSqlUpdatedAt && terminalSql ? (
        <p className="schema-terminal-badge muted">
          From terminal — edit or re-run below
        </p>
      ) : null}

      {!fullscreen && !previewMode ? (
        <p className="muted schema-spreadsheet-hint">
          Tables: <code className="mono">components</code>, <code className="mono">dependencies</code>,{' '}
          <code className="mono">properties</code>. Terminal: paste SQL or{' '}
          <code className="mono">sql SELECT …</code>
        </p>
      ) : null}

      {error ? <p className="error">{error}</p> : null}

      {mode === 'sql' ? (
        <div className="schema-sql-panel">
          <textarea
            className="schema-sql-input mono"
            spellCheck={false}
            value={sql}
            onChange={(e) => setSql(e.target.value)}
            rows={fullscreen ? 8 : 5}
            aria-label="SQL query"
          />
          <div className="schema-sql-actions">
            <button
              type="button"
              className="btn btn-primary btn-sm"
              disabled={sqlRunning}
              onClick={() => void onRunSql()}
            >
              {sqlRunning ? 'Running…' : 'Run SQL'}
            </button>
            <span className="muted schema-sql-hints">
              {SQL_HINTS.map((h) => (
                <button
                  key={h}
                  type="button"
                  className="schema-sql-example"
                  onClick={() => setSql(h)}
                  title={h}
                >
                  {h.length > 52 ? `${h.slice(0, 52)}…` : h}
                </button>
              ))}
            </span>
          </div>
          {sqlResult?.message ? <p className="muted">{sqlResult.message}</p> : null}
          {sqlResult && sqlResult.columns.length > 0 ? (
            <ResultTable
              columns={sqlResult.columns}
              rows={sqlResult.rows}
              caption={`${sqlResult.row_count} row(s)`}
              fullscreen={fullscreen}
            />
          ) : null}
        </div>
      ) : loading ? (
        <p className="muted">Loading full table…</p>
      ) : (
        <>
          <p className="muted schema-spreadsheet-meta">
            {visibleRows.length} shown · {total} total — click a cell to edit, ✕ to delete row
          </p>
          <div className="schema-spreadsheet-scroll">
            <table className="schema-spreadsheet-table">
              <thead>
                <tr>
                  <th className="schema-row-actions-col" />
                  {displayColumns.map((c) => (
                    <th key={c}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visibleRows.map(({ row, index: ri }) => (
                  <tr key={ri}>
                    <td className="schema-row-actions-col">
                      <button
                        type="button"
                        className="schema-row-delete"
                        title="Delete row"
                        onClick={() => void onDeleteRow(ri)}
                      >
                        ✕
                      </button>
                    </td>
                    {displayColumns.map((col) => {
                      const cellKey = `${ri}:${col}`
                      const val = row[col] == null ? '' : String(row[col])
                      return (
                        <td key={col}>
                          <input
                            className="schema-cell-input mono"
                            value={val}
                            disabled={savingCell === cellKey}
                            onChange={(e) => {
                              const next = e.target.value
                              setRows((prev) => {
                                const copy = [...prev]
                                copy[ri] = { ...copy[ri], [col]: next }
                                return copy
                              })
                            }}
                            onBlur={(e) => {
                              const next = e.target.value
                              const prevVal = row[col] == null ? '' : String(row[col])
                              if (next !== prevVal) void saveCell(ri, col, next)
                            }}
                          />
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )

  if (fullscreen) {
    return createPortal(
      <div className="schema-spreadsheet-overlay" role="dialog" aria-modal aria-label={displayTitle}>
        <header className="schema-spreadsheet-fs-head">
          <div>
            <h2 className="schema-spreadsheet-fs-title">{displayTitle}</h2>
            <p className="muted schema-spreadsheet-fs-sub">
              {projectId.slice(0, 8)}… · Esc to exit
            </p>
          </div>
          <button
            type="button"
            className="btn btn-icon btn-ghost"
            onClick={exitFullscreen}
            title="Exit full screen (Esc)"
            aria-label="Exit full screen"
          >
            <IconExitFullscreen />
          </button>
        </header>
        {panel}
      </div>,
      document.body,
    )
  }

  return panel
}

function ResultTable({
  columns,
  rows,
  caption,
  fullscreen,
}: {
  columns: string[]
  rows: Record<string, unknown>[]
  caption?: string
  fullscreen?: boolean
}) {
  return (
    <div className={`schema-spreadsheet-scroll ${fullscreen ? 'schema-spreadsheet-scroll--fs' : ''}`}>
      {caption ? <p className="muted">{caption}</p> : null}
      <table className="schema-spreadsheet-table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c}>{row[c] == null || row[c] === '' ? '—' : String(row[c])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
