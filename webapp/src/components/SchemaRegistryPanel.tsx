import { useCallback, useEffect, useState } from 'react'
import { formatApiError, getSchemaRegistry, refreshSchemaRegistry } from '../api/client'
import type { SchemaRegistryMeta } from '../api/types'
import { SchemaSpreadsheet, type RegistryTableKey } from './SchemaSpreadsheet'
import { useSchemaRegistryTerminalStore } from '../state/schemaRegistryTerminal'

const TABLE_LABELS: Record<RegistryTableKey, string> = {
  components: 'Components',
  dependencies: 'Dependencies',
  properties: 'Properties',
}

type Props = {
  projectId: string
  parseStatus?: string
}

export function SchemaRegistryPanel({ projectId, parseStatus }: Props) {
  const [table, setTable] = useState<RegistryTableKey>('components')
  const [meta, setMeta] = useState<SchemaRegistryMeta | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const terminalSession = useSchemaRegistryTerminalStore((s) => s.sessions[projectId])

  const loadMeta = useCallback(async () => {
    try {
      const doc = await getSchemaRegistry(projectId)
      setMeta({
        updated_at: doc.updated_at,
        parse_status: doc.parse_status,
        last_domain: doc.last_domain,
        node_count: doc.node_count,
        edge_count: doc.edge_count,
        part_count: doc.part_count,
        project_name: doc.project_name,
      })
      setError(null)
    } catch (e) {
      const msg = formatApiError(e)
      if (!msg.includes('404')) setError(msg)
    }
  }, [projectId])

  useEffect(() => {
    void loadMeta()
  }, [loadMeta, parseStatus, refreshKey])

  const onRefresh = async () => {
    try {
      const doc = await refreshSchemaRegistry(projectId)
      setMeta({
        updated_at: doc.updated_at,
        parse_status: doc.parse_status,
        last_domain: doc.last_domain,
        node_count: doc.node_count,
        edge_count: doc.edge_count,
        part_count: doc.part_count,
        project_name: doc.project_name,
      })
      setRefreshKey((k) => k + 1)
      setError(null)
    } catch (e) {
      setError(formatApiError(e))
    }
  }

  return (
    <div className="schema-registry-panel">
      <header className="schema-registry-head">
        <div>
          <h3 className="panel-title">Satellite schema registry</h3>
          <p className="muted schema-registry-sub">
            Edit CSVs in place or run SQL across components, dependencies, and properties.
          </p>
        </div>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => void onRefresh()}>
          Rebuild from IR
        </button>
      </header>

      {meta ? (
        <dl className="schema-registry-stats">
          <div>
            <dt>Updated</dt>
            <dd className="mono">{new Date(meta.updated_at).toLocaleString()}</dd>
          </div>
          <div>
            <dt>Parse</dt>
            <dd>{meta.parse_status}</dd>
          </div>
          <div>
            <dt>Components</dt>
            <dd>{meta.part_count}</dd>
          </div>
          <div>
            <dt>Dependencies</dt>
            <dd>{meta.edge_count}</dd>
          </div>
        </dl>
      ) : null}

      <div className="schema-registry-tabs" role="tablist">
        {(Object.keys(TABLE_LABELS) as RegistryTableKey[]).map((key) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={table === key}
            className={`schema-registry-tab${table === key ? ' active' : ''}`}
            onClick={() => setTable(key)}
          >
            {TABLE_LABELS[key]}
          </button>
        ))}
      </div>

      {error ? <p className="error">{error}</p> : null}

      <SchemaSpreadsheet
        key={`${table}-${refreshKey}-${terminalSession?.updatedAt ?? 0}`}
        projectId={projectId}
        table={table}
        onTableMutated={() => void loadMeta()}
        terminalSql={terminalSession?.sql}
        terminalSqlResult={terminalSession?.result ?? null}
        terminalSqlError={terminalSession?.error}
        terminalSqlUpdatedAt={terminalSession?.updatedAt}
      />
    </div>
  )
}
