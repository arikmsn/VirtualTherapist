import { useEffect, useState } from 'react'
import { adminAPI, AlertRow } from '@/lib/adminApi'

const ALERT_LABELS: Record<string, { label: string; color: string }> = {
  new_signup: { label: 'הרשמה', color: 'bg-indigo-900/60 text-indigo-300' },
  ai_error: { label: 'שגיאת AI', color: 'bg-red-900/60 text-red-300' },
  blocked_login: { label: 'חסימה', color: 'bg-orange-900/60 text-orange-300' },
  unblocked: { label: 'שחרור', color: 'bg-green-900/60 text-green-300' },
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('he-IL', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function AdminAlertsPage() {
  const [alerts, setAlerts] = useState<AlertRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [unreadOnly, setUnreadOnly] = useState(false)

  async function loadAlerts() {
    setLoading(true)
    try {
      const data = await adminAPI.getAlerts(unreadOnly)
      setAlerts(data)
    } catch {
      setError('שגיאה בטעינת התראות')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAlerts()
  }, [unreadOnly])

  async function markRead(id: number) {
    await adminAPI.markAlertRead(id)
    setAlerts((prev) => prev.map((a) => (a.id === id ? { ...a, is_read: true } : a)))
  }

  async function markAll() {
    await adminAPI.markAllRead()
    setAlerts((prev) => prev.map((a) => ({ ...a, is_read: true })))
  }

  const unreadCount = alerts.filter((a) => !a.is_read).length

  return (
    <div className="p-8">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">התראות</h1>
          <p className="text-sm text-gray-400">
            {unreadCount > 0 ? `${unreadCount} התראות לא נקראו` : 'הכל נקרא'}
          </p>
        </div>
        <div className="flex gap-3 items-center">
          <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
            <input
              type="checkbox"
              checked={unreadOnly}
              onChange={(e) => setUnreadOnly(e.target.checked)}
              className="rounded"
            />
            לא נקראו בלבד
          </label>
          {unreadCount > 0 && (
            <button
              onClick={markAll}
              className="text-xs text-indigo-400 hover:text-indigo-300 border border-indigo-700 px-3 py-1.5 rounded-lg transition-colors"
            >
              סמן הכל כנקרא
            </button>
          )}
        </div>
      </div>

      {error && <p className="text-red-400 mb-4">{error}</p>}

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500" />
        </div>
      ) : alerts.length === 0 ? (
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-8 text-center">
          <p className="text-gray-500 text-sm">אין התראות</p>
        </div>
      ) : (
        <div className="space-y-2">
          {alerts.map((alert) => {
            const style = ALERT_LABELS[alert.alert_type] || {
              label: alert.alert_type,
              color: 'bg-gray-700 text-gray-300',
            }
            return (
              <div
                key={alert.id}
                className={`flex items-start gap-4 bg-gray-800 rounded-xl border px-4 py-3 transition-opacity ${
                  alert.is_read
                    ? 'border-gray-700/50 opacity-60'
                    : 'border-gray-600'
                }`}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${style.color}`}>
                      {style.label}
                    </span>
                    {!alert.is_read && (
                      <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 flex-shrink-0" />
                    )}
                    {alert.therapist_name && (
                      <span className="text-xs text-gray-500">{alert.therapist_name}</span>
                    )}
                  </div>
                  <p className="text-sm text-gray-200">{alert.message}</p>
                  <p className="text-xs text-gray-500 mt-1">{formatDate(alert.created_at)}</p>
                </div>
                {!alert.is_read && (
                  <button
                    onClick={() => markRead(alert.id)}
                    className="text-xs text-gray-500 hover:text-gray-300 whitespace-nowrap mt-0.5"
                  >
                    סמן כנקרא
                  </button>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
