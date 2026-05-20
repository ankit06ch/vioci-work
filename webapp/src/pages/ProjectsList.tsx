import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { deleteProject, formatApiError, imageUrl, listProjects } from '../api/client'
import type { ProjectMeta } from '../api/types'

function statusClass(status: string) {
  if (status === 'error') return 'badge-err'
  if (status === 'running' || status === 'queued') return 'badge-warn'
  return ''
}

export function ProjectsList() {
  const [rows, setRows] = useState<ProjectMeta[] | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const r = await listProjects()
        if (!cancelled) setRows(r)
      } catch (e) {
        if (!cancelled) setErr(formatApiError(e))
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  if (err) {
    return (
      <div className="card">
        <div className="panel-head">
          <h3 className="panel-title">Link fault</h3>
          <span className="hud-chip hud-chip-orange">API DOWN</span>
        </div>
        <p className="error">{err}</p>
        <p className="muted">
          Run <code className="mono">make dev</code> for API + UI proxy.
        </p>
      </div>
    )
  }

  if (!rows) {
    return <p className="loading-pulse">Scanning mission registry…</p>
  }

  return (
    <div>
      <header className="page-header">
        <h2>Mission Registry</h2>
        <p className="muted">
          Active diagram missions · select to open integration workspace
        </p>
      </header>

      {!rows.length ? (
        <div className="card">
          <p className="muted">No missions in registry.</p>
          <div className="footer-actions">
            <Link to="/upload" className="btn btn-primary">
              Open Ingest Pipeline
            </Link>
          </div>
        </div>
      ) : (
        <div className="proj-list">
          {rows.map((p) => (
            <div key={p.id} className="proj-row card">
              <Link to={`/projects/${p.id}`}>
                <img
                  src={imageUrl(p.id)}
                  alt=""
                  onError={(e) => {
                    ;(e.target as HTMLImageElement).style.visibility = 'hidden'
                  }}
                />
              </Link>
              <div style={{ flex: 1, minWidth: 0 }}>
                <Link to={`/projects/${p.id}`}>
                  <strong style={{ fontFamily: 'var(--font-display)' }}>{p.name}</strong>
                </Link>
                <div className="muted" style={{ marginTop: 4 }}>
                  <span className={`badge ${statusClass(p.parse_status)}`}>
                    {p.parse_status}
                  </span>{' '}
                  <span className="mono" style={{ fontSize: '0.72rem' }}>
                    {p.last_provider ? `${p.last_provider} · ` : ''}
                    {p.last_domain ?? '—'}
                  </span>
                </div>
              </div>
              <Link to={`/projects/${p.id}`} className="btn btn-primary">
                Open workspace
              </Link>
              <button
                type="button"
                className="btn btn-ghost"
                title="Delete project"
                onClick={async () => {
                  if (!confirm('Delete this mission and all data?')) return
                  await deleteProject(p.id)
                  setRows((cur) => (cur ?? []).filter((x) => x.id !== p.id))
                }}
              >
                Purge
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
