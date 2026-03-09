import { useEffect, useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  BarChart,
  Bar,
  Legend,
} from 'recharts'
import { adminAPI, DashboardExtended } from '@/lib/adminApi'

const TYPE_META: Record<string, { label: string; icon: string; color: string }> = {
  text_claude: { label: 'Claude', icon: '🤖', color: '#6366F1' },
  text_openai: { label: 'OpenAI טקסט', icon: '💬', color: '#10B981' },
  transcription: { label: 'תמלול', icon: '🎙️', color: '#F59E0B' },
}
const TYPE_ORDER = ['text_claude', 'text_openai', 'transcription']

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

function SkeletonCard() {
  return (
    <div className="bg-gray-800 rounded-xl p-5 border border-gray-700 animate-pulse">
      <div className="h-3 bg-gray-700 rounded w-24 mb-3" />
      <div className="h-8 bg-gray-700 rounded w-16" />
    </div>
  )
}

export default function AdminDashboardPage() {
  const [data, setData] = useState<DashboardExtended | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    adminAPI
      .getDashboard()
      .then(setData)
      .catch((e) => setError(`שגיאה בטעינת נתונים (${e.message})`))
      .finally(() => setLoading(false))
  }, [])

  const stats = data?.stats
  const typeMap = data
    ? Object.fromEntries(data.token_by_type.map((t) => [t.usage_type, t]))
    : {}

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-white mb-1">לוח בקרה</h1>
      <p className="text-sm text-gray-400 mb-8">סטטוס כללי של הפלטפורמה</p>

      {error && <p className="text-red-400 mb-4 text-sm">{error}</p>}

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-10">
        {loading ? (
          Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)
        ) : !stats ? null : (
          <>
            <StatCard label="מטפלים רשומים" value={stats.total_therapists} />
            <StatCard
              label="פעילים (30 יום)"
              value={stats.active_last_30_days}
              sub="מבוסס על last_login — יתעדכן עם שימוש"
              accent="text-gray-300"
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
          </>
        )}
      </div>

      {/* Signups line chart */}
      <div className="bg-gray-800 rounded-xl p-5 border border-gray-700 mb-6">
        <h2 className="text-sm font-semibold text-gray-300 mb-4">הצטרפויות לאורך זמן (12 שבועות)</h2>
        {loading ? (
          <div className="h-44 bg-gray-700/40 animate-pulse rounded-lg" />
        ) : !data?.signup_by_week.length ? (
          <p className="text-gray-500 text-sm text-center py-6">אין נתונים</p>
        ) : (
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={data.signup_by_week} margin={{ top: 4, right: 4, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="week_label" tick={{ fill: '#9CA3AF', fontSize: 10 }} />
              <YAxis tick={{ fill: '#9CA3AF', fontSize: 10 }} allowDecimals={false} />
              <Tooltip
                contentStyle={{ background: '#1F2937', border: 'none', borderRadius: 8 }}
                labelStyle={{ color: '#E5E7EB' }}
                itemStyle={{ color: '#A5B4FC' }}
              />
              <Line
                type="monotone"
                dataKey="count"
                stroke="#818CF8"
                strokeWidth={2}
                dot={{ fill: '#6366F1', strokeWidth: 0, r: 3 }}
                name="הצטרפויות"
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Token breakdown section */}
      <div>
        <h2 className="text-sm font-semibold text-gray-300 mb-3">פילוח טוקנים החודש</h2>
        <div className="grid grid-cols-3 gap-3 mb-4">
          {loading
            ? Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)
            : TYPE_ORDER.map((ut) => {
                const meta = TYPE_META[ut]
                const d = typeMap[ut] || { calls: 0, tokens: 0, cost_usd: 0 }
                return (
                  <div
                    key={ut}
                    className="bg-gray-800 rounded-xl p-4 border border-gray-700"
                    style={{ borderTopColor: meta.color, borderTopWidth: 2 }}
                  >
                    <div className="flex items-center gap-1.5 mb-2">
                      <span>{meta.icon}</span>
                      <span className="text-xs font-medium text-gray-400">{meta.label}</span>
                    </div>
                    <p className="text-lg font-bold text-white">{d.tokens.toLocaleString()}</p>
                    <p className="text-xs text-gray-500">${d.cost_usd.toFixed(3)}</p>
                  </div>
                )
              })}
        </div>

        {/* Last 7 days stacked bar */}
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
          <h3 className="text-xs font-semibold text-gray-400 mb-3">טוקנים יומיים — 7 ימים אחרונים</h3>
          {loading ? (
            <div className="h-36 bg-gray-700/40 animate-pulse rounded-lg" />
          ) : !data?.token_by_day_stacked.length ? (
            <p className="text-gray-500 text-sm text-center py-4">אין נתונים</p>
          ) : (
            <ResponsiveContainer width="100%" height={150}>
              <BarChart
                data={data.token_by_day_stacked}
                margin={{ top: 4, right: 4, left: -10, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis
                  dataKey="date"
                  tick={{ fill: '#9CA3AF', fontSize: 10 }}
                  tickFormatter={(v) => v.slice(5)}
                />
                <YAxis tick={{ fill: '#9CA3AF', fontSize: 10 }} />
                <Tooltip
                  contentStyle={{ background: '#1F2937', border: 'none', borderRadius: 8 }}
                  labelStyle={{ color: '#E5E7EB' }}
                />
                <Legend
                  formatter={(value) => TYPE_META[value]?.label || value}
                  wrapperStyle={{ fontSize: 11, color: '#9CA3AF' }}
                />
                <Bar dataKey="text_claude" name="text_claude" stackId="a" fill="#6366F1" />
                <Bar dataKey="text_openai" name="text_openai" stackId="a" fill="#10B981" />
                <Bar dataKey="transcription" name="transcription" stackId="a" fill="#F59E0B" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  )
}
