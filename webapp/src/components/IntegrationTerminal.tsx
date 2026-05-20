import { useCallback, useEffect, useRef, useState } from 'react'
import {
  chatDiagram,
  chatNode,
  formatApiError,
  getProject,
  queueParse,
  runRegistrySql,
} from '../api/client'
import { extractSqlFromTerminal, formatSqlResultForTerminal, looksLikeRegistrySql } from '../lib/terminalSql'
import { fetchMe } from '../api/auth'
import { useSelectionStore } from '../state/project'
import {
  getTerminalSuggestions,
  resolveOpenTabCommandFuzzy,
  type TerminalSuggestion,
} from '../lib/terminalSuggestions'

type Line = { kind: 'in' | 'out' | 'err' | 'sys'; text: string }

export type WorkspaceTerminalAction =
  | { type: 'store-dynamic-result'; tabId: string; text: string }
  | {
      type: 'schema-registry-sql'
      sql: string
      result?: import('../api/types').SchemaRegistrySqlResult
      error?: string
    }

export type WorkspaceTerminalResult = {
  continueCopilot: boolean
  sysLines?: string[]
  dynamicTabId?: string
}

type Props = {
  projectId: string
  parseStatus?: string
  hasDiagram?: boolean
  onWorkspaceMessage?: (message: string) => WorkspaceTerminalResult
  onWorkspaceAction?: (action: WorkspaceTerminalAction) => void
  onOpenWorkspaceTab?: (tabId: string) => string
}

const HELP = `Available commands:
  help              Show this message
  clear             Clear terminal
  status            Project parse status
  parse             Queue IR parse (Gemini)
  whoami            Current user & organization
  context           Show selected node id
  open <tab>        Open workspace tab (diagram, graph, registry, mission, …)
  sql <query>       Run SQL on schema tables → Schema registry tab
  ask <message>     Engineering copilot (same as plain text)

SQL (also run without the sql prefix):
  SELECT * FROM dependencies
  UPDATE components SET mass_kg = '10' WHERE node_id = 'n1'

Natural language also opens tabs, e.g.:
  "show satellite schema"  → Satellite schema pane
  "component telemetry"    → Component inspector pane
  "pull up annotations"    → Annotations pane`

export function IntegrationTerminal({
  projectId,
  parseStatus,
  hasDiagram,
  onWorkspaceMessage,
  onWorkspaceAction,
  onOpenWorkspaceTab,
}: Props) {
  const selected = useSelectionStore((s) => s.selectedNodeId)
  const [lines, setLines] = useState<Line[]>([
    { kind: 'sys', text: 'VIOCI integration terminal v1.0 — type help for commands' },
  ])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [history, setHistory] = useState<string[]>([])
  const [histIdx, setHistIdx] = useState(-1)
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [suggestIdx, setSuggestIdx] = useState(-1)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const suggestions = showSuggestions ? getTerminalSuggestions(input, history) : []

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines, busy])

  const append = useCallback((kind: Line['kind'], text: string) => {
    setLines((prev) => [...prev, { kind, text }])
  }, [])

  const runSqlCommand = useCallback(
    async (statement: string) => {
      const sql = extractSqlFromTerminal(statement)
      if (!sql) {
        append('err', 'empty SQL statement')
        return
      }
      try {
        const res = await runRegistrySql(projectId, sql)
        append('out', formatSqlResultForTerminal(res))
        onWorkspaceAction?.({ type: 'schema-registry-sql', sql, result: res })
        if (onOpenWorkspaceTab) {
          append('sys', onOpenWorkspaceTab('schema-data'))
          append('sys', 'Full results → Schema registry tab (SQL)')
        }
      } catch (e) {
        const msg = formatApiError(e)
        append('err', msg)
        onWorkspaceAction?.({ type: 'schema-registry-sql', sql, error: msg })
        if (onOpenWorkspaceTab) {
          append('sys', onOpenWorkspaceTab('schema-data'))
        }
      }
    },
    [append, onOpenWorkspaceTab, onWorkspaceAction, projectId],
  )

  const runLocalCommand = useCallback(
    async (raw: string): Promise<boolean> => {
      const parts = raw.trim().split(/\s+/)
      const cmd = (parts[0] ?? '').toLowerCase()
      const rest = parts.slice(1).join(' ').trim()

      switch (cmd) {
        case 'help':
        case '?':
          append('out', HELP)
          return true
        case 'clear':
          setLines([{ kind: 'sys', text: 'terminal cleared' }])
          return true
        case 'status': {
          try {
            const m = await getProject(projectId)
            append(
              'out',
              [
                `project: ${m.name}`,
                `parse_status: ${m.parse_status}`,
                `domain: ${m.last_domain ?? '—'}`,
                `has_diagram: ${m.has_diagram}`,
                `handdrawn: ${m.handdrawn}`,
              ].join('\n'),
            )
          } catch (e) {
            append('err', formatApiError(e))
          }
          return true
        }
        case 'parse':
          try {
            await queueParse(projectId)
            append('out', 'Parse queued — watch progress above or status command')
          } catch (e) {
            append('err', formatApiError(e))
          }
          return true
        case 'whoami':
          try {
            const u = await fetchMe()
            append(
              'out',
              [
                `user: ${u.full_name} <${u.email}>`,
                `role: ${u.role}`,
                u.organization_name
                  ? `org: ${u.organization_name} (${u.organization_id})`
                  : 'org: (personal workspace)',
              ].join('\n'),
            )
          } catch (e) {
            append('err', formatApiError(e))
          }
          return true
        case 'context':
          append('out', selected ? `node_id: ${selected}` : 'no node selected (diagram-level context)')
          return true
        case 'open': {
          const name = rest.split(/\s+/)[0] ?? rest
          const tabId = resolveOpenTabCommandFuzzy(name)
          if (!tabId || !onOpenWorkspaceTab) {
            append(
              'err',
              'usage: open diagram|graph|registry|mission|annotations|inspector|launch|simulation',
            )
            return true
          }
          append('sys', onOpenWorkspaceTab(tabId))
          return true
        }
        case 'sql': {
          const statement = rest.trim()
          if (!statement) {
            append('err', 'usage: sql SELECT … | INSERT … | UPDATE … | DELETE …')
            return true
          }
          await runSqlCommand(statement)
          return true
        }
        case 'ask':
          if (!rest) {
            append('err', 'usage: ask <your question>')
            return true
          }
          return false
        default:
          return false
      }
    },
    [append, onOpenWorkspaceTab, projectId, runSqlCommand, selected],
  )

  const runCopilot = useCallback(
    async (message: string, silent = false): Promise<string | null> => {
      if (!hasDiagram && !message.toLowerCase().includes('parse')) {
        append('sys', 'No diagram IR yet — run parse first, or type: parse')
        return null
      }
      try {
        const reply = selected
          ? await chatNode(projectId, selected, message)
          : await chatDiagram(projectId, message)
        if (!silent) append('out', reply)
        return reply
      } catch (e) {
        const msg = formatApiError(e)
        if (msg.includes('503') || msg.toLowerCase().includes('google')) {
          append(
            'err',
            `${msg}\n\nTip: set GOOGLE_API_KEY in .env and restart make dev`,
          )
        } else {
          append('err', msg)
        }
        return null
      }
    },
    [append, hasDiagram, projectId, selected],
  )

  const execute = useCallback(async (overrideRaw?: string) => {
    const raw = (overrideRaw ?? input).trim()
    if (!raw || busy) return
    setInput('')
    setShowSuggestions(false)
    setSuggestIdx(-1)
    setHistory((h) => (h[h.length - 1] === raw ? h : [...h, raw]))
    setHistIdx(-1)
    append('in', raw)
    setBusy(true)

    try {
      let message = raw
      if (raw.toLowerCase().startsWith('ask ')) {
        message = raw.slice(4).trim()
      } else if (looksLikeRegistrySql(raw)) {
        await runSqlCommand(raw)
        return
      } else {
        const handled = await runLocalCommand(raw)
        if (handled) return
      }

      const prep = onWorkspaceMessage?.(message) ?? { continueCopilot: true }
      if (prep.sysLines?.length) {
        for (const line of prep.sysLines) append('sys', line)
      }
      if (!prep.continueCopilot) return

      if (prep.dynamicTabId) {
        const reply = await runCopilot(message, true)
        if (reply) {
          onWorkspaceAction?.({
            type: 'store-dynamic-result',
            tabId: prep.dynamicTabId,
            text: reply,
          })
          append('out', 'Analysis complete — see the new tab for the full response.')
        }
        return
      }

      await runCopilot(message)
    } finally {
      setBusy(false)
      inputRef.current?.focus()
    }
  }, [
    append,
    busy,
    input,
    onWorkspaceAction,
    onWorkspaceMessage,
    runCopilot,
    runLocalCommand,
    runSqlCommand,
  ])

  const applySuggestion = useCallback(
    (s: TerminalSuggestion, runNow: boolean) => {
      const value = s.value
      setInput(value)
      setShowSuggestions(false)
      setSuggestIdx(-1)
      if (runNow && !value.endsWith(' ')) {
        void execute(value)
      } else {
        inputRef.current?.focus()
      }
    },
    [execute],
  )

  return (
    <div className="integration-terminal">
      <div className="terminal-screen" role="log" aria-live="polite">
        {lines.map((line, i) => (
          <div key={i} className={`term-line term-${line.kind}`}>
            {line.kind === 'in' && <span className="term-prompt">&gt; </span>}
            {line.kind === 'out' && <span className="term-prompt">◆ </span>}
            {line.kind === 'err' && <span className="term-prompt">! </span>}
            {line.kind === 'sys' && <span className="term-prompt">// </span>}
            <span style={{ whiteSpace: 'pre-wrap' }}>{line.text}</span>
          </div>
        ))}
        {busy ? (
          <div className="term-line term-sys">
            <span className="term-prompt">// </span>
            processing…
          </div>
        ) : null}
        <div ref={bottomRef} />
      </div>
      <div className="terminal-input-wrap">
        {showSuggestions && suggestions.length > 0 ? (
          <ul className="terminal-suggestions" role="listbox" aria-label="Command suggestions">
            {suggestions.map((s, i) => (
              <li key={`${s.value}-${i}`} role="presentation">
                <button
                  type="button"
                  role="option"
                  aria-selected={i === suggestIdx}
                  className={`terminal-suggestion${i === suggestIdx ? ' terminal-suggestion--active' : ''}`}
                  onMouseDown={(e) => {
                    e.preventDefault()
                    applySuggestion(s, true)
                  }}
                >
                  <span className="terminal-suggestion-label mono">{s.label}</span>
                  {s.hint ? <span className="terminal-suggestion-hint muted">{s.hint}</span> : null}
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        <form
          className="terminal-input-row"
          onSubmit={(e) => {
            e.preventDefault()
            if (showSuggestions && suggestIdx >= 0 && suggestions[suggestIdx]) {
              applySuggestion(suggestions[suggestIdx]!, true)
              return
            }
            void execute()
          }}
        >
          <span className="term-prompt">&gt;</span>
          <input
            ref={inputRef}
            type="text"
            className="terminal-input mono"
            value={input}
            disabled={busy}
            placeholder="sql SELECT … · open registry · Tab for suggestions"
            onFocus={() => setShowSuggestions(true)}
            onBlur={() => {
              window.setTimeout(() => setShowSuggestions(false), 120)
            }}
            onChange={(e) => {
              setInput(e.target.value)
              setShowSuggestions(true)
              setSuggestIdx(-1)
              setHistIdx(-1)
            }}
            onKeyDown={(e) => {
              if (showSuggestions && suggestions.length > 0) {
                if (e.key === 'Tab' || (e.key === 'ArrowDown' && !e.altKey)) {
                  e.preventDefault()
                  const next =
                    e.key === 'Tab'
                      ? suggestIdx < 0
                        ? 0
                        : (suggestIdx + 1) % suggestions.length
                      : suggestIdx < 0
                        ? 0
                        : Math.min(suggestions.length - 1, suggestIdx + 1)
                  setSuggestIdx(next)
                  const pick = suggestions[next]!
                  if (e.key === 'Tab' && !e.shiftKey) {
                    setInput(pick.value)
                  }
                  return
                }
                if (e.key === 'ArrowUp' && !e.altKey) {
                  e.preventDefault()
                  if (suggestIdx > 0) {
                    setSuggestIdx(suggestIdx - 1)
                  } else if (suggestIdx === 0) {
                    setSuggestIdx(-1)
                  }
                  return
                }
                if (e.key === 'Escape') {
                  e.preventDefault()
                  setShowSuggestions(false)
                  setSuggestIdx(-1)
                  return
                }
              }
              if (e.key === 'ArrowUp' && (!showSuggestions || !suggestions.length)) {
                e.preventDefault()
                if (!history.length) return
                const next = histIdx < 0 ? history.length - 1 : Math.max(0, histIdx - 1)
                setHistIdx(next)
                setInput(history[next]!)
              }
              if (e.key === 'ArrowDown' && (!showSuggestions || !suggestions.length)) {
                e.preventDefault()
                if (histIdx < 0) return
                const next = histIdx + 1
                if (next >= history.length) {
                  setHistIdx(-1)
                  setInput('')
                } else {
                  setHistIdx(next)
                  setInput(history[next]!)
                }
              }
            }}
            autoComplete="off"
            spellCheck={false}
          />
          <button type="submit" className="btn btn-primary" disabled={busy}>
            Run
          </button>
        </form>
      </div>
      <div className="terminal-meta muted mono">
        parse: {parseStatus ?? '—'} · ctx: {selected ?? 'diagram'} ·{' '}
        <button type="button" className="btn btn-ghost" style={{ padding: '0 0.35rem', fontSize: '0.65rem' }} onClick={() => inputRef.current?.focus()}>
          focus
        </button>
      </div>
    </div>
  )
}
