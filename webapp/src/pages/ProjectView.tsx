import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import {
  formatApiError,
  autoDetectAnnotations,
  getAnnotations,
  getDiagram,
  getProject,
  openProjectEvents,
  queueParse,
  uploadSheetCsv,
} from '../api/client'
import type { Diagram, DiagramNode, PartAnnotation, ProjectMeta, WsEvent } from '../api/types'
import { AnnotationPanel } from '../components/AnnotationPanel'
import { WorkspaceDock, type DockTabMeta } from '../components/workspace/WorkspaceDock'
import { useWorkspaceDock } from '../hooks/useWorkspaceDock'
import {
  IntegrationTerminal,
  type WorkspaceTerminalAction,
  type WorkspaceTerminalResult,
} from '../components/IntegrationTerminal'
import { LoadingIndicator } from '../components/LoadingIndicator'
import { GraphViewWithProvider } from '../components/GraphView'
import { ImageOverlay } from '../components/ImageOverlay'
import { ProjectImage } from '../components/ProjectImage'
import { LaunchCompatPanel } from '../components/LaunchCompatPanel'
import { NodeInspector } from '../components/NodeInspector'
import { SimulatePanel } from '../components/SimulatePanel'
import { SubsystemComponentList } from '../components/SubsystemComponentList'
import { annotationsMissingMass, missionReadinessHint } from '../lib/annotations'
import { detectTerminalIntent } from '../lib/terminalIntents'
import type { PendingQuestion, SatelliteProfile } from '../lib/satelliteProfile'
import { WORKSPACE_TAB_CATALOG, WORKSPACE_TAB_LABELS } from '../lib/workspaceTabs'
import { SatelliteProfilePanel } from '../components/SatelliteProfilePanel'
import { SUBSYSTEMS, type Subsystem } from '../lib/subsystems'
import { useSelectionStore } from '../state/project'

type ContentTab = {
  id: string
  label: string
  closable: boolean
  kind: 'view' | 'tool' | 'dynamic'
}

const DEFAULT_OPEN = ['diagram']

export function ProjectView() {
  const { projectId = '' } = useParams()
  const [search, setSearch] = useSearchParams()
  const [meta, setMeta] = useState<ProjectMeta | null>(null)
  const [diagram, setDiagram] = useState<Diagram | null>(null)
  const [diagramLoadErr, setDiagramLoadErr] = useState<string | null>(null)
  const [events, setEvents] = useState<string[]>([])
  const [parseErr, setParseErr] = useState<string | null>(null)
  const [pageReady, setPageReady] = useState(false)
  const [pageError, setPageError] = useState<string | null>(null)
  const autoParseStarted = useRef(false)

  const [activeSubsystem, setActiveSubsystem] = useState<Subsystem>('Propulsion')
  const [openTabIds, setOpenTabIds] = useState<string[]>(DEFAULT_OPEN)
  const [dynamicTabs, setDynamicTabs] = useState<ContentTab[]>([])
  const [dynamicContent, setDynamicContent] = useState<Record<string, string>>({})
  const [annotations, setAnnotations] = useState<PartAnnotation[]>([])
  const [satelliteProfile, setSatelliteProfile] = useState<SatelliteProfile>({})
  const [profilePending, setProfilePending] = useState<PendingQuestion[]>([])

  const setSel = useSelectionStore((s) => s.setSelected)
  const setStoreDiagram = useSelectionStore((s) => s.setDiagram)
  const selectedId = useSelectionStore((s) => s.selectedNodeId)

  const dock = useWorkspaceDock(projectId, openTabIds)

  useEffect(() => {
    setSel(search.get('node') || null)
  }, [projectId, setSel])

  useEffect(() => {
    const onPop = () => {
      const n = new URLSearchParams(window.location.search).get('node')
      setSel(n || null)
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [setSel])

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

  const refreshAnnotations = useCallback(async () => {
    try {
      const doc = await autoDetectAnnotations(projectId)
      setAnnotations(doc.annotations)
    } catch {
      try {
        const doc = await getAnnotations(projectId)
        setAnnotations(doc.annotations)
      } catch {
        /* optional until first save */
      }
    }
  }, [projectId])

  const refreshDiagram = useCallback(async () => {
    try {
      const d = await getDiagram(projectId)
      setDiagram(d)
      setStoreDiagram(d)
      setDiagramLoadErr(null)
      setParseErr(null)
      await refreshAnnotations()
    } catch (e) {
      setDiagram(null)
      setStoreDiagram(null)
      setDiagramLoadErr(formatApiError(e))
    }
  }, [projectId, setStoreDiagram, refreshAnnotations])

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
    setOpenTabIds(DEFAULT_OPEN)
    setDynamicTabs([])
    setDynamicContent({})
    setAnnotations([])
    setActiveSubsystem('Propulsion')
    void (async () => {
      try {
        await refreshMeta()
        if (cancelled) return
        await refreshAnnotations()
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
    autoParseStarted.current = false
  }, [projectId])

  useEffect(() => {
    if (!meta || !projectId || meta.has_diagram || meta.parse_status !== 'idle') return
    if (autoParseStarted.current) return
    autoParseStarted.current = true
    void (async () => {
      try {
        await queueParse(projectId)
        await refreshMeta()
      } catch (e) {
        setParseErr(formatApiError(e))
        autoParseStarted.current = false
      }
    })()
  }, [meta, projectId, refreshMeta])

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

  const tabMeta = useMemo(() => {
    const meta: Record<string, DockTabMeta> = {}
    for (const t of WORKSPACE_TAB_CATALOG) {
      meta[t.id] = { id: t.id, label: t.label, closable: true }
    }
    for (const t of dynamicTabs) {
      meta[t.id] = { id: t.id, label: t.label, closable: true }
    }
    meta.terminal = { id: 'terminal', label: 'Terminal', closable: false }
    return meta
  }, [dynamicTabs])

  const openTab = useCallback(
    (tabId: string, label?: string, leafId?: string): string => {
      if (tabId !== 'terminal') {
        setOpenTabIds((ids) => (ids.includes(tabId) ? ids : [...ids, tabId]))
      }
      return dock.openTabWithMessage(tabId, {
        leafId,
        label: label ?? WORKSPACE_TAB_LABELS[tabId] ?? tabId,
      })
    },
    [dock],
  )

  const closeTab = useCallback(
    (tabId: string) => {
      if (tabId === 'terminal') return
      dock.closeTab(tabId)
      setOpenTabIds((ids) => ids.filter((id) => id !== tabId))
      if (tabId.startsWith('dynamic-')) {
        setDynamicTabs((t) => t.filter((x) => x.id !== tabId))
        setDynamicContent((c) => {
          const { [tabId]: _, ...rest } = c
          return rest
        })
      }
    },
    [dock],
  )

  const selectedNode: DiagramNode | null = useMemo(() => {
    if (!diagram || !selectedId) return null
    return diagram.nodes.find((n) => n.id === selectedId) ?? null
  }, [diagram, selectedId])

  const handleWorkspaceMessage = useCallback(
    (message: string): WorkspaceTerminalResult => {
      const intent = detectTerminalIntent(message)

      if (intent.type === 'dynamic') {
        const tabId = `dynamic-${Date.now()}`
        const tab: ContentTab = {
          id: tabId,
          label: intent.label,
          closable: true,
          kind: 'dynamic',
        }
        setDynamicTabs((t) => [...t, tab])
        const placement = openTab(tabId, intent.label)
        return { continueCopilot: true, dynamicTabId: tabId, sysLines: [placement] }
      }

      if (intent.type === 'diagram') {
        return { continueCopilot: false, sysLines: [openTab('diagram')] }
      }
      if (intent.type === 'graph') {
        return { continueCopilot: false, sysLines: [openTab('graph')] }
      }
      if (intent.type === 'mission') {
        return { continueCopilot: false, sysLines: [openTab('mission')] }
      }
      if (intent.type === 'inspector') {
        const line = openTab('inspector')
        const ctx = selectedId
          ? `Focused on component ${selectedId} — attach CSV or review telemetry schema in that pane.`
          : 'Select a component on the diagram for node-level telemetry schema.'
        return { continueCopilot: false, sysLines: [line, ctx] }
      }

      if (intent.type === 'annotations') {
        return {
          continueCopilot: false,
          sysLines: [
            openTab('annotations'),
            'Review auto-detected parts, draw vectors, and enter mass/size.',
          ],
        }
      }

      if (intent.type === 'launch') {
        const missing = annotationsMissingMass(annotations)
        const hint = missionReadinessHint(annotations)
        if (missing.length && hint) {
          return {
            continueCopilot: false,
            sysLines: [openTab('launch'), openTab('annotations'), hint],
          }
        }
        return { continueCopilot: true, sysLines: [openTab('launch')] }
      }

      if (intent.type === 'simulate') {
        const missing = annotationsMissingMass(annotations)
        const hint = missionReadinessHint(annotations)
        if (missing.length && hint) {
          return {
            continueCopilot: false,
            sysLines: [openTab('simulation'), openTab('annotations'), hint],
          }
        }
        return { continueCopilot: true, sysLines: [openTab('simulation')] }
      }

      return { continueCopilot: true }
    },
    [openTab, annotations, selectedId],
  )

  const handleWorkspaceAction = useCallback((action: WorkspaceTerminalAction) => {
    if (action.type === 'store-dynamic-result') {
      setDynamicContent((c) => ({ ...c, [action.tabId]: action.text }))
    }
  }, [])

  const statusBadge =
    meta?.parse_status === 'error'
      ? 'badge-err'
      : meta?.parse_status === 'running' || meta?.parse_status === 'queued'
        ? 'badge-warn'
        : ''

  const renderContentTab = (activeTabId: string) => {
    if (activeTabId === 'terminal') {
      return (
        <div className="mission-terminal-panel terminal-panel dock-terminal">
          <div className="terminal-header">
            <div className="terminal-dots">
              <span />
              <span />
              <span />
            </div>
            <span className="terminal-title">vioci-integration — ai copilot</span>
          </div>
          <div className="terminal-body mission-terminal-body">
          <IntegrationTerminal
            projectId={projectId}
            parseStatus={meta!.parse_status}
            hasDiagram={!!diagram}
            onWorkspaceMessage={handleWorkspaceMessage}
            onWorkspaceAction={handleWorkspaceAction}
            onOpenWorkspaceTab={(tabId) =>
              openTab(tabId, WORKSPACE_TAB_LABELS[tabId] ?? tabId)
            }
          />
          </div>
        </div>
      )
    }

    if (activeTabId === 'inspector') {
      return (
        <div className="mission-inspector-panel dock-inspector">
          <NodeInspector projectId={projectId} node={selectedNode} />
        </div>
      )
    }

    if (activeTabId === 'diagram') {
      if (diagram) {
        return (
          <div className="workspace-split">
            <div className="workspace-split-main">
              <ImageOverlay
                projectId={projectId}
                nodes={diagram.nodes}
                activeSubsystem={activeSubsystem}
                onDropCsv={async (nid, file) => {
                  await uploadSheetCsv(projectId, nid, file)
                  const d = await getDiagram(projectId)
                  setDiagram(d)
                  setStoreDiagram(d)
                  setSel(nid)
                }}
              />
            </div>
            <SubsystemComponentList nodes={diagram.nodes} subsystem={activeSubsystem} />
          </div>
        )
      }
      return (
        <div className="workspace-canvas">
          <span className="canvas-corner">
            {meta?.has_diagram ? 'LOADING IR…' : 'CONVERT SCHEMATIC TO OPEN WORKSPACE'}
          </span>
          <ProjectImage projectId={projectId} className="canvas-img" alt="Schematic" />
          {!meta?.has_diagram ? (
            <div className="workspace-parse-cta">
              <p className="muted">
                {meta?.parse_status === 'queued' || meta?.parse_status === 'running'
                  ? 'Converting schematic to graph…'
                  : meta?.parse_status === 'error'
                    ? 'Conversion failed. Re-convert from the explorer or try again shortly.'
                    : 'Starting conversion…'}
              </p>
              {events.length ? (
                <pre className="mono log-pre" style={{ marginTop: '0.5rem' }}>
                  {events.join('\n')}
                </pre>
              ) : null}
              {parseErr ? <p className="error">{parseErr}</p> : null}
            </div>
          ) : diagramLoadErr ? (
            <p className="error workspace-parse-cta">{diagramLoadErr}</p>
          ) : null}
        </div>
      )
    }

    if (activeTabId === 'graph') {
      if (diagram) {
        return <GraphViewWithProvider diagram={diagram} />
      }
      return (
        <p className="muted" style={{ padding: '1rem' }}>
          Conversion in progress — dependency graph unlocks when the schematic is ready.
        </p>
      )
    }

    if (activeTabId === 'launch') {
      return <LaunchCompatPanel compact hideHeader />
    }

    if (activeTabId === 'simulation') {
      return diagram ? (
        <SimulatePanel projectId={projectId} diagram={diagram} embedded />
      ) : (
        <p className="muted" style={{ padding: '1rem' }}>
          Conversion in progress — simulation unlocks when the graph is ready.
        </p>
      )
    }

    if (activeTabId === 'mission') {
      return (
        <SatelliteProfilePanel
          profile={satelliteProfile}
          pendingQuestions={profilePending}
          nodes={diagram?.nodes ?? []}
          activeSubsystem={activeSubsystem}
          onChange={(key, value) =>
            setSatelliteProfile((p) => ({ ...p, [key]: value }))
          }
          onAnswerPending={(questionId, value) => {
            setProfilePending((q) => q.filter((x) => x.id !== questionId))
            const q = profilePending.find((x) => x.id === questionId)
            if (q) setSatelliteProfile((p) => ({ ...p, [q.field]: value }))
          }}
        />
      )
    }

    if (activeTabId === 'annotations') {
      return (
        <AnnotationPanel
          projectId={projectId}
          hasDiagram={!!diagram}
          selectedNodeId={selectedId}
          onSelectNode={setSel}
        />
      )
    }

    if (activeTabId.startsWith('dynamic-')) {
      const text = dynamicContent[activeTabId]
      return (
        <div className="dynamic-tab-panel">
          {text ? (
            <pre className="mono log-pre" style={{ maxHeight: 'none', whiteSpace: 'pre-wrap' }}>
              {text}
            </pre>
          ) : (
            <LoadingIndicator label="Running analysis…" size="md" block />
          )}
        </div>
      )
    }

    return null
  }

  if (!pageReady) {
    return <LoadingIndicator label="Initializing mission workspace…" size="md" block />
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

      <div className="mission-workspace mission-workspace-dock">
        <WorkspaceDock
          layout={dock.layout}
          tabMeta={tabMeta}
          projectId={projectId}
          onSelectTab={dock.selectTab}
          onCloseTab={closeTab}
          onMoveTab={dock.moveTab}
          onAddTabToLeaf={(tabId, leafId) => {
            setOpenTabIds((ids) => (ids.includes(tabId) ? ids : [...ids, tabId]))
            dock.openTabWithMessage(tabId, {
              leafId,
              label: WORKSPACE_TAB_LABELS[tabId] ?? tabId,
            })
          }}
          renderPane={renderContentTab}
          renderLeafChrome={(_leafId, tabId) =>
            tabId === 'diagram' ? (
              <div className="subsystem-tabs" role="tablist" aria-label="Subsystem">
                {SUBSYSTEMS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    role="tab"
                    aria-selected={activeSubsystem === s}
                    className={`subsystem-tab ${activeSubsystem === s ? 'subsystem-tab-active' : ''}`}
                    onClick={() => setActiveSubsystem(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            ) : null
          }
        />
      </div>
    </div>
  )
}
