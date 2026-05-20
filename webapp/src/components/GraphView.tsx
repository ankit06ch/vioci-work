import { useCallback, useEffect, useMemo, useRef, type CSSProperties } from 'react'
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
} from 'reactflow'
import type { Edge, Node } from 'reactflow'
import 'reactflow/dist/style.css'
import type { Diagram, DiagramNode } from '../api/types'
import { componentDiagramNodes, nodeDisplayTitle } from '../lib/schematicLabels'
import { bboxForNode } from './ImageOverlay'
import { SchemaNode } from './SchemaNode'
import { useSelectionStore } from '../state/project'

const nodeTypes = { schema: SchemaNode }

function nodeStyle(selected: boolean): CSSProperties {
  return {
    borderRadius: 4,
    border: selected ? '1px solid #ff8f4a' : '1px solid rgba(255, 122, 89, 0.32)',
    background: selected ? 'rgba(255, 122, 89, 0.12)' : 'rgba(27, 23, 27, 0.92)',
    color: '#f3f1f1',
    fontSize: 11,
    fontWeight: 600,
    fontFamily: 'JetBrains Mono, monospace',
    boxShadow: selected
      ? '0 0 16px rgba(255, 122, 89, 0.22)'
      : '0 0 10px rgba(255, 122, 89, 0.06)',
  }
}

function nodePosition(n: DiagramNode, i: number) {
  const bb = bboxForNode(n)
  if (bb) return { x: bb.x + bb.w / 2 - 70, y: bb.y + bb.h / 2 - 24 }
  return { x: (i % 6) * 180, y: Math.floor(i / 6) * 120 }
}

type Props = {
  diagram: Diagram
}

export function GraphViewWithProvider(props: Props) {
  return (
    <ReactFlowProvider>
      <GraphViewInner {...props} />
    </ReactFlowProvider>
  )
}

function GraphViewInner({ diagram }: Props) {
  const selected = useSelectionStore((s) => s.selectedNodeId)
  const setSel = useSelectionStore((s) => s.setSelected)
  const { fitView } = useReactFlow()
  const fittedRef = useRef(false)

  const componentNodes = useMemo(
    () => componentDiagramNodes(diagram.nodes),
    [diagram.nodes],
  )

  const initNodes = useMemo(() => {
    return componentNodes.map((n, i) => {
      const p = nodePosition(n, i)
      return {
        id: n.id,
        type: 'schema',
        position: p,
        data: { label: nodeDisplayTitle(n) },
        style: nodeStyle(false),
      } satisfies Node
    })
  }, [componentNodes])

  const initEdges = useMemo(() => {
    const ids = new Set(componentNodes.map((n) => n.id))
    return diagram.edges
      .filter((e) => ids.has(e.source) && ids.has(e.target))
      .map(
        (e) =>
          ({
            id: e.id,
            source: e.source,
            target: e.target,
            label: e.label ?? undefined,
            style: { stroke: 'rgba(255, 122, 89, 0.4)', strokeWidth: 1.5 },
            labelStyle: { fill: '#b0a8ac', fontSize: 10 },
          }) satisfies Edge,
      )
  }, [componentNodes, diagram.edges])

  const [nodes, setNodes, onNodesChange] = useNodesState(initNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initEdges)

  useEffect(() => {
    setNodes(initNodes)
    setEdges(initEdges)
    fittedRef.current = false
  }, [diagram, initNodes, initEdges, setNodes, setEdges])

  useEffect(() => {
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        style: nodeStyle(n.id === selected),
      })),
    )
  }, [selected, setNodes])

  useEffect(() => {
    if (fittedRef.current || !diagram.nodes.length) return
    fittedRef.current = true
    const t = requestAnimationFrame(() => {
      fitView({ padding: 0.12, duration: 200 })
    })
    return () => cancelAnimationFrame(t)
  }, [diagram, fitView])

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      setSel(node.id)
    },
    [setSel],
  )

  return (
    <div className="flow-wrap">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={24} color="rgba(255, 122, 89, 0.05)" />
        <MiniMap
          nodeColor={() => '#ff7a59'}
          maskColor="rgba(7, 7, 8, 0.82)"
          style={{ background: '#0b0b0d' }}
        />
        <Controls />
      </ReactFlow>
    </div>
  )
}
