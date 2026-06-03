import { useEffect, useState } from 'react'
import { adminAPI, FeedbackRow } from '@/lib/adminApi'

const TYPE_META: Record<string, { label: string; color: string }> = {
  bug:     { label: 'תקלה',    color: 'bg-red-900/50 text-red-300' },
  contact: { label: 'יצירת קשר', color: 'bg-blue-900/50 text-blue-300' },
}

const STATUS_META: Record<string, { label: string; color: string }> = {
  new:      { label: 'חדש',     color: 'bg-indigo-800 text-indigo-200' },
  read:     { label: 'נקרא',    color: 'bg-slate-700 text-slate-300' },
  resolved: { label: 'טופל',    color: 'bg-green-900 text-green-300' },
}

const EMAIL_META: Record<string, { icon: string; color: string }> = {
  pending: { icon: '⏳', color: 'text-gray-400' },
  sent:    { icon: '✅', color: 'text-green-400' },
  failed:  { icon: '❌', color: 'text-red-400' },
  skipped: { icon: '⏭️', color: 'text-gray-500' },
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('he-IL', {
    day: '2-digit', month: '2-digit', year: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function AdminFeedbackPage() {
  const [rows, setRows] = useState<FeedbackRow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const [typeFilter, setTypeFilter] = useState<'all' | 'bug' | 'contact'>('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'new' | 'read' | 'resolved'>('all')

  async function load() {
    setLoading(true)
    setError('')
    try {
      setRows(await adminAPI.getFeedback())
    } catch (e: unknown) {
      setError(`שגיאה בטעינת ההודעות (${e instanceof Error ? e.message : e})`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function setStatus(id: number, status: string) {
    try {
      const updated = await adminAPI.setFeedbackStatus(id, status)
      setRows((prev) => prev.map((r) => (r.id === id ? updated : r)))
    } catch {
      // non-critical, ignore
    }
  }

  function toggle(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const filtered = rows.filter((r) => {
    if (typeFilter !== 'all' && r.type !== typeFilter) return false
    if (statusFilter !== 'all' && r.status !== statusFilter) return false
    return true
  })

  const newCount = rows.filter((r) => r.status === 'new').length

  return (
    <div className="p-6 md:p-8" dir="rtl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            📩 תיבת פניות
            {newCount > 0 && (
              <span className="text-sm font-normal bg-indigo-600 text-white rounded-full px-2 py-0.5">
                {newCount} חדש{newCount !== 1 ? 'ות' : ''}
              </span>
            )}
          </h1>
          <p className="text-gray-400 text-sm mt-1">כל הפניות שנשלחו מהאפליקציה — שמורות במסד הנתונים</p>
        </div>
        <button
          onClick={load}
          className="text-sm text-gray-400 hover:text-white px-3 py-1.5 border border-gray-700 rounded-lg hover:border-gray-500 transition-colors"
        >
          רענון
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 mb-4">
        {(['all', 'bug', 'contact'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTypeFilter(t)}
            className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
              typeFilter === t
                ? 'bg-indigo-600 border-indigo-500 text-white'
                : 'border-gray-700 text-gray-400 hover:border-gray-500 hover:text-white'
            }`}
          >
            {t === 'all' ? 'הכל' : t === 'bug' ? 'תקלות' : 'יצירת קשר'}
          </button>
        ))}
        <span className="text-gray-600 self-center">|</span>
        {(['all', 'new', 'read', 'resolved'] as const).map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
              statusFilter === s
                ? 'bg-indigo-600 border-indigo-500 text-white'
                : 'border-gray-700 text-gray-400 hover:border-gray-500 hover:text-white'
            }`}
          >
            {s === 'all' ? 'כל הסטטוסים' : STATUS_META[s]?.label ?? s}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading && (
        <div className="text-gray-400 py-8 text-center">טוען...</div>
      )}
      {error && (
        <div className="bg-red-900/40 border border-red-700 text-red-300 rounded-lg p-4 mb-4">{error}</div>
      )}
      {!loading && !error && filtered.length === 0 && (
        <div className="text-gray-500 py-12 text-center">אין פניות להציג</div>
      )}

      <div className="space-y-2">
        {filtered.map((row) => {
          const isOpen = expanded.has(row.id)
          const typeMeta = TYPE_META[row.type] ?? { label: row.type, color: 'bg-gray-700 text-gray-300' }
          const statusMeta = STATUS_META[row.status] ?? { label: row.status, color: 'bg-gray-700 text-gray-300' }
          const emailMeta = EMAIL_META[row.email_delivery_status] ?? { icon: '?', color: 'text-gray-400' }

          return (
            <div
              key={row.id}
              className="bg-gray-800/60 border border-gray-700 rounded-xl overflow-hidden"
            >
              {/* Row header — always visible */}
              <button
                onClick={() => { toggle(row.id); if (row.status === 'new') setStatus(row.id, 'read') }}
                className="w-full text-right px-4 py-3 flex items-start gap-3 hover:bg-gray-700/40 transition-colors"
              >
                {/* Type badge */}
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium mt-0.5 flex-shrink-0 ${typeMeta.color}`}>
                  {typeMeta.label}
                </span>

                {/* Main info */}
                <div className="flex-1 min-w-0 text-right">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium text-white text-sm truncate">{row.therapist_name}</span>
                    <span className="text-gray-400 text-xs">{row.therapist_email}</span>
                    {row.subject && (
                      <span className="text-gray-300 text-xs truncate">— {row.subject}</span>
                    )}
                  </div>
                  <div className="text-gray-400 text-xs mt-0.5 truncate">
                    {row.message.substring(0, 100)}{row.message.length > 100 ? '…' : ''}
                  </div>
                </div>

                {/* Right-side meta */}
                <div className="flex flex-col items-end gap-1 flex-shrink-0">
                  <span className="text-gray-500 text-xs">{formatDate(row.created_at)}</span>
                  <div className="flex items-center gap-1.5">
                    <span className={`text-xs ${emailMeta.color}`} title={`email: ${row.email_delivery_status}${row.email_delivery_error ? ` — ${row.email_delivery_error}` : ''}`}>
                      {emailMeta.icon}
                    </span>
                    <span className={`text-xs px-1.5 py-0.5 rounded ${statusMeta.color}`}>
                      {statusMeta.label}
                    </span>
                  </div>
                </div>
              </button>

              {/* Expanded body */}
              {isOpen && (
                <div className="px-4 pb-4 border-t border-gray-700/50">
                  <div className="pt-3 space-y-3">
                    {/* Full message */}
                    <pre className="text-sm text-gray-200 whitespace-pre-wrap leading-relaxed bg-gray-900/50 rounded-lg p-3 font-sans">
                      {row.message}
                    </pre>

                    {/* Email error details if any */}
                    {row.email_delivery_error && (
                      <div className="text-xs text-red-400 bg-red-950/40 rounded-lg p-2">
                        שגיאת אימייל: {row.email_delivery_error}
                      </div>
                    )}

                    {/* Status actions */}
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs text-gray-500">עדכן סטטוס:</span>
                      {(['new', 'read', 'resolved'] as const).map((s) => (
                        <button
                          key={s}
                          onClick={() => setStatus(row.id, s)}
                          disabled={row.status === s}
                          className={`text-xs px-2 py-1 rounded border transition-colors disabled:opacity-40 ${
                            row.status === s
                              ? 'border-gray-600 text-gray-400'
                              : 'border-gray-600 text-gray-300 hover:border-indigo-500 hover:text-white'
                          }`}
                        >
                          {STATUS_META[s].label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
