import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { UserProfile } from '../api/auth'

const TOKEN_KEY = 'vioci_token'

type AuthState = {
  token: string | null
  user: UserProfile | null
  setSession: (token: string, user: UserProfile) => void
  clearSession: () => void
  setUser: (user: UserProfile) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      setSession: (token, user) => {
        localStorage.setItem(TOKEN_KEY, token)
        set({ token, user })
      },
      clearSession: () => {
        localStorage.removeItem(TOKEN_KEY)
        set({ token: null, user: null })
      },
      setUser: (user) => set({ user }),
    }),
    { name: 'vioci-auth', partialize: (s) => ({ token: s.token, user: s.user }) },
  ),
)

export function getStoredToken(): string | null {
  return useAuthStore.getState().token ?? localStorage.getItem(TOKEN_KEY)
}
