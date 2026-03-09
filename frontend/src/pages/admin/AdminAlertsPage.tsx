import { useEffect, useState } from 'react'
import { adminAPI, AlertRow } from '@/lib/adminApi'

const ALERT_META: Record<string, { label: string; icon: string; color: string }> = {
  new_signup:          { label: 'הרשמה',          icon: '👤', color: 'bg-indigo-900/60 text-indigo-300' },
  inactive_therapist:  { label: 'לא פעיל',        icon: '😴', color: 'bg-slate-800 text-slate-300' },
  api_error:           { label: 'שגיאת API',      icon: '⚠️', color: 'bg-yellow-900/60 text-yellow-300' },
  high_usage:          { label: 'שימוש גבוה',     icon: '🔥', color: 'bg-orange-900/60 text-orange-300' },
  blocked_therapist:   { label: 'חסימה',           icon: '🚫', color: 'bg-red-900/60 text-red-300' },
  unblocked:           { label: 'שחרור חסימה',    icon: '✅', color: 'bg-green-900/60 text-green-300' },
  login_failed:        { label: 'כניסה כושלת',    icon: '🔐', color: 'bg-amber-900/60 text-amber-300' },
  system_error:        { label: 'שגיאת מערכת',    icon: '💥', color: 'bg-red-950 text-red-400' },
}

type FilterTab = 'all' | 'unread' | 'system' | 'users'

const TABS: { key: FilterTab; label: string }[] = [
  { key: 'all', label: 'הכל' },
  { key: 'unread', label: 'לא נקראו' },
  { key: 'system', label: 'שגיאות מערכת' },
  { key: 'users', label: 'משתמשים' },
]

const USER_TYPES = new Set(['new_signup', 'inactive_therapist', 'blocked_therapist', 'unblocked', 'login_failed'])
const SYSTEM_TYPES = new Set(['system_error', 'api_error'])

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('he-IL', {
    day: '2-digit', month: '2-digit', year: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function AdminAlertsPage() {
  const [alerts, setAlerts] = useState<AlertRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<FilterTab>('all')
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  async function load() {
    setLoading(true)
    setError('')
    try {
      const data = await adminAPI.getAlerts(false)
      setAlerts(data)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(`שגיאה בטעינת התראות (${msg})`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function markRead(id: number) {
    try {
      await adminAPI.markAlertRead(id)
      setAlerts((prev) => prev.map((a) => (a.id === id ? { ...a, is_read: true } : a)))
    } catch {
      // non-blocking
    }
  }

  async function markAll() {
    try {
      await adminAPI.markAllRead()
      setAlerts((prev) => prev.map((a) => ({ ...a, is_read: true })))
    } catch {
      // non-blocking
    }
  }

  function toggleExpand(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const filtered = alerts.filter((a) => {
    if (tab === 'unread') return !a.is_read
    if (tab === 'system') return SYSTEM_TYPES.has(a.alert_type)
    if (tab === 'users') return USER_TYPES.has(a.alert_type)
    return true
  })

  const unreadCount = alerts.filter((a) => !a.is_read).length

  return (
    <div className="p-8">
      <div className="flex items-start justify-between mb-5">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">התראות</h1>
          <p className="text-sm text-gray-400">
            {unreadCount > 0 ? `${unreadCount} התראות לא נקראו` : 'הכל נקרא'}
          </p>
        </div>
        {unreadCount > 0 && (
          <button
            onClick={markAll}
            className="text-xs text-indigo-400 hover:text-indigo-300 border border-indigo-700 px-3 py-1.5 rounded-lg transition-colors"
          >
            סמן הכל כנקרא
          </button>
        )}
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 mb-5 border-b border-gray-800">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-xs font-medium transition-colors ${
              tab === t.key
                ? 'text-white border-b-2 border-indigo-500'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            {t.label}
            {t.key === 'unread' && unreadCount > 0 && (
              <span className="mr-1.5 bg-indigo-700 text-indigo-200 text-xs px-1.5 py-0.5 rounded-full">
                {unreadCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {error && (
        <div className="bg-red-950 border border-red-800 rounded-xl p-4 mb-4 text-sm text-red-400">
          {error}
          <button onClick={load} className="mr-3 underline text-xs">נסה שוב</button>
        </div>
      )}

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-16 bg-gray-800 rounded-xl border border-gray-700 animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-8 text-center">
          <p className="text-gray-500 text-sm">אין התראות</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((alert) => {
            const meta = ALERT_META[alert.alert_type] || {
              label: alert.alert_type, icon: '📌', color: 'bg-gray-700 text-gray-300',
            }
            const isExpanded = expanded.has(alert.id)
            const isSystemError = alert.alert_type === 'system_error'

            return (
              <div
                key={alert.id}
                className={`bg-gray-800 rounded-xl border px-4 py-3 transition-opacity ${
                  alert.is_read ? 'border-gray-700/50 opacity-60' : 'border-gray-600'
                }`}
              >
                <div className="flex items-start gap-3">
                  <span className="text-lg flex-shrink-0 mt-0.5">{meta.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${meta.color}`}>
                        {meta.label}
                      </span>
                      {!alert.is_read && (
                        <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 flex-shrink-0" />
                      )}
                      {alert.therapist_name && (
                        <span className="text-xs text-gray-500">{alert.therapist_name}</span>
                      )}
                    </div>
                    <p className="text-sm text-gray-200 leading-snug">{alert.message.split('\n')[0]}</p>

                    {/* Expandable system_error detail */}
                    {isSystemError && alert.message.includes('\n') && (
                      <button
                        onClick={() => toggleExpand(alert.id)}
                        className="text-xs text-gray-500 hover:text-gray-300 mt-1 underline"
                      >
                        {isExpanded ? 'הסתר פרטים' : 'הצג stack trace'}
                      </button>
                    )}
                    {isExpanded && (
                      <pre className="mt-2 text-xs text-red-400 bg-gray-900 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap font-mono leading-relaxed">
                        {alert.message}
                      </pre>
                    )}

                    <p className="text-xs text-gray-500 mt-1">{formatDate(alert.created_at)}</p>
                  </div>
                  {!alert.is_read && (
                    <button
                      onClick={() => markRead(alert.id)}
                      className="text-xs text-gray-500 hover:text-gray-300 whitespace-nowrap flex-shrink-0 mt-0.5"
                    >
                      סמן כנקרא
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
