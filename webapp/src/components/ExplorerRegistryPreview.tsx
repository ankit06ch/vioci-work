import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getSchemaRegistry, formatApiError } from '../api/client'
import type { ExplorerSchemaFileId } from '../lib/schemaExports'
import { SchemaSpreadsheet, type RegistryTableKey } from './SchemaSpreadsheet'
import { LoadingIndicator } from './LoadingIndicator'

type Props = {
  projectId: string
  fileId: ExplorerSchemaFileId
  converted: boolean
}

const FILE_LABELS: Record<Exclude<ExplorerSchemaFileId, 'manifest'>, string> = {
  components: 'components.csv',
  dependencies: 'dependencies.csv',
  properties: 'properties.csv',
}

export function ExplorerRegistryPreview({ projectId, fileId, converted }: Props) {
  const [manifestSummary, setManifestSummary] = useState<string | null>(null)
  const [loading, setLoading] = useState(fileId === 'manifest')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (fileId !== 'manifest') return
    let cancelled = false
    setLoading(true)
    void (async () => {
      try {
        const doc = await getSchemaRegistry(projectId)
        if (cancelled) return
        setManifestSummary(
          `${doc.part_count} components · ${doc.edge_count} dependencies · updated ${new Date(doc.updated_at).toLocaleString()}`,
        )
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

  if (fileId === 'manifest') {
    if (loading) return <LoadingIndicator label="Loading manifest…" size="sm" block />
    if (error) return <p className="error">{error}</p>
    return (
      <div className="explorer-schema-preview">
        <p className="muted">{manifestSummary}</p>
        <Link to={`/projects/${projectId}`} className="btn btn-ghost btn-sm">
          Open workspace registry tab
        </Link>
      </div>
    )
  }

  const label = FILE_LABELS[fileId]

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
