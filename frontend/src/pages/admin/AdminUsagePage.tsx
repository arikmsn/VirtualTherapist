import { useEffect, useState } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts'
import { adminAPI, UsageStats } from '@/lib/adminApi'

const TYPE_META: Record<string, { label: string; icon: string; color: string }> = {
  text_claude: { label: 'Claude', icon: '🤖', color: '#6366F1' },
  text_openai: { label: 'OpenAI טקסט', icon: '💬', color: '#10B981' },
  transcription: { label: 'תמלול', icon: '🎙️', color: '#F59E0B' },
}
const TYPE_ORDER = ['text_claude', 'text_openai', 'transcription']

function SkeletonCard() {
  return (
    <div className="bg-gray-800 rounded-xl p-5 border border-gray-700 animate-pulse">
      <div className="h-3 bg-gray-700 rounded w-24 mb-3" />
      <div className="h-8 bg-gray-700 rounded w-16 mb-2" />
      <div className="h-2.5 bg-gray-700 rounded w-20" />
    </div>
  )
}

export default function AdminUsagePage() {
  const [stats, setStats] = useState<UsageStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [days, setDays] = useState(30)

  useEffect(() => {
    setLoading(true)
    setError('')
    adminAPI
      .getUsage(days)
      .then(setStats)
      .catch((e) => setError(`שגיאה בטעינת נתוני שימוש (${e.message})`))
      .finally(() => setLoading(false))
  }, [days])

  const typeMap = stats
    ? Object.fromEntries(stats.by_type.map((t) => [t.usage_type, t]))
    : {}

  const pieData = TYPE_ORDER.map((ut) => ({
    name: TYPE_META[ut].label,
    value: typeMap[ut]?.tokens || 0,
    color: TYPE_META[ut].color,
  })).filter((d) => d.value > 0)

  return (
    <div className="p-8">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">שימוש AI</h1>
          <p className="text-sm text-gray-400">פילוח לפי סוג, מודל ותאריך</p>
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

      {error && <p className="text-red-400 mb-6 text-sm">{error}</p>}

      {/* Type cards */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        {loading
          ? Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)
          : TYPE_ORDER.map((ut) => {
              const meta = TYPE_META[ut]
              const d = typeMap[ut] || { calls: 0, tokens: 0, cost_usd: 0 }
              return (
                <div
                  key={ut}
                  className="bg-gray-800 rounded-xl p-5 border border-gray-700"
                  style={{ borderTopColor: meta.color, borderTopWidth: 2 }}
                >
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-xl">{meta.icon}</span>
                    <span className="text-xs font-semibold text-gray-300">{meta.label}</span>
                  </div>
                  <p className="text-2xl font-bold text-white">{d.calls.toLocaleString()}</p>
                  <p className="text-xs text-gray-400 mt-0.5">קריאות</p>
                  <div className="mt-3 pt-3 border-t border-gray-700 grid grid-cols-2 gap-2">
                    <div>
                      <p className="text-sm font-medium text-gray-300">{d.tokens.toLocaleString()}</p>
                      <p className="text-xs text-gray-500">טוקנים</p>
                    </div>
                    <div>
                      <p className="text-sm font-medium text-gray-300">${d.cost_usd.toFixed(3)}</p>
                      <p className="text-xs text-gray-500">עלות משוערת</p>
                    </div>
                  </div>
                </div>
              )
            })}
      </div>

      {/* Stacked bar chart */}
      <div className="bg-gray-800 rounded-xl p-5 border border-gray-700 mb-6">
        <h2 className="text-sm font-semibold text-gray-300 mb-4">קריאות לפי יום — לפי סוג</h2>
        {loading ? (
          <div className="h-52 bg-gray-700/40 animate-pulse rounded-lg" />
        ) : !stats?.by_day.length ? (
          <p className="text-gray-500 text-sm text-center py-8">אין נתונים לתקופה זו</p>
        ) : (
          <ResponsiveContainer width="100%" height={230}>
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
              />
              <Legend
                formatter={(value) =>
                  TYPE_META[value.replace('_calls', '')]?.label || value
                }
                wrapperStyle={{ fontSize: 11, color: '#9CA3AF' }}
              />
              <Bar dataKey="text_claude_calls" name="text_claude" stackId="a" fill="#6366F1" />
              <Bar dataKey="text_openai_calls" name="text_openai" stackId="a" fill="#10B981" />
              <Bar dataKey="transcription_calls" name="transcription" stackId="a" fill="#F59E0B" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Token distribution pie */}
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <h2 className="text-sm font-semibold text-gray-300 mb-4">חלוקת טוקנים לפי סוג</h2>
          {loading ? (
            <div className="h-48 bg-gray-700/40 animate-pulse rounded-lg" />
          ) : pieData.length === 0 ? (
            <p className="text-gray-500 text-sm text-center py-8">אין נתונים</p>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  dataKey="value"
                  label={({ name, percent }) => percent ? `${name} ${(percent * 100).toFixed(0)}%` : name}
                  labelLine={false}
                >
                  {pieData.map((entry, index) => (
                    <Cell key={index} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value) => [(value as number).toLocaleString(), 'טוקנים']}
                  contentStyle={{ background: '#1F2937', border: 'none', borderRadius: 8 }}
                />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* By flow type */}
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <h2 className="text-sm font-semibold text-gray-300 mb-3">לפי סוג פעולה</h2>
          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-6 bg-gray-700/40 animate-pulse rounded" />
              ))}
            </div>
          ) : (
            <div className="space-y-2 overflow-y-auto max-h-48">
              {(stats?.by_flow || []).map((item) => (
                <div key={item.flow_type} className="flex items-center justify-between">
                  <span className="text-xs text-gray-400 font-mono">{item.flow_type}</span>
                  <span className="text-xs font-semibold text-indigo-400">
                    {item.count.toLocaleString()}
                  </span>
                </div>
              ))}
              {!stats?.by_flow.length && <p className="text-gray-500 text-sm">אין נתונים</p>}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
