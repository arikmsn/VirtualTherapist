import { createContext, useState, useCallback, useEffect, type ReactNode } from 'react'

const TOKEN_KEY = 'access_token'

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

export default function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isReady, setIsReady] = useState(false)

  // On mount: read token from localStorage (single source of truth)
  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY)
    if (stored) {
      setToken(stored)
      // Restore user from a separate key (non-sensitive metadata)
      const storedUser = localStorage.getItem('auth_user')
      if (storedUser) {
        try {
          setUser(JSON.parse(storedUser))
        } catch {
          // Corrupted — clear it
          localStorage.removeItem('auth_user')
        }
      }
    }
    setIsReady(true)
  }, [])

  const login = useCallback((newToken: string, newUser: AuthUser) => {
    localStorage.setItem(TOKEN_KEY, newToken)
    localStorage.setItem('auth_user', JSON.stringify(newUser))
    setToken(newToken)
    setUser(newUser)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem('auth_user')
    setToken(null)
    setUser(null)
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
