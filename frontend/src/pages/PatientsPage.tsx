import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  PlusIcon,
  MagnifyingGlassIcon,
  XMarkIcon,
  EyeIcon,
  EyeSlashIcon,
  ChevronLeftIcon,
  DocumentTextIcon,
  ChatBubbleLeftRightIcon,
  CalendarIcon,
} from '@heroicons/react/24/outline'
import { patientsAPI, sessionsAPI, exercisesAPI } from '@/lib/api'
import PhoneInput from '@/components/PhoneInput'

const SESSION_TYPES = [
  { value: 'individual', label: 'פרטני' },
  { value: 'couples', label: 'זוגי' },
  { value: 'family', label: 'משפחתי' },
  { value: 'group', label: 'קבוצתי' },
  { value: 'intake', label: 'אינטייק' },
  { value: 'follow_up', label: 'מעקב' },
]

interface Patient {
  id: number
  therapist_id: number
  full_name: string
  phone?: string
  email?: string
  status: string
  start_date?: string
  allow_ai_contact: boolean
  preferred_contact_time?: string
  completed_exercises_count: number
  missed_exercises_count: number
  created_at: string
}

interface Session {
  id: number
  patient_id: number
  session_date: string
  session_type?: string
}

export default function PatientsPage() {
  const navigate = useNavigate()
  const [patients, setPatients] = useState<Patient[]>([])
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)
  const [pendingTasksCount, setPendingTasksCount] = useState(0)
  const [patientOpenTasks, setPatientOpenTasks] = useState<Record<number, number>>({})
  const [searchTerm, setSearchTerm] = useState('')
  const [showInactive, setShowInactive] = useState(false)
  const [showCreateForm, setShowCreateForm] = useState(false)

  // Create-session-for-patient modal state
  const [createSessionFor, setCreateSessionFor] = useState<Patient | null>(null)
  const [newSessionDate, setNewSessionDate] = useState(new Date().toISOString().split('T')[0])
  const [newSessionTime, setNewSessionTime] = useState('')
  const [newSessionType, setNewSessionType] = useState('individual')
  const [newSessionDuration, setNewSessionDuration] = useState(50)
  const [creatingSession, setCreatingSession] = useState(false)
  const [createSessionError, setCreateSessionError] = useState('')

  // Create patient form state
  const [newPatient, setNewPatient] = useState({
    full_name: '',
    phone: '',
    email: '',
    primary_concerns: '',
  })
  const [creating, setCreating] = useState(false)

  const loadPatients = async (): Promise<Patient[]> => {
    try {
      const data = await patientsAPI.list()
      setPatients(data)
      return data
    } catch (error) {
      console.error('Error loading patients:', error)
      return []
    }
  }

  const loadSessions = async () => {
    try {
      const data = await sessionsAPI.list()
      setSessions(data)
    } catch (error) {
      console.error('Error loading sessions:', error)
    }
  }

  useEffect(() => {
    const init = async () => {
      const [patientsData] = await Promise.all([loadPatients(), loadSessions()])
      setLoading(false)

      // Fetch exercises for all active patients in parallel to get per-patient open task counts
      const active = patientsData.filter((p) => p.status === 'active')
      if (active.length > 0) {
        try {
          const lists = await Promise.all(
            active.map((p) => exercisesAPI.list(p.id).catch(() => []))
          )
          const openMap: Record<number, number> = {}
          active.forEach((p, i) => {
            openMap[p.id] = (lists[i] as any[]).filter((ex: any) => !ex.completed).length
          })
          setPatientOpenTasks(openMap)
          setPendingTasksCount(Object.values(openMap).reduce((sum, n) => sum + n, 0))
        } catch { /* not critical */ }
      }
    }
    init()
  }, [])

  // Lock body scroll when a modal is open
  useEffect(() => {
    const locked = showCreateForm || !!createSessionFor
    document.body.style.overflow = locked ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [showCreateForm, createSessionFor])

  // Next session per patient (nearest future session_date >= today)
  const nextSessionByPatient = useMemo(() => {
    const todayStr = new Date().toISOString().split('T')[0]
    const map: Record<number, Session | null> = {}
    patients.forEach((p) => {
      const future = sessions
        .filter((s) => s.patient_id === p.id && s.session_date >= todayStr)
        .sort((a, b) => a.session_date.localeCompare(b.session_date))
      map[p.id] = future[0] ?? null
    })
    return map
  }, [patients, sessions])

  const openCreateSession = (patient: Patient) => {
    setCreateSessionFor(patient)
    setNewSessionDate(new Date().toISOString().split('T')[0])
    setNewSessionTime('')
    setNewSessionType('individual')
    setNewSessionDuration(50)
    setCreateSessionError('')
  }

  const handleCreateSessionForPatient = async () => {
    if (!createSessionFor) return
    setCreatingSession(true)
    setCreateSessionError('')
    try {
      const startTime = newSessionTime ? `${newSessionDate}T${newSessionTime}:00` : undefined
      await sessionsAPI.create({
        patient_id: createSessionFor.id,
        session_date: newSessionDate,
        session_type: newSessionType,
        duration_minutes: newSessionDuration,
        start_time: startTime,
      })
      setCreateSessionFor(null)
      await loadSessions()
    } catch (err: any) {
      setCreateSessionError(err.response?.data?.detail || 'שגיאה ביצירת הפגישה')
    } finally {
      setCreatingSession(false)
    }
  }

  const handleCreatePatient = async () => {
    if (!newPatient.full_name.trim()) return
    setCreating(true)
    try {
      await patientsAPI.create({
        full_name: newPatient.full_name,
        phone: newPatient.phone || undefined,
        email: newPatient.email || undefined,
        primary_concerns: newPatient.primary_concerns || undefined,
      })
      setNewPatient({ full_name: '', phone: '', email: '', primary_concerns: '' })
      setShowCreateForm(false)
      await loadPatients()
    } catch (error) {
      console.error('Error creating patient:', error)
    } finally {
      setCreating(false)
    }
  }

  // Sessions this week
  const now = new Date()
  const dayOfWeek = now.getDay()
  const startOfWeek = new Date(now)
  startOfWeek.setDate(now.getDate() - dayOfWeek)
  startOfWeek.setHours(0, 0, 0, 0)
  const endOfWeek = new Date(startOfWeek)
  endOfWeek.setDate(startOfWeek.getDate() + 7)
  const sessionsThisWeek = sessions.filter((s) => {
    const d = new Date(s.session_date)
    return d >= startOfWeek && d < endOfWeek
  }).length

  const activeCount = patients.filter((p) => p.status === 'active').length

  const filteredPatients = patients
    .filter((p) => showInactive || p.status !== 'inactive')
    .filter((p) => p.full_name.includes(searchTerm))
    .sort((a, b) => a.full_name.localeCompare(b.full_name, 'he'))

  const inactiveCount = patients.filter((p) => p.status === 'inactive').length

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" dir="rtl">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-therapy-calm mx-auto mb-4"></div>
          <p className="text-gray-600">טוען מטופלים...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3 md:space-y-6 animate-fade-in" dir="rtl">
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">מטופלים</h1>
          <p className="hidden sm:block text-gray-600 mt-2">נהל את כל המטופלים שלך במקום אחד</p>
        </div>
        <button
          onClick={() => setShowCreateForm(true)}
          className="btn-primary flex items-center gap-2 flex-shrink-0 min-h-[44px] touch-manipulation"
        >
          <PlusIcon className="h-5 w-5" />
          מטופל חדש
        </button>
      </div>

      {/* Search + inactive toggle */}
      <div className="card">
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <MagnifyingGlassIcon className="absolute right-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="input-field pr-10"
              placeholder="חפש מטופל..."
            />
          </div>
          {inactiveCount > 0 && (
            <button
              onClick={() => setShowInactive((v) => !v)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${
                showInactive
                  ? 'bg-gray-200 text-gray-800 hover:bg-gray-300'
                  : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
              }`}
            >
              {showInactive ? (
                <EyeSlashIcon className="h-4 w-4" />
              ) : (
                <EyeIcon className="h-4 w-4" />
              )}
              {showInactive ? 'הסתר לא פעילים' : `הצג לא פעילים (${inactiveCount})`}
            </button>
          )}
        </div>
      </div>

      {/* Stats — slim 3-col strip on mobile, spacious cards on md+ */}
      <div className="grid grid-cols-3 gap-2 md:gap-4">
        <div className="bg-blue-50 border border-blue-200 rounded-xl flex flex-col items-center md:items-start py-2 px-2 md:py-5 md:px-6">
          <div className="text-2xl md:text-3xl font-bold text-blue-900 leading-none">{activeCount}</div>
          <div className="text-[11px] md:text-sm text-blue-700 mt-1 text-center md:text-start leading-tight">
            <span>פעילים</span>
          </div>
        </div>
        <div className="bg-green-50 border border-green-200 rounded-xl flex flex-col items-center md:items-start py-2 px-2 md:py-5 md:px-6">
          <div className="text-2xl md:text-3xl font-bold text-green-900 leading-none">{sessionsThisWeek}</div>
          <div className="text-[11px] md:text-sm text-green-700 mt-1 text-center md:text-start leading-tight">
            <span className="md:hidden">פגישות<br/>השבוע</span>
            <span className="hidden md:inline">פגישות השבוע</span>
          </div>
        </div>
        <div className="bg-purple-50 border border-purple-200 rounded-xl flex flex-col items-center md:items-start py-2 px-2 md:py-5 md:px-6">
          <div className="text-2xl md:text-3xl font-bold text-purple-900 leading-none">{pendingTasksCount}</div>
          <div className="text-[11px] md:text-sm text-purple-700 mt-1 text-center md:text-start leading-tight">
            <span className="md:hidden">משימות</span>
            <span className="hidden md:inline">משימות פתוחות</span>
          </div>
        </div>
      </div>

      {/* Patients List */}
      {filteredPatients.length === 0 ? (
        <div className="card text-center py-12">
          <div className="text-6xl mb-4">👥</div>
          <h3 className="text-xl font-bold text-gray-900 mb-2">
            {patients.length === 0
              ? 'אין מטופלים עדיין'
              : !showInactive && inactiveCount > 0 && activeCount === 0
              ? 'כל המטופלים לא פעילים'
              : 'לא נמצאו תוצאות'}
          </h3>
          <p className="text-gray-600">
            {patients.length === 0
              ? 'לחץ על "מטופל חדש" כדי להוסיף את המטופל הראשון'
              : !showInactive && inactiveCount > 0 && activeCount === 0
              ? 'לחץ על "הצג לא פעילים" כדי לראות את כל המטופלים'
              : 'נסה לחפש עם מונח אחר'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 md:gap-4">
          {filteredPatients.map((patient) => (
            <div
              key={patient.id}
              className="bg-white border border-gray-200 rounded-xl shadow-sm hover:shadow-md active:bg-gray-50 transition-all cursor-pointer px-4 py-3 md:p-6"
              onClick={() => navigate(`/patients/${patient.id}`)}
            >
              {/* Patient Header — always visible */}
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 md:w-12 md:h-12 bg-therapy-calm text-white rounded-full flex items-center justify-center font-bold md:text-lg flex-shrink-0">
                  {patient.full_name.charAt(0)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-bold text-base md:text-lg leading-tight truncate">{patient.full_name}</div>
                  <div className={`badge text-xs mt-0.5 ${
                    patient.status === 'active' ? 'badge-approved' : 'badge-draft'
                  }`}>
                    {patient.status === 'active' ? 'פעיל' :
                     patient.status === 'paused' ? 'מושהה' :
                     patient.status === 'completed' ? 'הושלם' : 'לא פעיל'}
                  </div>
                </div>

                {/* Mobile: icon action buttons + chevron navigation hint */}
                <div className="md:hidden flex items-center gap-0.5 flex-shrink-0">
                  <button
                    className="p-2 text-gray-400 hover:text-therapy-calm hover:bg-blue-50 rounded-lg touch-manipulation"
                    title="סיכומים"
                    onClick={(e) => {
                      e.stopPropagation()
                      navigate(`/patients/${patient.id}`, { state: { initialTab: 'summaries' } })
                    }}
                  >
                    <DocumentTextIcon className="h-5 w-5" />
                  </button>
                  <button
                    className="p-2 text-gray-400 hover:text-therapy-calm hover:bg-blue-50 rounded-lg touch-manipulation"
                    title="שלח הודעה"
                    onClick={(e) => {
                      e.stopPropagation()
                      navigate(`/patients/${patient.id}`, { state: { initialTab: 'inbetween' } })
                    }}
                  >
                    <ChatBubbleLeftRightIcon className="h-5 w-5" />
                  </button>
                  <ChevronLeftIcon className="h-4 w-4 text-gray-300 mr-1" />
                </div>
              </div>

              {/* Patient Stats — desktop only */}
              <div className="hidden md:block mt-4 space-y-2 text-sm">
                {patient.phone && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">טלפון:</span>
                    <a
                      href={`tel:${patient.phone}`}
                      onClick={(e) => e.stopPropagation()}
                      className="font-medium text-therapy-calm hover:underline"
                      dir="ltr"
                    >
                      {patient.phone}
                    </a>
                  </div>
                )}
                <div
                  className="flex justify-between cursor-pointer group"
                  onClick={(e) => {
                    e.stopPropagation()
                    navigate(`/patients/${patient.id}`, { state: { initialTab: 'sessions' } })
                  }}
                >
                  <span className="text-gray-600 group-hover:text-therapy-calm">משימות פתוחות:</span>
                  <span className="font-medium group-hover:text-therapy-calm">
                    {patientOpenTasks[patient.id] ?? 0}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-600 flex items-center gap-1">
                    <CalendarIcon className="h-3.5 w-3.5" />
                    פגישה הבאה:
                  </span>
                  {nextSessionByPatient[patient.id] ? (
                    <span className="font-medium">
                      {new Date(nextSessionByPatient[patient.id]!.session_date + 'T12:00:00').toLocaleDateString('he-IL')}
                    </span>
                  ) : (
                    <span className="flex items-center gap-1.5">
                      <span className="text-gray-400">לא נקבע</span>
                      <button
                        onClick={(e) => { e.stopPropagation(); openCreateSession(patient) }}
                        className="text-xs font-medium text-therapy-calm hover:underline"
                      >
                        · קביעת פגישה
                      </button>
                    </span>
                  )}
                </div>
              </div>

              {/* Actions — desktop only, full text buttons */}
              <div className="hidden md:grid mt-4 pt-4 border-t border-gray-200 grid-cols-2 gap-2">
                <button
                  className="text-sm btn-secondary py-2"
                  onClick={(e) => {
                    e.stopPropagation()
                    navigate(`/patients/${patient.id}`, { state: { initialTab: 'summaries' } })
                  }}
                >
                  סיכומים
                </button>
                <button
                  className="text-sm btn-secondary py-2"
                  onClick={(e) => {
                    e.stopPropagation()
                    navigate(`/patients/${patient.id}`, { state: { initialTab: 'inbetween' } })
                  }}
                >
                  שלח הודעה
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Session for Patient Modal */}
      {createSessionFor && (
        <div className="fixed inset-0 bg-black/50 flex items-start sm:items-center justify-center z-50 p-4 pt-8 sm:pt-4" dir="rtl">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg flex flex-col max-h-[calc(100vh-6rem)] sm:max-h-[85vh] overflow-x-hidden">
            <div className="flex items-center justify-between px-3 sm:px-6 py-4 border-b border-gray-100 flex-shrink-0">
              <div>
                <h2 className="text-xl font-bold text-gray-900">פגישה חדשה</h2>
                <p className="text-sm text-gray-500 mt-0.5">{createSessionFor.full_name}</p>
              </div>
              <button onClick={() => setCreateSessionFor(null)} className="text-gray-400 hover:text-gray-600 p-1 touch-manipulation">
                <XMarkIcon className="h-6 w-6" />
              </button>
            </div>

            <div className="overflow-y-auto flex-1 px-3 sm:px-6 py-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">תאריך *</label>
                <input
                  type="date"
                  value={newSessionDate}
                  onChange={(e) => setNewSessionDate(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">שעת התחלה</label>
                <select
                  value={newSessionTime}
                  onChange={(e) => setNewSessionTime(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
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
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">משך (דקות)</label>
                <input
                  type="number"
                  value={newSessionDuration}
                  onChange={(e) => setNewSessionDuration(Number(e.target.value))}
                  min={10} max={180}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">סוג פגישה</label>
                <select
                  value={newSessionType}
                  onChange={(e) => setNewSessionType(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
                >
                  {SESSION_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
              {createSessionError && (
                <div className="text-red-600 text-sm bg-red-50 rounded-lg p-3">{createSessionError}</div>
              )}
            </div>

            <div className="flex gap-3 px-3 sm:px-6 py-4 border-t border-gray-100 flex-shrink-0">
              <button
                onClick={handleCreateSessionForPatient}
                disabled={creatingSession}
                className="btn-primary flex-1 disabled:opacity-50 min-h-[44px] touch-manipulation"
              >
                {creatingSession ? 'יוצר...' : 'צור פגישה'}
              </button>
              <button
                onClick={() => setCreateSessionFor(null)}
                className="btn-secondary flex-1 min-h-[44px] touch-manipulation"
              >
                ביטול
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Patient Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 bg-black/50 flex items-start sm:items-center justify-center z-50 p-4 pt-8 sm:pt-4" dir="rtl">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg flex flex-col max-h-[calc(100vh-6rem)] sm:max-h-[85vh] overflow-x-hidden">

            {/* Sticky header */}
            <div className="flex items-center justify-between px-3 sm:px-6 py-4 border-b border-gray-100 flex-shrink-0">
              <h2 className="text-xl font-bold">מטופל חדש</h2>
              <button onClick={() => setShowCreateForm(false)} className="touch-manipulation p-1">
                <XMarkIcon className="h-6 w-6 text-gray-500 hover:text-gray-700" />
              </button>
            </div>

            {/* Scrollable body */}
            <div className="overflow-y-auto flex-1 px-3 sm:px-6 py-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">שם מלא *</label>
                <input
                  type="text"
                  value={newPatient.full_name}
                  onChange={(e) => setNewPatient({ ...newPatient, full_name: e.target.value })}
                  className="input-field"
                  placeholder="שם מלא של המטופל"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">טלפון</label>
                <PhoneInput
                  value={newPatient.phone}
                  onChange={(e164) => setNewPatient({ ...newPatient, phone: e164 })}
                  className="w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">אימייל</label>
                <input
                  type="email"
                  value={newPatient.email}
                  onChange={(e) => setNewPatient({ ...newPatient, email: e.target.value })}
                  className="input-field"
                  placeholder="patient@example.com"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">נושאים עיקריים</label>
                <textarea
                  value={newPatient.primary_concerns}
                  onChange={(e) => setNewPatient({ ...newPatient, primary_concerns: e.target.value })}
                  className="input-field h-20 resize-none"
                  placeholder="תיאור קצר של הנושאים העיקריים..."
                />
              </div>
            </div>

            {/* Sticky footer */}
            <div className="flex gap-3 px-3 sm:px-6 py-4 border-t border-gray-100 flex-shrink-0">
              <button
                onClick={handleCreatePatient}
                disabled={!newPatient.full_name.trim() || creating}
                className="btn-primary flex-1 disabled:opacity-50 min-h-[44px] touch-manipulation"
              >
                {creating ? 'יוצר...' : 'צור מטופל'}
              </button>
              <button
                onClick={() => setShowCreateForm(false)}
                className="btn-secondary flex-1 min-h-[44px] touch-manipulation"
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
