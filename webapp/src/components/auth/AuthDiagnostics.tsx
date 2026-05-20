import { useEffect, useState } from 'react'

const STEPS = [
  'Verifying credentials',
  'Establishing secure session',
  'Loading mission registry',
  'Initializing AI copilot',
  'Preparing workspace',
]

export function AuthDiagnostics() {
  const [step, setStep] = useState(0)

  useEffect(() => {
    const t = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 450)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="auth-diagnostics" role="status" aria-live="polite">
      <div className="auth-diag-bar" />
      {STEPS.map((label, i) => (
        <div key={label} className={`auth-diag-line ${i <= step ? 'active' : ''}`}>
          {i < step ? '✓' : '›'} {label}
        </div>
      ))}
    </div>
  )
}
