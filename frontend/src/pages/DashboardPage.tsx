import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  DocumentTextIcon,
  PaperAirplaneIcon,
  BellAlertIcon,
  CheckCircleIcon,
  ClockIcon,
  ChevronRightIcon,
  ChevronLeftIcon,
  CalendarDaysIcon,
} from '@heroicons/react/24/outline'
import { patientsAPI, sessionsAPI, messagesAPI } from '@/lib/api'
import { useAuth } from '@/auth/useAuth'

interface Patient {
  id: number
  full_name: string
  status: string
}

interface DailySession {
  id: number
  patient_id: number
  patient_name: string
  session_date: string
  start_time: string | null
  end_time: string | null
  session_type: string
  session_number: number
  has_summary: boolean
}

const SESSION_TYPE_LABELS: Record<string, string> = {
  individual: 'פרטני',
  couples: 'זוגי',
  family: 'משפחתי',
  group: 'קבוצתי',
  intake: 'אינטייק',
  follow_up: 'מעקב',
}

/** Format a Date to YYYY-MM-DD using local timezone (never UTC). */
function toLocalISO(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function todayISO(): string {
  return toLocalISO(new Date())
}

function formatDateHebrew(dateStr: string): string {
  const d = new Date(dateStr + 'T12:00:00')
  return d.toLocaleDateString('he-IL', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

function formatTime(isoStr: string | null): string {
  if (!isoStr) return ''
  const d = new Date(isoStr)
  if (isNaN(d.getTime())) return ''
  const h = String(d.getHours()).padStart(2, '0')
  const m = String(d.getMinutes()).padStart(2, '0')
  return `${h}:${m}`
}

function shiftDate(dateStr: string, days: number): string {
  const d = new Date(dateStr + 'T12:00:00')
  d.setDate(d.getDate() + days)
  return toLocalISO(d)
}

interface SimpleSession {
  id: number
  patient_id: number
  session_date: string
  session_number?: number
  summary_id?: number
}

function getGreeting(name: string | null): string {
  const hour = new Date().getHours()
  const firstName = name?.split(' ')[0] || ''
  const suffix = firstName ? `, ${firstName}` : ''
  if (hour >= 5 && hour < 12) return `בוקר טוב${suffix}`
  if (hour >= 12 && hour < 18) return `צהריים טובים${suffix}`
  return `ערב טוב${suffix}`
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [showMessagePickerModal, setShowMessagePickerModal] = useState(false)
  const [showSummaryModal, setShowSummaryModal] = useState(false)
  const [allSessions, setAllSessions] = useState<SimpleSession[]>([])

  const [stats, setStats] = useState({
    pendingMessages: 0,
    todaySessions: 0,
    activePatients: 0,
    completedSummaries: 0,
  })
  const [patients, setPatients] = useState<Patient[]>([])
  const [loading, setLoading] = useState(true)

  // Lock body scroll whenever a modal is open
  useEffect(() => {
    const locked = showSummaryModal || showMessagePickerModal
    document.body.style.overflow = locked ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [showSummaryModal, showMessagePickerModal])

  // Daily view state
  const [selectedDate, setSelectedDate] = useState<string>(todayISO())
  const [dailySessions, setDailySessions] = useState<DailySession[]>([])
  const [dailyLoading, setDailyLoading] = useState(true)

  // Load global stats
  useEffect(() => {
    const loadStats = async () => {
      try {
        const [patientsData, sessionsData, messagesData] = await Promise.all([
          patientsAPI.list(),
          sessionsAPI.list(),
          messagesAPI.getPending().catch(() => []),
        ])
        setPatients(patientsData)
        setAllSessions(sessionsData)
        const today = todayISO()
        setStats({
          pendingMessages: messagesData.length,
          todaySessions: sessionsData.filter(
            (s: any) => s.session_date === today
          ).length,
          activePatients: patientsData.filter(
            (p: any) => p.status === 'active'
          ).length,
          completedSummaries: sessionsData.filter(
            (s: any) => s.summary_id != null
          ).length,
        })
      } catch (error) {
        console.error('Error loading dashboard stats:', error)
      } finally {
        setLoading(false)
      }
    }
    loadStats()
  }, [])

  // Load daily sessions when date changes
  const loadDailySessions = useCallback(async (dateStr: string) => {
    setDailyLoading(true)
    try {
      const data = await sessionsAPI.listByDate(dateStr)
      setDailySessions(data)
    } catch (error) {
      console.error('Error loading daily sessions:', error)
      setDailySessions([])
    } finally {
      setDailyLoading(false)
    }
  }, [])

  useEffect(() => {
    loadDailySessions(selectedDate)
  }, [selectedDate, loadDailySessions])

  const isToday = selectedDate === todayISO()

  return (
    <div className="space-y-5 sm:space-y-8 animate-fade-in">
      {/* Welcome Header */}
      <div className="card bg-gradient-to-l from-therapy-calm to-therapy-gentle text-white">
        <h1 className="text-2xl sm:text-3xl font-bold mb-1 sm:mb-2">
          {getGreeting(user?.fullName || null)} 👋
        </h1>
        <p className="text-indigo-100 text-base sm:text-lg">
          ניהול מטופלים, סיכומים והודעות במקום אחד
        </p>
      </div>

      {/* ===== DAILY VIEW SECTION ===== */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <CalendarDaysIcon className="h-6 w-6 text-therapy-calm" />
            {isToday ? 'המפגשים של היום' : `מפגשים – ${formatDateHebrew(selectedDate)}`}
          </h2>
          <span className="text-sm text-gray-500">
            {dailySessions.length} מפגשים
          </span>
        </div>

        {/* Date Navigation */}
        <div className="flex items-center gap-3 mb-4 flex-wrap">
          <button
            onClick={() => setSelectedDate(shiftDate(selectedDate, -1))}
            className="btn-secondary text-sm px-3 py-1.5 flex items-center gap-1"
          >
            <ChevronRightIcon className="h-4 w-4" />
            יום קודם
          </button>
          <button
            onClick={() => setSelectedDate(shiftDate(selectedDate, 1))}
            className="btn-secondary text-sm px-3 py-1.5 flex items-center gap-1"
          >
            יום הבא
            <ChevronLeftIcon className="h-4 w-4" />
          </button>
          {!isToday && (
            <button
              onClick={() => setSelectedDate(todayISO())}
              className="text-sm px-3 py-1.5 bg-therapy-calm text-white rounded-lg hover:bg-therapy-calm/90 transition-colors"
            >
              היום
            </button>
          )}
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => e.target.value && setSelectedDate(e.target.value)}
            className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-therapy-calm/30 focus:border-therapy-calm"
          />
        </div>

        {/* Session List */}
        {dailyLoading ? (
          <div className="flex justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-therapy-calm"></div>
          </div>
        ) : dailySessions.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <CalendarDaysIcon className="h-12 w-12 mx-auto mb-2 text-gray-300" />
            <p>אין מפגשים בתאריך זה</p>
          </div>
        ) : (
          <div className="space-y-2">
            {dailySessions.map((session) => (
              <div
                key={session.id}
                className="flex flex-col sm:flex-row sm:items-center sm:justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors gap-2 sm:gap-0"
              >
                <div className="flex items-center gap-3 sm:gap-4">
                  {/* Time */}
                  <div className="text-base sm:text-lg font-mono font-semibold text-therapy-calm min-w-[52px] sm:min-w-[60px]">
                    {formatTime(session.start_time) || '—'}
                  </div>

                  {/* Patient name + session info */}
                  <div>
                    <div className="font-medium text-gray-900">{session.patient_name}</div>
                    <div className="text-xs text-gray-500">
                      {session.session_number ? `פגישה #${session.session_number}` : ''}
                      {session.session_number && session.session_type ? ' · ' : ''}
                      {SESSION_TYPE_LABELS[session.session_type] || session.session_type || ''}
                    </div>
                  </div>

                  {/* Summary badge — hidden on mobile to save space */}
                  <span className="hidden sm:inline text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                    {session.has_summary ? 'יש סיכום' : ''}
                  </span>
                  {!session.has_summary && (
                    <span className="hidden sm:inline text-xs bg-gray-200 text-gray-600 px-2 py-0.5 rounded-full">
                      ללא סיכום
                    </span>
                  )}
                </div>

                {/* Action buttons — full-width side-by-side on mobile */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => navigate(`/sessions/${session.id}`)}
                    className="flex-1 sm:flex-none text-sm px-3 py-2 sm:py-1 bg-therapy-calm text-white rounded-lg hover:bg-therapy-calm/90 transition-colors min-h-[40px] sm:min-h-0 touch-manipulation"
                  >
                    פתח סשן
                  </button>
                  <button
                    onClick={() => navigate(`/sessions/${session.id}?prep=1`)}
                    className="flex-1 sm:flex-none text-sm px-3 py-2 sm:py-1 bg-amber-100 text-amber-800 rounded-lg hover:bg-amber-200 transition-colors min-h-[40px] sm:min-h-0 touch-manipulation"
                  >
                    הכנה לפגישה
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* QUICK ACTIONS — navigate to the right place, no floating editors */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Action 1: Write Summary — opens patient+session picker */}
        <button
          onClick={() => setShowSummaryModal(true)}
          className="card group hover:shadow-2xl transition-all duration-300 hover:scale-105 cursor-pointer text-right"
        >
          <div className="flex flex-col items-start gap-4">
            <div className="w-16 h-16 bg-therapy-calm/10 rounded-full flex items-center justify-center group-hover:bg-therapy-calm group-hover:text-white transition-colors duration-300">
              <DocumentTextIcon className="h-8 w-8 text-therapy-calm group-hover:text-white" />
            </div>
            <div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">📝 סיכום פגישות מטופלים באמצעות AI</h3>
              <p className="text-gray-600 text-sm">
                בחר מטופל ופגישה וכתוב סיכום AI מובנה
              </p>
            </div>
            <div className="mt-auto w-full">
              <div className="text-sm text-therapy-calm font-medium">לחץ לבחירת פגישה →</div>
            </div>
          </div>
        </button>

        {/* Action 2: Send to Patient */}
        <button
          onClick={() => setShowMessagePickerModal(true)}
          className="card group hover:shadow-2xl transition-all duration-300 hover:scale-105 cursor-pointer text-right"
        >
          <div className="flex flex-col items-start gap-4">
            <div className="w-16 h-16 bg-therapy-support/10 rounded-full flex items-center justify-center group-hover:bg-therapy-support group-hover:text-white transition-colors duration-300">
              <PaperAirplaneIcon className="h-8 w-8 text-therapy-support group-hover:text-white" />
            </div>
            <div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">💬 שליחת הודעות</h3>
              <p className="text-gray-600 text-sm">
                צור הודעת מעקב אישית למטופל. המערכת תכתוב בסגנון שלך, אתה תאשר
              </p>
            </div>
            <div className="mt-auto w-full">
              {stats.pendingMessages > 0 && (
                <div className="mb-2 badge badge-pending">
                  {stats.pendingMessages} הודעות ממתינות לאישור
                </div>
              )}
              <div className="text-sm text-therapy-support font-medium">לחץ ליצירת הודעה →</div>
            </div>
          </div>
        </button>

        {/* Action 3: Go to Messages Center */}
        <button
          onClick={() => navigate('/messages')}
          className="card group hover:shadow-2xl transition-all duration-300 hover:scale-105 cursor-pointer text-right"
        >
          <div className="flex flex-col items-start gap-4">
            <div className="w-16 h-16 bg-therapy-warm/10 rounded-full flex items-center justify-center group-hover:bg-therapy-warm group-hover:text-white transition-colors duration-300">
              <BellAlertIcon className="h-8 w-8 text-therapy-warm group-hover:text-white" />
            </div>
            <div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">📨 מרכז הודעות</h3>
              <p className="text-gray-600 text-sm">
                צפה בכל ההודעות שנשלחו למטופלים, ערוך הודעות מתוזמנות וצפה בסטטוס
              </p>
            </div>
            <div className="mt-auto w-full">
              <div className="text-sm text-therapy-warm font-medium">עבור למרכז הודעות →</div>
            </div>
          </div>
        </button>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card bg-blue-50 border border-blue-200">
          <div className="flex items-center gap-3">
            <ClockIcon className="h-8 w-8 text-blue-600" />
            <div>
              <div className="text-2xl font-bold text-blue-900">{stats.pendingMessages}</div>
              <div className="text-sm text-blue-700">הודעות ממתינות</div>
            </div>
          </div>
        </div>

        <div className="card bg-green-50 border border-green-200">
          <div className="flex items-center gap-3">
            <CheckCircleIcon className="h-8 w-8 text-green-600" />
            <div>
              <div className="text-2xl font-bold text-green-900">{stats.todaySessions}</div>
              <div className="text-sm text-green-700">פגישות היום</div>
            </div>
          </div>
        </div>

        <div className="card bg-purple-50 border border-purple-200">
          <div className="flex items-center gap-3">
            <DocumentTextIcon className="h-8 w-8 text-purple-600" />
            <div>
              <div className="text-2xl font-bold text-purple-900">{stats.activePatients}</div>
              <div className="text-sm text-purple-700">מטופלים פעילים</div>
            </div>
          </div>
        </div>

        <div className="card bg-amber-50 border border-amber-200">
          <div className="flex items-center gap-3">
            <BellAlertIcon className="h-8 w-8 text-amber-600" />
            <div>
              <div className="text-2xl font-bold text-amber-900">{stats.completedSummaries}</div>
              <div className="text-sm text-amber-700">סיכומים</div>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="card">
        <h2 className="text-xl font-bold mb-4">פעילות אחרונה</h2>
        {loading ? (
          <p className="text-gray-500 text-center py-4">טוען...</p>
        ) : patients.length === 0 ? (
          <p className="text-gray-500 text-center py-4">
            אין פעילות עדיין. התחל על ידי הוספת מטופלים!
          </p>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
                <div>
                  <div className="font-medium">{stats.activePatients} מטופלים פעילים במערכת</div>
                  <div className="text-sm text-gray-500">סטטיסטיקה כללית</div>
                </div>
              </div>
            </div>
            {stats.pendingMessages > 0 && (
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                  <div>
                    <div className="font-medium">{stats.pendingMessages} הודעות ממתינות לאישורך</div>
                    <div className="text-sm text-gray-500">דורש פעולה</div>
                  </div>
                </div>
                <button
                  onClick={() => navigate('/messages')}
                  className="text-therapy-calm text-sm font-medium hover:underline"
                >
                  אשר עכשיו →
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Summary Modal — pick patient + session, then navigate */}
      {showSummaryModal && (
        <SummaryPickerModal
          patients={patients}
          sessions={allSessions}
          onClose={() => setShowSummaryModal(false)}
          onSelect={(sessionId) => {
            setShowSummaryModal(false)
            navigate(`/sessions/${sessionId}`)
          }}
        />
      )}

      {/* Message Patient Picker — selects a patient, then navigates to their messages tab */}
      {showMessagePickerModal && (
        <MessagePatientPickerModal
          patients={patients}
          onClose={() => setShowMessagePickerModal(false)}
          onSelect={(patientId) => {
            setShowMessagePickerModal(false)
            navigate(`/patients/${patientId}`, { state: { initialTab: 'inbetween' } })
          }}
        />
      )}
    </div>
  )
}

// Summary Picker Modal — select patient then session
// SummaryPickerModal — pick patient + session to open the summary editor.
// Mobile: top-aligned with pt-8 clearance; sticky title; scrollable session list; sticky cancel.
// Desktop: centered, max 85vh.
function SummaryPickerModal({
  patients,
  sessions,
  onClose,
  onSelect,
}: {
  patients: Patient[]
  sessions: SimpleSession[]
  onClose: () => void
  onSelect: (sessionId: number) => void
}) {
  const [selectedPatientId, setSelectedPatientId] = useState<string>('')

  const patientSessions = selectedPatientId
    ? sessions
        .filter((s) => s.patient_id === Number(selectedPatientId))
        .sort((a, b) => b.session_date.localeCompare(a.session_date))
    : []

  return (
    <div className="fixed inset-0 bg-black/50 flex items-start sm:items-center justify-center z-50 p-4 pt-8 sm:pt-4" dir="rtl">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg flex flex-col max-h-[calc(100vh-6rem)] sm:max-h-[85vh] animate-fade-in">

        {/* Sticky header */}
        <div className="px-4 sm:px-8 py-4 sm:py-6 border-b border-gray-100 flex-shrink-0">
          <h2 className="text-xl sm:text-2xl font-bold">בחר פגישה לסיכום</h2>
        </div>

        {/* Scrollable content */}
        <div className="overflow-y-auto flex-1 px-4 sm:px-8 py-4 sm:py-5 space-y-4">
          {/* Patient select */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">מטופל/ת</label>
            <select
              className="input-field"
              value={selectedPatientId}
              onChange={(e) => setSelectedPatientId(e.target.value)}
            >
              <option value="">-- בחר מטופל --</option>
              {[...patients]
                .sort((a, b) => a.full_name.localeCompare(b.full_name, 'he'))
                .map((p) => (
                  <option key={p.id} value={p.id}>{p.full_name}</option>
                ))}
            </select>
          </div>

          {/* Session list for selected patient */}
          {selectedPatientId && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">פגישה</label>
              {patientSessions.length === 0 ? (
                <p className="text-sm text-gray-500 bg-gray-50 rounded-lg p-3">
                  אין פגישות למטופל זה. צור פגישה חדשה דרך עמוד הפגישות.
                </p>
              ) : (
                <div className="space-y-2">
                  {patientSessions.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => onSelect(s.id)}
                      className="w-full text-right p-3 rounded-lg border border-gray-200 hover:border-therapy-calm hover:bg-therapy-calm/5 transition-colors flex items-center justify-between min-h-[44px] touch-manipulation"
                    >
                      <div>
                        <div className="font-medium">
                          {new Date(s.session_date + 'T12:00:00').toLocaleDateString('he-IL')}
                          {s.session_number ? ` · פגישה #${s.session_number}` : ''}
                        </div>
                      </div>
                      {s.summary_id != null ? (
                        <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full flex-shrink-0">
                          יש סיכום
                        </span>
                      ) : (
                        <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full flex-shrink-0">
                          ללא סיכום
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Sticky footer */}
        <div className="px-4 sm:px-8 py-4 border-t border-gray-100 flex-shrink-0">
          <button onClick={onClose} className="btn-secondary w-full min-h-[44px] touch-manipulation">ביטול</button>
        </div>
      </div>
    </div>
  )
}

// MessagePatientPickerModal — selects patient, then navigates to their Messages tab.
// Mobile: top-aligned with pt-8 clearance; sticky header+footer; scrollable patient select.
// Desktop: centered, max 85vh.
function MessagePatientPickerModal({
  patients,
  onClose,
  onSelect,
}: {
  patients: Patient[]
  onClose: () => void
  onSelect: (patientId: number) => void
}) {
  const [selectedId, setSelectedId] = useState('')

  return (
    <div className="fixed inset-0 bg-black/50 flex items-start sm:items-center justify-center z-50 p-4 pt-8 sm:pt-4" dir="rtl">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md flex flex-col max-h-[calc(100vh-6rem)] sm:max-h-[85vh] animate-fade-in">

        {/* Sticky header */}
        <div className="px-4 sm:px-8 py-4 sm:py-6 border-b border-gray-100 flex-shrink-0">
          <h2 className="text-xl sm:text-2xl font-bold">שליחת הודעה למטופל</h2>
          <p className="text-sm text-gray-500 mt-1">
            בחר מטופל כדי לפתוח את מרכז ההודעות שלו ולשלוח תזכורת
          </p>
        </div>

        {/* Scrollable content */}
        <div className="overflow-y-auto flex-1 px-4 sm:px-8 py-4 sm:py-5">
          <label className="block text-sm font-medium text-gray-700 mb-2">מטופל/ת</label>
          <select
            className="input-field"
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
          >
            <option value="">-- בחר מטופל --</option>
            {[...patients]
              .sort((a, b) => a.full_name.localeCompare(b.full_name, 'he'))
              .map((p) => (
                <option key={p.id} value={p.id}>{p.full_name}</option>
              ))}
          </select>
        </div>

        {/* Sticky footer */}
        <div className="flex gap-3 px-4 sm:px-8 py-4 border-t border-gray-100 flex-shrink-0">
          <button
            onClick={() => selectedId && onSelect(Number(selectedId))}
            disabled={!selectedId}
            className="btn-primary flex-1 disabled:opacity-50 min-h-[44px] touch-manipulation"
          >
            עבור למרכז הודעות →
          </button>
          <button onClick={onClose} className="btn-secondary min-h-[44px] touch-manipulation">ביטול</button>
        </div>
      </div>
    </div>
  )
}
