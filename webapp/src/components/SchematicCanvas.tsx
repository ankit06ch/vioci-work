import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type WheelEvent,
} from 'react'
import { ProjectImage } from './ProjectImage'

const MIN_SCALE = 0.08
const MAX_SCALE = 12
const ZOOM_STEP = 1.12

export type SchematicCanvasApi = {
  screenToWorld: (clientX: number, clientY: number) => [number, number]
  scale: number
}

type Props = {
  projectId: string
  imageKey?: number
  naturalSize: { w: number; h: number }
  onImageLoad?: (w: number, h: number) => void
  /** When true, left-drag on empty canvas pans (select mode). */
  panOnDrag?: boolean
  children?: (api: SchematicCanvasApi) => ReactNode
  cornerLabel?: string
  onSvgMouseDown?: (e: React.MouseEvent<SVGSVGElement>, api: SchematicCanvasApi) => void
  onSvgMouseMove?: (e: React.MouseEvent<SVGSVGElement>, api: SchematicCanvasApi) => void
  onSvgMouseUp?: (e: React.MouseEvent<SVGSVGElement>, api: SchematicCanvasApi) => void
  onSvgMouseLeave?: (e: React.MouseEvent<SVGSVGElement>, api: SchematicCanvasApi) => void
}

export function SchematicCanvas({
  projectId,
  imageKey = 0,
  naturalSize,
  onImageLoad,
  panOnDrag = true,
  children,
  cornerLabel,
  onSvgMouseDown,
  onSvgMouseMove,
  onSvgMouseUp,
  onSvgMouseLeave,
}: Props) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const panDrag = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null)
  const spaceHeld = useRef(false)

  const fitToView = useCallback(() => {
    const vp = viewportRef.current
    const { w, h } = naturalSize
    if (!vp || w <= 0 || h <= 0) return
    const pad = 24
    const s = Math.min((vp.clientWidth - pad) / w, (vp.clientHeight - pad) / h, 1.5)
    const clamped = Math.max(MIN_SCALE, Math.min(MAX_SCALE, s))
    setScale(clamped)
    setPan({
      x: (vp.clientWidth - w * clamped) / 2,
      y: (vp.clientHeight - h * clamped) / 2,
    })
  }, [naturalSize])

  useEffect(() => {
    fitToView()
  }, [fitToView, naturalSize.w, naturalSize.h, imageKey])

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space') spaceHeld.current = true
    }
    const onKeyUp = (e: KeyboardEvent) => {
      if (e.code === 'Space') {
        spaceHeld.current = false
        panDrag.current = null
      }
    }
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
    }
  }, [])

  const screenToWorld = useCallback(
    (clientX: number, clientY: number): [number, number] => {
      const vp = viewportRef.current
      if (!vp) return [0, 0]
      const rect = vp.getBoundingClientRect()
      const mx = clientX - rect.left
      const my = clientY - rect.top
      return [(mx - pan.x) / scale, (my - pan.y) / scale]
    },
    [pan.x, pan.y, scale],
  )

  const onWheel = useCallback(
    (e: WheelEvent) => {
      e.preventDefault()
      const vp = viewportRef.current
      if (!vp) return
      const rect = vp.getBoundingClientRect()
      const mx = e.clientX - rect.left
      const my = e.clientY - rect.top
      const worldX = (mx - pan.x) / scale
      const worldY = (my - pan.y) / scale
      const factor = e.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP
      const nextScale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, scale * factor))
      setScale(nextScale)
      setPan({
        x: mx - worldX * nextScale,
        y: my - worldY * nextScale,
      })
    },
    [pan.x, pan.y, scale],
  )

  const zoomBy = useCallback(
    (factor: number) => {
      const vp = viewportRef.current
      if (!vp) return
      const cx = vp.clientWidth / 2
      const cy = vp.clientHeight / 2
      const worldX = (cx - pan.x) / scale
      const worldY = (cy - pan.y) / scale
      const nextScale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, scale * factor))
      setScale(nextScale)
      setPan({
        x: cx - worldX * nextScale,
        y: cy - worldY * nextScale,
      })
    },
    [pan.x, pan.y, scale],
  )

  const canPanDrag = (e: React.PointerEvent) =>
    e.button === 1 ||
    spaceHeld.current ||
    (panOnDrag && e.button === 0 && (e.target as HTMLElement).dataset.panSurface === '1')

  const onPointerDown = (e: React.PointerEvent) => {
    if (!canPanDrag(e)) return
    e.preventDefault()
    panDrag.current = { x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y }
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  }

  const onPointerMove = (e: React.PointerEvent) => {
    if (!panDrag.current) return
    setPan({
      x: panDrag.current.panX + (e.clientX - panDrag.current.x),
      y: panDrag.current.panY + (e.clientY - panDrag.current.y),
    })
  }

  const onPointerUp = (e: React.PointerEvent) => {
    if (panDrag.current) {
      panDrag.current = null
      ;(e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId)
    }
  }

  const api: SchematicCanvasApi = { screenToWorld, scale }

  return (
    <div className="schematic-canvas-wrap">
      <div className="schematic-canvas-controls">
        <button type="button" className="btn btn-ghost" onClick={() => zoomBy(ZOOM_STEP)} title="Zoom in">
          +
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => zoomBy(1 / ZOOM_STEP)}
          title="Zoom out"
        >
          −
        </button>
        <button type="button" className="btn btn-ghost" onClick={fitToView} title="Fit schematic">
          Fit
        </button>
        <span className="muted mono schematic-canvas-zoom-label">{Math.round(scale * 100)}%</span>
        <span className="muted mono schematic-canvas-hint">Scroll to zoom · drag to pan · Space+drag</span>
      </div>
      <div
        ref={viewportRef}
        className="schematic-canvas-viewport"
        data-pan-surface="1"
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
      >
        <div
          className="schematic-canvas-stage"
          style={{
            width: naturalSize.w,
            height: naturalSize.h,
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})`,
            transformOrigin: '0 0',
          }}
        >
          {cornerLabel ? <span className="canvas-corner">{cornerLabel}</span> : null}
          <ProjectImage
            key={imageKey}
            projectId={projectId}
            className="schematic-canvas-img"
            alt="Schematic"
            draggable={false}
            onLoad={(ev) => {
              const t = ev.currentTarget
              onImageLoad?.(t.naturalWidth, t.naturalHeight)
            }}
          />
          {naturalSize.w > 0 ? (
            <svg
              className="schematic-canvas-svg"
              viewBox={`0 0 ${naturalSize.w} ${naturalSize.h}`}
              width={naturalSize.w}
              height={naturalSize.h}
              onMouseDown={onSvgMouseDown ? (e) => onSvgMouseDown(e, api) : undefined}
              onMouseMove={onSvgMouseMove ? (e) => onSvgMouseMove(e, api) : undefined}
              onMouseUp={onSvgMouseUp ? (e) => onSvgMouseUp(e, api) : undefined}
              onMouseLeave={onSvgMouseLeave ? (e) => onSvgMouseLeave(e, api) : undefined}
            >
              {children?.(api)}
            </svg>
          ) : null}
        </div>
      </div>
    </div>
  )
}
