import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { AuthDiagnostics } from '../components/auth/AuthDiagnostics'
import { AuthLayout } from '../components/auth/AuthLayout'
import { AuthSsoButtons } from '../components/auth/AuthSsoButtons'
import { BootSequence } from '../components/auth/BootSequence'
import { fetchMe, login } from '../api/auth'
import { formatApiError } from '../api/client'
import { useAuthStore } from '../state/auth'

const REMEMBER_KEY = 'vioci_remember_email'

export function Login() {
  const nav = useNavigate()
  const [search] = useSearchParams()
  const setSession = useAuthStore((s) => s.setSession)
  const [email, setEmail] = useState(() => localStorage.getItem(REMEMBER_KEY) ?? '')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [remember, setRemember] = useState(!!localStorage.getItem(REMEMBER_KEY))
  const [busy, setBusy] = useState(false)
  const [booting, setBooting] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [emailTouched, setEmailTouched] = useState(false)

  const next = search.get('next') || '/'
  const emailInvalid = emailTouched && email.length > 0 && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setEmailTouched(true)
    if (emailInvalid) return
    setBusy(true)
    setErr(null)
    try {
      if (remember) localStorage.setItem(REMEMBER_KEY, email)
      else localStorage.removeItem(REMEMBER_KEY)

      const { access_token, user } = await login(email, password)
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
    return (
      <BootSequence
        onComplete={() => {
          nav(next, { replace: true })
        }}
      />
    )
  }

  return (
    <AuthLayout showcaseActive={busy}>
      <div className="auth-form-card">
        <header className="auth-form-header">
          <span className="auth-form-eyebrow">Secure access</span>
          <h1>Sign in</h1>
          <p>Mission workspace for launch integration engineers</p>
        </header>

        <AuthSsoButtons />

        <div className="auth-divider">or email</div>

        <form onSubmit={(e) => void submit(e)}>
          <div className="auth-field">
            <label htmlFor="login-email">Work email</label>
            <input
              id="login-email"
              className={`auth-input ${emailInvalid ? 'invalid' : ''}`}
              type="email"
              autoComplete="email"
              required
              value={email}
              onBlur={() => setEmailTouched(true)}
              onChange={(e) => setEmail(e.target.value)}
            />
            {emailInvalid ? <p className="auth-field-hint">Enter a valid email address</p> : null}
          </div>

          <div className="auth-field">
            <label htmlFor="login-password">Password</label>
            <div className="auth-input-wrap">
              <input
                id="login-password"
                className="auth-input"
                type={showPw ? 'text' : 'password'}
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button
                type="button"
                className="auth-input-toggle"
                onClick={() => setShowPw((v) => !v)}
                tabIndex={-1}
              >
                {showPw ? 'Hide' : 'Show'}
              </button>
            </div>
          </div>

          <div className="auth-row-options">
            <label className="auth-remember">
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
              />
              Remember me
            </label>
            <a href="mailto:support@vioci.io?subject=Password%20reset" className="auth-forgot">
              Forgot password?
            </a>
          </div>

          {err ? <p className="error" style={{ marginBottom: '0.75rem' }}>{err}</p> : null}

          <button type="submit" className="btn btn-primary auth-submit-btn" disabled={busy}>
            {busy ? 'Authenticating…' : 'Sign in to workspace'}
          </button>

          {busy ? <AuthDiagnostics /> : null}
        </form>

        <p className="auth-footer-links">
          New operator? <Link to="/signup">Create account</Link>
          <br />
          <Link to="/signup/enterprise">Enterprise organization onboarding</Link>
        </p>
      </div>
    </AuthLayout>
  )
}
