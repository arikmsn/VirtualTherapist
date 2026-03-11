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
 *   - needs_consent = true            →  consent screen (new Google user)
 *   - is_onboarding_completed = false →  /onboarding  (new Google user after consent)
 *   - is_onboarding_completed = true  →  /dashboard   (returning user)
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authAPI } from '@/lib/api'
import { useAuth } from '@/auth/useAuth'
import { GOOGLE_STATE_KEY } from '@/components/auth/GoogleSignInButton'
import AppLogo from '@/components/common/AppLogo'

export default function GoogleCallbackPage() {
  const navigate = useNavigate()
  const { login } = useAuth()
  const [error, setError] = useState<string | null>(null)

  // Consent screen state
  const [needsConsent, setNeedsConsent] = useState(false)
  const [pendingToken, setPendingToken] = useState<string | null>(null)
  const [consentName, setConsentName] = useState<string>('')
  const [consentEmail, setConsentEmail] = useState<string>('')
  const [hasAcceptedTerms, setHasAcceptedTerms] = useState(false)
  const [consentLoading, setConsentLoading] = useState(false)
  const [consentError, setConsentError] = useState<string | null>(null)

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
    const redirectUri = `${window.location.origin}/auth/google/callback`

    authAPI.googleCallback(code, redirectUri, returnedState)
      .then((data) => {
        if (data.needs_consent && data.pending_token) {
          // New user — show consent screen before creating account
          setPendingToken(data.pending_token)
          setConsentName(data.full_name || '')
          setConsentEmail(data.email || '')
          setNeedsConsent(true)
          return
        }
        // Returning user — log in directly
        login(data.access_token!, {
          id: data.therapist_id!,
          email: data.email!,
          fullName: data.full_name!,
        }, data.is_onboarding_completed!)
        navigate(data.is_onboarding_completed ? '/dashboard' : '/onboarding', { replace: true })
      })
      .catch((err: any) => {
        const detail = err?.response?.data?.detail
        setError(detail || 'שגיאה בהתחברות עם גוגל. אנא נסה שוב.')
      })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleCompleteSignup = async () => {
    if (!hasAcceptedTerms) {
      setConsentError('חובה לאשר את תנאי השימוש ומדיניות הפרטיות כדי להמשיך.')
      return
    }
    if (!pendingToken) return

    setConsentLoading(true)
    setConsentError(null)
    try {
      const data = await authAPI.googleCompleteSignup(pendingToken, hasAcceptedTerms)
      login(data.access_token, {
        id: data.therapist_id,
        email: data.email,
        fullName: data.full_name,
      }, data.is_onboarding_completed)
      navigate(data.is_onboarding_completed ? '/dashboard' : '/onboarding', { replace: true })
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      setConsentError(detail || 'שגיאה ביצירת החשבון. אנא נסה שוב.')
    } finally {
      setConsentLoading(false)
    }
  }

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

  if (needsConsent) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-therapy-calm to-therapy-gentle flex items-center justify-center p-4" dir="rtl">
        <div className="bg-white rounded-2xl shadow-2xl px-8 pb-8 pt-5 w-full max-w-md">
          <div className="flex flex-col items-center mb-6">
            <a href="https://metapel.online" target="_blank" rel="noopener noreferrer" className="mx-auto mb-3 w-[200px] sm:w-[240px] block">
              <AppLogo variant="full" fluid />
            </a>
            <h1 className="text-xl font-bold text-gray-900">השלמת הרשמה</h1>
            <p className="text-sm text-gray-500 mt-1">צעד אחרון לפני שמתחילים</p>
          </div>

          <div className="space-y-4">
            {consentName && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">שם</label>
                <div className="input-field bg-gray-50 text-gray-500 cursor-not-allowed">{consentName}</div>
              </div>
            )}
            {consentEmail && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">אימייל</label>
                <div className="input-field bg-gray-50 text-gray-500 cursor-not-allowed">{consentEmail}</div>
              </div>
            )}

            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={hasAcceptedTerms}
                onChange={(e) => {
                  setHasAcceptedTerms(e.target.checked)
                  if (e.target.checked) setConsentError(null)
                }}
                className="mt-0.5 h-4 w-4 rounded border-gray-300 text-therapy-calm focus:ring-therapy-calm shrink-0"
              />
              <span className="text-sm text-gray-600">
                אישור שקראתי את{' '}
                <a
                  href="https://www.metapel.online/terms"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-therapy-calm hover:underline"
                >
                  תנאי השימוש ומדיניות הפרטיות
                </a>
              </span>
            </label>

            {consentError && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                {consentError}
              </div>
            )}

            <button
              type="button"
              onClick={handleCompleteSignup}
              disabled={consentLoading}
              className="w-full btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {consentLoading ? (
                <div className="flex items-center justify-center gap-2">
                  <div className="spinner w-5 h-5 border-2"></div>
                  יוצר חשבון...
                </div>
              ) : (
                'השלם הרשמה'
              )}
            </button>
          </div>
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
