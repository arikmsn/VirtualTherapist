import { useState } from 'react'
import { authAPI } from '@/lib/api'
import { useAuth } from '@/auth/useAuth'
import { strings } from '@/i18n/he'

interface Props {
  onSuccess: () => void
}

export default function ChangePasswordModal({ onSuccess }: Props) {
  const { clearMustChangePassword } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const validate = (): string => {
    if (!current || !next || !confirm) return strings.changePassword.error_empty
    if (next.length < 8) return strings.changePassword.error_too_short
    if (next !== confirm) return strings.changePassword.error_mismatch
    return ''
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const validationError = validate()
    if (validationError) {
      setError(validationError)
      return
    }
    setError('')
    setLoading(true)
    try {
      await authAPI.changePassword(current, next)
      clearMustChangePassword()
      onSuccess()
    } catch (err: any) {
      const detail = err.response?.data?.detail
      if (detail === 'הסיסמה הזמנית שגויה') {
        setError(strings.changePassword.error_wrong_temp)
      } else {
        setError(strings.changePassword.error_update_failed)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      dir="rtl"
    >
      <div className="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl w-full max-w-md">
        {/* Header */}
        <div className="px-6 pt-6 pb-4 border-b border-gray-800">
          <div className="flex items-center gap-3 mb-1">
            <span className="text-2xl">🔐</span>
            <h2 className="text-lg font-bold text-white">{strings.changePassword.title}</h2>
          </div>
          <p className="text-sm text-gray-400 mr-9">
            {strings.changePassword.subtitle}
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          {error && (
            <div className="bg-red-950 border border-red-800 text-red-400 text-sm px-4 py-3 rounded-lg">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              {strings.changePassword.current_label}
            </label>
            <input
              type="password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              placeholder={strings.changePassword.current_placeholder}
              autoComplete="current-password"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              {strings.changePassword.new_label}
            </label>
            <input
              type="password"
              value={next}
              onChange={(e) => setNext(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              placeholder={strings.changePassword.new_placeholder}
              autoComplete="new-password"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
              {strings.changePassword.confirm_label}
            </label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              placeholder={strings.changePassword.confirm_placeholder}
              autoComplete="new-password"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-lg transition-colors text-sm mt-2"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                {strings.changePassword.submit_loading}
              </span>
            ) : (
              strings.changePassword.submit_button
            )}
          </button>
        </form>
      </div>
    </div>
  )
}
