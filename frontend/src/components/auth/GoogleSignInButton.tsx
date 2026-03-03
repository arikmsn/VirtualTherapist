/**
 * GoogleSignInButton
 *
 * Builds the Google OAuth URL with a CSRF-safe `state` parameter and
 * redirects the browser to Google.
 *
 * State is HMAC-signed by the backend (GET /auth/google/state), stored in
 * sessionStorage, and verified server-side on callback. This provides both
 * client-side (sessionStorage comparison) and server-side (HMAC) CSRF protection.
 */

import { authAPI } from '@/lib/api'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined

const GOOGLE_SCOPES = [
  'openid',
  'https://www.googleapis.com/auth/userinfo.email',
  'https://www.googleapis.com/auth/userinfo.profile',
].join(' ')

export const GOOGLE_STATE_KEY = 'google_oauth_state'

function getRedirectUri(): string {
  return `${window.location.origin}/auth/google/callback`
}

async function startGoogleOAuth() {
  if (!GOOGLE_CLIENT_ID) {
    alert('Google Sign-In is not configured. Please contact support.')
    return
  }

  // Fetch a server-signed state token for CSRF protection.
  // The backend will verify the HMAC on callback.
  let state: string
  try {
    const result = await authAPI.googleState()
    state = result.state
  } catch {
    alert('שגיאה בפתיחת חלון Google. אנא נסה שוב.')
    return
  }

  sessionStorage.setItem(GOOGLE_STATE_KEY, state)

  const params = new URLSearchParams({
    client_id: GOOGLE_CLIENT_ID,
    redirect_uri: getRedirectUri(),
    response_type: 'code',
    scope: GOOGLE_SCOPES,
    include_granted_scopes: 'true',
    state,
    access_type: 'online',
  })

  window.location.href = `https://accounts.google.com/o/oauth2/v2/auth?${params}`
}

interface Props {
  disabled?: boolean
}

export default function GoogleSignInButton({ disabled }: Props) {
  return (
    <button
      type="button"
      onClick={startGoogleOAuth}
      disabled={disabled}
      className="w-full flex items-center justify-center gap-3 px-4 py-2.5 border border-gray-300 rounded-lg bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
    >
      {/* Google "G" logo */}
      <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
        <path
          fill="#4285F4"
          d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"
        />
        <path
          fill="#34A853"
          d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"
        />
        <path
          fill="#FBBC05"
          d="M3.964 10.706A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.706V4.962H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.038l3.007-2.332z"
        />
        <path
          fill="#EA4335"
          d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.962L3.964 7.294C4.672 5.163 6.656 3.58 9 3.58z"
        />
      </svg>
      המשך עם Google
    </button>
  )
}
