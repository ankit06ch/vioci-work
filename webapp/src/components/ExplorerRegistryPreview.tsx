import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchExplorerSchemaFile, formatApiError } from '../api/client'
import {
  EXPLORER_CSV_FILE_IDS,
  EXPLORER_JSON_FILE_IDS,
  SCHEMA_EXPORT_FILES,
  type ExplorerSchemaFileId,
} from '../lib/schemaExports'
import { SchemaSpreadsheet, type RegistryTableKey } from './SchemaSpreadsheet'
import { LoadingIndicator } from './LoadingIndicator'

type Props = {
  projectId: string
  fileId: ExplorerSchemaFileId
  converted: boolean
}

function ExplorerJsonPreview({
  projectId,
  fileId,
  converted,
}: {
  projectId: string
  fileId: ExplorerSchemaFileId
  converted: boolean
}) {
  const [raw, setRaw] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const label = SCHEMA_EXPORT_FILES.find((f) => f.id === fileId)?.label ?? fileId

  const formatted = useMemo(() => {
    if (!raw) return ''
    try {
      return JSON.stringify(JSON.parse(raw), null, 2)
    } catch {
      return raw
    }
  }, [raw])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    void (async () => {
      try {
        const text = await fetchExplorerSchemaFile(projectId, fileId)
        if (!cancelled) setRaw(text)
      } catch (e) {
        if (!cancelled) setError(formatApiError(e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [projectId, fileId, converted])

  if (loading) return <LoadingIndicator label={`Loading ${label}…`} size="sm" block />
  if (error) return <p className="error">{error}</p>
  if (!raw) return <p className="muted">File is empty.</p>

  return (
    <div className="explorer-json-preview">
      <pre className="explorer-json-pre mono">{formatted}</pre>
    </div>
  )
}

export function ExplorerRegistryPreview({ projectId, fileId, converted }: Props) {
  if (EXPLORER_JSON_FILE_IDS.has(fileId)) {
    return (
      <div className="explorer-schema-preview">
        <ExplorerJsonPreview projectId={projectId} fileId={fileId} converted={converted} />
        {fileId === 'manifest' ? (
          <Link to={`/projects/${projectId}`} className="btn btn-ghost btn-sm">
            Open workspace registry tab
          </Link>
        ) : null}
      </div>
    )
  }

  if (EXPLORER_CSV_FILE_IDS.has(fileId)) {
    const launchCsv = fileId.startsWith('launch_')
    if (launchCsv) {
      return (
        <div className="explorer-csv-preview">
          <LaunchCsvPreview projectId={projectId} fileId={fileId} converted={converted} />
        </div>
      )
    }
    const label = SCHEMA_EXPORT_FILES.find((f) => f.id === fileId)?.label ?? `${fileId}.csv`
    return (
      <div className="explorer-csv-preview">
        <SchemaSpreadsheet
          projectId={projectId}
          table={fileId as RegistryTableKey}
          title={label}
          previewMode
          key={`${projectId}-${fileId}-${converted}`}
        />
      </div>
    )
  }

  return <p className="muted">Unknown schema file.</p>
}

function LaunchCsvPreview({
  projectId,
  fileId,
  converted,
}: {
  projectId: string
  fileId: ExplorerSchemaFileId
  converted: boolean
}) {
  const [raw, setRaw] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const label = SCHEMA_EXPORT_FILES.find((f) => f.id === fileId)?.label ?? fileId

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    void (async () => {
      try {
        const text = await fetchExplorerSchemaFile(projectId, fileId)
        if (!cancelled) setRaw(text)
      } catch (e) {
        if (!cancelled) setError(formatApiError(e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [projectId, fileId, converted])

  if (loading) return <LoadingIndicator label={`Loading ${label}…`} size="sm" block />
  if (error) return <p className="error">{error}</p>

  return <pre className="explorer-csv-pre mono">{raw}</pre>
}
