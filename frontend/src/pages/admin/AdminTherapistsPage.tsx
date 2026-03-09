import { useEffect, useRef, useState } from 'react'
import { adminAPI, TherapistRow } from '@/lib/adminApi'

function formatDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('he-IL', {
    day: '2-digit', month: '2-digit', year: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function Toast({ message, type, onClose }: { message: string; type: 'success' | 'error'; onClose: () => void }) {
  useEffect(() => {
    const t = setTimeout(onClose, 4500)
    return () => clearTimeout(t)
  }, [onClose])
  return (
    <div className={`fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-5 py-3 rounded-xl shadow-2xl text-sm font-medium transition-all ${
      type === 'success' ? 'bg-green-800 text-green-100' : 'bg-red-900 text-red-200'
    }`}>
      {type === 'success' ? '✓' : '✕'} {message}
    </div>
  )
}

// ── Delete Confirmation Modal ──────────────────────────────────────────────────
function DeleteModal({
  therapist, onConfirm, onClose, loading,
}: { therapist: TherapistRow; onConfirm: () => void; onClose: () => void; loading: boolean }) {
  const [typed, setTyped] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  useEffect(() => { setTimeout(() => inputRef.current?.focus(), 50) }, [])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4" dir="rtl">
      <div className="bg-gray-900 border border-red-800 rounded-2xl p-6 w-full max-w-md shadow-2xl">
        <div className="flex items-center gap-3 mb-4">
          <span className="text-2xl">🗑️</span>
          <h2 className="text-lg font-bold text-white">מחיקת משתמש</h2>
        </div>
        <p className="text-sm text-gray-300 leading-relaxed mb-3">
          פעולה זו תמחק את המטפל{' '}
          <span className="font-semibold text-white">{therapist.full_name}</span> וכל הנתונים שלו לצמיתות.{' '}
          <span className="text-red-400 font-medium">לא ניתן לבטל פעולה זו.</span>
        </p>
        <p className="text-xs text-gray-400 mb-3">
          הקלד/י את כתובת האימייל לאישור:{' '}
          <span className="text-gray-200 font-mono">{therapist.email}</span>
        </p>
        <input
          ref={inputRef}
          type="text"
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          placeholder={therapist.email}
          className="w-full bg-gray-800 border border-gray-600 text-white rounded-lg px-4 py-2.5 text-sm mb-5 focus:outline-none focus:ring-2 focus:ring-red-500 font-mono"
          dir="ltr"
          onKeyDown={(e) => e.key === 'Enter' && typed === therapist.email && onConfirm()}
        />
        <div className="flex gap-3 justify-end">
          <button
            onClick={onClose}
            disabled={loading}
            className="px-4 py-2 text-sm text-gray-400 hover:text-white border border-gray-700 rounded-lg transition-colors"
          >
            ביטול
          </button>
          <button
            onClick={onConfirm}
            disabled={typed !== therapist.email || loading}
            className="px-4 py-2 text-sm font-semibold bg-red-700 text-white rounded-lg hover:bg-red-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'מוחק...' : 'אישור מחיקה'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Temp Password Modal ───────────────────────────────────────────────────────
function TempPasswordModal({
  therapist, onConfirm, onClose, loading,
}: { therapist: TherapistRow; onConfirm: () => void; onClose: () => void; loading: boolean }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4" dir="rtl">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 w-full max-w-sm shadow-2xl">
        <div className="flex items-center gap-3 mb-4">
          <span className="text-2xl">🔑</span>
          <h2 className="text-base font-bold text-white">שליחת סיסמה זמנית</h2>
        </div>
        <p className="text-sm text-gray-300 leading-relaxed mb-5">
          לשלוח סיסמה זמנית ל-{' '}
          <span className="font-mono text-gray-100 text-xs break-all">{therapist.email}</span>?
          <br />
          <span className="text-xs text-gray-500 mt-1 block">הסיסמה הנוכחית תוחלף מיד.</span>
        </p>
        <div className="flex gap-3 justify-end">
          <button
            onClick={onClose}
            disabled={loading}
            className="px-4 py-2 text-sm text-gray-400 hover:text-white border border-gray-700 rounded-lg transition-colors"
          >
            ביטול
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="px-4 py-2 text-sm font-semibold bg-indigo-600 text-white rounded-lg hover:bg-indigo-500 disabled:opacity-40 transition-colors"
          >
            {loading ? 'שולח...' : 'שלח סיסמה'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function AdminTherapistsPage() {
  const [therapists, setTherapists] = useState<TherapistRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [blocking, setBlocking] = useState<number | null>(null)
  const [search, setSearch] = useState('')

  const [deleteTarget, setDeleteTarget] = useState<TherapistRow | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [tempPwTarget, setTempPwTarget] = useState<TherapistRow | null>(null)
  const [sendingPw, setSendingPw] = useState(false)
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null)

  const showToast = (message: string, type: 'success' | 'error') => setToast({ message, type })

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
      showToast(
        t.is_blocked ? `${t.full_name} שוחרר/ה מהשהיה` : `${t.full_name} הושהה/תה`,
        'success',
      )
    } catch {
      showToast('שגיאה בהשהיית המשתמש', 'error')
    } finally {
      setBlocking(null)
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await adminAPI.deleteTherapist(deleteTarget.id)
      setTherapists((prev) => prev.filter((x) => x.id !== deleteTarget.id))
      showToast(`המטפל ${deleteTarget.full_name} נמחק בהצלחה`, 'success')
      setDeleteTarget(null)
    } catch (e: unknown) {
      showToast(`מחיקה נכשלה: ${e instanceof Error ? e.message : e}`, 'error')
    } finally {
      setDeleting(false)
    }
  }

  async function confirmTempPassword() {
    if (!tempPwTarget) return
    setSendingPw(true)
    try {
      const result = await adminAPI.sendTempPassword(tempPwTarget.id)
      showToast(`סיסמה זמנית נשלחה ל-${result.email_sent_to}`, 'success')
      setTempPwTarget(null)
    } catch (e: unknown) {
      showToast(`שגיאה: ${e instanceof Error ? e.message : e}`, 'error')
    } finally {
      setSendingPw(false)
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
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
      {deleteTarget && (
        <DeleteModal
          therapist={deleteTarget}
          onConfirm={confirmDelete}
          onClose={() => !deleting && setDeleteTarget(null)}
          loading={deleting}
        />
      )}
      {tempPwTarget && (
        <TempPasswordModal
          therapist={tempPwTarget}
          onConfirm={confirmTempPassword}
          onClose={() => !sendingPw && setTempPwTarget(null)}
          loading={sendingPw}
        />
      )}

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

      <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-x-auto">
        <table className="w-full text-sm min-w-[960px]">
          <thead>
            <tr className="border-b border-gray-700 text-gray-400 text-xs">
              <th className="text-right px-4 py-3 font-medium">שם / אימייל</th>
              <th className="text-right px-4 py-3 font-medium">נרשם</th>
              <th className="text-right px-4 py-3 font-medium">כניסה אחרונה</th>
              <th className="text-center px-4 py-3 font-medium">מטופלים פעילים</th>
              <th className="text-center px-4 py-3 font-medium">פגישות</th>
              <th className="text-center px-4 py-3 font-medium">AI</th>
              <th className="text-center px-4 py-3 font-medium">סטטוס</th>
              <th className="text-center px-4 py-3 font-medium">פעולות</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((t) => (
              <tr
                key={t.id}
                className={`border-b border-gray-700/50 hover:bg-white/[0.02] transition-colors ${
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
                <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">{formatDate(t.created_at)}</td>
                <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">{formatDate(t.last_login)}</td>
                <td className="px-4 py-3 text-center">
                  <span className={`text-sm font-medium ${t.active_patients > 0 ? 'text-green-400' : 'text-gray-500'}`}>
                    {t.active_patients}
                  </span>
                </td>
                <td className="px-4 py-3 text-center text-gray-300">{t.session_count}</td>
                <td className="px-4 py-3 text-center text-gray-300">{t.ai_call_count}</td>
                <td className="px-4 py-3 text-center">
                  {t.is_blocked ? (
                    <span className="text-xs bg-red-900/60 text-red-300 px-2 py-0.5 rounded-full">מושהה</span>
                  ) : (
                    <span className="text-xs bg-green-900/60 text-green-300 px-2 py-0.5 rounded-full">פעיל</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {!t.is_admin ? (
                    <div className="flex items-center justify-center gap-1.5 flex-wrap">
                      <button
                        onClick={() => toggleBlock(t)}
                        disabled={blocking === t.id}
                        className={`text-xs px-2.5 py-1 rounded-lg transition-colors disabled:opacity-50 ${
                          t.is_blocked
                            ? 'bg-green-800 text-green-200 hover:bg-green-700'
                            : 'bg-amber-900 text-amber-200 hover:bg-amber-800'
                        }`}
                      >
                        {blocking === t.id ? '...' : t.is_blocked ? 'שחרר' : 'השהה'}
                      </button>
                      <button
                        onClick={() => setTempPwTarget(t)}
                        className="text-xs px-2.5 py-1 rounded-lg bg-gray-700 text-gray-300 hover:bg-gray-600 border border-gray-600 transition-colors"
                      >
                        סיסמה זמנית
                      </button>
                      <button
                        onClick={() => setDeleteTarget(t)}
                        className="text-xs px-2.5 py-1 rounded-lg bg-red-950 text-red-400 hover:bg-red-900 border border-red-800 transition-colors"
                      >
                        מחק
                      </button>
                    </div>
                  ) : (
                    <span className="text-gray-600 text-xs text-center block">—</span>
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
