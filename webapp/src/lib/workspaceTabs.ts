/** Catalog of workspace panes users can open from the tab bar or terminal. */

export type WorkspaceTabDef = {
  id: string
  label: string
  /** Shown in the + menu description */
  hint?: string
}

export const WORKSPACE_TAB_CATALOG: WorkspaceTabDef[] = [
  { id: 'diagram', label: 'Satellite schema', hint: 'Uploaded schematic & IR overlay' },
  { id: 'graph', label: 'Dependency graph', hint: 'Block diagram graph' },
  { id: 'mission', label: 'Mission parameters', hint: 'Mass, orbit, power, fairing' },
  { id: 'annotations', label: 'Annotations', hint: 'Part mass, vectors, labels' },
  { id: 'inspector', label: 'Component inspector', hint: 'Telemetry schema & metrics' },
  { id: 'launch', label: 'Launch compatibility', hint: 'Fairing & vehicle fit' },
  { id: 'simulation', label: 'Simulation', hint: 'Engine sweep & analytics' },
]

export const WORKSPACE_TAB_LABELS: Record<string, string> = Object.fromEntries(
  WORKSPACE_TAB_CATALOG.map((t) => [t.id, t.label]),
)
