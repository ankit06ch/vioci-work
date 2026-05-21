import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthDiagnostics } from '../components/auth/AuthDiagnostics'
import { AuthLayout } from '../components/auth/AuthLayout'
import { AuthSsoButtons } from '../components/auth/AuthSsoButtons'
import { BootSequence } from '../components/auth/BootSequence'
import { fetchMe, signup } from '../api/auth'
import { formatApiError } from '../api/client'
import { useAuthStore } from '../state/auth'

export function Signup() {
  const nav = useNavigate()
  const setSession = useAuthStore((s) => s.setSession)
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [busy, setBusy] = useState(false)
  const [booting, setBooting] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const pwWeak = password.length > 0 && password.length < 8

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (pwWeak) return
    setBusy(true)
    setErr(null)
    try {
      const { access_token, user } = await signup(email, password, fullName)
      localStorage.setItem('vioci_token', access_token)
      useAuthStore.setState({ token: access_token })
      setSession(access_token, user ?? (await fetchMe()))
      setBooting(true)
    } catch (ex) {
      setErr(formatApiError(ex))
      setBusy(false)
    }
  }

  if (booting) {
    return <BootSequence onComplete={() => nav('/workspace', { replace: true })} />
  }

  return (
    <AuthLayout showcaseActive={busy}>
      <div className="auth-form-card">
        <header className="auth-form-header">
          <span className="auth-form-eyebrow">Operator registration</span>
          <h1>Create account</h1>
          <p>Personal mission workspace with full API access</p>
        </header>

        <AuthSsoButtons />

        <div className="auth-divider">or register</div>

        <form onSubmit={(e) => void submit(e)}>
          <div className="auth-field">
            <label htmlFor="su-name">Full name</label>
            <input
              id="su-name"
              className="auth-input"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          </div>
          <div className="auth-field">
            <label htmlFor="su-email">Work email</label>
            <input
              id="su-email"
              className="auth-input"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="auth-field">
            <label htmlFor="su-password">Password</label>
            <div className="auth-input-wrap">
              <input
                id="su-password"
                className={`auth-input ${pwWeak ? 'invalid' : ''}`}
                type={showPw ? 'text' : 'password'}
                minLength={8}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button
                type="button"
                className="auth-input-toggle"
                onClick={() => setShowPw((v) => !v)}
              >
                {showPw ? 'Hide' : 'Show'}
              </button>
            </div>
            {pwWeak ? <p className="auth-field-hint">Minimum 8 characters</p> : null}
          </div>

          {err ? <p className="error" style={{ marginBottom: '0.75rem' }}>{err}</p> : null}

          <button type="submit" className="btn btn-primary auth-submit-btn" disabled={busy}>
            {busy ? 'Creating account…' : 'Create account'}
          </button>
          {busy ? <AuthDiagnostics /> : null}
        </form>

        <p className="auth-footer-links">
          Already registered? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </AuthLayout>
  )
}
