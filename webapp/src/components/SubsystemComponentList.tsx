import type { DiagramNode } from '../api/types'
import { classifySubsystem, type Subsystem } from '../lib/subsystems'
import { componentDiagramNodes, nodeDisplayTitle } from '../lib/schematicLabels'
import { useSelectionStore } from '../state/project'

type Props = {
  nodes: DiagramNode[]
  subsystem: Subsystem
}

export function SubsystemComponentList({ nodes, subsystem }: Props) {
  const selected = useSelectionStore((s) => s.selectedNodeId)
  const setSel = useSelectionStore((s) => s.setSelected)

  const filtered = componentDiagramNodes(nodes).filter(
    (n) => classifySubsystem(n) === subsystem,
  )

  return (
    <aside className="subsystem-component-list">
      <div className="subsystem-component-head">
        <h4 className="panel-title" style={{ margin: 0, fontSize: '0.72rem' }}>
          {subsystem}
        </h4>
        <span className="muted mono" style={{ fontSize: '0.65rem' }}>
          {filtered.length} component{filtered.length === 1 ? '' : 's'}
        </span>
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
                className={`subsystem-component-btn ${selected === n.id ? 'subsystem-component-btn-active' : ''}`}
                onClick={() => setSel(n.id)}
              >
                <span className="subsystem-component-name">{nodeDisplayTitle(n)}</span>
                <span className="muted mono subsystem-component-kind">{n.kind}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  )
}
