import { useEffect, useState, type ReactNode } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { VIOCI_ICON_SRC, VIOCI_LOGO_SRC } from '../brand'
import { useAuthStore } from '../state/auth'
import { CommandPalette } from './CommandPalette'

type Props = { children: ReactNode }

const NAV = [
  { to: '/', label: 'Schematic Explorer', icon: '▤', section: 'Operations' },
  { to: '/docs', label: 'API Documentation', icon: '⎔', section: 'Developers' },
] as const

const AUTH_PATHS = ['/login', '/signup', '/signup/enterprise']

export function AppShell({ children }: Props) {
  const loc = useLocation()
  const nav = useNavigate()
  const user = useAuthStore((s) => s.user)
  const clearSession = useAuthStore((s) => s.clearSession)
  const isAuthPage = AUTH_PATHS.includes(loc.pathname)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [clock, setClock] = useState(() => new Date())

  useEffect(() => {
    const t = setInterval(() => setClock(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setPaletteOpen((o) => !o)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const utc = clock.toISOString().slice(11, 19)
  const isExplorerHome = loc.pathname === '/' || loc.pathname === '/upload'
  const isProjectWorkspace = loc.pathname.startsWith('/projects/')
  const isDocsPage = loc.pathname === '/docs'
  const mainContentClass = [
    'main-content',
    isExplorerHome && 'main-content-explorer',
    isProjectWorkspace && 'main-content-workspace',
    isDocsPage && 'main-content-scroll',
  ]
    .filter(Boolean)
    .join(' ')

  if (isAuthPage) {
    return <>{children}</>
  }

  return (
    <div className="app-shell">
      <div className="cinematic-bg" aria-hidden>
        <span className="cinematic-bg-bloom cinematic-bg-bloom--ember" />
        <span className="cinematic-bg-bloom cinematic-bg-bloom--honey" />
        <span className="cinematic-bg-bloom cinematic-bg-bloom--amber" />
        <span className="cinematic-bg-grain" />
      </div>
      <aside className="sidebar" aria-label="Main navigation">
        <div className="sidebar-brand">
          <Link to="/" className="brand-link" title="Mission Integration">
            <img
              src={VIOCI_ICON_SRC}
              alt=""
              className="brand-logo brand-logo-icon"
              aria-hidden
            />
            <img
              src={VIOCI_LOGO_SRC}
              alt=""
              className="brand-logo brand-logo-full vioci-logo"
            />
            <div className="brand-text sidebar-expand-only">
              <span className="brand-name">Mission Integration</span>
            </div>
          </Link>
        </div>

        <nav className="sidebar-nav">
          {(['Operations', 'Developers'] as const).map((section) => (
            <div key={section}>
              <div className="nav-section-label sidebar-expand-only">{section}</div>
              {NAV.filter((item) => item.section === section).map((item) => {
                const active =
                  item.to === '/'
                    ? loc.pathname === '/' || loc.pathname === '/upload'
                    : loc.pathname === item.to
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={`nav-item ${active ? 'nav-item-active' : ''}`}
                    title={item.label}
                  >
                    <span className="nav-icon">{item.icon}</span>
                    <span className="nav-label sidebar-expand-only">{item.label}</span>
                  </Link>
                )
              })}
            </div>
          ))}
        </nav>

        <div className="sidebar-footer sidebar-expand-only">
          <div className="sidebar-metric">
            <span className="metric-label">UTC</span>
            <span className="metric-value mono">{utc}</span>
          </div>
          <div className="sidebar-metric">
            <span className="metric-label">Build</span>
            <span className="metric-value mono">SG-0.9.1</span>
          </div>
        </div>
      </aside>

      <div className="main-column">
        <header
          className={`top-bar ${isExplorerHome || isProjectWorkspace ? 'top-bar-minimal' : ''}`}
        >
          {!isExplorerHome && !isProjectWorkspace ? (
            <div className="top-bar-left">
              <h1 className="top-title">Component Simulation Platform</h1>
              <span className="top-sub">Diagram → IR → Simulation · AI-assisted engineering</span>
            </div>
          ) : (
            <div className="top-bar-left" />
          )}
          <div className="top-bar-right">
            {user ? (
              <span className="muted mono" style={{ fontSize: '0.72rem' }}>
                {user.full_name}
                {user.organization_name ? ` · ${user.organization_name}` : ''}
              </span>
            ) : null}
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => setPaletteOpen(true)}
            >
              <span className="mono">⌘K</span> Command
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => {
                clearSession()
                nav('/login')
              }}
            >
              Sign out
            </button>
          </div>
        </header>
        <main className={mainContentClass}>
          {children}
        </main>
      </div>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  )
}
