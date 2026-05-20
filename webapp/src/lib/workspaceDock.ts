/** Resizable dock layout tree for mission workspace panes. */

export type DockLeaf = {
  type: 'leaf'
  id: string
  tabs: string[]
  activeTab: string
}

export type DockSplit = {
  type: 'split'
  id: string
  direction: 'horizontal' | 'vertical'
  children: DockNode[]
}

export type DockNode = DockLeaf | DockSplit

export type DockEdge = 'left' | 'right' | 'top' | 'bottom' | 'center'

export const MAX_DOCK_COLS = 3
export const MAX_DOCK_ROWS = 3

export type DockGridSize = { cols: number; rows: number }

export type LayoutPreset = 'cols-1' | 'cols-2' | 'cols-3' | 'rows-2'

export const RAIL_LEAF_TERMINAL = 'leaf-terminal'
export const RAIL_LEAF_INSPECTOR = 'leaf-inspector'
export const MAIN_LEAF = 'leaf-main'

const DEFAULT_TABS = ['diagram']

function terminalRailLeaf(): DockLeaf {
  return { type: 'leaf', id: RAIL_LEAF_TERMINAL, tabs: ['terminal'], activeTab: 'terminal' }
}

/** Terminal only — component inspector is a normal workspace tab. */
function terminalRail(): DockNode {
  return terminalRailLeaf()
}

function chunkTabs(tabs: string[], n: number): string[][] {
  if (n <= 0) return [['diagram']]
  if (n === 1) return [tabs]
  const size = Math.ceil(tabs.length / n)
  const out: string[][] = []
  for (let i = 0; i < n; i++) out.push(tabs.slice(i * size, (i + 1) * size))
  return out.filter((g) => g.length)
}

/** Default: schematic/schema pane + terminal (inspector opened on demand). */
export function buildInitialLayout(openTabs: string[]): DockNode {
  const tabs = openTabs.filter((t) => t !== 'terminal' && t !== 'inspector')
  const contentTabs = tabs.length ? tabs : ['diagram']
  const activeTab = contentTabs.includes('diagram') ? 'diagram' : contentTabs[0]!
  return {
    type: 'split',
    id: 'root',
    direction: 'horizontal',
    children: [
      {
        type: 'leaf',
        id: 'leaf-schema',
        tabs: contentTabs,
        activeTab,
      },
      terminalRail(),
    ],
  }
}

function buildTwoColumnLayout(openTabs: string[]): DockNode {
  const tabs = openTabs.filter((t) => t !== 'terminal' && t !== 'inspector')
  const [a, b] = chunkTabs(tabs, 2)
  return {
    type: 'split',
    id: 'root',
    direction: 'horizontal',
    children: [
      {
        type: 'split',
        id: 'main-cols',
        direction: 'horizontal',
        children: [
          {
            type: 'leaf',
            id: 'leaf-a',
            tabs: a.length ? a : ['diagram'],
            activeTab: a[0] ?? 'diagram',
          },
          {
            type: 'leaf',
            id: 'leaf-b',
            tabs: b.length ? b : ['annotations'],
            activeTab: b[0] ?? 'annotations',
          },
        ],
      },
      terminalRail(),
    ],
  }
}

export function defaultDockLayout(openTabs: string[] = DEFAULT_TABS): DockNode {
  return buildInitialLayout(openTabs)
}

export function dockStorageKey(projectId: string): string {
  return `vioci-dock-${projectId}`
}

function isLegacySingleColumn(layout: DockNode): boolean {
  return !!findLeaf(layout, MAIN_LEAF)
}

function isRailNode(node: DockNode): boolean {
  if (node.type === 'leaf') return node.id === RAIL_LEAF_TERMINAL
  if (node.type === 'split' && node.id === 'rail') {
    return node.children.every(isRailNode)
  }
  return false
}

function hasLegacyInspectorRail(layout: DockNode): boolean {
  return !!findLeaf(layout, RAIL_LEAF_INSPECTOR)
}

/** Collapse old vertical terminal+inspector rail to terminal-only. */
function stripLegacyInspectorRail(node: DockNode): DockNode {
  if (node.type === 'split' && node.id === 'rail') {
    const terminal = node.children.find(
      (c): c is DockLeaf => c.type === 'leaf' && c.id === RAIL_LEAF_TERMINAL,
    )
    return terminal ?? terminalRailLeaf()
  }
  if (node.type === 'split') {
    return { ...node, children: node.children.map(stripLegacyInspectorRail) }
  }
  return node
}

function countContentLeaves(node: DockNode): number {
  if (node.type === 'leaf') return isRailNode(node) ? 0 : 1
  return node.children.reduce((n, c) => n + countContentLeaves(c), 0)
}

/** Main workspace pane tree (excludes terminal/inspector rail). */
export function findMainPaneRoot(layout: DockNode): DockNode | null {
  if (layout.type === 'leaf') return isRailNode(layout) ? null : layout
  const nonRail = layout.children.filter((c) => !isRailNode(c))
  if (!nonRail.length) return null
  if (nonRail.length === 1) {
    const child = nonRail[0]!
    if (child.type === 'leaf') return child
    const inner = findMainPaneRoot(child)
    return inner ?? child
  }
  return nonRail.reduce((best, c) => (countContentLeaves(c) > countContentLeaves(best) ? c : best))
}

export function measureGrid(node: DockNode): DockGridSize {
  if (node.type === 'leaf') return { cols: 1, rows: 1 }
  const childBounds = node.children.map((c) => measureGrid(c))
  if (node.direction === 'horizontal') {
    return {
      cols: childBounds.reduce((s, b) => s + b.cols, 0),
      rows: Math.max(...childBounds.map((b) => b.rows), 1),
    }
  }
  return {
    cols: Math.max(...childBounds.map((b) => b.cols), 1),
    rows: childBounds.reduce((s, b) => s + b.rows, 0),
  }
}

/** Full mission workspace grid (content + terminal + inspector). */
export function measureDockGrid(layout: DockNode): DockGridSize {
  return measureGrid(layout)
}

/** @deprecated Use measureDockGrid — grid cap includes terminal/inspector. */
export function measureMainGrid(layout: DockNode): DockGridSize {
  return measureDockGrid(layout)
}

function cloneLayout(layout: DockNode): DockNode {
  return JSON.parse(JSON.stringify(layout)) as DockNode
}

function previewSplitLayout(layout: DockNode, targetLeafId: string, edge: DockEdge): DockNode {
  return splitLeaf(cloneLayout(layout), targetLeafId, edge, '__preview__')
}

export function wouldSplitExceedGrid(
  layout: DockNode,
  targetLeafId: string,
  edge: DockEdge,
): boolean {
  if (edge === 'center') return false
  const { cols, rows } = measureDockGrid(previewSplitLayout(layout, targetLeafId, edge))
  return cols > MAX_DOCK_COLS || rows > MAX_DOCK_ROWS
}

/** Split edges fall back to center when the 3×3 cap is reached; center always pins into a tab group. */
export function resolveDropEdge(
  layout: DockNode,
  edge: DockEdge,
  targetLeafId?: string,
): DockEdge {
  if (edge === 'center') return 'center'
  if (targetLeafId && wouldSplitExceedGrid(layout, targetLeafId, edge)) return 'center'
  return edge
}

export function canSplitDockGrid(
  layout: DockNode,
  targetLeafId: string,
  edge: DockEdge,
): boolean {
  return resolveDropEdge(layout, edge, targetLeafId) === edge
}

function clampLayoutGrid(layout: DockNode, openTabs: string[]): DockNode {
  const { cols, rows } = measureDockGrid(layout)
  if (cols <= MAX_DOCK_COLS && rows <= MAX_DOCK_ROWS) return layout
  const tabs = collectContentTabs(layout)
  return mergeOpenTabsIntoLayout(
    buildInitialLayout(tabs.length ? tabs : DEFAULT_TABS),
    openTabs,
  )
}

export function loadDockLayout(projectId: string, openTabs: string[]): DockNode {
  try {
    const raw = sessionStorage.getItem(dockStorageKey(projectId))
    if (!raw) return defaultDockLayout(openTabs)
    const parsed = JSON.parse(raw) as DockNode
    const hadInspectorRail = hasLegacyInspectorRail(parsed)
    let normalized = stripLegacyInspectorRail(parsed)
    if (isLegacySingleColumn(normalized) || hadInspectorRail) {
      const tabs = collectContentTabs(normalized)
      const merged = [...new Set([...tabs, ...openTabs.filter((t) => t !== 'terminal' && t !== 'inspector')])]
      return clampLayoutGrid(mergeOpenTabsIntoLayout(buildInitialLayout(merged), openTabs), openTabs)
    }
    return clampLayoutGrid(mergeOpenTabsIntoLayout(normalized, openTabs), openTabs)
  } catch {
    return defaultDockLayout(openTabs)
  }
}

export function saveDockLayout(projectId: string, layout: DockNode): void {
  try {
    sessionStorage.setItem(dockStorageKey(projectId), JSON.stringify(layout))
  } catch {
    /* quota */
  }
}

/** One empty content pane (full + menu) plus terminal/inspector rail. */
export function layoutWithEmptyWorkspace(): DockNode {
  return {
    type: 'split',
    id: 'root',
    direction: 'horizontal',
    children: [
      {
        type: 'leaf',
        id: 'leaf-workspace',
        tabs: [],
        activeTab: '',
      },
      terminalRail(),
    ],
  }
}

export function mergeOpenTabsIntoLayout(layout: DockNode, openTabs: string[]): DockNode {
  const contentTabs = openTabs.filter((t) => t !== 'terminal' && t !== 'inspector')
  const openSet = new Set(contentTabs)
  let next = mapLeaves(layout, (leaf) => {
    if (leaf.id === RAIL_LEAF_TERMINAL || leaf.id === RAIL_LEAF_INSPECTOR) return leaf
    const tabs = leaf.tabs.filter((t) => openSet.has(t))
    const activeTab =
      tabs.length === 0
        ? ''
        : tabs.includes(leaf.activeTab)
          ? leaf.activeTab
          : tabs[0]!
    return { ...leaf, tabs, activeTab }
  })
  next = pruneDockLayout(next) ?? layoutWithEmptyWorkspace()
  for (const tabId of contentTabs) {
    if (!findLeafHoldingTab(next, tabId)) {
      next = ensureTabOpen(next, tabId)
    }
  }
  if (!findFirstContentLeaf(next)) {
    next = layoutWithEmptyWorkspace()
  }
  return next
}

function mapLeaves(node: DockNode, fn: (leaf: DockLeaf) => DockLeaf): DockNode {
  if (node.type === 'leaf') return fn(node)
  return {
    ...node,
    children: node.children.map((c) => mapLeaves(c, fn)),
  }
}

export function findLeaf(node: DockNode, leafId: string): DockLeaf | null {
  if (node.type === 'leaf') return node.id === leafId ? node : null
  for (const c of node.children) {
    const f = findLeaf(c, leafId)
    if (f) return f
  }
  return null
}

export function findLeafHoldingTab(node: DockNode, tabId: string): DockLeaf | null {
  if (node.type === 'leaf') return node.tabs.includes(tabId) ? node : null
  for (const c of node.children) {
    const f = findLeafHoldingTab(c, tabId)
    if (f) return f
  }
  return null
}

function newLeafId(): string {
  return `leaf-${Date.now().toString(36)}`
}

function removeTabFromTree(node: DockNode, tabId: string): DockNode {
  if (node.type === 'leaf') {
    if (!node.tabs.includes(tabId)) return node
    const tabs = node.tabs.filter((t) => t !== tabId)
    if (!tabs.length) return node
    const activeTab = node.activeTab === tabId ? tabs[0]! : node.activeTab
    return { ...node, tabs, activeTab }
  }
  return { ...node, children: node.children.map((c) => removeTabFromTree(c, tabId)) }
}

export function moveTabToLeaf(
  layout: DockNode,
  tabId: string,
  targetLeafId: string,
  edge: DockEdge = 'center',
): DockNode {
  edge = resolveDropEdge(layout, edge, targetLeafId)
  let next = removeTabFromTree(layout, tabId)
  if (edge === 'center') {
    next = mapLeaves(next, (leaf) => {
      if (leaf.id !== targetLeafId) return leaf
      const tabs = leaf.tabs.includes(tabId) ? leaf.tabs : [...leaf.tabs, tabId]
      return { ...leaf, tabs, activeTab: tabId }
    })
    return pruneDockLayout(next) ?? minimalDockLayout()
  }
  const split = splitLeaf(next, targetLeafId, edge, tabId)
  return pruneDockLayout(split) ?? minimalDockLayout()
}

function splitLeaf(layout: DockNode, targetLeafId: string, edge: DockEdge, tabId: string): DockNode {
  const direction: 'horizontal' | 'vertical' =
    edge === 'left' || edge === 'right' ? 'horizontal' : 'vertical'
  const placeFirst = edge === 'left' || edge === 'top'

  const newLeaf: DockLeaf = {
    type: 'leaf',
    id: newLeafId(),
    tabs: [tabId],
    activeTab: tabId,
  }

  const replace = (node: DockNode): DockNode => {
    if (node.type === 'leaf') {
      if (node.id !== targetLeafId) return node
      const kept: DockLeaf = {
        ...node,
        tabs: node.tabs.filter((t) => t !== tabId),
        activeTab: node.activeTab === tabId ? node.tabs.find((t) => t !== tabId) ?? 'diagram' : node.activeTab,
      }
      if (!kept.tabs.length) {
        return placeFirst ? newLeaf : { ...newLeaf, tabs: [tabId], activeTab: tabId }
      }
      const children = placeFirst ? [newLeaf, kept] : [kept, newLeaf]
      return {
        type: 'split',
        id: `split-${newLeafId()}`,
        direction,
        children,
      }
    }
    return { ...node, children: node.children.map(replace) }
  }

  return replace(layout)
}

export function setLeafActive(layout: DockNode, leafId: string, tabId: string): DockNode {
  return mapLeaves(layout, (leaf) =>
    leaf.id === leafId && leaf.tabs.includes(tabId) ? { ...leaf, activeTab: tabId } : leaf,
  )
}

/** Depth-first pane order (left→right, top→bottom) for placement messages. */
export function collectDockLeavesInOrder(node: DockNode): DockLeaf[] {
  const out: DockLeaf[] = []
  const walk = (n: DockNode) => {
    if (n.type === 'leaf') {
      out.push(n)
      return
    }
    for (const child of n.children) walk(child)
  }
  walk(node)
  return out
}

export function formatTabPlacement(layout: DockNode, tabId: string, label: string): string {
  const leaf = findLeafHoldingTab(layout, tabId)
  if (!leaf) return `Pulling up ${label}…`
  const panes = collectDockLeavesInOrder(layout)
  const paneNum = panes.findIndex((p) => p.id === leaf.id) + 1
  const tabNum = leaf.tabs.indexOf(tabId) + 1
  const stack =
    leaf.tabs.length > 1 && tabNum > 0 ? ` (tab ${tabNum} in that pane)` : ''
  return `Pulling up ${label} in pane ${paneNum}${stack}.`
}

export function openTabInLayout(
  layout: DockNode,
  tabId: string,
  options?: { leafId?: string; label?: string },
): { layout: DockNode; message: string } {
  const label = options?.label ?? tabId
  let next = layout
  if (tabId === 'terminal') {
    const rail = findLeaf(next, RAIL_LEAF_TERMINAL)
    if (rail) next = setLeafActive(next, rail.id, 'terminal')
  } else {
    next = ensureTabOpen(next, tabId)
    if (options?.leafId) next = moveTabToLeaf(next, tabId, options.leafId, 'center')
    const holder = findLeafHoldingTab(next, tabId)
    if (holder) next = setLeafActive(next, holder.id, tabId)
  }
  return { layout: next, message: formatTabPlacement(next, tabId, label) }
}

/** Remove empty panes and collapse splits with a single child. */
export function pruneDockLayout(node: DockNode): DockNode | null {
  if (node.type === 'leaf') {
    return node.tabs.length > 0 ? node : null
  }
  const children = node.children
    .map((c) => pruneDockLayout(c))
    .filter((c): c is DockNode => c !== null)
  if (!children.length) return null
  if (children.length === 1) return children[0]!
  return { ...node, children }
}

function minimalDockLayout(): DockNode {
  return layoutWithEmptyWorkspace()
}

function withContentPane(layout: DockNode): DockNode {
  if (findFirstContentLeaf(layout)) return layout
  const pane: DockLeaf = {
    type: 'leaf',
    id: newLeafId(),
    tabs: [],
    activeTab: 'diagram',
  }
  if (layout.type === 'split') {
    return { ...layout, children: [pane, ...layout.children] }
  }
  return {
    type: 'split',
    id: 'root',
    direction: 'horizontal',
    children: [pane, layout],
  }
}

export function closeTabInLayout(layout: DockNode, tabId: string): DockNode {
  if (tabId === 'terminal') return layout
  const stripped = mapLeaves(layout, (leaf) => {
    if (leaf.id === RAIL_LEAF_TERMINAL || leaf.id === RAIL_LEAF_INSPECTOR) {
      if (!leaf.tabs.includes(tabId)) return leaf
      const tabs = leaf.tabs.filter((t) => t !== tabId)
      return {
        ...leaf,
        tabs,
        activeTab: tabs[0] ?? (leaf.id === RAIL_LEAF_TERMINAL ? 'terminal' : 'inspector'),
      }
    }
    if (!leaf.tabs.includes(tabId)) return leaf
    const tabs = leaf.tabs.filter((t) => t !== tabId)
    const activeTab = leaf.activeTab === tabId ? (tabs[0] ?? '') : leaf.activeTab
    return { ...leaf, tabs, activeTab }
  })
  const pruned = pruneDockLayout(stripped)
  if (!pruned) return layoutWithEmptyWorkspace()
  if (!findFirstContentLeaf(pruned)) return layoutWithEmptyWorkspace()
  return pruned
}

export function applyLayoutPreset(
  preset: LayoutPreset,
  openTabs: string[],
): DockNode {
  const tabs = openTabs.filter((t) => t !== 'terminal' && t !== 'inspector')
  const rail = terminalRail()
  const chunk = (n: number) => chunkTabs(tabs, n)

  if (preset === 'cols-1') {
    return buildInitialLayout(openTabs)
  }

  if (preset === 'cols-2') {
    return buildTwoColumnLayout(openTabs)
  }

  if (preset === 'cols-3') {
    const [a, b, c] = chunk(3)
    return {
      type: 'split',
      id: 'root',
      direction: 'horizontal',
      children: [
        {
          type: 'split',
          id: 'main-cols',
          direction: 'horizontal',
          children: [
            {
              type: 'leaf',
              id: 'leaf-a',
              tabs: a.length ? a : ['diagram'],
              activeTab: a[0] ?? 'diagram',
            },
            {
              type: 'leaf',
              id: 'leaf-b',
              tabs: b.length ? b : ['graph'],
              activeTab: b[0] ?? 'graph',
            },
            {
              type: 'leaf',
              id: 'leaf-c',
              tabs: c.length ? c : ['annotations'],
              activeTab: c[0] ?? 'annotations',
            },
          ],
        },
        rail,
      ],
    }
  }

  /* rows-2 */
  const [top, bottom] = chunk(2)
  return {
    type: 'split',
    id: 'root',
    direction: 'horizontal',
    children: [
      {
        type: 'split',
        id: 'main-rows',
        direction: 'vertical',
        children: [
          {
            type: 'leaf',
            id: 'leaf-top',
            tabs: top.length ? top : ['diagram'],
            activeTab: top[0] ?? 'diagram',
          },
          {
            type: 'leaf',
            id: 'leaf-bottom',
            tabs: bottom.length ? bottom : ['annotations'],
            activeTab: bottom[0] ?? 'annotations',
          },
        ],
      },
      rail,
    ],
  }
}

export function ensureTabOpen(layout: DockNode, tabId: string): DockNode {
  if (findLeafHoldingTab(layout, tabId)) return layout
  if (tabId === 'terminal') {
    const rail = findLeaf(layout, RAIL_LEAF_TERMINAL)
    if (rail) return setLeafActive(layout, rail.id, 'terminal')
  }
  const next = withContentPane(layout)
  const main = findLeaf(next, MAIN_LEAF) ?? findFirstContentLeaf(next)
  if (!main) return next
  return moveTabToLeaf(next, tabId, main.id, 'center')
}

function findFirstContentLeaf(node: DockNode): DockLeaf | null {
  if (node.type === 'leaf') {
    if (node.id !== RAIL_LEAF_TERMINAL && node.id !== RAIL_LEAF_INSPECTOR) return node
    return null
  }
  for (const c of node.children) {
    const f = findFirstContentLeaf(c)
    if (f) return f
  }
  return null
}

export function collectContentTabs(layout: DockNode): string[] {
  const out: string[] = []
  const walk = (n: DockNode) => {
    if (n.type === 'leaf') {
      if (n.id !== RAIL_LEAF_TERMINAL && n.id !== RAIL_LEAF_INSPECTOR) {
        for (const t of n.tabs) if (!out.includes(t)) out.push(t)
      }
    } else n.children.forEach(walk)
  }
  walk(layout)
  return out
}
