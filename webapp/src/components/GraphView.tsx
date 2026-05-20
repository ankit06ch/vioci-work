import { useCallback, useEffect, useMemo } from 'react'
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
} from 'reactflow'
import type { Edge, Node } from 'reactflow'
import 'reactflow/dist/style.css'
import type { Diagram, DiagramNode } from '../api/types'
import { bboxForNode } from './ImageOverlay'
import { SchemaNode } from './SchemaNode'
import { useSelectionStore } from '../state/project'

const nodeTypes = { schema: SchemaNode }

function nodePosition(n: DiagramNode, i: number) {
  const bb = bboxForNode(n)
  if (bb) return { x: bb.x + bb.w / 2 - 70, y: bb.y + bb.h / 2 - 24 }
  return { x: (i % 6) * 180, y: Math.floor(i / 6) * 120 }
}

function nodeLabel(n: DiagramNode) {
  const props = n.properties as Record<string, unknown>
  const disp = props?.display_name
  if (typeof disp === 'string' && disp) return disp
  if (n.label) return n.label
  return n.kind
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

  const initNodes = useMemo(() => {
    return diagram.nodes.map((n, i) => {
      const p = nodePosition(n, i)
      const sel = n.id === selected
      return {
        id: n.id,
        type: 'schema',
        position: p,
        data: { label: nodeLabel(n) },
        style: {
          borderRadius: 4,
          border: sel ? '1px solid #f97316' : '1px solid rgba(34, 211, 238, 0.35)',
          background: sel ? 'rgba(249, 115, 22, 0.12)' : 'rgba(15, 20, 28, 0.92)',
          color: '#e2e8f0',
          fontSize: 11,
          fontWeight: 600,
          fontFamily: 'JetBrains Mono, monospace',
          boxShadow: sel
            ? '0 0 16px rgba(249, 115, 22, 0.25)'
            : '0 0 8px rgba(34, 211, 238, 0.08)',
        },
      } satisfies Node
    })
  }, [diagram.nodes, selected])

  const initEdges = useMemo(() => {
    const ids = new Set(diagram.nodes.map((n) => n.id))
    return diagram.edges
      .filter((e) => ids.has(e.source) && ids.has(e.target))
      .map(
        (e) =>
          ({
            id: e.id,
            source: e.source,
            target: e.target,
            label: e.label ?? undefined,
            style: { stroke: 'rgba(34, 211, 238, 0.45)', strokeWidth: 1.5 },
            labelStyle: { fill: '#94a3b8', fontSize: 10 },
          }) satisfies Edge,
      )
  }, [diagram.nodes, diagram.edges])

  const [nodes, setNodes, onNodesChange] = useNodesState(initNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initEdges)

  useEffect(() => {
    setNodes(initNodes)
    setEdges(initEdges)
  }, [initNodes, initEdges, setNodes, setEdges])

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
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Lines} gap={20} color="rgba(34, 211, 238, 0.06)" />
        <MiniMap
          nodeColor={() => '#22d3ee'}
          maskColor="rgba(5, 6, 8, 0.8)"
          style={{ background: '#0a0d12' }}
        />
        <Controls />
      </ReactFlow>
    </div>
  )
}
