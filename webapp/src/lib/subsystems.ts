import type { DiagramNode } from '../api/types'

export const SUBSYSTEMS = [
  'Propulsion',
  'Avionics',
  'Solar arrays',
  'Payload',
  'Comms',
  'ADCS',
  'Batteries',
  'Structure',
] as const

export type Subsystem = (typeof SUBSYSTEMS)[number]

const KEYWORDS: Record<Subsystem, string[]> = {
  Propulsion: [
    'propulsion',
    'thruster',
    'engine',
    'motor',
    'tank',
    'propellant',
    'fuel',
    'valve',
    'nozzle',
  ],
  Avionics: [
    'avionics',
    'computer',
    'obc',
    'processor',
    'fpga',
    'mcu',
    'controller',
    'bus',
    'telemetry',
  ],
  'Solar arrays': ['solar', 'array', 'panel', 'photovoltaic', 'pv', 'sun'],
  Payload: ['payload', 'instrument', 'sensor', 'camera', 'science', 'experiment'],
  Comms: ['comm', 'antenna', 'rf', 'transmitter', 'receiver', 'radio', 'x-band', 's-band'],
  ADCS: ['adcs', 'reaction', 'wheel', 'gyro', 'star', 'tracker', 'magnetorquer', 'attitude'],
  Batteries: ['battery', 'bms', 'power', 'eps', 'regulator', 'converter', 'bus voltage'],
  Structure: ['structure', 'frame', 'bus', 'panel', 'deploy', 'mechanical', 'housing', 'truss'],
}

function nodeSearchText(node: DiagramNode): string {
  const props = node.properties as Record<string, unknown>
  const disp = props?.display_name
  const parts = [
    node.kind,
    node.label ?? '',
    typeof disp === 'string' ? disp : '',
    props?.subsystem as string | undefined,
    props?.category as string | undefined,
  ]
  return parts.filter(Boolean).join(' ').toLowerCase()
}

/** Assign each diagram node to a subsystem tab from kind, label, and properties. */
export function classifySubsystem(node: DiagramNode): Subsystem {
  const props = node.properties as Record<string, unknown>
  const explicit = props?.subsystem
  if (typeof explicit === 'string') {
    const hit = SUBSYSTEMS.find((s) => s.toLowerCase() === explicit.toLowerCase())
    if (hit) return hit
  }

  const text = nodeSearchText(node)
  let best: Subsystem = 'Structure'
  let bestScore = 0
  for (const sub of SUBSYSTEMS) {
    let score = 0
    for (const kw of KEYWORDS[sub]) {
      if (text.includes(kw)) score += kw.length > 4 ? 2 : 1
    }
    if (score > bestScore) {
      bestScore = score
      best = sub
    }
  }
  return best
}

export function nodesForSubsystem(
  nodes: DiagramNode[],
  subsystem: Subsystem,
): DiagramNode[] {
  return nodes.filter((n) => classifySubsystem(n) === subsystem)
}

export function subsystemCounts(nodes: DiagramNode[]): Record<Subsystem, number> {
  const counts = Object.fromEntries(SUBSYSTEMS.map((s) => [s, 0])) as Record<Subsystem, number>
  for (const n of nodes) counts[classifySubsystem(n)] += 1
  return counts
}
