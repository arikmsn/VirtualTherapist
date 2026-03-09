import { useEffect, useState } from 'react'
import { adminAPI, TherapistRow } from '@/lib/adminApi'

function formatDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('he-IL', {
    day: '2-digit', month: '2-digit', year: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function AdminTherapistsPage() {
  const [therapists, setTherapists] = useState<TherapistRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [blocking, setBlocking] = useState<number | null>(null)
  const [search, setSearch] = useState('')

  useEffect(() => {
    adminAPI
      .getTherapists()
      .then(setTherapists)
      .catch((e) => setError(`שגיאה בטעינת מטפלים (${e.message})`))
      .finally(() => setLoading(false))
  }, [])

  async function toggleBlock(t: TherapistRow) {
    setBlocking(t.id)
    try {
      const updated = await adminAPI.blockTherapist(t.id, !t.is_blocked)
      setTherapists((prev) => prev.map((x) => (x.id === updated.id ? updated : x)))
    } catch {
      alert('שגיאה')
    } finally {
      setBlocking(null)
    }
  }

  const filtered = therapists.filter(
    (t) =>
      t.full_name.toLowerCase().includes(search.toLowerCase()) ||
      t.email.toLowerCase().includes(search.toLowerCase()),
  )

  if (loading) {
    return (
      <div className="p-8">
        <div className="h-8 bg-gray-800 rounded w-32 mb-6 animate-pulse" />
        <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-14 border-b border-gray-700 animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-white mb-1">מטפלים</h1>
      <p className="text-sm text-gray-400 mb-6">{therapists.length} חשבונות רשומים</p>

      <input
        type="text"
        placeholder="חיפוש לפי שם או אימייל..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="mb-6 w-full max-w-sm bg-gray-800 border border-gray-700 text-white placeholder-gray-500 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        dir="rtl"
      />

      {error && <p className="text-red-400 mb-4 text-sm">{error}</p>}

      <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-700 text-gray-400 text-xs">
              <th className="text-right px-4 py-3 font-medium">שם / אימייל</th>
              <th className="text-right px-4 py-3 font-medium">נרשם</th>
              <th className="text-right px-4 py-3 font-medium">כניסה אחרונה</th>
              <th className="text-center px-4 py-3 font-medium">מטופלים פעילים</th>
              <th className="text-center px-4 py-3 font-medium">פגישות</th>
              <th className="text-center px-4 py-3 font-medium">AI</th>
              <th className="text-center px-4 py-3 font-medium">סטטוס</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((t) => (
              <tr
                key={t.id}
                className={`border-b border-gray-700/50 hover:bg-gray-750 transition-colors ${
                  t.is_blocked ? 'opacity-60' : ''
                }`}
              >
                <td className="px-4 py-3">
                  <p className="text-white font-medium">{t.full_name}</p>
                  <p className="text-gray-400 text-xs">{t.email}</p>
                  {t.is_admin && (
                    <span className="text-xs bg-indigo-900 text-indigo-300 px-1.5 py-0.5 rounded mt-0.5 inline-block">
                      אדמין
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
                  {formatDate(t.created_at)}
                </td>
                <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
                  {formatDate(t.last_login)}
                </td>
                <td className="px-4 py-3 text-center">
                  <span className={`text-sm font-medium ${t.active_patients > 0 ? 'text-green-400' : 'text-gray-500'}`}>
                    {t.active_patients}
                  </span>
                </td>
                <td className="px-4 py-3 text-center text-gray-300">{t.session_count}</td>
                <td className="px-4 py-3 text-center text-gray-300">{t.ai_call_count}</td>
                <td className="px-4 py-3 text-center">
                  {t.is_blocked ? (
                    <span className="text-xs bg-red-900/60 text-red-300 px-2 py-0.5 rounded-full">
                      מושהה
                    </span>
                  ) : (
                    <span className="text-xs bg-green-900/60 text-green-300 px-2 py-0.5 rounded-full">
                      פעיל
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-center">
                  {!t.is_admin && (
                    <button
                      onClick={() => toggleBlock(t)}
                      disabled={blocking === t.id}
                      className={`text-xs px-3 py-1 rounded-lg transition-colors disabled:opacity-50 ${
                        t.is_blocked
                          ? 'bg-green-800 text-green-200 hover:bg-green-700'
                          : 'bg-red-900 text-red-200 hover:bg-red-800'
                      }`}
                    >
                      {blocking === t.id ? '...' : t.is_blocked ? 'שחרר' : 'השהה'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <p className="text-center text-gray-500 py-8 text-sm">לא נמצאו תוצאות</p>
        )}
      </div>
    </div>
  )
}
