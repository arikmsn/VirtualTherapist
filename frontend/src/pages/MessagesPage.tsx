/**
 * MessagesPage — Message Control Center
 *
 * Monitoring & control dashboard for ALL messages across all patients.
 * Read-only for SENT/FAILED. Edit + Cancel allowed for SCHEDULED.
 * Composition always happens in Patient Profile → "הודעות ותזכורות" tab.
 */

import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ClockIcon,
  PencilSquareIcon,
  XMarkIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon,
  PlusIcon,
} from '@heroicons/react/24/outline'
import { messagesAPI, patientsAPI } from '@/lib/api'

// --- Types ---

interface Message {
  id: number
  patient_id: number
  content: string
  status: string
  message_type: string | null
  created_at: string
  scheduled_send_at: string | null
  channel: string | null
  recipient_phone: string | null
  sent_at: string | null
  requires_approval: boolean
}

interface Patient {
  id: number
  full_name: string
}

// --- Helpers ---

const STATUS_META: Record<string, { label: string; className: string }> = {
  pending_approval: { label: 'ממתין לאישור', className: 'bg-amber-100 text-amber-800' },
  approved: { label: 'מאושר', className: 'bg-blue-100 text-blue-800' },
  scheduled: { label: 'מתוזמן', className: 'bg-indigo-100 text-indigo-800' },
  sent: { label: 'נשלח', className: 'bg-green-100 text-green-800' },
  delivered: { label: 'נמסר', className: 'bg-green-100 text-green-800' },
  cancelled: { label: 'בוטל', className: 'bg-gray-100 text-gray-500' },
  failed: { label: 'נכשל', className: 'bg-red-100 text-red-700' },
  rejected: { label: 'נדחה', className: 'bg-gray-100 text-gray-500' },
}

const TYPE_LABELS: Record<string, string> = {
  task_reminder: 'תזכורת משימה',
  session_reminder: 'תזכורת לפגישה',
  follow_up: 'מעקב',
  exercise_reminder: 'תזכורת תרגיל',
  check_in: "צ'ק-אין",
}

// Parse ISO timestamp as UTC even when the backend omits the 'Z' suffix
function parseUTC(iso: string): Date {
  if (!iso.endsWith('Z') && !/[+-]\d{2}:?\d{2}$/.test(iso)) {
    return new Date(iso + 'Z')
  }
  return new Date(iso)
}

function formatDt(iso: string | null): string {
  if (!iso) return '—'
  return parseUTC(iso).toLocaleString('he-IL', {
    day: '2-digit',
    month: '2-digit',
    year: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// --- Component ---

export default function MessagesPage() {
  const navigate = useNavigate()

  const [messages, setMessages] = useState<Message[]>([])
  const [patients, setPatients] = useState<Patient[]>([])
  const [loading, setLoading] = useState(true)
  const [showPatientPicker, setShowPatientPicker] = useState(false)

  // Filters
  const [filterPatient, setFilterPatient] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [filterDateFrom, setFilterDateFrom] = useState('')
  const [filterDateTo, setFilterDateTo] = useState('')

  // Inline edit for SCHEDULED
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editContent, setEditContent] = useState('')
  const [editSaving, setEditSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (filterPatient) params.patient_id = filterPatient
      if (filterStatus) params.status = filterStatus
      if (filterDateFrom) params.date_from = new Date(filterDateFrom).toISOString()
      if (filterDateTo) params.date_to = new Date(filterDateTo + 'T23:59:59').toISOString()

      const [msgs, pts] = await Promise.all([
        messagesAPI.getAll(params as any),
        patientsAPI.list(),
      ])
      setMessages(msgs)
      setPatients(pts)
    } catch (err) {
      console.error('Error loading messages:', err)
    } finally {
      setLoading(false)
    }
  }, [filterPatient, filterStatus, filterDateFrom, filterDateTo])

  useEffect(() => { load() }, [load])

  const patientName = (id: number) =>
    patients.find((p) => p.id === id)?.full_name || `מטופל #${id}`

  const handleCancel = async (messageId: number) => {
    try {
      await messagesAPI.cancelMessage(messageId)
      await load()
    } catch (err) {
      console.error('Cancel failed:', err)
    }
  }

  const handleSaveEdit = async (messageId: number) => {
    setEditSaving(true)
    try {
      await messagesAPI.editScheduled(messageId, { content: editContent })
      setEditingId(null)
      await load()
    } catch (err) {
      console.error('Edit failed:', err)
    } finally {
      setEditSaving(false)
    }
  }

  const sortedPatients = [...patients].sort((a, b) =>
    a.full_name.localeCompare(b.full_name, 'he')
  )

  const FILTER_STATUSES = ['scheduled', 'sent', 'failed', 'cancelled']

  return (
    <div className="space-y-6 animate-fade-in" dir="rtl">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">מרכז הודעות</h1>
          <p className="text-gray-600 mt-1 text-sm">
            ניטור וניהול כל ההודעות לכל המטופלים.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowPatientPicker(true)}
            className="btn-primary flex items-center gap-2 text-sm min-h-[40px] touch-manipulation"
          >
            <PlusIcon className="h-4 w-4" />
            הודעה חדשה
          </button>
          <button
            onClick={load}
            className="btn-secondary flex items-center gap-2 text-sm"
          >
            <ArrowPathIcon className="h-4 w-4" />
            רענן
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">מטופל</label>
            <select
              className="input-field text-sm"
              value={filterPatient}
              onChange={(e) => setFilterPatient(e.target.value)}
            >
              <option value="">כולם</option>
              {sortedPatients.map((p) => (
                <option key={p.id} value={p.id}>{p.full_name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">סטטוס</label>
            <select
              className="input-field text-sm"
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
            >
              <option value="">הכל</option>
              {FILTER_STATUSES.map((s) => (
                <option key={s} value={s}>{STATUS_META[s].label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">מתאריך</label>
            <input type="date" className="input-field text-sm" value={filterDateFrom}
              onChange={(e) => setFilterDateFrom(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">עד תאריך</label>
            <input type="date" className="input-field text-sm" value={filterDateTo}
              onChange={(e) => setFilterDateTo(e.target.value)} />
          </div>
        </div>
        {(filterPatient || filterStatus || filterDateFrom || filterDateTo) && (
          <button
            onClick={() => { setFilterPatient(''); setFilterStatus(''); setFilterDateFrom(''); setFilterDateTo('') }}
            className="mt-2 text-xs text-gray-500 hover:text-red-600 underline"
          >
            נקה סינון
          </button>
        )}
      </div>

      <div className="text-sm text-gray-500">
        {loading ? 'טוען...' : `${messages.filter((m) => m.status !== 'draft').length} הודעות`}
      </div>

      {/* List */}
      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-therapy-calm"></div>
        </div>
      ) : messages.filter((m) => m.status !== 'draft').length === 0 ? (
        <div className="card text-center py-12 text-gray-400">
          <p className="text-lg">אין הודעות תואמות</p>
          <p className="text-sm mt-1">שנה את הסינון או צור הודעות חדשות דרך פרופיל המטופל</p>
        </div>
      ) : (
        <div className="space-y-3">
          {messages.filter((m) => m.status !== 'draft').map((msg) => {
            const sm = STATUS_META[msg.status] || { label: msg.status, className: 'bg-gray-100 text-gray-600' }
            const isScheduled = msg.status === 'scheduled'
            const isEditing = editingId === msg.id

            return (
              <div key={msg.id} className="card space-y-3">
                {/* Header row */}
                <div className="flex items-start justify-between flex-wrap gap-2">
                  <div className="space-y-0.5">
                    <button
                      onClick={() => navigate(`/patients/${msg.patient_id}`, { state: { initialTab: 'inbetween' } })}
                      className="font-semibold text-therapy-calm hover:underline text-sm"
                    >
                      {patientName(msg.patient_id)}
                    </button>
                    <div className="flex items-center gap-2 text-xs text-gray-500 flex-wrap">
                      <span>{TYPE_LABELS[msg.message_type || ''] || msg.message_type || 'הודעה'}</span>
                      {msg.channel && <span className="uppercase">{msg.channel}</span>}
                      {msg.recipient_phone && (
                        <span dir="ltr" className="font-mono">{msg.recipient_phone}</span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-3 flex-wrap">
                    <span className={`badge text-xs ${sm.className}`}>{sm.label}</span>
                    <div className="text-xs text-gray-400 text-left">
                      {isScheduled && msg.scheduled_send_at ? (
                        <div className="flex items-center gap-1">
                          <ClockIcon className="h-3 w-3" />
                          {formatDt(msg.scheduled_send_at)}
                        </div>
                      ) : msg.sent_at ? (
                        <span>נשלח: {formatDt(msg.sent_at)}</span>
                      ) : (
                        <span>נוצר: {formatDt(msg.created_at)}</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Content */}
                {isEditing ? (
                  <div className="space-y-2">
                    <textarea
                      value={editContent}
                      onChange={(e) => setEditContent(e.target.value)}
                      rows={3}
                      className="input-field resize-none text-sm w-full"
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleSaveEdit(msg.id)}
                        disabled={editSaving}
                        className="btn-primary text-sm flex items-center gap-1 disabled:opacity-50"
                      >
                        <CheckCircleIcon className="h-4 w-4" />
                        {editSaving ? 'שומר...' : 'שמור'}
                      </button>
                      <button onClick={() => setEditingId(null)} className="btn-secondary text-sm">ביטול</button>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-gray-700 whitespace-pre-line leading-relaxed">{msg.content}</p>
                )}

                {/* SCHEDULED controls */}
                {isScheduled && !isEditing && (
                  <div className="flex items-center gap-4 pt-1 border-t border-gray-100">
                    <button
                      onClick={() => { setEditingId(msg.id); setEditContent(msg.content) }}
                      className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800"
                    >
                      <PencilSquareIcon className="h-4 w-4" />
                      ערוך תוכן
                    </button>
                    <button
                      onClick={() => handleCancel(msg.id)}
                      className="flex items-center gap-1 text-sm text-red-500 hover:text-red-700"
                    >
                      <XMarkIcon className="h-4 w-4" />
                      בטל תזמון
                    </button>
                  </div>
                )}

                {msg.status === 'failed' && (
                  <div className="flex items-center gap-1 text-xs text-red-600">
                    <ExclamationTriangleIcon className="h-3 w-3" />
                    שליחה נכשלה — פנה לתמיכה
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
      {/* Patient Picker Modal */}
      {showPatientPicker && (
        <div className="fixed inset-0 bg-black/50 flex items-start sm:items-center justify-center z-50 p-4 pt-8 sm:pt-4" dir="rtl">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md flex flex-col max-h-[calc(100vh-6rem)] sm:max-h-[85vh] animate-fade-in">
            <div className="px-5 sm:px-8 py-4 sm:py-6 border-b border-gray-100 flex-shrink-0">
              <h2 className="text-xl sm:text-2xl font-bold">הודעה חדשה — בחר מטופל</h2>
              <p className="text-sm text-gray-500 mt-1">בחר מטופל כדי לפתוח את מרכז ההודעות שלו</p>
            </div>
            <div className="overflow-y-auto flex-1 px-5 sm:px-8 py-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">מטופל/ת</label>
              <select
                className="input-field"
                defaultValue=""
                onChange={(e) => {
                  if (e.target.value) {
                    setShowPatientPicker(false)
                    navigate(`/patients/${e.target.value}`, { state: { initialTab: 'inbetween' } })
                  }
                }}
              >
                <option value="">-- בחר מטופל --</option>
                {sortedPatients.map((p) => (
                  <option key={p.id} value={p.id}>{p.full_name}</option>
                ))}
              </select>
            </div>
            <div className="px-5 sm:px-8 py-4 border-t border-gray-100 flex-shrink-0">
              <button
                onClick={() => setShowPatientPicker(false)}
                className="btn-secondary w-full min-h-[44px] touch-manipulation"
              >
                ביטול
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
