import { useEffect, useState } from 'react'
import { adminAPI, DashboardStats } from '@/lib/adminApi'

function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string
  value: string | number
  sub?: string
  accent?: string
}) {
  return (
    <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <p className={`text-3xl font-bold ${accent || 'text-white'}`}>{value}</p>
      {sub && <p className="text-xs text-gray-500 mt-1">{sub}</p>}
    </div>
  )
}

export default function AdminDashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    adminAPI
      .getDashboard()
      .then(setStats)
      .catch(() => setError('שגיאה בטעינת נתונים'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500" />
      </div>
    )
  }

  if (error || !stats) {
    return <div className="p-8 text-red-400">{error || 'שגיאה'}</div>
  }

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-white mb-1">לוח בקרה</h1>
      <p className="text-sm text-gray-400 mb-8">סטטוס כללי של הפלטפורמה</p>

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard label="מטפלים רשומים" value={stats.total_therapists} />
        <StatCard
          label="פעילים (30 יום)"
          value={stats.active_last_30_days}
          accent="text-green-400"
        />
        <StatCard
          label="הרשמות חדשות (7 ימים)"
          value={stats.new_signups_last_7_days}
          accent="text-indigo-400"
        />
        <StatCard label="קריאות AI סה״כ" value={stats.total_ai_calls.toLocaleString()} />
        <StatCard
          label="טוקנים סה״כ"
          value={stats.total_tokens.toLocaleString()}
          sub="prompt + completion"
        />
        <StatCard
          label="התראות לא נקראו"
          value={stats.unread_alerts}
          accent={stats.unread_alerts > 0 ? 'text-amber-400' : 'text-white'}
        />
      </div>
    </div>
  )
}
