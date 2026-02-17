import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  DocumentTextIcon,
  PaperAirplaneIcon,
  MicrophoneIcon,
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

function todayISO(): string {
  return new Date().toISOString().split('T')[0]
}

function formatDateHebrew(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00')
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
  return d.toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' })
}

function shiftDate(dateStr: string, days: number): string {
  const d = new Date(dateStr + 'T00:00:00')
  d.setDate(d.getDate() + days)
  return d.toISOString().split('T')[0]
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [showSessionModal, setShowSessionModal] = useState(false)
  const [showMessageModal, setShowMessageModal] = useState(false)

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
        <h1 className="text-3xl font-bold mb-2">שלום! 👋</h1>
        <p className="text-indigo-100 text-lg">
          מה תרצה לעשות היום?
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
            onClick={() => setSelectedDate(shiftDate(selectedDate, 1))}
            className="btn-secondary text-sm px-3 py-1.5 flex items-center gap-1"
          >
            <ChevronRightIcon className="h-4 w-4" />
            יום קודם
          </button>
          <button
            onClick={() => setSelectedDate(shiftDate(selectedDate, -1))}
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
                      פגישה #{session.session_number} · {session.session_type}
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

      {/* THE 3 MAIN BUTTONS - This is the core interface! */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Button 1: Write Summary */}
        <button
          onClick={() => setShowSessionModal(true)}
          className="card group hover:shadow-2xl transition-all duration-300 hover:scale-105 cursor-pointer text-right"
        >
          <div className="flex flex-col items-start gap-4">
            <div className="w-16 h-16 bg-therapy-calm/10 rounded-full flex items-center justify-center group-hover:bg-therapy-calm group-hover:text-white transition-colors duration-300">
              <DocumentTextIcon className="h-8 w-8 text-therapy-calm group-hover:text-white" />
            </div>
            <div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">📝 כתיבת סיכום</h3>
              <p className="text-gray-600 text-sm">
                הקלט דקה-דקתיים או הקלד הערות, והמערכת תיצור סיכום מובנה בסגנון שלך
              </p>
            </div>
            <div className="mt-auto w-full">
              <div className="text-sm text-therapy-calm font-medium">לחץ ליצירת סיכום →</div>
            </div>
          </div>
        </button>

        {/* Button 2: Send to Patient */}
        <button
          onClick={() => setShowMessageModal(true)}
          className="card group hover:shadow-2xl transition-all duration-300 hover:scale-105 cursor-pointer text-right"
        >
          <div className="flex flex-col items-start gap-4">
            <div className="w-16 h-16 bg-therapy-support/10 rounded-full flex items-center justify-center group-hover:bg-therapy-support group-hover:text-white transition-colors duration-300">
              <PaperAirplaneIcon className="h-8 w-8 text-therapy-support group-hover:text-white" />
            </div>
            <div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">👤 שליחה למטופל</h3>
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

        {/* Button 3: New Recording */}
        <button
          onClick={() => setShowSessionModal(true)}
          className="card group hover:shadow-2xl transition-all duration-300 hover:scale-105 cursor-pointer text-right"
        >
          <div className="flex flex-col items-start gap-4">
            <div className="w-16 h-16 bg-therapy-warm/10 rounded-full flex items-center justify-center group-hover:bg-therapy-warm group-hover:text-white transition-colors duration-300">
              <MicrophoneIcon className="h-8 w-8 text-therapy-warm group-hover:text-white" />
            </div>
            <div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">🎙️ הקלטה חדשה</h3>
              <p className="text-gray-600 text-sm">
                הקלט סיכום פגישה והמערכת תתמלל ותיצור סיכום מובנה אוטומטית
              </p>
            </div>
            <div className="mt-auto w-full">
              <div className="text-sm text-therapy-warm font-medium">לחץ להקלטה →</div>
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

      {/* Modals */}
      {showSessionModal && (
        <SessionModal onClose={() => setShowSessionModal(false)} />
      )}

      {showMessageModal && (
        <MessageModal
          patients={patients}
          onClose={() => setShowMessageModal(false)}
        />
      )}
    </div>
  )
}

// Session Summary Modal
function SessionModal({ onClose }: { onClose: () => void }) {
  const [recordingMode, setRecordingMode] = useState<'audio' | 'text'>('audio')

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" dir="rtl">
      <div className="bg-white rounded-xl p-8 max-w-2xl w-full mx-4 animate-fade-in">
        <h2 className="text-2xl font-bold mb-6">יצירת סיכום פגישה</h2>

        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            בחר שיטה
          </label>
          <div className="grid grid-cols-2 gap-4">
            <button
              onClick={() => setRecordingMode('audio')}
              className={`p-4 border-2 rounded-lg ${
                recordingMode === 'audio'
                  ? 'border-therapy-calm bg-blue-50'
                  : 'border-gray-300 hover:border-gray-400'
              }`}
            >
              <MicrophoneIcon className="h-8 w-8 mx-auto mb-2 text-therapy-warm" />
              <div className="font-medium">הקלטה</div>
              <div className="text-xs text-gray-500">הקלט קול והמערכת תתמלל</div>
            </button>

            <button
              onClick={() => setRecordingMode('text')}
              className={`p-4 border-2 rounded-lg ${
                recordingMode === 'text'
                  ? 'border-therapy-calm bg-blue-50'
                  : 'border-gray-300 hover:border-gray-400'
              }`}
            >
              <DocumentTextIcon className="h-8 w-8 mx-auto mb-2 text-therapy-calm" />
              <div className="font-medium">טקסט</div>
              <div className="text-xs text-gray-500">הקלד הערות ישירות</div>
            </button>
          </div>
        </div>

        {recordingMode === 'audio' ? (
          <div className="bg-gray-50 rounded-lg p-8 text-center">
            <div className="w-24 h-24 bg-therapy-warm rounded-full mx-auto mb-4 flex items-center justify-center">
              <MicrophoneIcon className="h-12 w-12 text-white" />
            </div>
            <button className="btn-primary mb-2">🎙️ התחל הקלטה</button>
            <p className="text-sm text-gray-600">לחץ כדי להתחיל להקליט</p>
          </div>
        ) : (
          <div>
            <textarea
              className="input-field h-40 resize-none"
              placeholder="הקלד כאן את רשימות הפגישה... המערכת תיצור מזה סיכום מובנה בסגנון שלך"
            />
            <button className="btn-primary mt-4 w-full">צור סיכום</button>
          </div>
        )}

        <button
          onClick={onClose}
          className="btn-secondary w-full mt-4"
        >
          ביטול
        </button>
      </div>
    </div>
  )
}

// Message Modal - now receives real patients list
function MessageModal({ patients, onClose }: { patients: Patient[]; onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" dir="rtl">
      <div className="bg-white rounded-xl p-8 max-w-2xl w-full mx-4 animate-fade-in">
        <h2 className="text-2xl font-bold mb-6">יצירת הודעה למטופל</h2>

        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            בחר מטופל
          </label>
          <select className="input-field">
            <option value="">-- בחר מטופל --</option>
            {patients.map((p) => (
              <option key={p.id} value={p.id}>{p.full_name}</option>
            ))}
          </select>
        </div>

        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            סוג הודעה
          </label>
          <select className="input-field">
            <option>מעקב אחר תרגיל</option>
            <option>תזכורת לפגישה</option>
            <option>צ'ק-אין כללי</option>
            <option>תזכורת לתרגיל בית</option>
          </select>
        </div>

        <button className="btn-primary w-full mb-2">✨ צור הודעה (AI)</button>
        <p className="text-xs text-gray-500 text-center mb-4">
          המערכת תיצור הודעה בסגנון שלך. תוכל לערוך ולאשר לפני השליחה
        </p>

        <button
          onClick={onClose}
          className="btn-secondary w-full"
        >
          ביטול
        </button>
      </div>
    </div>
  )
}
