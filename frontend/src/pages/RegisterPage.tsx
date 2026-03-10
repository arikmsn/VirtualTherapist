import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '@/auth/useAuth'
import { authAPI } from '@/lib/api'
import PhoneInput from '@/components/PhoneInput'
import AppLogo from '@/components/common/AppLogo'
import GoogleSignInButton from '@/components/auth/GoogleSignInButton'

export default function RegisterPage() {
  const navigate = useNavigate()
  const { login } = useAuth()
  const [searchParams] = useSearchParams()
  const intendedPlan = searchParams.get('plan') === 'pro' ? 'pro' : undefined
  const [formData, setFormData] = useState({
    fullName: '',
    email: '',
    phone: '',
    password: '',
    confirmPassword: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (formData.password !== formData.confirmPassword) {
      setError('הסיסמאות אינן תואמות')
      return
    }

    if (formData.password.length < 8) {
      setError('הסיסמה חייבת להכיל לפחות 8 תווים')
      return
    }

    setLoading(true)

    try {
      const data = await authAPI.register(
        formData.email,
        formData.password,
        formData.fullName,
        formData.phone,
        intendedPlan
      )
      login(data.access_token, { id: data.therapist_id, email: data.email, fullName: data.full_name }, false)
      navigate('/onboarding')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'שגיאה ברישום')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-therapy-calm to-therapy-gentle flex items-center justify-center p-4" dir="rtl">
      <div className="bg-white rounded-2xl shadow-2xl px-8 pb-8 pt-5 w-full max-w-md">
        {/* Logo + title header */}
        <div className="flex flex-col items-center mb-5">
          <a href="https://metapel.online" target="_blank" rel="noopener noreferrer" className="mx-auto mb-3 w-[200px] sm:w-[240px] md:w-[260px] block">
            <AppLogo variant="full" fluid />
          </a>
          <h1 className="text-xl font-bold text-gray-900">הרשמה</h1>
        </div>

        {/* Register Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              שם מלא
            </label>
            <input
              type="text"
              value={formData.fullName}
              onChange={(e) => setFormData({ ...formData, fullName: e.target.value })}
              className="input-field"
              placeholder="ד״ר שרה כהן"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              אימייל
            </label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              className="input-field"
              placeholder="your@email.com"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              טלפון (אופציונלי)
            </label>
            <PhoneInput
              value={formData.phone}
              onChange={(e164) => setFormData({ ...formData, phone: e164 })}
              className="w-full"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              סיסמה
            </label>
            <input
              type="password"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              className="input-field"
              placeholder="••••••••"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              אימות סיסמה
            </label>
            <input
              type="password"
              value={formData.confirmPassword}
              onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
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
                נרשם...
              </div>
            ) : (
              'הרשמה'
            )}
          </button>
        </form>

        {/* Google Sign-In */}
        <div className="mt-4">
          <div className="relative flex items-center gap-3 my-4">
            <div className="flex-1 border-t border-gray-200" />
            <span className="text-xs text-gray-400 whitespace-nowrap">או</span>
            <div className="flex-1 border-t border-gray-200" />
          </div>
          <GoogleSignInButton disabled={loading} />
        </div>

        {/* Login Link */}
        <div className="mt-6 text-center">
          <p className="text-gray-600">
            כבר יש לך חשבון?{' '}
            <Link to="/login" className="text-therapy-calm font-medium hover:underline">
              התחבר כאן
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
          </div>
        </div>
      </div>
    </div>
  )
}
