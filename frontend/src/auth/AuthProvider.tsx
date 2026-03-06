import { createContext, useState, useCallback, useEffect, useRef, type ReactNode } from 'react'
import { authAPI, therapistAPI } from '@/lib/api'

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
  onboardingCompleted: boolean | null  // null = not yet loaded
  login: (token: string, user: AuthUser, onboardingCompleted?: boolean) => void
  logout: () => void
  markOnboardingComplete: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

// How many ms before expiry to proactively refresh (5 minutes)
const REFRESH_BEFORE_MS = 5 * 60 * 1000

export default function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isReady, setIsReady] = useState(false)
  const [onboardingCompleted, setOnboardingCompleted] = useState<boolean | null>(null)
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
    setOnboardingCompleted(null)
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

  const login = useCallback((newToken: string, newUser: AuthUser, completed?: boolean) => {
    localStorage.setItem(TOKEN_KEY, newToken)
    localStorage.setItem('auth_user', JSON.stringify(newUser))
    setToken(newToken)
    setUser(newUser)
    if (completed !== undefined) {
      setOnboardingCompleted(completed)
    } else {
      // Callers should always pass `completed`; this fetch is a safety net so
      // onboardingCompleted never stays null and the UI never gets stuck on a
      // permanent loading spinner.
      therapistAPI.getProfile().then((profile) => {
        setOnboardingCompleted(profile.onboarding_completed ?? true)
      }).catch(() => {
        setOnboardingCompleted(true)
      })
    }
    scheduleRefresh(newToken)
  }, [scheduleRefresh])

  const markOnboardingComplete = useCallback(() => {
    setOnboardingCompleted(true)
  }, [])

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
          // Fetch onboarding status from profile (non-blocking)
          therapistAPI.getProfile().then((profile) => {
            setOnboardingCompleted(profile.onboarding_completed ?? true)
          }).catch(() => {
            // If profile fetch fails, assume onboarding done to avoid blocking the UI
            setOnboardingCompleted(true)
          })
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
    onboardingCompleted,
    login,
    logout,
    markOnboardingComplete,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
