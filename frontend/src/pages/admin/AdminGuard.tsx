/**
 * AdminGuard — checks sessionStorage for a valid admin_token.
 * If absent or expired (basic check), redirects to home.
 */

import { useEffect, useState } from 'react'
import { useNavigate, Outlet } from 'react-router-dom'

function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return payload.exp * 1000 < Date.now()
  } catch {
    return true
  }
}

export default function AdminGuard() {
  const navigate = useNavigate()
  const [ok, setOk] = useState(false)

  useEffect(() => {
    const token = sessionStorage.getItem('admin_token')
    if (!token || isTokenExpired(token)) {
      sessionStorage.removeItem('admin_token')
      navigate('/', { replace: true })
    } else {
      setOk(true)
    }
  }, [navigate])

  if (!ok) return null
  return <Outlet />
}
