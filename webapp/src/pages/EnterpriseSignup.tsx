import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthDiagnostics } from '../components/auth/AuthDiagnostics'
import { AuthLayout } from '../components/auth/AuthLayout'
import { BootSequence } from '../components/auth/BootSequence'
import { fetchMe, signupEnterprise } from '../api/auth'
import { formatApiError } from '../api/client'
import { useAuthStore } from '../state/auth'

export function EnterpriseSignup() {
  const nav = useNavigate()
  const setSession = useAuthStore((s) => s.setSession)
  const [orgName, setOrgName] = useState('')
  const [orgSlug, setOrgSlug] = useState('')
  const [plan, setPlan] = useState('enterprise')
  const [fullName, setFullName] = useState('')
  const [jobTitle, setJobTitle] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [busy, setBusy] = useState(false)
  const [booting, setBooting] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setErr(null)
    try {
      const { access_token, user } = await signupEnterprise({
        organization_name: orgName,
        organization_slug: orgSlug.trim() || undefined,
        plan,
        email,
        password,
        full_name: fullName,
        job_title: jobTitle.trim() || undefined,
      })
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
      <div className="auth-form-card wide">
        <header className="auth-form-header">
          <span className="hud-chip hud-chip-orange" style={{ marginBottom: '0.65rem' }}>
            ENTERPRISE
          </span>
          <span className="auth-form-eyebrow">Organization onboarding</span>
          <h1>Provision your team</h1>
          <p>Shared mission registry, SSO-ready architecture, and integration APIs</p>
        </header>

        <form onSubmit={(e) => void submit(e)} className="auth-form-grid">
          <fieldset className="auth-fieldset auth-span-full" style={{ gridColumn: '1 / -1' }}>
            <legend>Organization</legend>
            <div className="auth-form-grid" style={{ margin: 0 }}>
              <div className="auth-field">
                <label>Organization name</label>
                <input
                  className="auth-input"
                  required
                  placeholder="Acme Aerospace"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                />
              </div>
              <div className="auth-field">
                <label>URL slug (optional)</label>
                <input
                  className="auth-input mono"
                  placeholder="acme-aerospace"
                  value={orgSlug}
                  onChange={(e) => setOrgSlug(e.target.value)}
                />
              </div>
              <div className="auth-field auth-span-full">
                <label>Plan</label>
                <select className="auth-input select-glass" value={plan} onChange={(e) => setPlan(e.target.value)}>
                  <option value="enterprise">Enterprise — teams &amp; full API</option>
                  <option value="starter">Starter — evaluation</option>
                </select>
              </div>
            </div>
          </fieldset>

          <fieldset className="auth-fieldset auth-span-full" style={{ gridColumn: '1 / -1' }}>
            <legend>Administrator</legend>
            <div className="auth-form-grid" style={{ margin: 0 }}>
              <div className="auth-field">
                <label>Full name</label>
                <input
                  className="auth-input"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                />
              </div>
              <div className="auth-field">
                <label>Job title</label>
                <input
                  className="auth-input"
                  placeholder="Integration lead"
                  value={jobTitle}
                  onChange={(e) => setJobTitle(e.target.value)}
                />
              </div>
              <div className="auth-field">
                <label>Work email</label>
                <input
                  className="auth-input"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div className="auth-field">
                <label>Password</label>
                <div className="auth-input-wrap">
                  <input
                    className="auth-input"
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
              </div>
            </div>
          </fieldset>

          {err ? (
            <p className="error auth-span-full" style={{ margin: 0 }}>
              {err}
            </p>
          ) : null}

          <button
            type="submit"
            className="btn btn-primary auth-submit-btn auth-span-full"
            disabled={busy}
          >
            {busy ? 'Creating organization…' : 'Provision organization'}
          </button>
          {busy ? (
            <div className="auth-span-full">
              <AuthDiagnostics />
            </div>
          ) : null}
        </form>

        <p className="auth-footer-links">
          <Link to="/signup">Personal account</Link> · <Link to="/login">Sign in</Link>
        </p>
      </div>
    </AuthLayout>
  )
}
