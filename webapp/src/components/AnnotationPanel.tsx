import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
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
import { totalMassKg } from '../lib/annotations'
import { PartDataFieldsEditor } from './PartDataFieldsEditor'
import { isAxisReferenceLabel } from '../lib/schematicLabels'
import { SchematicCanvas, type SchematicCanvasApi } from './SchematicCanvas'
import { IconEnterFullscreen, IconExitFullscreen } from './FullscreenIcons'

type DrawMode = 'select' | 'line' | 'arrow' | 'rect' | 'polygon' | 'polyline'

function translatePart(a: PartAnnotation, dx: number, dy: number): PartAnnotation {
  const move = (p: [number, number]): [number, number] => [p[0] + dx, p[1] + dy]
  return {
    ...a,
    auto_detected: false,
    bbox: a.bbox
      ? { ...a.bbox, x: a.bbox.x + dx, y: a.bbox.y + dy }
      : null,
    vectors: a.vectors.map((v) => ({ ...v, points: v.points.map(move) })),
  }
}

function clonePart(a: PartAnnotation): PartAnnotation {
  return JSON.parse(JSON.stringify(a)) as PartAnnotation
}

type ShapeEditDrag = {
  mode: 'vertex' | 'edge'
  partId: string
  vectorId: string
  kind: AnnotationVectorKind
  vertexIndex?: number
  edgeIndex?: number
  closed?: boolean
  snapshot: [number, number][]
  latestPoints: [number, number][]
  worldStart: [number, number]
  moved: boolean
}

function closedPathFromPoints(points: [number, number][]): string {
  if (points.length < 2) return ''
  return `${points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`).join(' ')} Z`
}

function isAxisAlignedRect(points: [number, number][], eps = 2): boolean {
  if (points.length < 3) return true
  const snap = (n: number) => Math.round(n / eps) * eps
  const xs = new Set(points.map((p) => snap(p[0])))
  const ys = new Set(points.map((p) => snap(p[1])))
  return xs.size <= 2 && ys.size <= 2
}

function updatePointsForVertex(
  kind: AnnotationVectorKind,
  points: [number, number][],
  index: number,
  newPt: [number, number],
  axisAlignRect: boolean,
): [number, number][] {
  const next = points.map((p, i) => (i === index ? newPt : [...p] as [number, number]))
  if (kind === 'rect' && axisAlignRect && next.length >= 4) {
    const xs = next.map((p) => p[0])
    const ys = next.map((p) => p[1])
    const x0 = Math.min(...xs)
    const x1 = Math.max(...xs)
    const y0 = Math.min(...ys)
    const y1 = Math.max(...ys)
    return [
      [x0, y0],
      [x1, y0],
      [x1, y1],
      [x0, y1],
    ]
  }
  return next
}

function effectiveVectorKind(
  kind: AnnotationVectorKind,
  points: [number, number][],
): AnnotationVectorKind {
  if (kind === 'rect' && points.length >= 4 && !isAxisAlignedRect(points)) {
    return 'polygon'
  }
  return kind
}

function updatePointsForEdge(
  points: [number, number][],
  edgeIndex: number,
  dx: number,
  dy: number,
  closed: boolean,
): [number, number][] {
  const n = points.length
  const i1 = closed ? (edgeIndex + 1) % n : edgeIndex + 1
  if (i1 >= n) return points
  return points.map((p, i) =>
    i === edgeIndex || i === i1 ? [p[0] + dx, p[1] + dy] : p,
  )
}

function edgeMidpoints(
  points: [number, number][],
  closed: boolean,
): [number, number][] {
  const out: [number, number][] = []
  const edgeCount = closed ? points.length : points.length - 1
  for (let i = 0; i < edgeCount; i++) {
    const j = closed ? (i + 1) % points.length : i + 1
    const a = points[i]!
    const b = points[j]!
    out.push([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2])
  }
  return out
}

function resolveEditableVector(
  a: PartAnnotation,
  selectedVectorId: string | null,
): AnnotationVector | null {
  const vectors = vectorsForDisplay(a)
  if (selectedVectorId) {
    const v = vectors.find((x) => x.id === selectedVectorId)
    if (v && v.points.length >= 2) return v
  }
  return (
    vectors.find((v) => v.kind === 'polygon' && v.points.length >= 3) ??
    vectors.find((v) => v.kind === 'rect' && v.points.length >= 3) ??
    vectors.find((v) => v.kind === 'polyline' && v.points.length >= 2) ??
    vectors.find(
      (v) => (v.kind === 'line' || v.kind === 'arrow') && v.points.length >= 2,
    ) ??
    null
  )
}

function partInteriorPath(a: PartAnnotation): string | null {
  const vectors = vectorsForDisplay(a)
  const poly = vectors.find((v) => v.kind === 'polygon' && v.points.length >= 3)
  if (poly) return closedPathFromPoints(poly.points)
  const rect = vectors.find((v) => v.kind === 'rect' && v.points.length >= 3)
  if (rect) return closedPathFromPoints(rect.points)
  const hit = partHitBounds(a)
  if (!hit) return null
  const { x, y, w, h } = hit
  return `M ${x} ${y} L ${x + w} ${y} L ${x + w} ${y + h} L ${x} ${y + h} Z`
}

function vectorPointsForDisplay(
  a: PartAnnotation,
  v: AnnotationVector,
  live: { partId: string; vectorId: string; points: [number, number][] } | null,
): [number, number][] {
  if (live && live.partId === a.id && live.vectorId === v.id) return live.points
  return v.points
}

function bboxFromPoints(points: [number, number][]): BBoxPx | null {
  if (!points.length) return null
  const xs = points.map((p) => p[0])
  const ys = points.map((p) => p[1])
  return {
    x: Math.min(...xs),
    y: Math.min(...ys),
    w: Math.max(...xs) - Math.min(...xs),
    h: Math.max(...ys) - Math.min(...ys),
  }
}

type Props = {
  projectId: string
  hasDiagram: boolean
  selectedNodeId: string | null
  onSelectNode: (nodeId: string | null) => void
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

function hasPolygonOutline(a: PartAnnotation): boolean {
  return a.vectors.some((v) => v.kind === 'polygon' && v.points.length >= 3)
}

/** Hide axis-aligned bbox overlay when a polygon defines the component shape. */
function shouldShowBboxOverlay(a: PartAnnotation): boolean {
  if (hasPolygonOutline(a)) return false
  return !!(a.bbox && a.bbox.w > 0 && a.bbox.h > 0)
}

/** Drop auto rectangle outlines superseded by a polygon trace. */
function vectorsForDisplay(a: PartAnnotation): AnnotationVector[] {
  if (!hasPolygonOutline(a)) return a.vectors
  return a.vectors.filter((v) => !(v.auto && v.kind === 'rect'))
}

/** Persist polygon as the shape (strip redundant bbox / auto-rect from older saves). */
function normalizePartShape(a: PartAnnotation): PartAnnotation {
  let next = a
  if (hasPolygonOutline(a)) {
    next = {
      ...a,
      bbox: null,
      vectors: vectorsForDisplay(a),
    }
  }
  return next
}

function filterComponentAnnotations(parts: PartAnnotation[]): PartAnnotation[] {
  return parts.filter((a) => !isAxisReferenceLabel(a.name))
}

function renderVector(
  v: AnnotationVector,
  selected: boolean,
  interactive: boolean,
  onSelect?: (e: React.MouseEvent) => void,
  pointsOverride?: [number, number][],
) {
  const pts = pointsOverride ?? v.points
  const stroke = selected ? '#ff7a59' : v.auto ? 'rgba(255, 122, 89, 0.85)' : '#22d3ee'
  const sw = selected ? 3 : 1.5
  const pick = (e: React.MouseEvent) => {
    e.stopPropagation()
    onSelect?.(e)
  }

  if (v.kind === 'polygon' && pts.length >= 3) {
    const d = `${pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`).join(' ')} Z`
    return (
      <g
        key={v.id}
        className={`${selected ? 'annotation-vector-selected' : ''}${interactive ? ' annotation-vector-interactive' : ''}`.trim()}
        onClick={interactive ? pick : undefined}
      >
        {interactive ? (
          <path
            d={d}
            fill="transparent"
            stroke="transparent"
            strokeWidth={VECTOR_HIT_STROKE}
            style={{ cursor: 'pointer', pointerEvents: 'stroke' }}
            onClick={pick}
          />
        ) : null}
        <path
          d={d}
          fill={selected ? 'rgba(255, 122, 89, 0.2)' : 'rgba(255, 122, 89, 0.12)'}
          stroke={stroke}
          strokeWidth={sw}
          strokeLinejoin="round"
          strokeDasharray={v.auto && !selected ? '5 3' : undefined}
          pointerEvents="none"
        />
        {v.label ? (
          <text
            x={pts[0]![0] + 4}
            y={Math.max(12, pts[0]![1] - 6)}
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

  if (v.kind === 'rect' && pts.length >= 3) {
    const d = closedPathFromPoints(pts)
    return (
      <g
        key={v.id}
        className={`${selected ? 'annotation-vector-selected' : ''}${interactive ? ' annotation-vector-interactive' : ''}`.trim()}
        onClick={interactive ? pick : undefined}
      >
        {interactive ? (
          <path
            d={d}
            fill="transparent"
            stroke="transparent"
            strokeWidth={VECTOR_HIT_STROKE}
            style={{ cursor: 'pointer', pointerEvents: 'stroke' }}
            onClick={pick}
          />
        ) : null}
        <path
          d={d}
          fill={selected ? 'rgba(255, 122, 89, 0.18)' : 'rgba(255, 122, 89, 0.1)'}
          stroke={stroke}
          strokeWidth={sw}
          strokeLinejoin="round"
          strokeDasharray={v.auto && !selected ? '6 4' : undefined}
          pointerEvents="none"
        />
        {v.label && pts[0] ? (
          <text
            x={pts[0][0] + 4}
            y={Math.max(12, pts[0][1] - 6)}
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
  if (pts.length < 2) return null
  const d =
    v.kind === 'arrow'
      ? `M ${pts[0]![0]} ${pts[0]![1]} L ${pts[1]![0]} ${pts[1]![1]}`
      : pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`).join(' ')
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
      {v.label && pts[0] ? (
        <text
          x={pts[0][0]}
          y={pts[0][1] - 8}
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
  const propsNameInputRef = useRef<HTMLInputElement>(null)
  const schematicApiRef = useRef<SchematicCanvasApi | null>(null)
  const partDragRef = useRef<{
    id: string
    worldStart: [number, number]
    snapshot: PartAnnotation
    moved: boolean
    dx: number
    dy: number
  } | null>(null)
  const suppressPartClickRef = useRef(false)
  const shapeEditRef = useRef<ShapeEditDrag | null>(null)
  const [shapeEditLive, setShapeEditLive] = useState<{
    partId: string
    vectorId: string
    points: [number, number][]
  } | null>(null)
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
  const [draftCursor, setDraftCursor] = useState<[number, number] | null>(null)
  const [partDragOffset, setPartDragOffset] = useState<{
    id: string
    dx: number
    dy: number
    snapshot: PartAnnotation
  } | null>(null)
  const [busy, setBusy] = useState(false)
  const [detecting, setDetecting] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved'>('idle')
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const detectOnce = useRef(false)
  const [imgKey, setImgKey] = useState(0)
  const [fullscreen, setFullscreen] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [propsPanelOpen, setPropsPanelOpen] = useState(false)

  void histVer

  const displayAnnotations = useMemo(() => {
    let list = annotations
    if (partDragOffset) {
      list = list.map((a) =>
        a.id === partDragOffset.id
          ? translatePart(partDragOffset.snapshot, partDragOffset.dx, partDragOffset.dy)
          : a,
      )
    }
    if (shapeEditLive) {
      list = list.map((a) => {
        if (a.id !== shapeEditLive.partId) return a
        const vectors = a.vectors.map((v) =>
          v.id === shapeEditLive.vectorId ? { ...v, points: shapeEditLive.points } : v,
        )
        const v = vectors.find((x) => x.id === shapeEditLive.vectorId)
        let next: PartAnnotation = { ...a, vectors, auto_detected: false }
        if (v?.kind === 'rect') next.bbox = bboxFromPoints(shapeEditLive.points)
        return normalizePartShape(next)
      })
    }
    return list
  }, [annotations, partDragOffset, shapeEditLive])

  const primaryAnnId = selectedAnnIds.at(-1) ?? null
  const selectedAnn =
    selectedAnnIds.length === 1
      ? (displayAnnotations.find((a) => a.id === primaryAnnId) ?? null)
      : null
  const isDrawingPath = drawMode === 'polygon' || drawMode === 'polyline'
  const isPartSelected = (id: string) => selectedAnnIds.includes(id)

  const editShape = useMemo(() => {
    if (drawMode !== 'select' || selectedAnnIds.length !== 1 || !primaryAnnId) return null
    const a = displayAnnotations.find((x) => x.id === primaryAnnId)
    if (!a) return null
    const v = resolveEditableVector(a, selectedVectorId)
    if (!v) return null
    const points = vectorPointsForDisplay(a, v, shapeEditLive)
    return { part: a, vector: v, points }
  }, [
    drawMode,
    selectedAnnIds.length,
    primaryAnnId,
    displayAnnotations,
    selectedVectorId,
    shapeEditLive,
  ])

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
      apply(filterComponentAnnotations(doc.annotations.map(normalizePartShape)), false)
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
      replace(filterComponentAnnotations(doc.annotations.map(normalizePartShape)), true)
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
        if (!inField && isDrawingPath && draftPoints.length > 0) {
          e.preventDefault()
          setDraftPoints([])
          setDraftCursor(null)
          return
        }
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
    isDrawingPath,
    draftPoints.length,
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
        setPropsPanelOpen(true)
        requestAnimationFrame(() => {
          propsNameInputRef.current?.focus()
          propsNameInputRef.current?.select()
          propsNameInputRef.current
            ?.closest('.annotation-part-li--expanded')
            ?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
        })
      }
    },
    [annotations, onSelectNode],
  )

  useEffect(() => {
    if (!selectedAnn) setPropsPanelOpen(false)
  }, [selectedAnn])

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

  const updateSelectedExtra = useCallback(
    (extra: Record<string, unknown>) => {
      if (!primaryAnnId || selectedAnnIds.length !== 1) return
      apply(
        annotations.map((a) =>
          a.id === primaryAnnId
            ? { ...a, extra, auto_detected: false }
            : a,
        ),
        true,
      )
    },
    [annotations, apply, primaryAnnId, selectedAnnIds.length],
  )

  const selectedVector = useMemo(() => {
    if (!selectedVectorId || !primaryAnnId) return null
    const ann = annotations.find((a) => a.id === primaryAnnId)
    const vec = ann?.vectors.find((v) => v.id === selectedVectorId)
    return ann && vec ? { ann, vec } : null
  }, [annotations, primaryAnnId, selectedVectorId])

  const updateSelectedVector = useCallback(
    (patch: Partial<Pick<AnnotationVector, 'label'>>) => {
      if (!selectedVectorId || !primaryAnnId) return
      apply(
        annotations.map((a) => {
          if (a.id !== primaryAnnId) return a
          return {
            ...a,
            auto_detected: false,
            vectors: a.vectors.map((v) =>
              v.id === selectedVectorId ? { ...v, ...patch } : v,
            ),
          }
        }),
        true,
      )
    },
    [annotations, apply, primaryAnnId, selectedVectorId],
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

  const resolveVectorTargetId = useCallback((): string | null => {
    if (primaryAnnId) return primaryAnnId
    if (!annotations.length) {
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
      return a.id
    }
    return annotations[0]?.id ?? null
  }, [annotations, apply, primaryAnnId])

  const finishPathDrawing = useCallback(() => {
    const minPts = drawMode === 'polygon' ? 3 : 2
    if (draftPoints.length < minPts) {
      setDraftPoints([])
      setDraftCursor(null)
      return
    }
    const targetId = resolveVectorTargetId()
    if (!targetId) return
    const kind: AnnotationVectorKind = drawMode === 'polygon' ? 'polygon' : 'polyline'
    const vec: AnnotationVector = {
      id: uid(),
      kind,
      points: [...draftPoints],
      auto: false,
      label: annotations.find((a) => a.id === targetId)?.name,
    }
    apply(
      annotations.map((a) => {
        if (a.id !== targetId) return a
        const cleaned = a.vectors.filter((v) => !(v.auto && v.kind === 'rect'))
        const next: PartAnnotation = {
          ...a,
          vectors: [...cleaned, vec],
          auto_detected: false,
          // Polygon points are the shape — do not replace with axis-aligned bbox rect.
          bbox: kind === 'polygon' ? null : a.bbox,
        }
        return next
      }),
      true,
    )
    setDraftPoints([])
    setDraftCursor(null)
  }, [annotations, apply, draftPoints, drawMode, resolveVectorTargetId])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      const inField = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'

      if (!inField && isDrawingPath && draftPoints.length > 0) {
        if (e.key === 'Escape') {
          e.preventDefault()
          setDraftPoints([])
          setDraftCursor(null)
          return
        }
        if (e.key === 'Enter') {
          e.preventDefault()
          finishPathDrawing()
          return
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [isDrawingPath, draftPoints.length, finishPathDrawing])

  const commitShapePoints = useCallback(
    (
      partId: string,
      vectorId: string,
      kind: AnnotationVectorKind,
      points: [number, number][],
    ) => {
      apply(
        annotations.map((a) => {
          if (a.id !== partId) return a
          const vectors = a.vectors.map((v) => {
            if (v.id !== vectorId) return v
            const kindOut = effectiveVectorKind(kind, points)
            return { ...v, kind: kindOut, points }
          })
          let next: PartAnnotation = { ...a, vectors, auto_detected: false }
          const v = vectors.find((x) => x.id === vectorId)
          if (v?.kind === 'rect') next.bbox = bboxFromPoints(v.points)
          else if (v?.kind === 'polygon') next.bbox = null
          return normalizePartShape(next)
        }),
        true,
      )
    },
    [annotations, apply],
  )

  const startVertexDrag = useCallback(
    (
      e: React.PointerEvent,
      a: PartAnnotation,
      v: AnnotationVector,
      vertexIndex: number,
      api: SchematicCanvasApi,
    ) => {
      if (drawMode !== 'select' || shapeEditRef.current || partDragRef.current) return
      e.stopPropagation()
      e.preventDefault()
      const snapshot = v.points.map((p) => [...p] as [number, number])
      shapeEditRef.current = {
        mode: 'vertex',
        partId: a.id,
        vectorId: v.id,
        kind: v.kind,
        vertexIndex,
        snapshot,
        latestPoints: snapshot,
        worldStart: worldPt(api, e.clientX, e.clientY),
        moved: false,
      }
      setSelectedAnnIds([a.id])
      setSelectedVectorId(v.id)
      ;(e.currentTarget as SVGElement).setPointerCapture(e.pointerId)
    },
    [drawMode],
  )

  const startEdgeDrag = useCallback(
    (
      e: React.PointerEvent,
      a: PartAnnotation,
      v: AnnotationVector,
      edgeIndex: number,
      closed: boolean,
      api: SchematicCanvasApi,
    ) => {
      if (drawMode !== 'select' || shapeEditRef.current || partDragRef.current) return
      e.stopPropagation()
      e.preventDefault()
      const snapshot = v.points.map((p) => [...p] as [number, number])
      shapeEditRef.current = {
        mode: 'edge',
        partId: a.id,
        vectorId: v.id,
        kind: v.kind,
        edgeIndex,
        closed,
        snapshot,
        latestPoints: snapshot,
        worldStart: worldPt(api, e.clientX, e.clientY),
        moved: false,
      }
      setSelectedAnnIds([a.id])
      setSelectedVectorId(v.id)
      ;(e.currentTarget as SVGElement).setPointerCapture(e.pointerId)
    },
    [drawMode],
  )

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      const drag = shapeEditRef.current
      const api = schematicApiRef.current
      if (!drag || !api) return
      const [x, y] = worldPt(api, e.clientX, e.clientY)
      const dx = x - drag.worldStart[0]
      const dy = y - drag.worldStart[1]
      if (Math.hypot(dx, dy) > 1) drag.moved = true
      if (drag.mode === 'vertex' && drag.vertexIndex != null) {
        drag.latestPoints = updatePointsForVertex(
          drag.kind,
          drag.snapshot,
          drag.vertexIndex,
          [x, y],
          false,
        )
      } else if (drag.mode === 'edge' && drag.edgeIndex != null) {
        drag.latestPoints = updatePointsForEdge(
          drag.snapshot,
          drag.edgeIndex,
          dx,
          dy,
          drag.closed ?? false,
        )
      }
      setShapeEditLive({
        partId: drag.partId,
        vectorId: drag.vectorId,
        points: drag.latestPoints,
      })
    }
    const onUp = () => {
      const drag = shapeEditRef.current
      if (!drag) return
      if (drag.moved) {
        suppressPartClickRef.current = true
        commitShapePoints(
          drag.partId,
          drag.vectorId,
          drag.kind,
          drag.latestPoints,
        )
      }
      shapeEditRef.current = null
      setShapeEditLive(null)
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
  }, [commitShapePoints])

  const startPartDrag = useCallback(
    (e: React.PointerEvent, a: PartAnnotation, api: SchematicCanvasApi) => {
      if (drawMode !== 'select' || partDragRef.current || shapeEditRef.current) return
      e.stopPropagation()
      e.preventDefault()
      const worldStart = worldPt(api, e.clientX, e.clientY)
      partDragRef.current = {
        id: a.id,
        worldStart,
        snapshot: clonePart(a),
        moved: false,
        dx: 0,
        dy: 0,
      }
      setPartDragOffset({ id: a.id, dx: 0, dy: 0, snapshot: clonePart(a) })
      ;(e.currentTarget as SVGRectElement).setPointerCapture(e.pointerId)
    },
    [drawMode, dim.w, dim.h],
  )

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      const drag = partDragRef.current
      const api = schematicApiRef.current
      if (!drag || !api) return
      const [x, y] = worldPt(api, e.clientX, e.clientY)
      const dx = x - drag.worldStart[0]
      const dy = y - drag.worldStart[1]
      if (Math.hypot(dx, dy) > 2) drag.moved = true
      drag.dx = dx
      drag.dy = dy
      setPartDragOffset({ id: drag.id, dx, dy, snapshot: drag.snapshot })
    }
    const onUp = () => {
      const drag = partDragRef.current
      if (!drag) return
      if (drag.moved) {
        suppressPartClickRef.current = true
        const { id, snapshot, dx, dy } = drag
        apply(
          annotations.map((a) => (a.id === id ? translatePart(snapshot, dx, dy) : a)),
          true,
        )
      }
      partDragRef.current = null
      setPartDragOffset(null)
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
    }
  }, [annotations, apply, dim.w, dim.h])

  const onSelectBackdropPointerDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return
    e.stopPropagation()
    clearSelection()
  }

  const onSvgPointerDown = (e: React.PointerEvent<SVGSVGElement>, api: SchematicCanvasApi) => {
    schematicApiRef.current = api
    if (drawMode === 'select') return
    if (dim.w <= 0) return
    e.stopPropagation()
    e.preventDefault()

    if (drawMode === 'polygon' || drawMode === 'polyline') {
      const pt = worldPt(api, e.clientX, e.clientY)
      const closePx = Math.max(12, 18 / api.scale)
      if (
        drawMode === 'polygon' &&
        draftPoints.length >= 3 &&
        Math.hypot(pt[0] - draftPoints[0]![0], pt[1] - draftPoints[0]![1]) <= closePx
      ) {
        finishPathDrawing()
        return
      }
      setDraftPoints((prev) => [...prev, pt])
      setDraftCursor(pt)
      return
    }

    if (drawMode === 'line' || drawMode === 'arrow' || drawMode === 'rect') {
      const pt = worldPt(api, e.clientX, e.clientY)
      if (draftPoints.length === 0) {
        setDraftPoints([pt])
        setDraftCursor(pt)
        return
      }
      commitTwoPointShape(api, e.clientX, e.clientY)
      return
    }
  }

  const commitTwoPointShape = (
    api: SchematicCanvasApi,
    clientX: number,
    clientY: number,
  ) => {
    const end = worldPt(api, clientX, clientY)
    const start = draftPoints[0]
    if (!start) return
    let points: [number, number][] = [start, end]
    if (drawMode === 'rect') {
      points = [
        [start[0], start[1]],
        [end[0], start[1]],
        [end[0], end[1]],
        [start[0], end[1]],
      ]
    }
    const targetId = resolveVectorTargetId()
    if (!targetId) {
      setDraftPoints([])
      setDraftCursor(null)
      return
    }
    const kind: AnnotationVectorKind =
      drawMode === 'arrow' ? 'arrow' : drawMode === 'rect' ? 'rect' : 'line'
    const vec: AnnotationVector = {
      id: uid(),
      kind,
      points,
      auto: false,
      label: annotations.find((a) => a.id === targetId)?.name ?? null,
    }
    const bb = kind === 'rect' ? bboxFromPoints(points) : null
    apply(
      annotations.map((a) => {
        if (a.id !== targetId) return a
        const next: PartAnnotation = {
          ...a,
          vectors: [...a.vectors, vec],
          auto_detected: false,
        }
        if (bb) next.bbox = bb
        return next
      }),
      true,
    )
    setDraftPoints([])
    setDraftCursor(null)
  }

  const onSvgPointerMove = (e: React.PointerEvent<SVGSVGElement>, api: SchematicCanvasApi) => {
    schematicApiRef.current = api
    if (isDrawingPath && draftPoints.length > 0) {
      setDraftCursor(worldPt(api, e.clientX, e.clientY))
      return
    }
    if (!draftPoints.length || drawMode === 'select' || isDrawingPath) return
    setDraftCursor(worldPt(api, e.clientX, e.clientY))
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
          {(
            [
              ['select', 'Select'],
              ['polygon', 'Polygon'],
              ['polyline', 'Path'],
              ['line', 'Line'],
              ['arrow', 'Arrow'],
              ['rect', 'Rect'],
            ] as [DrawMode, string][]
          ).map(([m, label]) => (
            <button
              key={m}
              type="button"
              className={`btn btn-ghost ${drawMode === m ? 'tab-active' : ''}`}
              onClick={() => {
                setDrawMode(m)
                setDraftPoints([])
                setDraftCursor(null)
              }}
            >
              {label}
            </button>
          ))}
          {isDrawingPath && draftPoints.length > 0 ? (
            <button type="button" className="btn btn-ghost" onClick={() => finishPathDrawing()}>
              Finish shape ({draftPoints.length} pts)
            </button>
          ) : null}
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

      <div
        className={`annotation-body ${sidebarOpen ? '' : 'annotation-body--sidebar-collapsed'}`.trim()}
      >
        <SchematicCanvas
          projectId={projectId}
          imageKey={imgKey}
          naturalSize={dim}
          panOnDrag={
            drawMode === 'select' && !partDragOffset && !shapeEditLive && !isDrawingPath
          }
          svgInteractive={drawMode !== 'select'}
          cornerLabel={
            isDrawingPath
              ? 'Click each corner · click first point or Enter to finish · Esc cancel'
              : drawMode === 'line' || drawMode === 'arrow' || drawMode === 'rect'
                ? 'Click start, then click end · Esc cancel'
                : 'Drag corner handles to reshape · edge handles to slide sides · drag inside to move · scroll to zoom'
          }
          onImageLoad={(w, h) => setDim({ w, h })}
          onPanSurfacePointerDown={drawMode === 'select' ? clearSelection : undefined}
          onSvgPointerDown={onSvgPointerDown}
          onSvgPointerMove={onSvgPointerMove}
          onSvgPointerLeave={() => {
            if (!isDrawingPath) setDraftPoints([])
            setDraftCursor(null)
          }}
        >
          {(api) => {
            schematicApiRef.current = api
            return (
            <>
              {drawMode === 'select' && dim.w > 0 ? (
                <rect
                  className="annotation-select-backdrop"
                  x={0}
                  y={0}
                  width={dim.w}
                  height={dim.h}
                  fill="transparent"
                  onPointerDown={onSelectBackdropPointerDown}
                />
              ) : null}
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
              {displayAnnotations.map((a) => {
                const bb = a.bbox
                if (!bb || !shouldShowBboxOverlay(a)) return null
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
                ? displayAnnotations.map((a) => {
                    if (isPartSelected(a.id)) return null
                    const hit = partHitBounds(a)
                    if (!hit) return null
                    return (
                      <rect
                        key={`hit-${a.id}`}
                        className="annotation-part-hit"
                        x={hit.x}
                        y={hit.y}
                        width={hit.w}
                        height={hit.h}
                        style={{ cursor: 'pointer' }}
                        onPointerDown={(e) => startPartDrag(e, a, api)}
                        onClick={(e) => {
                          if (suppressPartClickRef.current) {
                            suppressPartClickRef.current = false
                            e.stopPropagation()
                            return
                          }
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
              {displayAnnotations.map((a) => {
                const partSel = isPartSelected(a.id) && !selectedVectorId
                return vectorsForDisplay(a).map((v) => {
                  const pts = vectorPointsForDisplay(a, v, shapeEditLive)
                  const selected =
                    v.id === selectedVectorId ||
                    (partSel &&
                      (v.kind === 'polygon' || v.kind === 'rect') &&
                      pts.length >= 3)
                  return renderVector(
                    v,
                    selected,
                    drawMode === 'select',
                    (e) =>
                      selectVector(a, v, {
                        shiftKey: e.shiftKey,
                        ctrlKey: e.metaKey || e.ctrlKey,
                      }),
                    pts,
                  )
                })
              })}
              {drawMode === 'select'
                ? displayAnnotations.map((a) => {
                    if (!isPartSelected(a.id)) return null
                    const d = partInteriorPath(a)
                    if (!d) return null
                    const dragging = partDragOffset?.id === a.id
                    return (
                      <path
                        key={`body-${a.id}`}
                        d={d}
                        className={`annotation-part-body-drag${dragging ? ' annotation-part-body-drag--dragging' : ''}`}
                        fill={
                          dragging
                            ? 'rgba(255, 122, 89, 0.14)'
                            : 'rgba(255, 122, 89, 0.05)'
                        }
                        stroke="none"
                        style={{ cursor: dragging ? 'grabbing' : 'grab' }}
                        onPointerDown={(e) => startPartDrag(e, a, api)}
                        onClick={(e) => {
                          if (suppressPartClickRef.current) {
                            suppressPartClickRef.current = false
                            e.stopPropagation()
                            return
                          }
                          e.stopPropagation()
                          selectPartWithModifiers(a, {
                            shiftKey: e.shiftKey,
                            ctrlKey: e.metaKey || e.ctrlKey,
                          })
                        }}
                      />
                    )
                  })
                : null}
              {drawMode === 'select' && editShape
                ? (() => {
                    const { part: a, vector: v, points: pts } = editShape
                    const r = Math.max(5, 8 / api.scale)
                    const er = Math.max(4, 6 / api.scale)
                    const closed =
                      v.kind === 'polygon' ||
                      v.kind === 'rect' ||
                      (v.kind === 'polyline' && pts.length >= 3)
                    const showEdges = pts.length >= 3
                    const mids = showEdges ? edgeMidpoints(pts, closed) : []
                    return (
                      <g key={`handles-${v.id}`} className="annotation-shape-handles">
                        {mids.map((p, edgeIndex) => (
                          <rect
                            key={`edge-${edgeIndex}`}
                            className="annotation-shape-handle annotation-shape-handle--edge"
                            x={p[0] - er}
                            y={p[1] - er}
                            width={er * 2}
                            height={er * 2}
                            rx={1}
                            onPointerDown={(e) => startEdgeDrag(e, a, v, edgeIndex, closed, api)}
                          />
                        ))}
                        {pts.map((p, vertexIndex) => (
                          <circle
                            key={`vertex-${vertexIndex}`}
                            className="annotation-shape-handle annotation-shape-handle--vertex"
                            cx={p[0]}
                            cy={p[1]}
                            r={r}
                            onPointerDown={(e) =>
                              startVertexDrag(e, a, v, vertexIndex, api)
                            }
                          />
                        ))}
                      </g>
                    )
                  })()
                : null}
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
              {isDrawingPath && draftPoints.length >= 3 && drawMode === 'polygon' ? (
                <circle
                  className="annotation-path-close"
                  cx={draftPoints[0]![0]}
                  cy={draftPoints[0]![1]}
                  r={Math.max(10, 16 / api.scale)}
                  fill="rgba(34, 211, 238, 0.15)"
                  stroke="#22d3ee"
                  strokeWidth={2}
                  onPointerDown={(e) => {
                    e.stopPropagation()
                    e.preventDefault()
                    finishPathDrawing()
                  }}
                  onDoubleClick={(e) => {
                    e.stopPropagation()
                    finishPathDrawing()
                  }}
                />
              ) : null}
              {isDrawingPath && draftPoints.length >= 1 ? (
                <g className="annotation-draft-overlay">
                  {draftPoints.map((p, i) => (
                    <circle
                      key={`draft-pt-${i}`}
                      cx={p[0]}
                      cy={p[1]}
                      r={i === 0 && drawMode === 'polygon' ? 6 : 4}
                      fill={i === 0 && drawMode === 'polygon' ? 'rgba(34, 211, 238, 0.35)' : '#22d3ee'}
                      stroke="#22d3ee"
                      strokeWidth={1.5}
                    />
                  ))}
                  {draftCursor ? (
                    <path
                      d={`${draftPoints.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`).join(' ')} L ${draftCursor[0]} ${draftCursor[1]}`}
                      stroke="#22d3ee"
                      strokeWidth={2}
                      strokeDasharray="6 4"
                      fill="none"
                      strokeLinejoin="round"
                    />
                  ) : null}
                </g>
              ) : null}
              {!isDrawingPath && draftPoints.length >= 1 ? (
                <g className="annotation-draft-overlay">
                  <circle cx={draftPoints[0]![0]} cy={draftPoints[0]![1]} r={4} fill="#22d3ee" />
                  {draftCursor ? (
                    <path
                      d={
                        drawMode === 'rect'
                          ? `M ${draftPoints[0]![0]} ${draftPoints[0]![1]} L ${draftCursor[0]} ${draftPoints[0]![1]} L ${draftCursor[0]} ${draftCursor[1]} L ${draftPoints[0]![0]} ${draftCursor[1]} Z`
                          : `M ${draftPoints[0]![0]} ${draftPoints[0]![1]} L ${draftCursor[0]} ${draftCursor[1]}`
                      }
                      stroke="#22d3ee"
                      strokeWidth={2}
                      fill={drawMode === 'rect' ? 'rgba(34, 211, 238, 0.08)' : 'none'}
                    />
                  ) : null}
                </g>
              ) : null}
            </>
            )
          }}
        </SchematicCanvas>

        <aside
          className={`annotation-sidebar ${sidebarOpen ? '' : 'annotation-sidebar--collapsed'} ${fullscreen && !sidebarOpen ? 'annotation-sidebar-hidden' : ''}`.trim()}
        >
          {sidebarOpen ? (
            <>
              <div className="annotation-sidebar-section">
                <div className="annotation-sidebar-section-head">
                  <span className="annotation-sidebar-section-title">Components</span>
                  <button
                    type="button"
                    className="btn btn-ghost annotation-sidebar-minimize"
                    title="Minimize sidebar"
                    aria-label="Minimize sidebar"
                    onClick={() => setSidebarOpen(false)}
                  >
                    −
                  </button>
                </div>
                <p className="muted annotation-sidebar-hint">
                  Polygon/Path: click corners on the schematic, Enter or click the first point to close.
                  Line/Arrow/Rect: click start, then end. Attach Mass, size, power, etc. per part when needed.
                </p>
                <ul className="annotation-part-list">
                  {annotations.map((a) => {
                    const isSingleSelected =
                      selectedAnnIds.length === 1 && primaryAnnId === a.id
                    const showInlineEditor = isSingleSelected && propsPanelOpen && selectedAnn
                    return (
                      <li
                        key={a.id}
                        className={showInlineEditor ? 'annotation-part-li--expanded' : undefined}
                      >
                        <div className="annotation-part-row">
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
                          {isSingleSelected ? (
                            <button
                              type="button"
                              className="annotation-props-inline-toggle"
                              aria-expanded={propsPanelOpen}
                              aria-label={propsPanelOpen ? 'Collapse details' : 'Expand details'}
                              title={propsPanelOpen ? 'Collapse details' : 'Expand details'}
                              onClick={() => setPropsPanelOpen((o) => !o)}
                            >
                              {propsPanelOpen ? '▾' : '▸'}
                            </button>
                          ) : null}
                        </div>
                        {showInlineEditor ? (
                          <div className="annotation-props annotation-props--inline">
                            <label className="annotation-field">
                              Part name
                              <input
                                ref={propsNameInputRef}
                                className="auth-input"
                                value={selectedAnn.name}
                                onChange={(e) => updateSelected({ name: e.target.value })}
                              />
                            </label>
                            {selectedVector ? (
                              <label className="annotation-field">
                                Shape label (on schematic)
                                <input
                                  className="auth-input"
                                  value={selectedVector.vec.label ?? ''}
                                  placeholder={selectedAnn.name}
                                  onChange={(e) =>
                                    updateSelectedVector({
                                      label: e.target.value || null,
                                    })
                                  }
                                />
                              </label>
                            ) : null}
                            <PartDataFieldsEditor
                              part={selectedAnn}
                              onChange={updateSelected}
                              onExtraChange={updateSelectedExtra}
                            />
                            <p className="muted" style={{ fontSize: '0.68rem', margin: '0 0 0.35rem' }}>
                              {selectedVectorId
                                ? 'Line/shape selected — Delete removes it.'
                                : 'Delete removes this part.'}
                            </p>
                            <button
                              type="button"
                              className="btn btn-ghost"
                              onClick={() => deleteSelection()}
                            >
                              {selectedVectorId ? 'Remove line/shape' : 'Remove part'}
                            </button>
                          </div>
                        ) : null}
                      </li>
                    )
                  })}
                </ul>
              </div>

              {selectedAnnIds.length > 1 ? (
                <div className="annotation-sidebar-section">
                  <button
                    type="button"
                    className="annotation-props-toggle"
                    aria-expanded={propsPanelOpen}
                    onClick={() => setPropsPanelOpen((o) => !o)}
                  >
                    <span>{selectedAnnIds.length} parts selected</span>
                    <span className="annotation-props-chevron" aria-hidden>
                      {propsPanelOpen ? '▾' : '▸'}
                    </span>
                  </button>
                  {propsPanelOpen ? (
                    <div className="annotation-props">
                      <button type="button" className="btn btn-ghost" onClick={() => deleteSelection()}>
                        Remove {selectedAnnIds.length} parts
                      </button>
                    </div>
                  ) : null}
                </div>
              ) : !selectedAnn ? (
                <p className="muted annotation-sidebar-empty">
                  Double-click a part in the list or on the schematic to edit it.
                </p>
              ) : null}
            </>
          ) : (
            <button
              type="button"
              className="annotation-sidebar-expand"
              title="Show components panel"
              onClick={() => setSidebarOpen(true)}
            >
              <span className="annotation-sidebar-expand-label">Components</span>
            </button>
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
