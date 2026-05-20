import { useCallback, useState } from 'react'
import type { DiagramNode } from '../api/types'
import { classifySubsystem, type Subsystem } from '../lib/subsystems'
import { componentDiagramNodes } from '../lib/schematicLabels'
import { ProjectImage } from './ProjectImage'
import { useSelectionStore } from '../state/project'

export function bboxForNode(n: DiagramNode) {
  const g = n.geometry
  if (g?.bbox && g.bbox.w > 0 && g.bbox.h > 0) return g.bbox
  const pl = g?.polyline_px
  if (pl?.length) {
    let minX = Infinity
    let minY = Infinity
    let maxX = -Infinity
    let maxY = -Infinity
    for (const pt of pl) {
      const [x, y] = pt
      minX = Math.min(minX, x)
      minY = Math.min(minY, y)
      maxX = Math.max(maxX, x)
      maxY = Math.max(maxY, y)
    }
    const w = Math.max(8, maxX - minX)
    const h = Math.max(8, maxY - minY)
    return { x: minX, y: minY, w, h }
  }
  const ports = n.ports?.filter((p) => p.position_px)
  if (ports?.length) {
    const xs = ports.map((p) => p.position_px![0])
    const ys = ports.map((p) => p.position_px![1])
    const minX = Math.min(...xs)
    const maxX = Math.max(...xs)
    const minY = Math.min(...ys)
    const maxY = Math.max(...ys)
    const pad = 36
    return {
      x: minX - pad,
      y: minY - pad,
      w: Math.max(24, maxX - minX + 2 * pad),
      h: Math.max(24, maxY - minY + 2 * pad),
    }
  }
  return null
}

type Props = {
  projectId: string
  nodes: DiagramNode[]
  activeSubsystem?: Subsystem
  onDropCsv?: (nodeId: string, file: File) => void
}

export function ImageOverlay({ projectId, nodes, activeSubsystem, onDropCsv }: Props) {
  const selected = useSelectionStore((s) => s.selectedNodeId)
  const setSel = useSelectionStore((s) => s.setSelected)
  const [dim, setDim] = useState({ w: 0, h: 0 })

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
  }, [])

  return (
    <div className="workspace-canvas">
      <span className="canvas-corner">
        DIAGRAM OVERLAY · {activeSubsystem?.toUpperCase() ?? 'ALL'}
      </span>
      <ProjectImage
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
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            width: '100%',
            height: '100%',
            pointerEvents: 'none',
          }}
          viewBox={`0 0 ${dim.w} ${dim.h}`}
          preserveAspectRatio="xMidYMid meet"
        >
          {componentDiagramNodes(nodes).map((n) => {
            const bb = bboxForNode(n)
            if (!bb) return null
            const inSubsystem =
              !activeSubsystem || classifySubsystem(n) === activeSubsystem
            const cls = n.id === selected ? 'hotspot hotspot-selected' : 'hotspot'
            return (
              <rect
                key={n.id}
                x={bb.x}
                y={bb.y}
                width={bb.w}
                height={bb.h}
                className={cls}
                style={{
                  pointerEvents: inSubsystem ? 'auto' : 'none',
                  opacity: inSubsystem ? 1 : 0.22,
                }}
                onClick={() => setSel(n.id)}
                onDragOver={onDropCsv ? onDragOver : undefined}
                onDrop={
                  onDropCsv
                    ? (e) => {
                        e.preventDefault()
                        const f = e.dataTransfer.files[0]
                        if (f) onDropCsv(n.id, f)
                      }
                    : undefined
                }
              />
            )
          })}
        </svg>
      ) : null}
    </div>
  )
}
