import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

type Props = { open: boolean; onClose: () => void }

type Command = {
  id: string
  label: string
  hint: string
  path: string
  external?: boolean
}

const COMMANDS: Command[] = [
  { id: 'explorer', label: 'Schematic Explorer', hint: 'Upload & convert diagrams', path: '/' },
  { id: 'docs', label: 'API Documentation', hint: 'REST reference & curl examples', path: '/docs' },
  {
    id: 'swagger',
    label: 'OpenAPI Swagger UI',
    hint: 'Interactive API explorer',
    path: '/api/docs',
    external: true,
  },
]

export function CommandPalette({ open, onClose }: Props) {
  const nav = useNavigate()
  const [q, setQ] = useState('')

  useEffect(() => {
    if (!open) setQ('')
  }, [open])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase()
    if (!s) return [...COMMANDS]
    return COMMANDS.filter(
      (c) => c.label.toLowerCase().includes(s) || c.hint.toLowerCase().includes(s),
    )
  }, [q])

  if (!open) return null

  return (
    <div className="palette-backdrop" onClick={onClose} role="presentation">
      <div
        className="palette-panel glass-panel"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Command palette"
      >
        <div className="palette-header">
          <span className="mono palette-prompt">&gt;_</span>
          <input
            className="palette-input"
            autoFocus
            placeholder="simulate launch stresses · compare falcon9 vs electron · navigate…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && filtered[0]) {
                nav(filtered[0].path)
                onClose()
              }
            }}
          />
        </div>
        <ul className="palette-list">
          {filtered.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                className="palette-item"
                onClick={() => {
                  if (c.external) {
                    window.open(c.path, '_blank', 'noopener')
                  } else {
                    nav(c.path)
                  }
                  onClose()
                }}
              >
                <span>{c.label}</span>
                <span className="muted">{c.hint}</span>
              </button>
            </li>
          ))}
          {!filtered.length ? (
            <li className="muted palette-empty">No matching commands</li>
          ) : null}
        </ul>
      </div>
    </div>
  )
}
