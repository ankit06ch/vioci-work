import { Fragment, useCallback, useRef, useState, type ReactNode } from 'react'
import { Group, Panel, Separator } from 'react-resizable-panels'
import type { DockEdge, DockLeaf, DockNode } from '../../lib/workspaceDock'
import { RAIL_LEAF_TERMINAL } from '../../lib/workspaceDock'
import {
  MAX_DOCK_COLS,
  MAX_DOCK_ROWS,
  measureDockGrid,
  resolveDropEdge,
} from '../../lib/workspaceDock'
import { ClosableTabBar, type TabAddOption } from '../ClosableTabBar'
import { WORKSPACE_TAB_CATALOG } from '../../lib/workspaceTabs'

export type DockTabMeta = {
  id: string
  label: string
  closable: boolean
}

export type DockDropTarget = {
  leafId: string
  edge: DockEdge
  rawEdge?: DockEdge
}

const EDGE_LABELS: Record<DockEdge, string> = {
  left: 'Split left',
  right: 'Split right',
  top: 'Split above',
  bottom: 'Split below',
  center: 'Add to tabs',
}

function dropLabel(layout: DockNode, edge: DockEdge, rawEdge: DockEdge): string {
  if (edge === 'center' && rawEdge !== 'center') {
    const { cols, rows } = measureDockGrid(layout)
    if (rawEdge === 'left' || rawEdge === 'right') {
      return cols >= MAX_DOCK_COLS ? `Add to tabs (max ${MAX_DOCK_COLS} cols)` : EDGE_LABELS.center
    }
    return rows >= MAX_DOCK_ROWS ? `Add to tabs (max ${MAX_DOCK_ROWS} rows)` : EDGE_LABELS.center
  }
  return EDGE_LABELS[edge]
}

type Props = {
  layout: DockNode
  tabMeta: Record<string, DockTabMeta>
  projectId: string
  onSelectTab: (leafId: string, tabId: string) => void
  onCloseTab: (tabId: string) => void
  onMoveTab: (tabId: string, targetLeafId: string, edge: DockEdge) => void
  onAddTabToLeaf?: (tabId: string, leafId: string) => void
  renderPane: (tabId: string, leafId: string) => ReactNode
  renderLeafChrome?: (leafId: string, tabId: string) => ReactNode | null
}

function edgeFromPointer(rect: DOMRect, clientX: number, clientY: number): DockEdge {
  const x = (clientX - rect.left) / rect.width
  const y = (clientY - rect.top) / rect.height
  const band = 0.24
  if (x < band) return 'left'
  if (x > 1 - band) return 'right'
  if (y < band) return 'top'
  if (y > 1 - band) return 'bottom'
  return 'center'
}

export function WorkspaceDock({
  layout,
  tabMeta,
  projectId,
  onSelectTab,
  onCloseTab,
  onMoveTab,
  onAddTabToLeaf,
  renderPane,
  renderLeafChrome,
}: Props) {
  const [dragTabId, setDragTabId] = useState<string | null>(null)
  const [dropTarget, setDropTarget] = useState<DockDropTarget | null>(null)

  const endDrag = useCallback(() => {
    setDragTabId(null)
    setDropTarget(null)
  }, [])

  const onDrop = useCallback(
    (leafId: string, edge: DockEdge) => {
      if (!dragTabId) return
      onMoveTab(dragTabId, leafId, edge)
      endDrag()
    },
    [dragTabId, onMoveTab, endDrag],
  )

  const nodeProps = {
    layout,
    tabMeta,
    projectId,
    dragTabId,
    dropTarget,
    onTabDragStart: setDragTabId,
    onTabDragEnd: endDrag,
    onDrop,
    onDragHover: setDropTarget,
    onSelectTab,
    onCloseTab,
    onAddTabToLeaf,
    renderPane,
    renderLeafChrome,
  }

  return (
    <div className={`workspace-dock ${dragTabId ? 'workspace-dock--dragging' : ''}`}>
      <DockNodeView node={layout} {...nodeProps} />
    </div>
  )
}

type NodeProps = {
  layout: DockNode
  node: DockNode
  tabMeta: Record<string, DockTabMeta>
  projectId: string
  dragTabId: string | null
  dropTarget: DockDropTarget | null
  onTabDragStart: (tabId: string) => void
  onTabDragEnd: () => void
  onDrop: (leafId: string, edge: DockEdge) => void
  onDragHover: (target: DockDropTarget | null) => void
  onSelectTab: (leafId: string, tabId: string) => void
  onCloseTab: (tabId: string) => void
  onAddTabToLeaf?: (tabId: string, leafId: string) => void
  renderPane: (tabId: string, leafId: string) => ReactNode
  renderLeafChrome?: (leafId: string, tabId: string) => ReactNode | null
}

function DockNodeView({ node, projectId, ...props }: NodeProps) {
  if (node.type === 'leaf') {
    return <DockLeafView leaf={node} {...props} />
  }

  const orientation = node.direction
  const groupId = `vioci-${projectId}-${node.id}`
  const n = node.children.length
  const defaultEach = n > 0 ? 100 / n : 50

  return (
    <Group orientation={orientation} id={groupId} className="dock-split-group">
      {node.children.map((child, i) => {
        const isTerminalRail = child.type === 'leaf' && child.id === RAIL_LEAF_TERMINAL
        return (
        <Fragment key={child.type === 'leaf' ? child.id : child.id}>
          {i > 0 ? <Separator className="dock-resize-handle" /> : null}
          <Panel
            id={`${groupId}-p${i}`}
            minSize={isTerminalRail ? 22 : 10}
            defaultSize={isTerminalRail ? 34 : defaultEach}
            className="dock-panel"
          >
            <DockNodeView node={child} projectId={projectId} {...props} />
          </Panel>
        </Fragment>
        )
      })}
    </Group>
  )
}

type LeafProps = Omit<NodeProps, 'node' | 'projectId'> & { leaf: DockLeaf }

function DockLeafView({
  layout,
  leaf,
  tabMeta,
  dragTabId,
  dropTarget,
  onTabDragStart,
  onTabDragEnd,
  onDrop,
  onDragHover,
  onSelectTab,
  onCloseTab,
  onAddTabToLeaf,
  renderPane,
  renderLeafChrome,
}: LeafProps) {
  const leafRef = useRef<HTMLDivElement>(null)
  const tabs = leaf.tabs.map((id) => tabMeta[id]).filter((t): t is DockTabMeta => !!t)
  const isRail = leaf.id === RAIL_LEAF_TERMINAL
  const railTab = isRail ? tabMeta[leaf.tabs[0]!] : null
  const addOptions: TabAddOption[] = isRail
    ? []
    : (leaf.tabs.length === 0
        ? WORKSPACE_TAB_CATALOG
        : WORKSPACE_TAB_CATALOG.filter((t) => !leaf.tabs.includes(t.id))
      ).map((t) => ({
        id: t.id,
        label: t.label,
        hint: t.hint,
      }))
  const isEmpty = !isRail && leaf.tabs.length === 0

  const activeDrop = dropTarget?.leafId === leaf.id ? dropTarget.edge : null
  const activeDropRaw = dropTarget?.leafId === leaf.id ? dropTarget.rawEdge : null

  const handleDragOver = (e: React.DragEvent) => {
    if (e.dataTransfer.types.includes('Files')) {
      e.preventDefault()
      e.dataTransfer.dropEffect = 'copy'
      return
    }
    if (!dragTabId) return
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    const rect = leafRef.current?.getBoundingClientRect()
    if (!rect) return
    const rawEdge = edgeFromPointer(rect, e.clientX, e.clientY)
    const edge = resolveDropEdge(layout, rawEdge, leaf.id)
    onDragHover({ leafId: leaf.id, edge, rawEdge })
  }

  const handleDragLeave = (e: React.DragEvent) => {
    const rel = e.relatedTarget as Node | null
    if (rel && leafRef.current?.contains(rel)) return
    if (dropTarget?.leafId === leaf.id) onDragHover(null)
  }

  const startTabDrag = (tabId: string, e: React.DragEvent) => {
    e.dataTransfer.setData('text/vioci-tab', tabId)
    e.dataTransfer.effectAllowed = 'move'
    onTabDragStart(tabId)
  }

  return (
    <div
      ref={leafRef}
      className={`dock-leaf ${dragTabId ? 'dock-leaf--drop-ready' : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={(e) => {
        e.preventDefault()
        if (activeDrop) onDrop(leaf.id, activeDrop)
      }}
    >
      {isRail && railTab ? (
        <div
          className={`dock-rail-tab ${dragTabId === railTab.id ? 'dock-rail-tab--dragging' : ''}`}
          draggable
          onDragStart={(e) => startTabDrag(railTab.id, e)}
          onDragEnd={onTabDragEnd}
        >
          <span className="dock-rail-tab-grip" aria-hidden>
            ⠿
          </span>
          <span>{railTab.label}</span>
        </div>
      ) : (
        <ClosableTabBar
          className="workspace-content-tabs dock-leaf-tabs"
          tabs={tabs}
          activeId={leaf.activeTab || tabs[0]?.id || ''}
          draggingTabId={dragTabId}
          onSelect={(id) => onSelectTab(leaf.id, id)}
          onClose={onCloseTab}
          draggable
          onTabDragStart={onTabDragStart}
          onTabDragEnd={onTabDragEnd}
          addOptions={addOptions}
          onAddTab={(tabId) => onAddTabToLeaf?.(tabId, leaf.id)}
        />
      )}

      {dragTabId && activeDrop ? (
        <div
          className={`dock-insert dock-insert--${activeDrop} ${activeDropRaw && activeDropRaw !== activeDrop ? 'dock-insert--fallback' : ''}`}
          aria-hidden
        >
          <span className="dock-insert-label mono">
            {dropLabel(layout, activeDrop, activeDropRaw ?? activeDrop)}
          </span>
        </div>
      ) : null}

      {renderLeafChrome?.(leaf.id, leaf.activeTab)}

      <div className="dock-leaf-content workspace-tab-content">
        {isEmpty ? (
          <div className="dock-leaf-empty">
            <p className="dock-leaf-empty-title">No tabs in this pane</p>
            <p className="muted dock-leaf-empty-hint">
              Use <strong>+</strong> above to open Satellite schema, Diagram, Annotations, or other
              tools. Terminal commands like <span className="mono">open mission</span> work too.
            </p>
          </div>
        ) : (
          renderPane(leaf.activeTab, leaf.id)
        )}
      </div>
    </div>
  )
}
