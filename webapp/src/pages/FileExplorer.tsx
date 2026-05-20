import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  createFolder,
  deleteFolder,
  deleteProject,
  formatApiError,
  listFolders,
  listProjects,
  moveProjectToFolder,
  openProjectEvents,
  queueParse,
  refreshSchemaRegistry,
  uploadProjects,
} from '../api/client'
import type { ProjectMeta, SchemaFolder, WsEvent } from '../api/types'
import { ExplorerRegistryPreview } from '../components/ExplorerRegistryPreview'
import { ExplorerTree } from '../components/ExplorerTree'
import { LoadingIndicator } from '../components/LoadingIndicator'
import { ProjectImage } from '../components/ProjectImage'
import {
  SCHEMA_EXPORT_FILES,
  type ExplorerSchemaFileId,
} from '../lib/schemaExports'
import { schemaRegistryCsvUrl } from '../api/client'

const ACCEPT = 'image/png,image/jpeg,image/webp,image/gif,application/pdf,.pdf'

function extLabel(name: string): string {
  const i = name.lastIndexOf('.')
  return i >= 0 ? name.slice(i + 1).toUpperCase() : 'IMG'
}

function statusLabel(p: ProjectMeta): string {
  if (p.parse_status === 'done' && p.has_diagram) return 'Converted'
  if (p.parse_status === 'error') return 'Failed'
  if (p.parse_status === 'running' || p.parse_status === 'queued') return 'Converting…'
  return 'Ready'
}

function statusClass(p: ProjectMeta): string {
  if (p.parse_status === 'error') return 'explorer-status-err'
  if (p.parse_status === 'done' && p.has_diagram) return 'explorer-status-ok'
  if (p.parse_status === 'running' || p.parse_status === 'queued') return 'explorer-status-busy'
  return 'explorer-status-idle'
}

function formatWhen(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

export function FileExplorer() {
  const nav = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const [rows, setRows] = useState<ProjectMeta[] | null>(null)
  const [folders, setFolders] = useState<SchemaFolder[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selectedSchemaFile, setSelectedSchemaFile] = useState<ExplorerSchemaFileId | null>(
    null,
  )
  const [schemaExpanded, setSchemaExpanded] = useState<Record<string, boolean>>({})
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null)
  const [creatingFolder, setCreatingFolder] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [drag, setDrag] = useState(false)
  const [parseLog, setParseLog] = useState<string[]>([])
  const [converting, setConverting] = useState(false)

  const selected = useMemo(
    () => rows?.find((r) => r.id === selectedId) ?? null,
    [rows, selectedId],
  )

  const refresh = useCallback(async () => {
    const [r, f] = await Promise.all([listProjects(), listFolders()])
    setRows(r)
    setFolders(f)
    setSelectedId((cur) => {
      if (cur && r.some((x) => x.id === cur)) return cur
      return r[0]?.id ?? null
    })
  }, [])

  useEffect(() => {
    if (!selected?.has_diagram || selected.has_schema_registry) return
    void (async () => {
      try {
        await refreshSchemaRegistry(selected.id)
        await refresh()
        setSchemaExpanded((prev) => ({ ...prev, [selected.id]: true }))
      } catch {
        /* optional backfill for projects converted before registry existed */
      }
    })()
  }, [selected?.id, selected?.has_diagram, selected?.has_schema_registry, refresh])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const [r, f] = await Promise.all([listProjects(), listFolders()])
        if (!cancelled) {
          setRows(r)
          setFolders(f)
          setSelectedId(r[0]?.id ?? null)
        }
      } catch (e) {
        if (!cancelled) setErr(formatApiError(e))
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    return () => {
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!rows?.some((r) => r.parse_status === 'running' || r.parse_status === 'queued')) return
    const t = setInterval(() => {
      void refresh().catch(() => {})
    }, 2500)
    return () => clearInterval(t)
  }, [rows, refresh])

  const attachParseEvents = useCallback(
    (projectId: string) => {
      setConverting(true)
      setParseLog([])
      wsRef.current?.close()
      const ws = openProjectEvents(projectId, (ev: WsEvent) => {
        const line = ev.message
          ? `${ev.phase ?? ev.type}: ${ev.message}`
          : `${ev.type}${ev.progress != null ? ` (${Math.round(ev.progress * 100)}%)` : ''}`
        setParseLog((prev) => [...prev.slice(-40), line])
        if (ev.type === 'error' || (ev.phase === 'done' && ev.progress === 1)) {
          setSchemaExpanded((prev) => ({ ...prev, [projectId]: true }))
          setSelectedSchemaFile('dependencies')
          void refresh()
        }
      })
      wsRef.current = ws
      ws.onclose = () => {
        setConverting(false)
        wsRef.current = null
        void refresh()
      }
    },
    [refresh],
  )

  const onUpload = useCallback(
    async (files: FileList | File[] | null, folderId: string | null = selectedFolderId) => {
      const list = files ? Array.from(files) : []
      if (!list.length) return
      setBusy(true)
      setErr(null)
      try {
        const created = await uploadProjects(list, folderId)
        await refresh()
        if (created.length) {
          const firstId = created[0].id
          setSelectedId(firstId)
          setSchemaExpanded((prev) => ({ ...prev, [firstId]: true }))
          setSelectedSchemaFile(null)
          setRows((cur) =>
            (cur ?? []).map((r) =>
              created.some((p) => p.id === r.id)
                ? { ...r, parse_status: 'queued' as const }
                : r,
            ),
          )
          attachParseEvents(firstId)
        }
      } catch (e) {
        setErr(formatApiError(e))
      } finally {
        setBusy(false)
      }
    },
    [refresh, selectedFolderId, attachParseEvents],
  )

  const onCreateFolder = useCallback(
    async (name: string, parentId: string | null) => {
      setErr(null)
      try {
        const f = await createFolder(name, parentId)
        await refresh()
        setSelectedFolderId(f.id)
      } catch (e) {
        setErr(formatApiError(e))
      }
    },
    [refresh],
  )

  const onDeleteFolder = useCallback(
    async (folderId: string) => {
      try {
        await deleteFolder(folderId)
        if (selectedFolderId === folderId) setSelectedFolderId(null)
        await refresh()
      } catch (e) {
        setErr(formatApiError(e))
      }
    },
    [refresh, selectedFolderId],
  )

  const onMoveProject = useCallback(
    async (projectId: string, folderId: string | null) => {
      try {
        await moveProjectToFolder(projectId, folderId)
        await refresh()
      } catch (e) {
        setErr(formatApiError(e))
      }
    },
    [refresh],
  )

  const onConvert = useCallback(async () => {
    if (!selected) return
    setErr(null)
    try {
      await queueParse(selected.id)
      setRows((cur) =>
        (cur ?? []).map((r) =>
          r.id === selected.id ? { ...r, parse_status: 'queued' as const } : r,
        ),
      )
      attachParseEvents(selected.id)
    } catch (e) {
      setErr(formatApiError(e))
      setConverting(false)
    }
  }, [selected, refresh, attachParseEvents])

  const onDelete = useCallback(async () => {
    if (!selected) return
    if (!confirm(`Remove "${selected.name}" from the explorer?`)) return
    try {
      await deleteProject(selected.id)
      const next = (rows ?? []).filter((r) => r.id !== selected.id)
      setRows(next)
      setSelectedId(next[0]?.id ?? null)
    } catch (e) {
      setErr(formatApiError(e))
    }
  }, [selected, rows])

  const uploadTargetName =
    selectedFolderId != null
      ? folders.find((f) => f.id === selectedFolderId)?.name ?? 'folder'
      : 'schematics'

  if (err && !rows) {
    return (
      <div className="file-explorer-full">
        <p className="error" style={{ padding: '1.5rem' }}>
          {err}
        </p>
        <p className="muted" style={{ padding: '0 1.5rem' }}>
          Run `make dev` so the API is available on port 8000.
        </p>
      </div>
    )
  }

  return (
    <div
      className={`file-explorer-full ${drag ? 'file-explorer-drag' : ''}`}
      onDragOver={(e) => {
        if (e.dataTransfer.types.includes('Files')) {
          e.preventDefault()
          setDrag(true)
        }
      }}
      onDragLeave={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) setDrag(false)
      }}
      onDrop={(e) => {
        if (!e.dataTransfer.files?.length) return
        e.preventDefault()
        setDrag(false)
        void onUpload(e.dataTransfer.files, selectedFolderId)
      }}
    >
      <div className="explorer-chrome">
        <span className="explorer-chrome-title">Schematic Explorer</span>
        <div className="explorer-chrome-actions">
          <span className="muted mono explorer-chrome-hint">
            Drop onto folders · {rows?.length ?? '…'} files
          </span>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => setCreatingFolder((c) => !c)}
          >
            {creatingFolder ? 'Cancel folder' : 'New folder'}
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={busy}
            onClick={() => inputRef.current?.click()}
            title={`Upload to ${uploadTargetName}`}
          >
            {busy ? 'Uploading…' : 'Upload'}
          </button>
          <button type="button" className="btn btn-ghost" disabled={!rows} onClick={() => void refresh()}>
            Refresh
          </button>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept={ACCEPT}
            hidden
            onChange={(e) => void onUpload(e.target.files)}
          />
        </div>
      </div>

      {err ? <p className="error explorer-chrome-err">{err}</p> : null}

      <div className="explorer-body">
        <aside className="explorer-tree-pane" aria-label="Schematic files">
          {!rows ? (
            <LoadingIndicator className="explorer-loading" label="Loading schematics…" size="md" block />
          ) : (
            <ExplorerTree
              folders={folders}
              projects={rows}
              selectedProjectId={selectedId}
              selectedSchemaFile={selectedSchemaFile}
              selectedFolderId={selectedFolderId}
              schemaExpanded={schemaExpanded}
              onToggleSchemaExpand={(pid) =>
                setSchemaExpanded((prev) => ({ ...prev, [pid]: !prev[pid] }))
              }
              onSelectProject={(id) => {
                setSelectedId(id)
                setSelectedSchemaFile(null)
              }}
              onSelectSchemaFile={(id, file) => {
                setSelectedId(id)
                setSelectedSchemaFile(file)
                setSchemaExpanded((prev) => ({ ...prev, [id]: true }))
              }}
              onSelectFolder={setSelectedFolderId}
              onOpenProject={(id) => nav(`/projects/${id}`)}
              onCreateFolder={(name, parentId) => void onCreateFolder(name, parentId)}
              onDeleteFolder={(id) => void onDeleteFolder(id)}
              onMoveProject={(pid, fid) => void onMoveProject(pid, fid)}
              onUploadToFolder={(fid, files) => void onUpload(files, fid)}
              statusClass={statusClass}
              statusLabel={statusLabel}
              creatingFolder={creatingFolder}
              onCancelCreateFolder={() => setCreatingFolder(false)}
            />
          )}
        </aside>

        <section className="explorer-detail-pane">
          {!selected ? (
            <div className="explorer-detail-empty">
              <p className="muted">Select a schematic in the tree, or drop files onto a folder.</p>
              <p className="mono explorer-drop-hint">image/* · PDF</p>
            </div>
          ) : (
            <>
              <div className="explorer-detail-head">
                <div>
                  <h3>
                    {selectedSchemaFile
                      ? SCHEMA_EXPORT_FILES.find((f) => f.id === selectedSchemaFile)?.label ??
                        selectedSchemaFile
                      : selected.name}
                  </h3>
                  <p className="muted mono explorer-detail-id">
                    {selectedSchemaFile
                      ? `${selected.name} · schema export`
                      : selected.folder_id
                        ? folders.find((f) => f.id === selected.folder_id)?.name ?? 'folder'
                        : 'schematics'}
                  </p>
                </div>
                <span className={`badge ${statusClass(selected)}`}>{statusLabel(selected)}</span>
              </div>

              {selectedSchemaFile ? (
                <ExplorerRegistryPreview
                  projectId={selected.id}
                  fileId={selectedSchemaFile}
                  converted={selected.has_diagram}
                />
              ) : (
                <div className="explorer-preview">
                  <ProjectImage projectId={selected.id} alt={selected.name} />
                </div>
              )}

              {(selected.has_schema_registry ||
                (selected.parse_status === 'done' && selected.has_diagram)) &&
              !selectedSchemaFile ? (
                <div className="explorer-schema-exports">
                  <h4 className="explorer-schema-exports-title">Schema exports</h4>
                  <p className="muted explorer-schema-exports-hint">
                    Generated on upload; refreshed when conversion completes. Expand the schematic
                    in the tree to open each file.
                  </p>
                  <ul className="explorer-schema-exports-list">
                    {SCHEMA_EXPORT_FILES.map((f) => (
                      <li key={f.id}>
                        <button
                          type="button"
                          className="explorer-schema-exports-link"
                          onClick={() => {
                            setSelectedSchemaFile(f.id)
                            setSchemaExpanded((prev) => ({ ...prev, [selected.id]: true }))
                          }}
                        >
                          <span>{f.icon}</span> {f.label}
                        </button>
                        {f.id !== 'manifest' ? (
                          <a
                            className="explorer-schema-dl"
                            href={schemaRegistryCsvUrl(
                              selected.id,
                              f.id as 'components' | 'dependencies' | 'properties',
                            )}
                            download
                          >
                            Download
                          </a>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <dl className="explorer-meta">
                <div>
                  <dt>Uploaded</dt>
                  <dd>{formatWhen(selected.created_at)}</dd>
                </div>
                <div>
                  <dt>Format</dt>
                  <dd className="mono">{extLabel(selected.name)}</dd>
                </div>
                <div>
                  <dt>Domain</dt>
                  <dd>{selected.last_domain ?? '—'}</dd>
                </div>
                <div>
                  <dt>Provider</dt>
                  <dd>{selected.last_provider ?? '—'}</dd>
                </div>
                <div>
                  <dt>Schema registry</dt>
                  <dd>{selected.has_schema_registry ? 'On disk' : '—'}</dd>
                </div>
              </dl>

              {selected.parse_error ? (
                <p className="error explorer-parse-err">{selected.parse_error}</p>
              ) : null}

              {parseLog.length > 0 ? (
                <pre className="explorer-log mono">{parseLog.join('\n')}</pre>
              ) : null}

              <div className="explorer-actions">
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={
                    converting ||
                    selected.parse_status === 'running' ||
                    selected.parse_status === 'queued'
                  }
                  onClick={() => void onConvert()}
                >
                  {selected.has_diagram
                    ? 'Re-convert'
                    : converting ||
                        selected.parse_status === 'running' ||
                        selected.parse_status === 'queued'
                      ? 'Converting…'
                      : 'Convert to graph'}
                </button>
                <Link
                  to={`/projects/${selected.id}`}
                  className={`btn ${selected.has_diagram ? 'btn-primary' : 'btn-ghost'}`}
                >
                  Open workspace
                </Link>
                <button type="button" className="btn btn-ghost" onClick={() => void onDelete()}>
                  Delete
                </button>
              </div>
            </>
          )}
        </section>
      </div>

      {drag ? (
        <div className="explorer-drag-overlay">
          Upload to {uploadTargetName}
        </div>
      ) : null}
    </div>
  )
}
