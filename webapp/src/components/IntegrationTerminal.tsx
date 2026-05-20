import { useCallback, useEffect, useRef, useState } from 'react'
import {
  chatDiagram,
  chatNode,
  formatApiError,
  getProject,
  queueParse,
} from '../api/client'
import { fetchMe } from '../api/auth'
import { useSelectionStore } from '../state/project'

type Line = { kind: 'in' | 'out' | 'err' | 'sys'; text: string }

type Props = {
  projectId: string
  parseStatus?: string
  hasDiagram?: boolean
}

const HELP = `Available commands:
  help              Show this message
  clear             Clear terminal
  status            Project parse status
  parse             Queue IR parse (Gemini)
  whoami            Current user & organization
  context           Show selected node id
  ask <message>     Engineering copilot (same as plain text)

Natural language (without a command prefix) is sent to the AI copilot.`

export function IntegrationTerminal({ projectId, parseStatus, hasDiagram }: Props) {
  const selected = useSelectionStore((s) => s.selectedNodeId)
  const [lines, setLines] = useState<Line[]>([
    { kind: 'sys', text: 'VIOCI integration terminal v1.0 — type help for commands' },
  ])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [history, setHistory] = useState<string[]>([])
  const [histIdx, setHistIdx] = useState(-1)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines, busy])

  const append = useCallback((kind: Line['kind'], text: string) => {
    setLines((prev) => [...prev, { kind, text }])
  }, [])

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
    [append, projectId, selected],
  )

  const runCopilot = useCallback(
    async (message: string) => {
      if (!hasDiagram && !message.toLowerCase().includes('parse')) {
        append('sys', 'No diagram IR yet — run parse first, or type: parse')
      }
      try {
        const reply = selected
          ? await chatNode(projectId, selected, message)
          : await chatDiagram(projectId, message)
        append('out', reply)
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
      }
    },
    [append, hasDiagram, projectId, selected],
  )

  const execute = useCallback(async () => {
    const raw = input.trim()
    if (!raw || busy) return
    setInput('')
    setHistory((h) => (h[h.length - 1] === raw ? h : [...h, raw]))
    setHistIdx(-1)
    append('in', raw)
    setBusy(true)

    try {
      let message = raw
      if (raw.toLowerCase().startsWith('ask ')) {
        message = raw.slice(4).trim()
        await runCopilot(message)
      } else {
        const handled = await runLocalCommand(raw)
        if (!handled) {
          await runCopilot(raw)
        }
      }
    } finally {
      setBusy(false)
      inputRef.current?.focus()
    }
  }, [append, busy, input, runCopilot, runLocalCommand])

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
      <form
        className="terminal-input-row"
        onSubmit={(e) => {
          e.preventDefault()
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
          placeholder="help · status · parse · ask … or natural language"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowUp') {
              e.preventDefault()
              if (!history.length) return
              const next = histIdx < 0 ? history.length - 1 : Math.max(0, histIdx - 1)
              setHistIdx(next)
              setInput(history[next])
            }
            if (e.key === 'ArrowDown') {
              e.preventDefault()
              if (histIdx < 0) return
              const next = histIdx + 1
              if (next >= history.length) {
                setHistIdx(-1)
                setInput('')
              } else {
                setHistIdx(next)
                setInput(history[next])
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
      <div className="terminal-meta muted mono">
        parse: {parseStatus ?? '—'} · ctx: {selected ?? 'diagram'} ·{' '}
        <button type="button" className="btn btn-ghost" style={{ padding: '0 0.35rem', fontSize: '0.65rem' }} onClick={() => inputRef.current?.focus()}>
          focus
        </button>
      </div>
    </div>
  )
}
