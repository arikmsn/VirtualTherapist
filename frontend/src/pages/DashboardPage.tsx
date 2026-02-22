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

export default function DashboardPage() {
  const navigate = useNavigate()
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
    <div className="space-y-8 animate-fade-in">
      {/* Welcome Header */}
      <div className="card bg-gradient-to-l from-therapy-calm to-therapy-gentle text-white">
        <h1 className="text-3xl font-bold mb-2">לוח הפגישות להיום</h1>
        <p className="text-indigo-100 text-lg">
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
                className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
              >
                <div className="flex items-center gap-4">
                  {/* Time */}
                  <div className="text-lg font-mono font-semibold text-therapy-calm min-w-[60px]">
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

                  {/* Summary badge */}
                  {session.has_summary ? (
                    <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                      יש סיכום
                    </span>
                  ) : (
                    <span className="text-xs bg-gray-200 text-gray-600 px-2 py-0.5 rounded-full">
                      ללא סיכום
                    </span>
                  )}
                </div>

                {/* Action buttons */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => navigate(`/sessions/${session.id}`)}
                    className="text-sm px-3 py-1 bg-therapy-calm text-white rounded-lg hover:bg-therapy-calm/90 transition-colors"
                  >
                    פתח סשן
                  </button>
                  <button
                    onClick={() => navigate(`/sessions/${session.id}?prep=1`)}
                    className="text-sm px-3 py-1 bg-amber-100 text-amber-800 rounded-lg hover:bg-amber-200 transition-colors"
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
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" dir="rtl">
      <div className="bg-white rounded-xl p-8 max-w-lg w-full mx-4 animate-fade-in">
        <h2 className="text-2xl font-bold mb-6">בחר פגישה לסיכום</h2>

        {/* Patient select */}
        <div className="mb-4">
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
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">פגישה</label>
            {patientSessions.length === 0 ? (
              <p className="text-sm text-gray-500 bg-gray-50 rounded-lg p-3">
                אין פגישות למטופל זה. צור פגישה חדשה דרך עמוד הפגישות.
              </p>
            ) : (
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {patientSessions.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => onSelect(s.id)}
                    className="w-full text-right p-3 rounded-lg border border-gray-200 hover:border-therapy-calm hover:bg-therapy-calm/5 transition-colors flex items-center justify-between"
                  >
                    <div>
                      <div className="font-medium">
                        {new Date(s.session_date + 'T12:00:00').toLocaleDateString('he-IL')}
                        {s.session_number ? ` · פגישה #${s.session_number}` : ''}
                      </div>
                    </div>
                    {s.summary_id != null ? (
                      <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                        יש סיכום
                      </span>
                    ) : (
                      <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">
                        ללא סיכום
                      </span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <button onClick={onClose} className="btn-secondary w-full">ביטול</button>
      </div>
    </div>
  )
}

// Patient picker for messaging — selects patient, then navigates to their Messages tab
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
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" dir="rtl">
      <div className="bg-white rounded-xl p-8 max-w-md w-full mx-4 animate-fade-in">
        <h2 className="text-2xl font-bold mb-2">שליחת הודעה למטופל</h2>
        <p className="text-sm text-gray-500 mb-6">
          בחר מטופל כדי לפתוח את מרכז ההודעות שלו ולשלוח תזכורת
        </p>

        <div className="mb-6">
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

        <div className="flex gap-3">
          <button
            onClick={() => selectedId && onSelect(Number(selectedId))}
            disabled={!selectedId}
            className="btn-primary flex-1 disabled:opacity-50"
          >
            עבור למרכז הודעות →
          </button>
          <button onClick={onClose} className="btn-secondary">ביטול</button>
        </div>
      </div>
    </div>
  )
}
