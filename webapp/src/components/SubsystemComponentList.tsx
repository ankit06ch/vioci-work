import { useEffect, useMemo, useState } from 'react'
import type { DiagramNode } from '../api/types'
import { classifySubsystem, type Subsystem } from '../lib/subsystems'
import { componentDiagramNodes, nodeDisplayTitle } from '../lib/schematicLabels'
import { useSelectionStore } from '../state/project'

type Props = {
  nodes: DiagramNode[]
  subsystem: Subsystem
  onDeleteNodes?: (ids: string[]) => void | Promise<void>
  onRenameNode?: (id: string, label: string) => void | Promise<void>
}

export function SubsystemComponentList({ nodes, subsystem, onDeleteNodes, onRenameNode }: Props) {
  const selected = useSelectionStore((s) => s.selectedNodeId)
  const setSel = useSelectionStore((s) => s.setSelected)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [anchorId, setAnchorId] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [menu, setMenu] = useState<{ x: number; y: number; node: DiagramNode } | null>(null)

  const filtered = useMemo(
    () => componentDiagramNodes(nodes).filter((n) => classifySubsystem(n) === subsystem),
    [nodes, subsystem],
  )

  useEffect(() => {
    const visible = new Set(filtered.map((n) => n.id))
    setSelectedIds((ids) => ids.filter((id) => visible.has(id)))
    setAnchorId((id) => (id && visible.has(id) ? id : null))
  }, [filtered])

  const selectNode = (node: DiagramNode, shift: boolean) => {
    if (shift && anchorId) {
      const a = filtered.findIndex((n) => n.id === anchorId)
      const b = filtered.findIndex((n) => n.id === node.id)
      if (a >= 0 && b >= 0) {
        const [start, end] = a < b ? [a, b] : [b, a]
        const range = filtered.slice(start, end + 1).map((n) => n.id)
        setSelectedIds(range)
        setSel(node.id)
        return
      }
    }
    setAnchorId(node.id)
    setSelectedIds([node.id])
    setSel(node.id)
  }

  const deleteSelection = async () => {
    if (!selectedIds.length || !onDeleteNodes || deleting) return
    setDeleting(true)
    try {
      await onDeleteNodes(selectedIds)
      setSelectedIds([])
      setAnchorId(null)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <aside
      className="subsystem-component-list"
      tabIndex={0}
      onClick={() => setMenu(null)}
      onKeyDown={(e) => {
        if ((e.key === 'Backspace' || e.key === 'Delete') && selectedIds.length) {
          e.preventDefault()
          void deleteSelection()
        }
      }}
    >
      <div className="subsystem-component-head">
        <h4 className="panel-title" style={{ margin: 0, fontSize: '0.72rem' }}>
          {subsystem}
        </h4>
        <div className="subsystem-component-actions">
          <span className="muted mono" style={{ fontSize: '0.65rem' }}>
            {selectedIds.length ? `${selectedIds.length} selected` : `${filtered.length} component${filtered.length === 1 ? '' : 's'}`}
          </span>
          {selectedIds.length ? (
            <button
              type="button"
              className="subsystem-component-delete"
              disabled={deleting || !onDeleteNodes}
              onClick={() => void deleteSelection()}
            >
              {deleting ? 'Deleting…' : 'Delete'}
            </button>
          ) : null}
        </div>
      </div>
      {filtered.length === 0 ? (
        <p className="muted" style={{ fontSize: '0.78rem', padding: '0.5rem 0' }}>
          No components classified under this subsystem. Select another tab or refine labels in
          the schematic.
        </p>
      ) : (
        <ul className="subsystem-component-items">
          {filtered.map((n) => (
            <li key={n.id}>
              <button
                type="button"
                className={`subsystem-component-btn ${
                  selected === n.id || selectedIds.includes(n.id) ? 'subsystem-component-btn-active' : ''
                } ${selectedIds.includes(n.id) ? 'subsystem-component-btn-multi' : ''}`}
                onClick={(e) => selectNode(n, e.shiftKey)}
                onContextMenu={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  if (!selectedIds.includes(n.id)) {
                    setSelectedIds([n.id])
                    setAnchorId(n.id)
                  }
                  setSel(n.id)
                  setMenu({ x: e.clientX, y: e.clientY, node: n })
                }}
              >
                <span className="subsystem-component-name">{nodeDisplayTitle(n)}</span>
                <span className="muted mono subsystem-component-kind">{n.kind}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {menu ? (
        <div
          className="schematic-context-menu"
          style={{ left: menu.x, top: menu.y }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="schematic-context-title">{nodeDisplayTitle(menu.node)}</div>
          <button
            type="button"
            onClick={() => {
              const next = window.prompt('Rename component', nodeDisplayTitle(menu.node))
              setMenu(null)
              if (next?.trim()) void onRenameNode?.(menu.node.id, next.trim())
            }}
          >
            Rename
          </button>
          <button
            type="button"
            onClick={() => {
              const ids = selectedIds.includes(menu.node.id) ? selectedIds : [menu.node.id]
              setMenu(null)
              void onDeleteNodes?.(ids)
            }}
          >
            Delete
          </button>
        </div>
      ) : null}
    </aside>
  )
}
