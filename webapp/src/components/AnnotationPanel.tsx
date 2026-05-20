import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  autoDetectAnnotations,
  enhanceProjectImage,
  formatApiError,
  getAnnotations,
  saveAnnotations,
} from '../api/client'
import type { AnnotationVector, AnnotationVectorKind, PartAnnotation } from '../api/types'
import { useUndoStack } from '../hooks/useUndoStack'
import { ANNOTATION_FIELDS, totalMassKg } from '../lib/annotations'
import { ProjectImage } from './ProjectImage'

type DrawMode = 'select' | 'line' | 'arrow' | 'rect'

type Props = {
  projectId: string
  hasDiagram: boolean
  selectedNodeId: string | null
  onSelectNode: (nodeId: string | null) => void
}

function uid() {
  return crypto.randomUUID?.() ?? `a-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function clientToImage(
  e: React.MouseEvent<SVGSVGElement>,
  svg: SVGSVGElement,
  dim: { w: number; h: number },
): [number, number] {
  const pt = svg.createSVGPoint()
  pt.x = e.clientX
  pt.y = e.clientY
  const ctm = svg.getScreenCTM()
  if (!ctm) return [0, 0]
  const p = pt.matrixTransform(ctm.inverse())
  return [Math.max(0, Math.min(dim.w, p.x)), Math.max(0, Math.min(dim.h, p.y))]
}

function renderVector(v: AnnotationVector, selected: boolean) {
  const stroke = selected ? '#ff7a59' : v.auto ? 'rgba(255, 122, 89, 0.85)' : '#22d3ee'
  const sw = selected ? 2.5 : 1.5
  if (v.kind === 'rect' && v.points.length >= 2) {
    const xs = v.points.map((p) => p[0])
    const ys = v.points.map((p) => p[1])
    const x = Math.min(...xs)
    const y = Math.min(...ys)
    const w = Math.max(...xs) - x
    const h = Math.max(...ys) - y
    return (
      <g key={v.id}>
        <rect
          x={x}
          y={y}
          width={w}
          height={h}
          fill="rgba(255, 122, 89, 0.1)"
          stroke={stroke}
          strokeWidth={sw}
          strokeDasharray={v.auto ? '6 4' : undefined}
        />
        {v.label ? (
          <text x={x + 4} y={Math.max(12, y - 6)} fill={stroke} fontSize={12} fontFamily="monospace">
            {v.label}
          </text>
        ) : null}
      </g>
    )
  }
  if (v.points.length < 2) return null
  const d =
    v.kind === 'arrow'
      ? `M ${v.points[0][0]} ${v.points[0][1]} L ${v.points[1][0]} ${v.points[1][1]}`
      : v.points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`).join(' ')
  return (
    <g key={v.id}>
      <path
        d={d}
        fill="none"
        stroke={stroke}
        strokeWidth={sw}
        markerEnd={v.kind === 'arrow' ? 'url(#ann-arrow)' : undefined}
      />
      {v.label && v.points[0] ? (
        <text
          x={v.points[0][0]}
          y={v.points[0][1] - 8}
          fill={stroke}
          fontSize={11}
          fontFamily="monospace"
        >
          {v.label}
        </text>
      ) : null}
    </g>
  )
}

export function AnnotationPanel({
  projectId,
  hasDiagram,
  selectedNodeId,
  onSelectNode,
}: Props) {
  const panelRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const {
    present: annotations,
    push,
    replace,
    undo,
    redo,
    canUndo,
    canRedo,
    histVer,
  } = useUndoStack<PartAnnotation[]>([])
  const [imageEnhanced, setImageEnhanced] = useState(false)
  const [qualityScore, setQualityScore] = useState<number | null>(null)
  const [selectedAnnId, setSelectedAnnId] = useState<string | null>(null)
  const [drawMode, setDrawMode] = useState<DrawMode>('select')
  const [dim, setDim] = useState({ w: 0, h: 0 })
  const [draftPoints, setDraftPoints] = useState<[number, number][]>([])
  const [busy, setBusy] = useState(false)
  const [detecting, setDetecting] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved'>('idle')
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const detectOnce = useRef(false)
  const [imgKey, setImgKey] = useState(0)
  const [fullscreen, setFullscreen] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)

  void histVer

  const selectedAnn = annotations.find((a) => a.id === selectedAnnId) ?? null

  const persist = useCallback(
    (next: PartAnnotation[]) => {
      if (saveTimer.current) clearTimeout(saveTimer.current)
      setSaveState('saving')
      saveTimer.current = setTimeout(() => {
        void (async () => {
          try {
            await saveAnnotations(projectId, next)
            setSaveState('saved')
            setErr(null)
          } catch (e) {
            setSaveState('idle')
            setErr(formatApiError(e))
          }
        })()
      }, 600)
    },
    [projectId],
  )

  const apply = useCallback(
    (next: PartAnnotation[], history: boolean) => {
      if (history) push(next)
      else replace(next, true)
      persist(next)
    },
    [push, replace, persist],
  )

  const runAutoDetect = useCallback(async () => {
    setDetecting(true)
    try {
      const doc = await autoDetectAnnotations(projectId)
      apply(doc.annotations, false)
      setImageEnhanced(doc.image_enhanced)
      setQualityScore(doc.image_quality_score)
      setErr(null)
    } catch (e) {
      setErr(formatApiError(e))
    } finally {
      setDetecting(false)
    }
  }, [apply, projectId])

  const load = useCallback(async () => {
    detectOnce.current = false
    try {
      const doc = await getAnnotations(projectId)
      replace(doc.annotations, true)
      setImageEnhanced(doc.image_enhanced)
      setQualityScore(doc.image_quality_score)
      setErr(null)
    } catch (e) {
      setErr(formatApiError(e))
    }
  }, [projectId, replace])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!hasDiagram || detectOnce.current) return
    detectOnce.current = true
    void runAutoDetect()
  }, [hasDiagram, runAutoDetect])

  useEffect(() => {
    if (selectedNodeId) {
      const match = annotations.find((a) => a.node_id === selectedNodeId)
      if (match) setSelectedAnnId(match.id)
    }
  }, [selectedNodeId, annotations])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && fullscreen) {
        setFullscreen(false)
        return
      }
      if (!(e.metaKey || e.ctrlKey) || e.key.toLowerCase() !== 'z') return
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
      e.preventDefault()
      if (e.shiftKey) {
        const nxt = redo()
        if (nxt) persist(nxt)
      } else {
        const prev = undo()
        if (prev) persist(prev)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [undo, redo, persist, fullscreen])

  useEffect(() => {
    if (!fullscreen) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [fullscreen])

  const toggleFullscreen = useCallback(async () => {
    const el = panelRef.current
    if (!el) return
    if (fullscreen) {
      if (document.fullscreenElement === el) {
        await document.exitFullscreen().catch(() => {})
      }
      setFullscreen(false)
      return
    }
    setFullscreen(true)
    setSidebarOpen(true)
    try {
      await el.requestFullscreen()
    } catch {
      /* fixed overlay still applies */
    }
  }, [fullscreen])

  useEffect(() => {
    const onFs = () => {
      const el = panelRef.current
      if (!el) return
      if (!document.fullscreenElement) setFullscreen(false)
      else if (document.fullscreenElement === el) setFullscreen(true)
    }
    document.addEventListener('fullscreenchange', onFs)
    return () => document.removeEventListener('fullscreenchange', onFs)
  }, [])

  const updateSelected = useCallback(
    (patch: Partial<PartAnnotation>) => {
      if (!selectedAnnId) return
      apply(
        annotations.map((a) =>
          a.id === selectedAnnId ? { ...a, ...patch, auto_detected: false } : a,
        ),
        true,
      )
    },
    [annotations, selectedAnnId, apply],
  )

  const addManualPart = () => {
    const a: PartAnnotation = {
      id: uid(),
      node_id: null,
      name: 'New part',
      auto_detected: false,
      bbox: null,
      vectors: [],
      mass_kg: null,
      length_m: null,
      width_m: null,
      height_m: null,
      depth_m: null,
      volume_m3: null,
      material: null,
      power_w: null,
      notes: null,
      extra: {},
    }
    apply([...annotations, a], true)
    setSelectedAnnId(a.id)
  }

  const onSvgMouseDown = (e: React.MouseEvent<SVGSVGElement>) => {
    if (drawMode === 'select' || !svgRef.current || dim.w <= 0) return
    const pt = clientToImage(e, svgRef.current, dim)
    setDraftPoints([pt])
  }

  const onSvgMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!draftPoints.length || drawMode === 'select' || !svgRef.current) return
    const pt = clientToImage(e, svgRef.current, dim)
    setDraftPoints([draftPoints[0], pt])
  }

  const onSvgMouseUp = () => {
    if (!draftPoints.length || drawMode === 'select') return
    let points = draftPoints
    if (drawMode === 'rect' && points.length >= 2) {
      const [a, b] = points
      points = [
        [a[0], a[1]],
        [b[0], a[1]],
        [b[0], b[1]],
        [a[0], b[1]],
      ]
    }
    if (points.length < 2) {
      setDraftPoints([])
      return
    }
    let targetId = selectedAnnId
    if (!targetId) {
      if (!annotations.length) {
        addManualPart()
        setDraftPoints([])
        return
      }
      targetId = annotations[0].id
    }
    const kind: AnnotationVectorKind =
      drawMode === 'arrow' ? 'arrow' : drawMode === 'rect' ? 'rect' : 'line'
    const vec: AnnotationVector = {
      id: uid(),
      kind,
      points,
      auto: false,
      label: annotations.find((a) => a.id === targetId)?.name,
    }
    apply(
      annotations.map((a) =>
        a.id === targetId ? { ...a, vectors: [...a.vectors, vec], auto_detected: false } : a,
      ),
      true,
    )
    setDraftPoints([])
  }

  const onEnhance = async () => {
    setBusy(true)
    try {
      const r = await enhanceProjectImage(projectId)
      setImageEnhanced(r.enhanced)
      setQualityScore(r.quality_score)
      setImgKey((k) => k + 1)
      setErr(null)
      await runAutoDetect()
    } catch (e) {
      setErr(formatApiError(e))
    } finally {
      setBusy(false)
    }
  }

  const totalMass = totalMassKg(annotations)

  const panel = (
    <div
      className={`annotation-panel ${fullscreen ? 'annotation-panel--fullscreen' : ''} ${fullscreen && !sidebarOpen ? 'annotation-panel--canvas-focus' : ''}`}
      ref={panelRef}
      tabIndex={-1}
    >
      <div className="annotation-toolbar">
        <span className="muted mono" style={{ fontSize: '0.72rem' }}>
          {fullscreen ? 'Fullscreen annotations' : 'AI overlays · edit values on the right'}
          {imageEnhanced ? ' · enhanced' : ''}
          {qualityScore != null ? ` · ${(qualityScore * 100).toFixed(0)}%` : ''}
          {totalMass != null ? ` · Σ ${totalMass.toFixed(2)} kg` : ''}
        </span>
        <div className="annotation-toolbar-actions">
          <button
            type="button"
            className="btn btn-ghost"
            disabled={!canUndo}
            title="Undo (⌘Z / Ctrl+Z)"
            onClick={() => {
              const prev = undo()
              if (prev) persist(prev)
            }}
          >
            Undo
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={!canRedo}
            title="Redo (⇧⌘Z)"
            onClick={() => {
              const nxt = redo()
              if (nxt) persist(nxt)
            }}
          >
            Redo
          </button>
          <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => void onEnhance()}>
            {busy ? 'Enhancing…' : 'Enhance labels'}
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={detecting}
            onClick={() => void runAutoDetect()}
          >
            {detecting ? 'Detecting…' : 'Re-detect AI'}
          </button>
          {(['select', 'line', 'arrow', 'rect'] as DrawMode[]).map((m) => (
            <button
              key={m}
              type="button"
              className={`btn btn-ghost ${drawMode === m ? 'tab-active' : ''}`}
              onClick={() => setDrawMode(m)}
            >
              {m}
            </button>
          ))}
          <button type="button" className="btn btn-ghost" onClick={addManualPart}>
            + Part
          </button>
          {fullscreen ? (
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => setSidebarOpen((o) => !o)}
            >
              {sidebarOpen ? 'Hide panel' : 'Show panel'}
            </button>
          ) : null}
          <button
            type="button"
            className={`btn ${fullscreen ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => void toggleFullscreen()}
            title={fullscreen ? 'Exit full screen (Esc)' : 'Full screen'}
          >
            {fullscreen ? 'Exit full screen' : 'Full screen'}
          </button>
          <span className="muted mono" style={{ fontSize: '0.68rem' }}>
            {saveState === 'saving' ? 'Saving…' : saveState === 'saved' ? 'Saved' : ''}
          </span>
        </div>
      </div>

      {err ? <p className="error annotation-err">{err}</p> : null}

      <div className="annotation-body">
        <div className="annotation-canvas workspace-canvas">
          <ProjectImage
            key={imgKey}
            projectId={projectId}
            className="canvas-img"
            alt="Schematic"
            onLoad={(e) => {
              const t = e.currentTarget
              setDim({ w: t.naturalWidth, h: t.naturalHeight })
            }}
          />
          {dim.w > 0 ? (
            <svg
              ref={svgRef}
              className="annotation-svg"
              viewBox={`0 0 ${dim.w} ${dim.h}`}
              preserveAspectRatio="xMidYMid meet"
              onMouseDown={onSvgMouseDown}
              onMouseMove={onSvgMouseMove}
              onMouseUp={onSvgMouseUp}
              onMouseLeave={() => setDraftPoints([])}
            >
              <defs>
                <marker
                  id="ann-arrow"
                  markerWidth="8"
                  markerHeight="8"
                  refX="6"
                  refY="4"
                  orient="auto"
                >
                  <path d="M0,0 L8,4 L0,8 z" fill="#22d3ee" />
                </marker>
              </defs>
              {annotations.map((a) =>
                a.vectors.map((v) => renderVector(v, a.id === selectedAnnId)),
              )}
              {annotations.map(
                (a) =>
                  a.bbox && (
                    <rect
                      key={`bb-${a.id}`}
                      x={a.bbox.x}
                      y={a.bbox.y}
                      width={a.bbox.w}
                      height={a.bbox.h}
                      fill="rgba(255, 122, 89, 0.06)"
                      stroke={a.id === selectedAnnId ? '#ff7a59' : 'rgba(255, 122, 89, 0.35)'}
                      strokeWidth={a.id === selectedAnnId ? 2 : 1}
                      strokeDasharray="4 3"
                      style={{ pointerEvents: 'all', cursor: 'pointer' }}
                      onClick={() => {
                        setSelectedAnnId(a.id)
                        if (a.node_id) onSelectNode(a.node_id)
                      }}
                    />
                  ),
              )}
              {draftPoints.length >= 1 ? (
                <circle cx={draftPoints[0][0]} cy={draftPoints[0][1]} r={4} fill="#22d3ee" />
              ) : null}
              {draftPoints.length >= 2 ? (
                <path
                  d={`M ${draftPoints[0][0]} ${draftPoints[0][1]} L ${draftPoints[1][0]} ${draftPoints[1][1]}`}
                  stroke="#22d3ee"
                  strokeWidth={2}
                  fill="none"
                />
              ) : null}
            </svg>
          ) : null}
        </div>

        <aside className={`annotation-sidebar ${sidebarOpen ? '' : 'annotation-sidebar-hidden'}`}>
          <p className="muted" style={{ fontSize: '0.72rem', margin: '0 0 0.5rem' }}>
            Components are placed automatically after convert. Select a part to enter mass, size,
            and material — saved to the database.
          </p>
          <ul className="annotation-part-list">
            {annotations.map((a) => (
              <li key={a.id}>
                <button
                  type="button"
                  className={`annotation-part-btn ${a.id === selectedAnnId ? 'annotation-part-btn-active' : ''}`}
                  onClick={() => {
                    setSelectedAnnId(a.id)
                    if (a.node_id) onSelectNode(a.node_id)
                  }}
                >
                  <span>{a.name}</span>
                  {a.auto_detected ? (
                    <span className="mono muted" style={{ fontSize: '0.62rem' }}>
                      AI
                    </span>
                  ) : null}
                </button>
              </li>
            ))}
          </ul>

          {selectedAnn ? (
            <div className="annotation-props">
              <label className="annotation-field">
                Part name
                <input
                  className="auth-input"
                  value={selectedAnn.name}
                  onChange={(e) => updateSelected({ name: e.target.value })}
                />
              </label>
              {ANNOTATION_FIELDS.map((f) => (
                <label key={f.key} className="annotation-field">
                  {f.label}
                  {f.unit ? ` (${f.unit})` : ''}
                  <input
                    className="auth-input"
                    type={f.key === 'material' ? 'text' : 'number'}
                    step="any"
                    value={
                      f.key === 'material'
                        ? (selectedAnn.material ?? '')
                        : (selectedAnn[f.key] ?? '')
                    }
                    onChange={(e) => {
                      const v = e.target.value
                      if (f.key === 'material') {
                        updateSelected({ material: v || null })
                      } else {
                        const n = v === '' ? null : Number(v)
                        updateSelected({ [f.key]: n } as Partial<PartAnnotation>)
                      }
                    }}
                  />
                </label>
              ))}
              <label className="annotation-field">
                Notes
                <textarea
                  className="input-msg"
                  rows={2}
                  value={selectedAnn.notes ?? ''}
                  onChange={(e) => updateSelected({ notes: e.target.value || null })}
                />
              </label>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => {
                  apply(
                    annotations.filter((a) => a.id !== selectedAnnId),
                    true,
                  )
                  setSelectedAnnId(null)
                }}
              >
                Remove part
              </button>
            </div>
          ) : (
            <p className="muted">Select an AI-detected part to edit properties, or use + Part / draw tools.</p>
          )}
        </aside>
      </div>
    </div>
  )

  if (fullscreen) {
    return createPortal(panel, document.body)
  }
  return panel
}
