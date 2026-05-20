import { useEffect, useState, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { fetchMe } from '../api/auth'
import { formatApiError } from '../api/client'
import { LoadingIndicator } from './LoadingIndicator'
import { useAuthStore } from '../state/auth'

type Props = { children: ReactNode }

export function ProtectedRoute({ children }: Props) {
  const location = useLocation()
  const token = useAuthStore((s) => s.token)
  const user = useAuthStore((s) => s.user)
  const setUser = useAuthStore((s) => s.setUser)
  const clearSession = useAuthStore((s) => s.clearSession)
  const [checking, setChecking] = useState(!!token && !user)

  useEffect(() => {
    if (!token) {
      setChecking(false)
      return
    }
    if (user) {
      setChecking(false)
      return
    }
    let cancelled = false
    void (async () => {
      try {
        const u = await fetchMe()
        if (!cancelled) setUser(u)
      } catch {
        if (!cancelled) clearSession()
      } finally {
        if (!cancelled) setChecking(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [token, user, setUser, clearSession])

  if (!token) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />
  }

  if (checking) {
    return <LoadingIndicator label="Authenticating…" size="md" block />
  }

  if (!user) {
    return (
      <div className="card">
        <p className="error">Session expired — {formatApiError('unauthorized')}</p>
        <Navigate to="/login" replace />
      </div>
    )
  }

  return <>{children}</>
}
