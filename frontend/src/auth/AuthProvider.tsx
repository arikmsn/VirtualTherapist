import { createContext, useState, useCallback, useEffect, useRef, type ReactNode } from 'react'
import { authAPI } from '@/lib/api'

const TOKEN_KEY = 'access_token'

// Decode the JWT payload to read the exp claim (no library needed)
function getTokenExp(token: string): number | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return typeof payload.exp === 'number' ? payload.exp : null
  } catch {
    return null
  }
}

export interface AuthUser {
  id: number
  email: string
  fullName: string
}

export interface AuthContextValue {
  isAuthenticated: boolean
  isReady: boolean
  token: string | null
  user: AuthUser | null
  login: (token: string, user: AuthUser) => void
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

// How many ms before expiry to proactively refresh (5 minutes)
const REFRESH_BEFORE_MS = 5 * 60 * 1000

export default function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isReady, setIsReady] = useState(false)
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearRefreshTimer = useCallback(() => {
    if (refreshTimerRef.current !== null) {
      clearTimeout(refreshTimerRef.current)
      refreshTimerRef.current = null
    }
  }, [])

  const logout = useCallback(() => {
    clearRefreshTimer()
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem('auth_user')
    setToken(null)
    setUser(null)
  }, [clearRefreshTimer])

  // scheduleRefresh is defined after logout so it can reference it
  const scheduleRefresh = useCallback((currentToken: string) => {
    clearRefreshTimer()

    const exp = getTokenExp(currentToken)
    if (!exp) return

    const nowMs = Date.now()
    const expMs = exp * 1000
    const refreshAtMs = expMs - REFRESH_BEFORE_MS
    const delayMs = refreshAtMs - nowMs

    if (delayMs <= 0) {
      // Token already expired or about to — nothing to schedule; next API call handles logout
      return
    }

    refreshTimerRef.current = setTimeout(async () => {
      try {
        const data = await authAPI.refresh()
        const newToken = data.access_token
        const newUser: AuthUser = {
          id: data.therapist_id,
          email: data.email,
          fullName: data.full_name,
        }
        localStorage.setItem(TOKEN_KEY, newToken)
        localStorage.setItem('auth_user', JSON.stringify(newUser))
        setToken(newToken)
        setUser(newUser)
        // Recurse: schedule the next refresh for the new token
        scheduleRefresh(newToken)
      } catch {
        // Refresh failed (token expired on server or network error)
        // The axios 401 interceptor will have already triggered logout+redirect,
        // but call logout() here too for local state cleanup.
        logout()
      }
    }, delayMs)
  }, [clearRefreshTimer, logout]) // scheduleRefresh recurses via the ref below

  const login = useCallback((newToken: string, newUser: AuthUser) => {
    localStorage.setItem(TOKEN_KEY, newToken)
    localStorage.setItem('auth_user', JSON.stringify(newUser))
    setToken(newToken)
    setUser(newUser)
    scheduleRefresh(newToken)
  }, [scheduleRefresh])

  // On mount: restore token from localStorage and schedule refresh if still valid
  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY)
    if (stored) {
      setToken(stored)
      const storedUser = localStorage.getItem('auth_user')
      if (storedUser) {
        try {
          const parsedUser = JSON.parse(storedUser) as AuthUser
          setUser(parsedUser)
          scheduleRefresh(stored)
        } catch {
          localStorage.removeItem('auth_user')
        }
      }
    }
    setIsReady(true)

    return () => clearRefreshTimer()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const value: AuthContextValue = {
    isAuthenticated: token !== null,
    isReady,
    token,
    user,
    login,
    logout,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
