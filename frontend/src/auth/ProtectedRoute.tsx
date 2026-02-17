import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './useAuth'

/**
 * Wraps authenticated routes. Redirects to /login if the user is not
 * authenticated. This is the ONLY place in the app that enforces the
 * "must be logged in" redirect — individual pages should never do this.
 */
export default function ProtectedRoute() {
  const { isAuthenticated } = useAuth()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
