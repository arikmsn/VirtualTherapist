import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/auth/useAuth'
import { authAPI } from '@/lib/api'
import AppLogo from '@/components/common/AppLogo'

export default function LoginPage() {
  const navigate = useNavigate()
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const data = await authAPI.login(email, password)
      login(data.access_token, { id: data.therapist_id, email: data.email, fullName: data.full_name })
      // Return to the page the user was on before the session expired
      const redirectTo = sessionStorage.getItem('redirect_after_login') || '/dashboard'
      sessionStorage.removeItem('redirect_after_login')
      navigate(redirectTo)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'שגיאה בהתחברות')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-therapy-calm to-therapy-gentle flex items-center justify-center p-4" dir="rtl">
      <div className="bg-white rounded-2xl shadow-2xl p-8 w-full max-w-md">
        {/* Logo — full brand image centered, title + subtitle as plain text below */}
        <div className="flex flex-col items-center mb-8">
          <AppLogo variant="full" size="lg" className="max-w-[260px] mb-6" />
          <h1 className="text-xl font-bold text-gray-900">התחברות</h1>
          <p className="text-sm text-gray-500 mt-2">מטפל אונליין – עוזר חכם למטפלים</p>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              אימייל
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input-field"
              placeholder="your@email.com"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              סיסמה
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input-field"
              placeholder="••••••••"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <div className="flex items-center justify-center gap-2">
                <div className="spinner w-5 h-5 border-2"></div>
                מתחבר...
              </div>
            ) : (
              'התחברות'
            )}
          </button>
        </form>

        {/* Register Link */}
        <div className="mt-6 text-center">
          <p className="text-gray-600">
            עדיין אין לך חשבון?{' '}
            <Link to="/register" className="text-therapy-calm font-medium hover:underline">
              הירשם עכשיו
            </Link>
          </p>
        </div>

        {/* Security Notice */}
        <div className="mt-8 pt-6 border-t border-gray-200">
          <div className="flex items-center justify-center gap-2 text-xs text-gray-500">
            <span>🔒</span>
            <span>מוצפן מקצה לקצה</span>
            <span>•</span>
            <span>תואם GDPR</span>
            <span>•</span>
            <span>נתונים בישראל</span>
          </div>
        </div>
      </div>
    </div>
  )
}
