import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '@/auth/useAuth'
import { authAPI } from '@/lib/api'
import PhoneInput from '@/components/PhoneInput'
import AppLogo from '@/components/common/AppLogo'
import GoogleSignInButton from '@/components/auth/GoogleSignInButton'
import { strings } from '@/i18n/he'

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
  const [hasAcceptedTerms, setHasAcceptedTerms] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (formData.password !== formData.confirmPassword) {
      setError(strings.register.error_password_mismatch)
      return
    }

    if (formData.password.length < 8) {
      setError(strings.register.error_password_too_short)
      return
    }

    if (!hasAcceptedTerms) {
      setError(strings.register.error_terms_required)
      return
    }

    setLoading(true)

    try {
      const data = await authAPI.register(
        formData.email,
        formData.password,
        formData.fullName,
        formData.phone,
        intendedPlan,
        hasAcceptedTerms
      )
      login(data.access_token, { id: data.therapist_id, email: data.email, fullName: data.full_name }, false)
      navigate('/onboarding')
    } catch (err: any) {
      setError(err.response?.data?.detail || strings.register.error_registration_failed)
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
          <h1 className="text-xl font-bold text-gray-900">{strings.register.page_title}</h1>
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
              {strings.register.full_name_label}
            </label>
            <input
              type="text"
              value={formData.fullName}
              onChange={(e) => setFormData({ ...formData, fullName: e.target.value })}
              className="input-field"
              placeholder={strings.register.full_name_placeholder}
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {strings.register.email_label}
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
              {strings.register.phone_label}
            </label>
            <PhoneInput
              value={formData.phone}
              onChange={(e164) => setFormData({ ...formData, phone: e164 })}
              className="w-full"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {strings.register.password_label}
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
              {strings.register.confirm_password_label}
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

          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={hasAcceptedTerms}
              onChange={(e) => {
                setHasAcceptedTerms(e.target.checked)
                if (e.target.checked) setError('')
              }}
              className="mt-0.5 h-4 w-4 rounded border-gray-300 text-therapy-calm focus:ring-therapy-calm shrink-0"
            />
            <span className="text-sm text-gray-600">
              {strings.register.terms_text}{' '}
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

          <button
            type="submit"
            disabled={loading}
            className="w-full btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <div className="flex items-center justify-center gap-2">
                <div className="spinner w-5 h-5 border-2"></div>
                {strings.register.register_loading}
              </div>
            ) : (
              strings.register.register_button
            )}
          </button>
        </form>

        {/* Google Sign-In */}
        <div className="mt-4">
          <div className="relative flex items-center gap-3 my-4">
            <div className="flex-1 border-t border-gray-200" />
            <span className="text-xs text-gray-400 whitespace-nowrap">{strings.register.or_divider}</span>
            <div className="flex-1 border-t border-gray-200" />
          </div>
          <GoogleSignInButton
            disabled={loading}
            onBeforeStart={() => {
              if (!hasAcceptedTerms) {
                setError(strings.register.error_terms_required)
                return false
              }
              return true
            }}
          />
        </div>

        {/* Login Link */}
        <div className="mt-6 text-center">
          <p className="text-gray-600">
            <Link to="/login" className="text-therapy-calm font-medium hover:underline">
              {strings.register.login_link}
            </Link>
          </p>
        </div>

        {/* Security Notice */}
        <div className="mt-8 pt-6 border-t border-gray-200">
          <div className="flex items-center justify-center gap-2 text-xs text-gray-500">
            <span>🔒</span>
            <span>{strings.register.security_notice}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
