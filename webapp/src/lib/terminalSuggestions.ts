import { resolveOpenTabCommand } from './terminalIntents'
import { WORKSPACE_TAB_CATALOG } from './workspaceTabs'

export type TerminalSuggestion = {
  value: string
  label: string
  hint?: string
}

const COMMANDS: TerminalSuggestion[] = [
  { value: 'help', label: 'help', hint: 'Command list' },
  { value: 'clear', label: 'clear', hint: 'Clear screen' },
  { value: 'status', label: 'status', hint: 'Project status' },
  { value: 'parse', label: 'parse', hint: 'Queue IR parse' },
  { value: 'whoami', label: 'whoami', hint: 'Current user' },
  { value: 'context', label: 'context', hint: 'Selected node' },
  { value: 'open ', label: 'open', hint: 'Open a workspace tab' },
  { value: 'sql ', label: 'sql', hint: 'Query schema registry tables' },
  { value: 'ask ', label: 'ask', hint: 'Copilot with prefix' },
]

const SQL_SUGGESTIONS: TerminalSuggestion[] = [
  {
    value: 'sql SELECT * FROM components LIMIT 20',
    label: 'sql SELECT components',
    hint: 'Opens Schema registry tab',
  },
  {
    value: 'SELECT * FROM dependencies',
    label: 'SELECT dependencies',
    hint: 'Direct SQL (no prefix)',
  },
  {
    value: 'SELECT source_name, target_name, kind FROM dependencies',
    label: 'dependency columns',
    hint: 'Graph edges as SQL',
  },
]

const OPEN_TARGETS: TerminalSuggestion[] = [
  ...WORKSPACE_TAB_CATALOG.map((t) => ({
    value: `open ${t.id}`,
    label: t.label,
    hint: t.hint ?? t.id,
  })),
  { value: 'open overlay', label: 'Diagram overlay', hint: 'Alias for diagram' },
  { value: 'open registry', label: 'Schema registry', hint: 'CSV tables + SQL' },
  { value: 'open schema', label: 'Mission parameters', hint: 'Alias for mission' },
  { value: 'open sim', label: 'Simulation', hint: 'Alias for simulation' },
  { value: 'open telemetry', label: 'Component inspector', hint: 'Alias for inspector' },
]

function matchesPrefix(text: string, query: string): boolean {
  const t = text.toLowerCase()
  const q = query.toLowerCase()
  return t.startsWith(q) || t.includes(q)
}

export function getTerminalSuggestions(input: string, history: string[]): TerminalSuggestion[] {
  const trimmed = input
  if (!trimmed) {
    const recent = history.slice(-4).reverse().map((h) => ({
      value: h,
      label: h,
      hint: 'Recent',
    }))
    return [...recent, ...COMMANDS].slice(0, 12)
  }

  const parts = trimmed.split(/\s+/)
  const cmd = parts[0]?.toLowerCase() ?? ''

  if (cmd === 'open' || (parts.length === 1 && 'open'.startsWith(cmd))) {
    const arg = parts.slice(1).join(' ').trim().toLowerCase()
    const pool = OPEN_TARGETS.filter(
      (s) =>
        !arg ||
        matchesPrefix(s.value.replace(/^open\s+/, ''), arg) ||
        matchesPrefix(s.label, arg),
    )
    if (parts.length === 1 && cmd !== 'open') {
      return [{ value: 'open ', label: 'open', hint: 'Open workspace tab' }, ...pool].slice(0, 12)
    }
    return pool.slice(0, 12)
  }

  if (cmd === 'ask' || (parts.length === 1 && 'ask'.startsWith(cmd))) {
    return [{ value: 'ask ', label: 'ask', hint: 'Engineering copilot' }]
  }

  if (cmd === 'sql' || (parts.length === 1 && 'sql'.startsWith(cmd))) {
    const arg = parts.slice(1).join(' ').trim()
    if (!arg) return SQL_SUGGESTIONS
    return SQL_SUGGESTIONS.filter((s) => matchesPrefix(s.value, trimmed)).slice(0, 8)
  }

  const upper = trimmed.split(/\s+/)[0]?.toUpperCase() ?? ''
  if (['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'WITH'].includes(upper)) {
    return [{ value: trimmed, label: 'Run SQL', hint: 'Schema registry tab' }]
  }

  const cmdMatches = COMMANDS.filter(
    (s) => matchesPrefix(s.value.trim(), trimmed) || matchesPrefix(s.label, trimmed),
  )
  if (cmdMatches.length) return cmdMatches.slice(0, 12)

  const historyMatches = history
    .filter((h) => matchesPrefix(h, trimmed))
    .slice(-6)
    .reverse()
    .map((h) => ({ value: h, label: h, hint: 'History' }))

  return historyMatches.slice(0, 8)
}

/** Resolve `open <partial>` for execution (longest prefix wins). */
export function resolveOpenTabCommandFuzzy(name: string): string | null {
  const exact = resolveOpenTabCommand(name)
  if (exact) return exact
  const q = name.toLowerCase().trim()
  if (!q) return null
  const candidates = OPEN_TARGETS.map((s) => s.value.replace(/^open\s+/, ''))
  const hits = candidates.filter((c) => c.startsWith(q) || q.startsWith(c))
  if (hits.length === 1) return resolveOpenTabCommand(hits[0]!)
  return null
}
