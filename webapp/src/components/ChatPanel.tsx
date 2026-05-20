import { useState } from 'react'
import { chatDiagram, chatNode } from '../api/client'
import { useSelectionStore } from '../state/project'

type Props = {
  projectId: string
  terminal?: boolean
}

export function ChatPanel({ projectId, terminal }: Props) {
  const selected = useSelectionStore((s) => s.selectedNodeId)
  const [msgs, setMsgs] = useState<{ role: 'user' | 'assistant'; text: string }[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)

  const send = async () => {
    const t = input.trim()
    if (!t || busy) return
    setInput('')
    setMsgs((m) => [...m, { role: 'user', text: t }])
    setBusy(true)
    try {
      const reply = selected
        ? await chatNode(projectId, selected, t)
        : await chatDiagram(projectId, t)
      setMsgs((m) => [...m, { role: 'assistant', text: reply }])
    } catch (e) {
      setMsgs((m) => [
        ...m,
        { role: 'assistant', text: `ERR: ${e instanceof Error ? e.message : String(e)}` },
      ])
    } finally {
      setBusy(false)
    }
  }

  const hints = [
    'simulate launch stresses',
    'compare falcon9 vs electron',
    'detect integration risks',
    'optimize payload configuration',
  ]

  return (
    <div className={terminal ? '' : 'card'}>
      {!terminal && (
        <p className="muted" style={{ marginTop: 0 }}>
          {selected
            ? 'Node context active — query this component.'
            : 'Diagram-level copilot — select a node for targeted analysis.'}
        </p>
      )}
      {terminal && !msgs.length && (
        <p className="muted mono" style={{ fontSize: '0.72rem', marginBottom: 8 }}>
          Try: {hints.map((h) => `"${h}"`).join(' · ')}
        </p>
      )}
      <div className="chat-transcript">
        {msgs.map((m, i) => (
          <div
            key={i}
            className={m.role === 'user' ? 'chat-line-user' : 'chat-line-assistant'}
            style={{ marginBottom: 8, whiteSpace: 'pre-wrap' }}
          >
            {m.text}
          </div>
        ))}
        {!msgs.length ? (
          <span className="muted mono">// awaiting engineering query…</span>
        ) : null}
        {busy ? (
          <div className="mono" style={{ color: 'var(--cyan)', marginTop: 8 }}>
            ◆ streaming response…
          </div>
        ) : null}
      </div>
      <textarea
        className="input-msg"
        value={input}
        placeholder={
          terminal
            ? '> simulate launch stresses | compare falcon9 vs electron…'
            : 'Ask a question…'
        }
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            void send()
          }
        }}
      />
      <div className="footer-actions">
        <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void send()}>
          {busy ? 'Processing…' : 'Execute'}
        </button>
        {terminal && <span className="hud-chip hud-chip-cyan">GEMINI</span>}
      </div>
    </div>
  )
}
