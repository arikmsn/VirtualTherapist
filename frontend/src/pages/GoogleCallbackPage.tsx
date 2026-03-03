/**
 * GoogleCallbackPage
 *
 * Google redirects here after the user approves access:
 *   /auth/google/callback?code=...&state=...
 *
 * Security:
 *   1. Verify the `state` parameter matches the value stored in sessionStorage
 *      by GoogleSignInButton (CSRF protection).
 *   2. Send `code` + `redirect_uri` to the backend for token exchange and
 *      ID token verification — no secrets ever touch the frontend.
 *
 * Routing after success:
 *   - is_onboarding_completed = false  →  /onboarding  (new Google user)
 *   - is_onboarding_completed = true   →  /dashboard   (returning user)
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authAPI } from '@/lib/api'
import { useAuth } from '@/auth/useAuth'
import { GOOGLE_STATE_KEY } from '@/components/auth/GoogleSignInButton'

export default function GoogleCallbackPage() {
  const navigate = useNavigate()
  const { login } = useAuth()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const code = params.get('code')
    const returnedState = params.get('state')
    const errorParam = params.get('error')

    // Google can return an error (e.g. user clicked "Cancel")
    if (errorParam) {
      setError('ההתחברות בוטלה. אנא נסה שוב.')
      return
    }

    if (!code || !returnedState) {
      setError('פרמטרים חסרים בחזרה מגוגל. אנא נסה שוב.')
      return
    }

    // ── CSRF check ──────────────────────────────────────────────────────
    const expectedState = sessionStorage.getItem(GOOGLE_STATE_KEY)
    sessionStorage.removeItem(GOOGLE_STATE_KEY)

    if (!expectedState || returnedState !== expectedState) {
      setError('שגיאת אבטחה (state לא תואם). אנא נסה שוב.')
      return
    }

    // ── Exchange code with backend ────────────────────────────────────
    // Send state along so the backend can verify the HMAC signature.
    const redirectUri = `${window.location.origin}/auth/google/callback`

    authAPI.googleCallback(code, redirectUri, returnedState)
      .then((data) => {
        login(data.access_token, {
          id: data.therapist_id,
          email: data.email,
          fullName: data.full_name,
        })
        navigate(data.is_onboarding_completed ? '/dashboard' : '/onboarding', { replace: true })
      })
      .catch((err: any) => {
        const detail = err?.response?.data?.detail
        setError(detail || 'שגיאה בהתחברות עם גוגל. אנא נסה שוב.')
      })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-therapy-calm to-therapy-gentle flex items-center justify-center p-4" dir="rtl">
        <div className="bg-white rounded-2xl shadow-2xl px-8 py-10 w-full max-w-sm text-center">
          <div className="text-4xl mb-4">⚠️</div>
          <h1 className="text-lg font-semibold text-gray-900 mb-2">שגיאה בהתחברות</h1>
          <p className="text-sm text-gray-600 mb-6">{error}</p>
          <a
            href="/login"
            className="inline-block btn-primary text-sm px-6 py-2"
          >
            חזרה להתחברות
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-therapy-calm to-therapy-gentle flex items-center justify-center" dir="rtl">
      <div className="flex flex-col items-center gap-4 text-white">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-white" />
        <p className="text-sm opacity-80">מתחבר עם גוגל...</p>
      </div>
    </div>
  )
}
