import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import {
  formatApiError,
  getDiagram,
  getProject,
  imageUrl,
  openProjectEvents,
  queueParse,
  uploadSheetCsv,
} from '../api/client'
import type { Diagram, DiagramNode, ProjectMeta, WsEvent } from '../api/types'
import { IntegrationTerminal } from '../components/IntegrationTerminal'
import { GraphViewWithProvider } from '../components/GraphView'
import { ImageOverlay } from '../components/ImageOverlay'
import { LaunchCompatPanel } from '../components/LaunchCompatPanel'
import { NodeInspector } from '../components/NodeInspector'
import { SimulatePanel } from '../components/SimulatePanel'
import { useSelectionStore } from '../state/project'

const SUBSYSTEMS = [
  'Propulsion',
  'Avionics',
  'Solar arrays',
  'Payload',
  'Comms',
  'ADCS',
  'Batteries',
  'Structure',
] as const

export function ProjectView() {
  const { projectId = '' } = useParams()
  const [search, setSearch] = useSearchParams()
  const [meta, setMeta] = useState<ProjectMeta | null>(null)
  const [diagram, setDiagram] = useState<Diagram | null>(null)
  const [mainTab, setMainTab] = useState<'image' | 'graph'>('image')
  const [bottomTab, setBottomTab] = useState<'terminal' | 'sim'>('terminal')
  const [events, setEvents] = useState<string[]>([])
  const [parseErr, setParseErr] = useState<string | null>(null)
  const [pageReady, setPageReady] = useState(false)
  const [pageError, setPageError] = useState<string | null>(null)

  const setSel = useSelectionStore((s) => s.setSelected)
  const setStoreDiagram = useSelectionStore((s) => s.setDiagram)
  const selectedId = useSelectionStore((s) => s.selectedNodeId)

  useEffect(() => {
    const n = search.get('node')
    if (n && n !== selectedId) {
      setSel(n)
    }
  }, [projectId, search, setSel, selectedId])

  useEffect(() => {
    const cur = search.get('node')
    if ((cur ?? null) === (selectedId ?? null)) return
    const next = new URLSearchParams(search)
    if (selectedId) next.set('node', selectedId)
    else next.delete('node')
    setSearch(next, { replace: true })
  }, [selectedId, projectId, search, setSearch])

  const refreshMeta = useCallback(async () => {
    const m = await getProject(projectId)
    setMeta(m)
  }, [projectId])

  const refreshDiagram = useCallback(async () => {
    try {
      const d = await getDiagram(projectId)
      setDiagram(d)
      setStoreDiagram(d)
      setParseErr(null)
    } catch {
      setDiagram(null)
      setStoreDiagram(null)
    }
  }, [projectId, setStoreDiagram])

  useEffect(() => {
    if (!projectId) {
      setPageError('Missing project id in URL.')
      setPageReady(true)
      setMeta(null)
      setDiagram(null)
      return
    }
    let cancelled = false
    setPageReady(false)
    setPageError(null)
    setMeta(null)
    setDiagram(null)
    setEvents([])
    void (async () => {
      try {
        await refreshMeta()
        if (cancelled) return
        await refreshDiagram()
      } catch (e) {
        if (!cancelled) setPageError(formatApiError(e))
      } finally {
        if (!cancelled) setPageReady(true)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [projectId, refreshMeta, refreshDiagram])

  useEffect(() => {
    if (!projectId || !pageReady || pageError) return
    const ws = openProjectEvents(projectId, (msg: WsEvent) => {
      const line = `${msg.phase ?? msg.type}: ${msg.message ?? ''} (${msg.progress ?? ''})`
      setEvents((ev) => [...ev.slice(-40), line])
      if (msg.type === 'error' || msg.phase === 'error') {
        setParseErr(msg.message ?? 'error')
      }
      if (msg.phase === 'done' && (msg.progress ?? 0) >= 1) {
        void refreshMeta()
        void refreshDiagram()
      }
    })
    return () => {
      ws.close()
    }
  }, [projectId, pageReady, pageError, refreshDiagram, refreshMeta])

  const selectedNode: DiagramNode | null = useMemo(() => {
    if (!diagram || !selectedId) return null
    return diagram.nodes.find((n) => n.id === selectedId) ?? null
  }, [diagram, selectedId])

  const statusBadge =
    meta?.parse_status === 'error'
      ? 'badge-err'
      : meta?.parse_status === 'running' || meta?.parse_status === 'queued'
        ? 'badge-warn'
        : ''

  if (!pageReady) {
    return <p className="loading-pulse">Initializing mission workspace…</p>
  }

  if (pageError || !meta) {
    return (
      <div className="card">
        <div className="panel-head">
          <h3 className="panel-title">System fault</h3>
          <span className="hud-chip hud-chip-orange">OFFLINE</span>
        </div>
        <p className="error">{pageError ?? 'Project could not be loaded.'}</p>
        <p className="muted" style={{ marginTop: '0.75rem', lineHeight: 1.6 }}>
          Backend required on port <strong>8000</strong>. Run{' '}
          <code className="mono">make dev</code> from repo root.
        </p>
        <div className="footer-actions">
          <Link to="/" className="btn btn-primary">
            Mission Registry
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="mission-layout">
      <header className="mission-header">
        <Link to="/" className="btn btn-ghost">
          ← Registry
        </Link>
        <h2>{meta.name}</h2>
        <span className={`badge ${statusBadge}`}>{meta.parse_status}</span>
        {meta.last_provider ? (
          <span className="muted mono" style={{ fontSize: '0.75rem' }}>
            {meta.last_provider}
            {meta.last_domain ? ` · ${meta.last_domain}` : ''}
            {meta.handdrawn ? ' · hand-drawn CV' : ''}
          </span>
        ) : null}
        <span className="gpu-indicator">IR pipeline</span>
        {meta.parse_error ? <span className="error">{meta.parse_error}</span> : null}
      </header>

      <div className="mission-grid">
        <section className="panel panel-workspace glass-panel">
          <div className="panel-head">
            <h3 className="panel-title">
              <span className="panel-icon">◇</span> Mission Workspace
            </h3>
            <span className="hud-chip hud-chip-cyan">CANVAS LIVE</span>
          </div>

          <div className="subsystem-tags">
            {SUBSYSTEMS.map((s) => (
              <span key={s} className="subsystem-tag" title="Subsystem layer (visual)">
                {s}
              </span>
            ))}
          </div>

          <div className="tabs">
            <button
              type="button"
              className={`tab ${mainTab === 'image' ? 'tab-active' : ''}`}
              onClick={() => setMainTab('image')}
            >
              Diagram overlay
            </button>
            <button
              type="button"
              className={`tab ${mainTab === 'graph' ? 'tab-active' : ''}`}
              onClick={() => setMainTab('graph')}
            >
              Dependency graph
            </button>
          </div>

          {diagram ? (
            mainTab === 'image' ? (
              <ImageOverlay
                imageSrc={imageUrl(projectId)}
                nodes={diagram.nodes}
                onDropCsv={async (nid, file) => {
                  await uploadSheetCsv(projectId, nid, file)
                  const d = await getDiagram(projectId)
                  setDiagram(d)
                  setStoreDiagram(d)
                  setSel(nid)
                }}
              />
            ) : (
              <GraphViewWithProvider diagram={diagram} />
            )
          ) : (
            <div className="workspace-canvas">
              <span className="canvas-corner">AWAITING PARSE · NO IR</span>
              <img src={imageUrl(projectId)} alt="source" className="canvas-img" />
            </div>
          )}

          <div className="parse-inline" style={{ marginTop: '0.85rem' }}>
            <div className="panel-head" style={{ marginBottom: '0.5rem' }}>
              <h3 className="panel-title" style={{ fontSize: '0.72rem' }}>
                <span className="panel-icon">⚡</span> IR Ingest
              </h3>
            </div>
            <p className="muted" style={{ marginBottom: 8, fontSize: '0.75rem' }}>
              Gemini · auto domain detection
            </p>
            <button
              type="button"
              className="btn btn-primary"
              onClick={async () => {
                setParseErr(null)
                try {
                  await queueParse(projectId)
                  await refreshMeta()
                } catch (e) {
                  setParseErr(formatApiError(e))
                }
              }}
            >
              Execute parse
            </button>
            {parseErr ? <p className="error">{parseErr}</p> : null}
            {events.length ? (
              <pre className="mono log-pre">{events.join('\n')}</pre>
            ) : null}
          </div>
        </section>

        <aside className="panel panel-telemetry">
          <NodeInspector projectId={projectId} node={selectedNode} />
        </aside>

        <section className="panel panel-launch glass-panel">
          <LaunchCompatPanel compact />
        </section>

        <section className="panel panel-sim glass-panel">
          <div className="panel-head">
            <h3 className="panel-title">
              <span className="panel-icon">▣</span> Simulation
            </h3>
          </div>
          {diagram ? (
            <SimulatePanel projectId={projectId} diagram={diagram} embedded />
          ) : (
            <p className="muted">Run parse to enable parameter sweeps and analytic engines.</p>
          )}
        </section>

        <section className="panel panel-terminal terminal-panel glass-panel">
          <div className="terminal-header">
            <div className="terminal-dots">
              <span />
              <span />
              <span />
            </div>
            <span className="terminal-title">vioci-integration — ai copilot</span>
            <div className="tabs" style={{ margin: 0, padding: 2 }}>
              <button
                type="button"
                className={`tab ${bottomTab === 'terminal' ? 'tab-active' : ''}`}
                onClick={() => setBottomTab('terminal')}
              >
                Terminal
              </button>
              <button
                type="button"
                className={`tab ${bottomTab === 'sim' ? 'tab-active' : ''}`}
                onClick={() => setBottomTab('sim')}
                disabled={!diagram}
              >
                Full sim
              </button>
            </div>
          </div>
          <div className="terminal-body">
            {bottomTab === 'terminal' ? (
              <IntegrationTerminal
                projectId={projectId}
                parseStatus={meta.parse_status}
                hasDiagram={!!diagram}
              />
            ) : diagram ? (
              <SimulatePanel projectId={projectId} diagram={diagram} embedded />
            ) : null}
          </div>
        </section>
      </div>
    </div>
  )
}
