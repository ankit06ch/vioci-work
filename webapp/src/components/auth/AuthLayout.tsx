import { useMemo, type ReactNode } from 'react'
import { AuthShowcase } from './AuthShowcase'
import '../../auth.css'

type Props = {
  children: ReactNode
  showcaseActive?: boolean
}

export function AuthLayout({ children, showcaseActive }: Props) {
  const particles = useMemo(
    () =>
      Array.from({ length: 24 }, (_, i) => ({
        id: i,
        left: `${(i * 17) % 100}%`,
        top: `${(i * 23) % 100}%`,
        delay: `${(i % 8) * 0.5}s`,
      })),
    [],
  )

  return (
    <div className="auth-experience">
      <div className="auth-ambient">
        <div className="auth-grid-bg" />
        <div className="auth-orbital" />
        <div className="auth-particles">
          {particles.map((p) => (
            <span
              key={p.id}
              className="auth-particle"
              style={{ left: p.left, top: p.top, animationDelay: p.delay }}
            />
          ))}
        </div>
      </div>
      <AuthShowcase active={showcaseActive} />
      <div className="auth-panel">
        <div className="auth-panel-inner">{children}</div>
      </div>
    </div>
  )
}
