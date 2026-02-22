/**
 * MessagesCenter — one-way WhatsApp reminder composer + history.
 *
 * Therapist flow:
 *   1. Pick message type (task reminder / session reminder)
 *   2. Set recipient (patient default phone or custom number)
 *   3. API generates AI draft → therapist edits freely
 *   4. Pick send time (now / later today / specific date+time)
 *   5. Confirm → sent immediately or stored as SCHEDULED
 *
 * History shows all messages (DRAFT, SENT, SCHEDULED, CANCELLED, FAILED).
 * SCHEDULED messages can be edited or cancelled.
 *
 * PRD reference: Feature 4 — In-Between Flow v1 (one-way MVP)
 */

import { useState, useEffect, useCallback } from 'react'
import {
  PaperAirplaneIcon,
  ClockIcon,
  ArrowPathIcon,
  XMarkIcon,
  PencilSquareIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  PlusIcon,
} from '@heroicons/react/24/outline'
import { messagesAPI } from '@/lib/api'

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
}

interface MessagesCenterProps {
  patientId: number
  patientName: string
  patientPhone?: string   // Decrypted patient phone (default recipient)
}

type SendWhen = 'now' | 'today' | 'custom'

// --- Helpers ---

const STATUS_LABELS: Record<string, { label: string; className: string }> = {
  draft: { label: 'טיוטה', className: 'badge-draft' },
  scheduled: { label: 'מתוזמן', className: 'bg-blue-100 text-blue-800' },
  sent: { label: 'נשלח', className: 'badge-approved' },
  delivered: { label: 'נמסר', className: 'badge-approved' },
  cancelled: { label: 'בוטל', className: 'bg-gray-100 text-gray-600' },
  failed: { label: 'נכשל', className: 'bg-red-100 text-red-700' },
  rejected: { label: 'נדחה', className: 'bg-gray-100 text-gray-600' },
  approved: { label: 'מאושר', className: 'badge-approved' },
}

const TYPE_LABELS: Record<string, string> = {
  task_reminder: 'תזכורת משימה',
  session_reminder: 'תזכורת לפגישה',
  follow_up: 'מעקב',
  exercise_reminder: 'תזכורת תרגיל',
  check_in: "צ'ק-אין",
  session: 'תזכורת',
}

function formatDatetime(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleString('he-IL', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// --- Component ---

export default function MessagesCenter({
  patientId,
  patientName,
  patientPhone,
}: MessagesCenterProps) {
  // Composer state
  const [composerOpen, setComposerOpen] = useState(false)
  const [messageType, setMessageType] = useState<'task_reminder' | 'session_reminder'>('task_reminder')
  const [useCustomPhone, setUseCustomPhone] = useState(false)
  const [customPhone, setCustomPhone] = useState('')
  const [content, setContent] = useState('')
  const [sendWhen, setSendWhen] = useState<SendWhen>('now')
  const [sendTime, setSendTime] = useState('') // HH:mm for "today"
  const [sendDatetime, setSendDatetime] = useState('') // datetime-local for "custom"

  // Task context (for task_reminder)
  const [taskText, setTaskText] = useState('')
  // Session context (for session_reminder)
  const [sessionDate, setSessionDate] = useState('')
  const [sessionTime, setSessionTime] = useState('')

  // Scheduling sub-panel (shown when therapist clicks "תזמן")
  const [showScheduler, setShowScheduler] = useState(false)

  // Async state
  const [generating, setGenerating] = useState(false)
  const [generatorError, setGeneratorError] = useState('')
  const [draftId, setDraftId] = useState<number | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [confirmError, setConfirmError] = useState('')

  // History state
  const [messages, setMessages] = useState<Message[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)

  // Edit-scheduled inline
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editContent, setEditContent] = useState('')
  const [editSaving, setEditSaving] = useState(false)

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const data = await messagesAPI.getPatientHistory(patientId)
      setMessages(data)
    } catch (err) {
      console.error('Error loading message history:', err)
    } finally {
      setHistoryLoading(false)
    }
  }, [patientId])

  useEffect(() => {
    loadHistory()
  }, [loadHistory])

  const handleGenerate = async () => {
    setGenerating(true)
    setGeneratorError('')
    setContent('')
    setDraftId(null)

    const context: Record<string, string> = {}
    if (messageType === 'task_reminder' && taskText) context.task = taskText
    if (messageType === 'session_reminder') {
      if (sessionDate) context.session_date = sessionDate
      if (sessionTime) context.session_time = sessionTime
    }

    try {
      const draft = await messagesAPI.generateDraft(patientId, messageType, context)
      setContent(draft.content)
      setDraftId(draft.id)
    } catch (err: any) {
      setGeneratorError(err.response?.data?.detail || 'שגיאה בייצור הטיוטה')
    } finally {
      setGenerating(false)
    }
  }

  const buildSendAt = (): string | null => {
    if (sendWhen === 'now') return null
    if (sendWhen === 'today' && sendTime) {
      const d = new Date()
      const [h, m] = sendTime.split(':').map(Number)
      d.setHours(h, m, 0, 0)
      return d.toISOString()
    }
    if (sendWhen === 'custom' && sendDatetime) {
      return new Date(sendDatetime).toISOString()
    }
    return null
  }

  const resetComposer = () => {
    setComposerOpen(false)
    setContent('')
    setDraftId(null)
    setTaskText('')
    setSessionDate('')
    setSessionTime('')
    setSendWhen('now')
    setSendTime('')
    setSendDatetime('')
    setUseCustomPhone(false)
    setCustomPhone('')
    setShowScheduler(false)
  }

  const handleConfirm = async (sendAt: string | null) => {
    if (!draftId || !content.trim()) return
    setConfirming(true)
    setConfirmError('')
    const recipientPhone = useCustomPhone ? customPhone : (patientPhone || undefined)
    try {
      await messagesAPI.sendOrSchedule(draftId, {
        content,
        recipient_phone: recipientPhone,
        send_at: sendAt,
      })
      resetComposer()
      await loadHistory()
    } catch (err: any) {
      setConfirmError(err.response?.data?.detail || 'שגיאה בשליחה')
    } finally {
      setConfirming(false)
    }
  }

  const handleCancel = async (messageId: number) => {
    try {
      await messagesAPI.cancelMessage(messageId)
      await loadHistory()
    } catch (err: any) {
      console.error('Cancel failed:', err)
    }
  }

  const handleSaveEdit = async (messageId: number) => {
    setEditSaving(true)
    try {
      await messagesAPI.editScheduled(messageId, { content: editContent })
      setEditingId(null)
      await loadHistory()
    } catch (err: any) {
      console.error('Edit failed:', err)
    } finally {
      setEditSaving(false)
    }
  }

  const todayInputMin = (() => {
    const now = new Date()
    return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
  })()

  const datetimeLocalMin = new Date().toISOString().slice(0, 16)

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-5">
      {/* Open composer button */}
      {!composerOpen && (
        <button
          onClick={() => setComposerOpen(true)}
          className="btn-primary flex items-center gap-2"
        >
          <PlusIcon className="h-5 w-5" />
          הודעה חדשה
        </button>
      )}

      {/* ── Composer ── */}
      {composerOpen && (
        <div className="card border-blue-200 bg-blue-50 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold text-blue-900">יצירת הודעה חדשה</h3>
            <button
              onClick={resetComposer}
              className="text-gray-400 hover:text-gray-600"
            >
              <XMarkIcon className="h-5 w-5" />
            </button>
          </div>

          {/* Message type selector */}
          <div>
            <p className="text-sm font-medium text-gray-700 mb-2">סוג הודעה</p>
            <div className="flex gap-2">
              {(['task_reminder', 'session_reminder'] as const).map((type) => (
                <button
                  key={type}
                  onClick={() => setMessageType(type)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
                    messageType === type
                      ? 'bg-therapy-calm text-white border-therapy-calm'
                      : 'bg-white text-gray-600 border-gray-300 hover:border-therapy-calm'
                  }`}
                >
                  {type === 'task_reminder' ? 'תזכורת משימה' : 'תזכורת לפגישה'}
                </button>
              ))}
            </div>
          </div>

          {/* Context fields */}
          {messageType === 'task_reminder' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                תיאור המשימה (אופציונלי)
              </label>
              <input
                type="text"
                value={taskText}
                onChange={(e) => setTaskText(e.target.value)}
                className="input-field"
                placeholder="לדוגמה: תרגול נשימה 5 דקות ביום"
              />
            </div>
          )}

          {messageType === 'session_reminder' && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">תאריך הפגישה</label>
                <input
                  type="date"
                  value={sessionDate}
                  onChange={(e) => setSessionDate(e.target.value)}
                  className="input-field"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">שעת הפגישה</label>
                <select
                  value={sessionTime}
                  onChange={(e) => setSessionTime(e.target.value)}
                  className="input-field"
                >
                  <option value="">בחר שעה...</option>
                  {Array.from({ length: 14 }, (_, i) => i + 7).map((hour) =>
                    [0, 30].map((min) => {
                      const val = `${String(hour).padStart(2, '0')}:${String(min).padStart(2, '0')}`
                      return <option key={val} value={val}>{val}</option>
                    })
                  )}
                </select>
              </div>
            </div>
          )}

          {/* Generate button */}
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="btn-secondary flex items-center gap-2 disabled:opacity-50 text-sm"
          >
            {generating ? (
              <>
                <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-therapy-calm"></span>
                מייצר טיוטה...
              </>
            ) : (
              <>
                <ArrowPathIcon className="h-4 w-4" />
                {draftId ? 'ייצר מחדש' : 'ייצר טיוטה'}
              </>
            )}
          </button>

          {generatorError && (
            <div className="text-sm text-red-700 bg-red-50 rounded p-2">{generatorError}</div>
          )}

          {/* Content textarea */}
          {(content || draftId) && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                תוכן ההודעה <span className="text-gray-400 font-normal">(ניתן לערוך)</span>
              </label>
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                rows={4}
                className="input-field resize-none text-sm"
              />
              <p className="text-xs text-gray-400 mt-1">{content.length} תווים</p>
            </div>
          )}

          {/* Recipient */}
          {draftId && (
            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">נמען</p>
              <div className="space-y-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    checked={!useCustomPhone}
                    onChange={() => setUseCustomPhone(false)}
                    className="accent-therapy-calm"
                  />
                  <span className="text-sm text-gray-700">
                    מטופל: {patientName}
                    {patientPhone && <span className="text-gray-400 mr-1"> — {patientPhone}</span>}
                  </span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    checked={useCustomPhone}
                    onChange={() => setUseCustomPhone(true)}
                    className="accent-therapy-calm"
                  />
                  <span className="text-sm text-gray-700">מספר אחר:</span>
                </label>
                {useCustomPhone && (
                  <input
                    type="tel"
                    value={customPhone}
                    onChange={(e) => setCustomPhone(e.target.value)}
                    placeholder="+972501234567"
                    className="input-field mr-6"
                    dir="ltr"
                  />
                )}
              </div>
            </div>
          )}

          {confirmError && (
            <div className="text-sm text-red-700 bg-red-50 rounded p-2">{confirmError}</div>
          )}

          {/* Primary actions: Send now | Schedule */}
          {draftId && (
            <div className="space-y-3">
              {/* First-class action buttons */}
              <div className="flex gap-3">
                <button
                  onClick={() => handleConfirm(null)}
                  disabled={confirming || !content.trim()}
                  className="btn-primary flex items-center gap-2 disabled:opacity-50"
                >
                  {confirming && !showScheduler ? (
                    <>
                      <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></span>
                      שולח...
                    </>
                  ) : (
                    <>
                      <PaperAirplaneIcon className="h-4 w-4" />
                      שלח עכשיו
                    </>
                  )}
                </button>
                <button
                  onClick={() => setShowScheduler((v) => !v)}
                  disabled={confirming}
                  className={`btn-secondary flex items-center gap-2 disabled:opacity-50 ${showScheduler ? 'ring-2 ring-therapy-calm' : ''}`}
                >
                  <ClockIcon className="h-4 w-4" />
                  תזמן לשעה אחרת
                </button>
                <button
                  onClick={resetComposer}
                  className="btn-secondary"
                >
                  ביטול
                </button>
              </div>

              {/* Scheduling panel — shown only when therapist clicks "תזמן" */}
              {showScheduler && (
                <div className="bg-white border border-blue-200 rounded-xl p-4 space-y-3">
                  <p className="text-sm font-medium text-gray-700">בחר מועד שליחה</p>
                  <div className="space-y-2">
                    {([
                      { value: 'today', label: 'היום בשעה' },
                      { value: 'custom', label: 'תאריך ושעה ספציפיים' },
                    ] as const).map(({ value, label }) => (
                      <label key={value} className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="radio"
                          checked={sendWhen === value}
                          onChange={() => setSendWhen(value)}
                          className="accent-therapy-calm"
                        />
                        <span className="text-sm text-gray-700">{label}</span>
                        {value === 'today' && sendWhen === 'today' && (
                          <input
                            type="time"
                            value={sendTime}
                            min={todayInputMin}
                            onChange={(e) => setSendTime(e.target.value)}
                            className="input-field w-28 text-sm"
                          />
                        )}
                        {value === 'custom' && sendWhen === 'custom' && (
                          <input
                            type="datetime-local"
                            value={sendDatetime}
                            min={datetimeLocalMin}
                            onChange={(e) => setSendDatetime(e.target.value)}
                            className="input-field text-sm"
                            dir="ltr"
                          />
                        )}
                      </label>
                    ))}
                  </div>
                  <button
                    onClick={() => handleConfirm(buildSendAt())}
                    disabled={confirming || !content.trim() || (sendWhen === 'today' && !sendTime) || (sendWhen === 'custom' && !sendDatetime)}
                    className="btn-primary flex items-center gap-2 disabled:opacity-50 text-sm"
                  >
                    {confirming && showScheduler ? (
                      <>
                        <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></span>
                        מתזמן...
                      </>
                    ) : (
                      <>
                        <ClockIcon className="h-4 w-4" />
                        אשר תזמון
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── History ── */}
      <div>
        <h3 className="text-base font-bold text-gray-800 mb-3">היסטוריית הודעות</h3>

        {historyLoading ? (
          <div className="flex items-center justify-center h-24">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-therapy-calm"></div>
          </div>
        ) : messages.length === 0 ? (
          <div className="card text-center py-10 text-gray-400">
            <PaperAirplaneIcon className="h-10 w-10 mx-auto mb-2 opacity-30" />
            <p className="text-sm">אין הודעות עדיין</p>
          </div>
        ) : (
          <div className="space-y-3">
            {messages.map((msg) => {
              const statusMeta = STATUS_LABELS[msg.status] || { label: msg.status, className: 'badge-draft' }
              const isScheduled = msg.status === 'scheduled'
              const isEditing = editingId === msg.id

              return (
                <div key={msg.id} className="card space-y-2">
                  {/* Header row */}
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2 text-sm">
                      <span className="font-medium text-gray-700">
                        {TYPE_LABELS[msg.message_type || ''] || msg.message_type || 'הודעה'}
                      </span>
                      {msg.recipient_phone && (
                        <span className="text-gray-400 text-xs" dir="ltr">{msg.recipient_phone}</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`badge text-xs ${statusMeta.className}`}>
                        {statusMeta.label}
                      </span>
                      <span className="text-xs text-gray-400">
                        {msg.sent_at
                          ? formatDatetime(msg.sent_at)
                          : msg.scheduled_send_at
                            ? `📅 ${formatDatetime(msg.scheduled_send_at)}`
                            : formatDatetime(msg.created_at)}
                      </span>
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
                          שמור
                        </button>
                        <button
                          onClick={() => setEditingId(null)}
                          className="btn-secondary text-sm"
                        >
                          ביטול
                        </button>
                      </div>
                    </div>
                  ) : (
                    <p className="text-sm text-gray-700 whitespace-pre-line">{msg.content}</p>
                  )}

                  {/* Scheduled actions */}
                  {isScheduled && !isEditing && (
                    <div className="flex items-center gap-3 pt-1 border-t border-gray-100">
                      <button
                        onClick={() => { setEditingId(msg.id); setEditContent(msg.content) }}
                        className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800"
                      >
                        <PencilSquareIcon className="h-4 w-4" />
                        ערוך
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

                  {/* Failed indicator */}
                  {msg.status === 'failed' && (
                    <div className="flex items-center gap-1 text-xs text-red-600">
                      <ExclamationTriangleIcon className="h-3 w-3" />
                      השליחה נכשלה — נסה שוב
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
