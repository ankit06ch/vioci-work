import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  autoDetectAnnotations,
  enhanceProjectImage,
  restoreProjectImage,
  formatApiError,
  getAnnotations,
  saveAnnotations,
} from '../api/client'
import type {
  AnnotationVector,
  AnnotationVectorKind,
  BBoxPx,
  PartAnnotation,
} from '../api/types'
import { useUndoStack } from '../hooks/useUndoStack'
import { ANNOTATION_FIELDS, totalMassKg } from '../lib/annotations'
import { SchematicCanvas, type SchematicCanvasApi } from './SchematicCanvas'

type DrawMode = 'select' | 'line' | 'arrow' | 'rect'

type Props = {
  projectId: string
  hasDiagram: boolean
  selectedNodeId: string | null
  onSelectNode: (nodeId: string | null) => void
}

function IconEnterFullscreen() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M2.5 6V2.5H6M10 2.5H13.5V6M13.5 10V13.5H10M6 13.5H2.5V10"
        stroke="currentColor"
        strokeWidth="1.35"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function IconExitFullscreen() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M6 2.5H2.5V6M13.5 6V2.5H10M10 13.5H13.5V10M2.5 10V13.5H6"
        stroke="currentColor"
        strokeWidth="1.35"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function uid() {
  return crypto.randomUUID?.() ?? `a-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

const MIN_HIT_PX = 20
const VECTOR_HIT_STROKE = 14

function partHitBounds(a: PartAnnotation): BBoxPx | null {
  let x: number
  let y: number
  let w: number
  let h: number
  const shapePts = a.vectors
    .filter((v) => v.kind === 'polygon' && v.points.length >= 3)
    .flatMap((v) => v.points)
  if (shapePts.length >= 3) {
    const xs = shapePts.map((p) => p[0])
    const ys = shapePts.map((p) => p[1])
    x = Math.min(...xs)
    y = Math.min(...ys)
    w = Math.max(...xs) - x
    h = Math.max(...ys) - y
  } else if (a.bbox && a.bbox.w > 0 && a.bbox.h > 0) {
    ;({ x, y, w, h } = a.bbox)
  } else {
    const pts = a.vectors.flatMap((v) => v.points)
    if (!pts.length) return null
    const xs = pts.map((p) => p[0])
    const ys = pts.map((p) => p[1])
    x = Math.min(...xs)
    y = Math.min(...ys)
    w = Math.max(...xs) - x
    h = Math.max(...ys) - y
  }
  if (w < MIN_HIT_PX) {
    const pad = (MIN_HIT_PX - w) / 2
    x -= pad
    w = MIN_HIT_PX
  }
  if (h < MIN_HIT_PX) {
    const pad = (MIN_HIT_PX - h) / 2
    y -= pad
    h = MIN_HIT_PX
  }
  return { x, y, w, h }
}

function renderVector(
  v: AnnotationVector,
  selected: boolean,
  interactive: boolean,
  onSelect?: (e: React.MouseEvent) => void,
) {
  const stroke = selected ? '#ff7a59' : v.auto ? 'rgba(255, 122, 89, 0.85)' : '#22d3ee'
  const sw = selected ? 3 : 1.5
  const pick = (e: React.MouseEvent) => {
    e.stopPropagation()
    onSelect?.(e)
  }

  if (v.kind === 'polygon' && v.points.length >= 3) {
    const d = `${v.points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`).join(' ')} Z`
    return (
      <g
        key={v.id}
        className={selected ? 'annotation-vector-selected' : undefined}
        style={{ pointerEvents: interactive ? 'visiblePainted' : 'none', cursor: interactive ? 'pointer' : undefined }}
        onClick={interactive ? pick : undefined}
      >
        <path
          d={d}
          fill={selected ? 'rgba(255, 122, 89, 0.2)' : 'rgba(255, 122, 89, 0.12)'}
          stroke={stroke}
          strokeWidth={sw}
          strokeLinejoin="round"
          strokeDasharray={v.auto && !selected ? '5 3' : undefined}
        />
        {v.label ? (
          <text
            x={v.points[0][0] + 4}
            y={Math.max(12, v.points[0][1] - 6)}
            fill={stroke}
            fontSize={11}
            fontFamily="monospace"
            pointerEvents="none"
          >
            {v.label}
          </text>
        ) : null}
      </g>
    )
  }

  if (v.kind === 'rect' && v.points.length >= 2) {
    const xs = v.points.map((p) => p[0])
    const ys = v.points.map((p) => p[1])
    const x = Math.min(...xs)
    const y = Math.min(...ys)
    const w = Math.max(...xs) - x
    const h = Math.max(...ys) - y
    return (
      <g
        key={v.id}
        className={selected ? 'annotation-vector-selected' : undefined}
        style={{ pointerEvents: interactive ? 'visiblePainted' : 'none', cursor: interactive ? 'pointer' : undefined }}
        onClick={interactive ? pick : undefined}
      >
        <rect
          x={x}
          y={y}
          width={w}
          height={h}
          fill={selected ? 'rgba(255, 122, 89, 0.18)' : 'rgba(255, 122, 89, 0.1)'}
          stroke={stroke}
          strokeWidth={sw}
          strokeDasharray={v.auto && !selected ? '6 4' : undefined}
        />
        {v.label ? (
          <text
            x={x + 4}
            y={Math.max(12, y - 6)}
            fill={stroke}
            fontSize={12}
            fontFamily="monospace"
            pointerEvents="none"
          >
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
    <g key={v.id} className={selected ? 'annotation-vector-selected' : undefined}>
      {interactive ? (
        <path
          d={d}
          fill="none"
          stroke="transparent"
          strokeWidth={VECTOR_HIT_STROKE}
          style={{ cursor: 'pointer', pointerEvents: 'stroke' }}
          onClick={pick}
        />
      ) : null}
      <path
        d={d}
        fill="none"
        stroke={stroke}
        strokeWidth={sw}
        strokeLinecap="round"
        strokeLinejoin="round"
        pointerEvents="none"
        markerEnd={v.kind === 'arrow' ? 'url(#ann-arrow)' : undefined}
      />
      {v.label && v.points[0] ? (
        <text
          x={v.points[0][0]}
          y={v.points[0][1] - 8}
          fill={stroke}
          fontSize={11}
          fontFamily="monospace"
          pointerEvents="none"
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
  const nameInputRef = useRef<HTMLInputElement>(null)
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
  const [selectedAnnIds, setSelectedAnnIds] = useState<string[]>([])
  const [selectedVectorId, setSelectedVectorId] = useState<string | null>(null)
  const listAnchorId = useRef<string | null>(null)
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

  const primaryAnnId = selectedAnnIds.at(-1) ?? null
  const selectedAnn =
    selectedAnnIds.length === 1
      ? (annotations.find((a) => a.id === primaryAnnId) ?? null)
      : null
  const isPartSelected = (id: string) => selectedAnnIds.includes(id)

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
      if (match) setSelectedAnnIds([match.id])
    }
  }, [selectedNodeId, annotations])

  const clearSelection = useCallback(() => {
    setSelectedAnnIds([])
    setSelectedVectorId(null)
    listAnchorId.current = null
  }, [])

  const deleteSelection = useCallback(() => {
    if (selectedVectorId && selectedAnnIds.length <= 1) {
      const parentId = annotations.find((a) =>
        a.vectors.some((v) => v.id === selectedVectorId),
      )?.id
      if (!parentId) {
        setSelectedVectorId(null)
        return
      }
      const next = annotations
        .map((a) =>
          a.id === parentId
            ? {
                ...a,
                vectors: a.vectors.filter((v) => v.id !== selectedVectorId),
                auto_detected: false,
              }
            : a,
        )
        .filter((a) => a.id !== parentId || a.vectors.length > 0 || a.bbox)
      apply(next, true)
      setSelectedVectorId(null)
      if (!next.some((a) => a.id === parentId)) clearSelection()
      else setSelectedAnnIds((ids) => ids.filter((id) => id === parentId))
      return
    }
    if (selectedAnnIds.length > 0) {
      const drop = new Set(selectedAnnIds)
      apply(
        annotations.filter((a) => !drop.has(a.id)),
        true,
      )
      clearSelection()
    }
  }, [annotations, apply, selectedAnnIds, selectedVectorId, clearSelection])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      const inField = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'

      if (e.key === 'Escape') {
        if (fullscreen) {
          setFullscreen(false)
          return
        }
        if (!inField && (selectedAnnIds.length > 0 || selectedVectorId)) {
          e.preventDefault()
          clearSelection()
          return
        }
      }

      if (!inField && drawMode === 'select' && (e.key === 'Delete' || e.key === 'Backspace')) {
        if (selectedAnnIds.length > 0 || selectedVectorId) {
          e.preventDefault()
          deleteSelection()
        }
        return
      }

      if (!(e.metaKey || e.ctrlKey) || e.key.toLowerCase() !== 'z') return
      if (inField) return
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
  }, [
    undo,
    redo,
    persist,
    fullscreen,
    drawMode,
    deleteSelection,
    clearSelection,
    selectedAnnIds.length,
    selectedVectorId,
  ])

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

  const selectPartWithModifiers = useCallback(
    (
      a: PartAnnotation,
      opts?: { shiftKey?: boolean; ctrlKey?: boolean; focusName?: boolean },
    ) => {
      const shift = opts?.shiftKey ?? false
      const ctrl = opts?.ctrlKey ?? false
      const anchor = listAnchorId.current
      const order = annotations.map((x) => x.id)

      setSelectedVectorId(null)
      setSelectedAnnIds((prev) => {
        if (shift && anchor) {
          const i0 = order.indexOf(anchor)
          const i1 = order.indexOf(a.id)
          if (i0 < 0 || i1 < 0) return prev.includes(a.id) ? prev : [...prev, a.id]
          const lo = Math.min(i0, i1)
          const hi = Math.max(i0, i1)
          return order.slice(lo, hi + 1)
        }
        if (shift) {
          return prev.includes(a.id) ? prev : [...prev, a.id]
        }
        if (ctrl) {
          return prev.includes(a.id) ? prev.filter((id) => id !== a.id) : [...prev, a.id]
        }
        return [a.id]
      })
      listAnchorId.current = a.id
      if (!shift && !ctrl && a.node_id) onSelectNode(a.node_id)
      setSidebarOpen(true)
      if (opts?.focusName) {
        requestAnimationFrame(() => nameInputRef.current?.focus())
      }
    },
    [annotations, onSelectNode],
  )

  const selectVector = useCallback(
    (a: PartAnnotation, v: AnnotationVector, opts?: { shiftKey?: boolean; ctrlKey?: boolean }) => {
      if (opts?.shiftKey || opts?.ctrlKey) {
        selectPartWithModifiers(a, opts)
        setSelectedVectorId(v.id)
        return
      }
      setSelectedAnnIds([a.id])
      listAnchorId.current = a.id
      setSelectedVectorId(v.id)
      if (a.node_id) onSelectNode(a.node_id)
      setSidebarOpen(true)
    },
    [onSelectNode, selectPartWithModifiers],
  )

  const updateSelected = useCallback(
    (patch: Partial<PartAnnotation>) => {
      if (!primaryAnnId || selectedAnnIds.length !== 1) return
      apply(
        annotations.map((a) => {
          if (a.id !== primaryAnnId) return a
          const next: PartAnnotation = { ...a, ...patch, auto_detected: false }
          if (typeof patch.name === 'string') {
            next.vectors = a.vectors.map((v) => ({ ...v, label: patch.name }))
          }
          return next
        }),
        true,
      )
    },
    [annotations, primaryAnnId, selectedAnnIds.length, apply],
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
    setSelectedAnnIds([a.id])
    listAnchorId.current = a.id
  }

  const worldPt = (api: SchematicCanvasApi, clientX: number, clientY: number): [number, number] => {
    const [x, y] = api.screenToWorld(clientX, clientY)
    return [Math.max(0, Math.min(dim.w, x)), Math.max(0, Math.min(dim.h, y))]
  }

  const onSvgMouseDown = (e: React.MouseEvent<SVGSVGElement>, api: SchematicCanvasApi) => {
    if (drawMode === 'select') {
      if (e.target === e.currentTarget) {
        clearSelection()
      }
      return
    }
    if (dim.w <= 0) return
    e.stopPropagation()
    setDraftPoints([worldPt(api, e.clientX, e.clientY)])
  }

  const onSvgMouseMove = (e: React.MouseEvent<SVGSVGElement>, api: SchematicCanvasApi) => {
    if (!draftPoints.length || drawMode === 'select') return
    setDraftPoints([draftPoints[0], worldPt(api, e.clientX, e.clientY)])
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
    let targetId = primaryAnnId
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

  const onRestore = async () => {
    setBusy(true)
    try {
      const r = await restoreProjectImage(projectId)
      setImageEnhanced(r.enhanced)
      setQualityScore(r.quality_score)
      setImgKey((k) => k + 1)
      setErr(null)
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
            {busy ? 'Sharpening…' : 'Sharpen image'}
          </button>
          {imageEnhanced ? (
            <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => void onRestore()}>
              {busy ? 'Restoring…' : 'Restore original'}
            </button>
          ) : null}
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
            className={`btn btn-icon ${fullscreen ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => void toggleFullscreen()}
            title={fullscreen ? 'Exit full screen (Esc)' : 'Full screen'}
            aria-label={fullscreen ? 'Exit full screen' : 'Full screen'}
          >
            {fullscreen ? <IconExitFullscreen /> : <IconEnterFullscreen />}
          </button>
          <span className="muted mono" style={{ fontSize: '0.68rem' }}>
            {saveState === 'saving' ? 'Saving…' : saveState === 'saved' ? 'Saved' : ''}
          </span>
        </div>
      </div>

      {err ? <p className="error annotation-err">{err}</p> : null}

      <div className="annotation-body">
        <SchematicCanvas
          projectId={projectId}
          imageKey={imgKey}
          naturalSize={dim}
          panOnDrag={drawMode === 'select'}
          cornerLabel="Shift+click multi-select · Delete removes · scroll to zoom"
          onImageLoad={(w, h) => setDim({ w, h })}
          onSvgMouseDown={onSvgMouseDown}
          onSvgMouseMove={onSvgMouseMove}
          onSvgMouseUp={onSvgMouseUp}
          onSvgMouseLeave={() => setDraftPoints([])}
        >
          {() => (
            <>
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
              {annotations.map((a) => {
                const bb = a.bbox
                if (!bb) return null
                const partSel = isPartSelected(a.id) && !selectedVectorId
                return (
                  <rect
                    key={`bb-${a.id}`}
                    x={bb.x}
                    y={bb.y}
                    width={bb.w}
                    height={bb.h}
                    fill={
                      isPartSelected(a.id) ? 'rgba(255, 122, 89, 0.12)' : 'rgba(255, 122, 89, 0.06)'
                    }
                    stroke={isPartSelected(a.id) ? '#ff7a59' : 'rgba(255, 122, 89, 0.35)'}
                    strokeWidth={isPartSelected(a.id) ? 2 : 1}
                    strokeDasharray={partSel ? '4 3' : undefined}
                    style={{ pointerEvents: 'none' }}
                  />
                )
              })}
              {drawMode === 'select'
                ? annotations.map((a) => {
                    const hit = partHitBounds(a)
                    if (!hit) return null
                    const sel = isPartSelected(a.id) && !selectedVectorId
                    return (
                      <rect
                        key={`hit-${a.id}`}
                        className={`annotation-part-hit${sel ? ' annotation-part-hit--selected' : ''}`}
                        x={hit.x}
                        y={hit.y}
                        width={hit.w}
                        height={hit.h}
                        onClick={(e) => {
                          e.stopPropagation()
                          selectPartWithModifiers(a, {
                            shiftKey: e.shiftKey,
                            ctrlKey: e.metaKey || e.ctrlKey,
                          })
                        }}
                        onDoubleClick={(e) => {
                          e.stopPropagation()
                          selectPartWithModifiers(a, { focusName: true })
                        }}
                      />
                    )
                  })
                : null}
              {annotations.map((a) =>
                a.vectors.map((v) =>
                  renderVector(
                    v,
                    v.id === selectedVectorId,
                    drawMode === 'select',
                    (e) =>
                      selectVector(a, v, {
                        shiftKey: e.shiftKey,
                        ctrlKey: e.metaKey || e.ctrlKey,
                      }),
                  ),
                ),
              )}
              {drawMode === 'select' && selectedAnn && selectedAnnIds.length === 1
                ? (() => {
                    const hit = partHitBounds(selectedAnn)
                    if (!hit) return null
                    const labelW = Math.max(160, Math.min(360, hit.w + 40))
                    const labelX = Math.max(0, hit.x)
                    const labelY = Math.max(4, hit.y - 32)
                    return (
                      <foreignObject
                        key="part-name-editor"
                        x={labelX}
                        y={labelY}
                        width={labelW}
                        height={30}
                        className="annotation-name-fo"
                      >
                        <input
                          ref={nameInputRef}
                          type="text"
                          className="annotation-name-on-canvas auth-input"
                          value={selectedAnn.name}
                          placeholder="Part name"
                          onChange={(e) => updateSelected({ name: e.target.value })}
                          onPointerDown={(e) => e.stopPropagation()}
                          onClick={(e) => e.stopPropagation()}
                          onKeyDown={(e) => e.stopPropagation()}
                        />
                      </foreignObject>
                    )
                  })()
                : null}
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
            </>
          )}
        </SchematicCanvas>

        <aside className={`annotation-sidebar ${sidebarOpen ? '' : 'annotation-sidebar-hidden'}`}>
          <p className="muted" style={{ fontSize: '0.72rem', margin: '0 0 0.5rem' }}>
            Overlays follow component shape along leader lines. Re-detect AI after diagram
            updates. Shift+click to multi-select; Delete removes.
          </p>
          <ul className="annotation-part-list">
            {annotations.map((a) => (
              <li key={a.id}>
                <button
                  type="button"
                  className={`annotation-part-btn ${isPartSelected(a.id) ? 'annotation-part-btn-active' : ''}`}
                  onClick={(e) =>
                    selectPartWithModifiers(a, {
                      shiftKey: e.shiftKey,
                      ctrlKey: e.metaKey || e.ctrlKey,
                    })
                  }
                  onDoubleClick={(e) => {
                    e.preventDefault()
                    selectPartWithModifiers(a, { focusName: true })
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

          {selectedAnnIds.length > 1 ? (
            <div className="annotation-props">
              <p className="muted" style={{ fontSize: '0.78rem', margin: 0 }}>
                {selectedAnnIds.length} parts selected
              </p>
              <button type="button" className="btn btn-ghost" onClick={() => deleteSelection()}>
                Remove {selectedAnnIds.length} parts
              </button>
            </div>
          ) : selectedAnn ? (
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
              <p className="muted" style={{ fontSize: '0.68rem', margin: '0 0 0.35rem' }}>
                {selectedVectorId
                  ? 'Line/shape selected — Delete removes it.'
                  : 'Delete removes this part.'}
              </p>
              <button type="button" className="btn btn-ghost" onClick={() => deleteSelection()}>
                {selectedVectorId ? 'Remove line/shape' : 'Remove part'}
              </button>
            </div>
          ) : (
            <p className="muted">Click a part on the schematic to name and edit it, or use + Part.</p>
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
