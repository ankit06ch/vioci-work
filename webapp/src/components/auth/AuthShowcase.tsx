import { useEffect, useState } from 'react'
import { VIOCI_ICON_SRC } from '../../brand'

const SLIDES = [
  {
    label: 'Satellite blueprint',
    svg: (
      <svg viewBox="0 0 320 200" fill="none" aria-hidden>
        <rect x="120" y="70" width="80" height="60" stroke="rgba(255,122,89,0.45)" strokeWidth="1" />
        <line x1="80" y1="100" x2="120" y2="100" stroke="rgba(255,122,89,0.3)" />
        <line x1="200" y1="100" x2="240" y2="100" stroke="rgba(255,122,89,0.3)" />
        <rect x="60" y="92" width="24" height="16" stroke="rgba(200,110,55,0.38)" strokeWidth="1" />
        <rect x="236" y="92" width="24" height="16" stroke="rgba(200,110,55,0.38)" strokeWidth="1" />
        <circle cx="160" cy="55" r="12" stroke="rgba(255,122,89,0.42)" strokeWidth="1" />
        <path d="M160 130 L160 170" stroke="rgba(176,168,172,0.28)" strokeDasharray="4 4" />
      </svg>
    ),
  },
  {
    label: 'Launch compatibility',
    svg: (
      <svg viewBox="0 0 320 200" fill="none" aria-hidden>
        <path d="M160 30 L175 150 L145 150 Z" stroke="rgba(255,122,89,0.48)" strokeWidth="1.2" fill="rgba(255,122,89,0.06)" />
        <rect x="100" y="155" width="120" height="25" rx="2" stroke="rgba(255,122,89,0.35)" strokeWidth="1" />
        <text x="160" y="172" textAnchor="middle" fill="rgba(176,168,172,0.55)" fontSize="10" fontFamily="monospace">
          ENVELOPE OK
        </text>
        <line x1="50" y1="100" x2="270" y2="100" stroke="rgba(255,122,89,0.18)" strokeDasharray="6 4" />
      </svg>
    ),
  },
  {
    label: 'Telemetry stream',
    svg: (
      <svg viewBox="0 0 320 200" fill="none" aria-hidden>
        {[40, 70, 55, 90, 65, 110, 80].map((h, i) => (
          <rect
            key={i}
            x={50 + i * 32}
            y={160 - h}
            width="20"
            height={h}
            fill="rgba(255,122,89,0.12)"
            stroke="rgba(255,122,89,0.35)"
            strokeWidth="1"
          />
        ))}
        <polyline
          points="50,120 82,95 114,110 146,75 178,90 210,60 242,80"
          stroke="rgba(255,143,74,0.5)"
          strokeWidth="1.5"
          fill="none"
        />
      </svg>
    ),
  },
  {
    label: 'Mission simulation',
    svg: (
      <svg viewBox="0 0 320 200" fill="none" aria-hidden>
        <ellipse cx="160" cy="100" rx="100" ry="40" stroke="rgba(255,122,89,0.22)" strokeWidth="1" />
        <ellipse cx="160" cy="100" rx="70" ry="28" stroke="rgba(200,110,55,0.2)" strokeDasharray="4 6" />
        <circle cx="220" cy="100" r="6" fill="rgba(255,143,74,0.55)" />
        <circle cx="100" cy="100" r="4" fill="rgba(255,122,89,0.45)" />
      </svg>
    ),
  },
] as const

const TERMINAL_LINES = [
  { cls: 'line-ok', text: '[OK]  mission_registry.db — connected' },
  { cls: 'line-info', text: '[..]  loading orbital propagator' },
  { cls: 'line-ok', text: '[OK]  launch_compat_engine — nominal' },
  { cls: 'line-warn', text: '[..]  awaiting operator session' },
]

const STATS = [
  { label: 'Active simulations', value: '128', accent: 'accent-warm' },
  { label: 'Launch readiness', value: '94%', accent: 'accent-orange' },
  { label: 'Integrations', value: '2.4k', accent: '' },
]

export function AuthShowcase({ active }: { active?: boolean }) {
  const [slide, setSlide] = useState(0)
  const [termLine, setTermLine] = useState(0)

  useEffect(() => {
    const t = setInterval(() => setSlide((s) => (s + 1) % SLIDES.length), 5000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    const t = setInterval(() => setTermLine((l) => (l + 1) % TERMINAL_LINES.length), 2200)
    return () => clearInterval(t)
  }, [])

  return (
    <aside className={`auth-showcase ${active ? 'auth-showcase-active' : ''}`}>
      <div className="auth-showcase-brand">
        <img src={VIOCI_ICON_SRC} alt="" className="auth-showcase-logo vioci-logo" />
        <p className="auth-showcase-tagline">Mission Integration</p>
      </div>

      <div className="auth-visual-stage">
        {SLIDES.map((s, i) => (
          <div key={s.label} className={`auth-visual-slide ${i === slide ? 'active' : ''}`}>
            {s.svg}
            <span className="auth-visual-label">{s.label}</span>
          </div>
        ))}
      </div>

      <div className="auth-stats-row">
        {STATS.map((st) => (
          <div key={st.label} className="auth-stat-card">
            <span className="auth-stat-label">{st.label}</span>
            <span className={`auth-stat-value ${st.accent}`}>{st.value}</span>
          </div>
        ))}
      </div>

      <div className="auth-mini-terminal" aria-live="polite">
        {TERMINAL_LINES.map((line, i) => (
          <div
            key={line.text}
            className={line.cls}
            style={{ opacity: i <= termLine ? 1 : 0.25 }}
          >
            {line.text}
          </div>
        ))}
      </div>
    </aside>
  )
}
