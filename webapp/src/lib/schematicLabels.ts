import type { DiagramNode } from '../api/types'

const AXIS_COMPACT = /^[+-±]?[xyz]$|^[xyz][+-±]?$/i

/** +X / -Y / ±Z style coordinate frame labels — not components. */
export function isAxisReferenceLabel(name: string): boolean {
  const raw = name.trim()
  if (!raw) return false
  const compact = raw.replace(/\s+/g, '')
  if (AXIS_COMPACT.test(compact)) return true
  const low = raw.toLowerCase()
  if (low === 'x' || low === 'y' || low === 'z') return true
  if (/^[+-]?\s*[xyz]\s*(axis)?$/i.test(low)) return true
  return false
}

const SCHEMATIC_GRAPHIC_KINDS = new Set([
  'line',
  'arrow',
  'connector',
  'edge',
  'leader',
  'dimension',
  'axis',
  'polyline',
  'path',
  'wire',
  'link',
  'reference',
  'frame',
  'grid',
  'guide',
])

function nodeCaption(node: DiagramNode): string {
  const props = node.properties as Record<string, unknown>
  const disp = props?.display_name
  if (typeof disp === 'string' && disp.trim()) return disp.trim()
  if (node.label?.trim()) return node.label.trim()
  return ''
}

export function nodeDisplayTitle(node: DiagramNode): string {
  const cap = nodeCaption(node)
  if (cap) return cap
  return node.kind
}

/** Axis ticks and unlabeled schematic lines/arrows are not bill-of-materials components. */
export function shouldSkipDiagramNodeForComponents(node: DiagramNode): boolean {
  const title = nodeDisplayTitle(node)
  if (isAxisReferenceLabel(title)) return true
  const kind = (node.kind || '').toLowerCase()
  if (!SCHEMATIC_GRAPHIC_KINDS.has(kind)) return false
  if (!nodeCaption(node)) return true
  if (isAxisReferenceLabel(title)) return true
  if (title.length <= 3 && ['line', 'wire', 'link', 'conn'].includes(title.toLowerCase())) {
    return true
  }
  return false
}

export function componentDiagramNodes(nodes: DiagramNode[]): DiagramNode[] {
  return nodes.filter((n) => !shouldSkipDiagramNodeForComponents(n))
}
