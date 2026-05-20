export type TerminalIntent =
  | { type: 'diagram' }
  | { type: 'graph' }
  | { type: 'schema-data' }
  | { type: 'mission' }
  | { type: 'inspector' }
  | { type: 'launch' }
  | { type: 'simulate' }
  | { type: 'annotations' }
  | { type: 'dynamic'; label: string }
  | { type: 'copilot' }

export function detectTerminalIntent(text: string): TerminalIntent {
  const lower = text.toLowerCase().trim()

  if (
    /\b(telemetry|metrics|component metrics|component data|node inspector|inspector|csv telemetry|channel data)\b/.test(
      lower,
    )
  ) {
    return { type: 'inspector' }
  }
  if (
    /\b(satellite schema|spacecraft schema|mission schema|mission profile|satellite profile|mission parameters|bus schema|vehicle schema|pull up schema|show schema)\b/.test(
      lower,
    ) ||
    /\b(schema of (the )?satellite|satellite (profile|parameters))\b/.test(lower)
  ) {
    return { type: 'mission' }
  }
  if (
    /\b(schematic|diagram overlay|ir overlay|overlay diagram|show (me )?the diagram)\b/.test(
      lower,
    ) ||
    /\b(pull up|show|open)\b.*\b(diagram|schematic)\b/.test(lower)
  ) {
    return { type: 'diagram' }
  }
  if (
    /\b(dependency graph|block diagram|topology|show (me )?the graph)\b/.test(lower) ||
    /\b(pull up|show|open)\b.*\b(graph|dependencies)\b/.test(lower)
  ) {
    return { type: 'graph' }
  }
  if (
    /\b(schema registry|schema table|schema data|satellite registry|query schema|excel)\b/.test(
      lower,
    ) ||
    /\b(pull up|show|open)\b.*\b(registry|schema (data|table))\b/.test(lower)
  ) {
    return { type: 'schema-data' }
  }
  if (
    /\b(launch|falcon|electron|starship|vulcan|ariane|rocket|fairing|envelope|compat)\b/.test(
      lower,
    )
  ) {
    return { type: 'launch' }
  }
  if (/\b(simulate|simulation|sweep|engine|analytic|ngspice)\b/.test(lower)) {
    return { type: 'simulate' }
  }
  if (
    /\b(annotate|annotation|part mass|component mass|vector|weight|dimensions|size)\b/.test(
      lower,
    )
  ) {
    return { type: 'annotations' }
  }
  if (/\b(compare|analyze|assess|evaluate|risk)\b/.test(lower)) {
    const short = text.slice(0, 36).trim() || 'Analysis'
    return { type: 'dynamic', label: short.length > 28 ? `${short.slice(0, 28)}…` : short }
  }
  return { type: 'copilot' }
}

/** Tab id for `open <name>` terminal command. */
export function resolveOpenTabCommand(name: string): string | null {
  const n = name.toLowerCase().trim()
  const map: Record<string, string> = {
    diagram: 'diagram',
    overlay: 'diagram',
    schematic: 'diagram',
    graph: 'graph',
    registry: 'schema-data',
    'schema-data': 'schema-data',
    table: 'schema-data',
    mission: 'mission',
    sql: 'schema-data',
    schema: 'mission',
    satellite: 'mission',
    profile: 'mission',
    annotations: 'annotations',
    annotate: 'annotations',
    inspector: 'inspector',
    telemetry: 'inspector',
    metrics: 'inspector',
    launch: 'launch',
    simulation: 'simulation',
    simulate: 'simulation',
    sim: 'simulation',
    terminal: 'terminal',
  }
  return map[n] ?? null
}
