import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  createFolder,
  deleteFolder,
  deleteProject,
  formatApiError,
  imageUrl,
  listFolders,
  listProjects,
  moveProjectToFolder,
  openProjectEvents,
  queueParse,
  uploadProjects,
} from '../api/client'
import type { ProjectMeta, SchemaFolder, WsEvent } from '../api/types'
import { ExplorerTree } from '../components/ExplorerTree'

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

  const onUpload = useCallback(
    async (files: FileList | File[] | null) => {
      const list = files ? Array.from(files) : []
      if (!list.length) return
      setBusy(true)
      setErr(null)
      try {
        const created = await uploadProjects(list, selectedFolderId)
        await refresh()
        if (created.length) setSelectedId(created[0].id)
      } catch (e) {
        setErr(formatApiError(e))
      } finally {
        setBusy(false)
      }
    },
    [refresh, selectedFolderId],
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
    setConverting(true)
    setParseLog([])
    setErr(null)
    try {
      await queueParse(selected.id)
      setRows((cur) =>
        (cur ?? []).map((r) =>
          r.id === selected.id ? { ...r, parse_status: 'queued' as const } : r,
        ),
      )
      wsRef.current?.close()
      const ws = openProjectEvents(selected.id, (ev: WsEvent) => {
        const line = ev.message
          ? `${ev.phase ?? ev.type}: ${ev.message}`
          : `${ev.type}${ev.progress != null ? ` (${Math.round(ev.progress * 100)}%)` : ''}`
        setParseLog((prev) => [...prev.slice(-40), line])
        if (ev.type === 'error' || (ev.phase === 'done' && ev.progress === 1)) {
          void refresh()
        }
      })
      wsRef.current = ws
      ws.onclose = () => {
        setConverting(false)
        wsRef.current = null
        void refresh()
      }
    } catch (e) {
      setErr(formatApiError(e))
      setConverting(false)
    }
  }, [selected, refresh])

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

  if (err && !rows) {
    return (
      <div className="card">
        <p className="error">{err}</p>
        <p className="muted">Run `make dev` so the API is available on port 8000.</p>
      </div>
    )
  }

  const uploadTarget =
    selectedFolderId != null
      ? folders.find((f) => f.id === selectedFolderId)?.name ?? 'folder'
      : 'schematics'

  return (
    <div
      className={`file-explorer ${drag ? 'file-explorer-drag' : ''}`}
      onDragOver={(e) => {
        e.preventDefault()
        setDrag(true)
      }}
      onDragLeave={(e) => {
        if (e.currentTarget === e.target) setDrag(false)
      }}
      onDrop={(e) => {
        e.preventDefault()
        setDrag(false)
        void onUpload(e.dataTransfer.files)
      }}
    >
      <header className="page-header explorer-header">
        <div>
          <h2>Schematic Explorer</h2>
          <p className="muted">
            Organize schematics in folders, convert to machine-readable graphs, open the workspace
          </p>
        </div>
        <div className="explorer-toolbar">
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy}
            onClick={() => inputRef.current?.click()}
          >
            {busy ? 'Uploading…' : `Upload to ${uploadTarget}`}
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
      </header>

      {err ? <p className="error explorer-err">{err}</p> : null}

      <div className="explorer-layout card">
        <aside className="explorer-tree" aria-label="Schematic files">
          <div className="explorer-tree-head">
            <span className="mono">PATH</span>
            <div className="explorer-tree-head-actions">
              <button
                type="button"
                className="btn btn-ghost explorer-new-folder-btn"
                onClick={() => setCreatingFolder((c) => !c)}
              >
                {creatingFolder ? 'Cancel' : '+ Folder'}
              </button>
              <span className="muted">{rows?.length ?? '…'} files</span>
            </div>
          </div>

          {!rows ? (
            <p className="loading-pulse explorer-loading">Loading registry…</p>
          ) : (
            <ExplorerTree
              folders={folders}
              projects={rows}
              selectedProjectId={selectedId}
              selectedFolderId={selectedFolderId}
              onSelectProject={setSelectedId}
              onSelectFolder={setSelectedFolderId}
              onOpenProject={(id) => nav(`/projects/${id}`)}
              onCreateFolder={(name, parentId) => void onCreateFolder(name, parentId)}
              onDeleteFolder={(id) => void onDeleteFolder(id)}
              onMoveProject={(pid, fid) => void onMoveProject(pid, fid)}
              statusClass={statusClass}
              statusLabel={statusLabel}
              creatingFolder={creatingFolder}
              onCancelCreateFolder={() => setCreatingFolder(false)}
            />
          )}
        </aside>

        <section className="explorer-detail">
          {!selected ? (
            <div className="explorer-detail-empty">
              <p className="muted">Select a schematic or drop files anywhere to upload.</p>
              <div className="explorer-drop-hint">
                <span className="mono">image/* · PDF</span>
              </div>
            </div>
          ) : (
            <>
              <div className="explorer-detail-head">
                <div>
                  <h3>{selected.name}</h3>
                  <p className="muted mono" style={{ fontSize: '0.72rem' }}>
                    {selected.id}
                    {selected.folder_id
                      ? ` · ${folders.find((f) => f.id === selected.folder_id)?.name ?? 'folder'}`
                      : ''}
                  </p>
                </div>
                <span className={`badge ${statusClass(selected)}`}>{statusLabel(selected)}</span>
              </div>

              <div className="explorer-preview">
                <img src={imageUrl(selected.id)} alt="" />
              </div>

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
                    : converting || selected.parse_status === 'running'
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

      {drag ? <div className="explorer-drag-overlay">Drop schematics to upload</div> : null}
    </div>
  )
}
