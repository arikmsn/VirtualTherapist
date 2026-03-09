import { useEffect, useState } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'
import { adminAPI, UsageStats } from '@/lib/adminApi'

export default function AdminUsagePage() {
  const [stats, setStats] = useState<UsageStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [days, setDays] = useState(30)

  useEffect(() => {
    setLoading(true)
    adminAPI
      .getUsage(days)
      .then(setStats)
      .catch(() => setError('שגיאה בטעינת נתוני שימוש'))
      .finally(() => setLoading(false))
  }, [days])

  return (
    <div className="p-8">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">שימוש AI</h1>
          <p className="text-sm text-gray-400">קריאות וטוקנים לפי תקופה</p>
        </div>
        <div className="flex gap-2">
          {[7, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
                days === d
                  ? 'bg-indigo-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:text-white border border-gray-700'
              }`}
            >
              {d} ימים
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500" />
        </div>
      )}
      {error && <p className="text-red-400">{error}</p>}

      {stats && !loading && (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 gap-4 mb-8">
            <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
              <p className="text-xs text-gray-400 mb-1">קריאות AI</p>
              <p className="text-3xl font-bold text-white">{stats.total_calls.toLocaleString()}</p>
            </div>
            <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
              <p className="text-xs text-gray-400 mb-1">טוקנים</p>
              <p className="text-3xl font-bold text-white">{stats.total_tokens.toLocaleString()}</p>
            </div>
          </div>

          {/* Calls by day chart */}
          <div className="bg-gray-800 rounded-xl p-5 border border-gray-700 mb-6">
            <h2 className="text-sm font-semibold text-gray-300 mb-4">קריאות לפי יום</h2>
            {stats.by_day.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={stats.by_day} margin={{ top: 4, right: 4, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: '#9CA3AF', fontSize: 10 }}
                    tickFormatter={(v) => v.slice(5)}
                  />
                  <YAxis tick={{ fill: '#9CA3AF', fontSize: 10 }} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{ background: '#1F2937', border: 'none', borderRadius: 8 }}
                    labelStyle={{ color: '#E5E7EB' }}
                    itemStyle={{ color: '#818CF8' }}
                  />
                  <Bar dataKey="calls" fill="#6366F1" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-gray-500 text-sm text-center py-8">אין נתונים לתקופה זו</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-6">
            {/* By flow type */}
            <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
              <h2 className="text-sm font-semibold text-gray-300 mb-3">לפי סוג פעולה</h2>
              <div className="space-y-2">
                {stats.by_flow.length === 0 && (
                  <p className="text-gray-500 text-sm">אין נתונים</p>
                )}
                {stats.by_flow.map((item) => (
                  <div key={item.flow_type} className="flex items-center justify-between">
                    <span className="text-xs text-gray-400 font-mono">{item.flow_type}</span>
                    <span className="text-xs font-semibold text-indigo-400">
                      {item.count.toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* By model */}
            <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
              <h2 className="text-sm font-semibold text-gray-300 mb-3">לפי מודל</h2>
              <div className="space-y-2">
                {stats.by_model.length === 0 && (
                  <p className="text-gray-500 text-sm">אין נתונים</p>
                )}
                {stats.by_model.map((item) => (
                  <div key={item.model} className="flex items-center justify-between">
                    <span className="text-xs text-gray-400 font-mono truncate max-w-[160px]">
                      {item.model}
                    </span>
                    <span className="text-xs font-semibold text-green-400">
                      {item.count.toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
