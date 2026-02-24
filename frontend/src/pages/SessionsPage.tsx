import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  DocumentTextIcon,
  CheckCircleIcon,
  PlusIcon,
  XMarkIcon,
  TrashIcon,
  SparklesIcon,
  LightBulbIcon,
} from '@heroicons/react/24/outline'
import { sessionsAPI, patientsAPI } from '@/lib/api'

interface PrepBrief {
  history_summary: string[]    // מה היה עד עכשיו
  last_session: string[]       // מה היה בפגישה האחרונה
  tasks_to_check: string[]     // משימות לבדיקה היום
  focus_for_today: string[]    // על מה כדאי להתמקד
  watch_out_for: string[]      // שים לב
}

interface Session {
  id: number
  therapist_id: number
  patient_id: number
  session_date: string
  session_type?: string
  duration_minutes?: number
  session_number?: number
  has_recording: boolean
  summary_id?: number
  created_at: string
}

interface Patient {
  id: number
  full_name: string
}

const SESSION_TYPES = [
  { value: 'individual', label: 'פרטני' },
  { value: 'couples', label: 'זוגי' },
  { value: 'family', label: 'משפחתי' },
  { value: 'group', label: 'קבוצתי' },
  { value: 'intake', label: 'אינטייק' },
  { value: 'follow_up', label: 'מעקב' },
]

export default function SessionsPage() {
  const navigate = useNavigate()
  const [sessions, setSessions] = useState<Session[]>([])
  const [patients, setPatients] = useState<Patient[]>([])
  const [patientMap, setPatientMap] = useState<Record<number, string>>({})
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'all' | 'with_summary' | 'no_summary'>('all')

  // Delete session modal state
  const [deleteTarget, setDeleteTarget] = useState<Session | null>(null)
  const [deleteStep, setDeleteStep] = useState<1 | 2>(1)
  const [deleting, setDeleting] = useState(false)
  const [notifyPatient, setNotifyPatient] = useState(false)

  // Prep brief modal state
  const [prepSession, setPrepSession] = useState<Session | null>(null)
  const [prepBrief, setPrepBrief] = useState<PrepBrief | null>(null)
  const [prepLoading, setPrepLoading] = useState(false)
  const [prepError, setPrepError] = useState('')

  // Create session modal state
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')
  const [formData, setFormData] = useState({
    patient_id: '',
    session_date: new Date().toISOString().split('T')[0],
    start_time: '',
    session_type: 'individual',
    duration_minutes: 50,
  })

  const loadSessions = async () => {
    try {
      const data = await sessionsAPI.list()
      setSessions(data)
    } catch (error) {
      console.error('Error loading sessions:', error)
    }
  }

  const loadPatients = async () => {
    try {
      const data = await patientsAPI.list()
      setPatients(data)
      const map: Record<number, string> = {}
      data.forEach((p: Patient) => {
        map[p.id] = p.full_name
      })
      setPatientMap(map)
    } catch (error) {
      console.error('Error loading patients:', error)
    }
  }

  useEffect(() => {
    const loadData = async () => {
      await Promise.all([loadSessions(), loadPatients()])
      setLoading(false)
    }
    loadData()
  }, [])

  const openDeleteModal = (session: Session) => {
    setDeleteTarget(session)
    setDeleteStep(1)
    setNotifyPatient(false)
  }

  const closeDeleteModal = () => {
    setDeleteTarget(null)
    setDeleteStep(1)
    setNotifyPatient(false)
  }

  const handleDeleteSession = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await sessionsAPI.delete(deleteTarget.id, notifyPatient)
      setSessions((prev) => prev.filter((s) => s.id !== deleteTarget.id))
      closeDeleteModal()
    } catch (error) {
      console.error('Error deleting session:', error)
    } finally {
      setDeleting(false)
    }
  }

  const handleCreateSession = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreateError('')

    if (!formData.patient_id) {
      setCreateError('יש לבחור מטופל')
      return
    }

    setCreating(true)
    try {
      let startTime: string | undefined
      if (formData.start_time) {
        startTime = `${formData.session_date}T${formData.start_time}:00`
      }

      await sessionsAPI.create({
        patient_id: Number(formData.patient_id),
        session_date: formData.session_date,
        session_type: formData.session_type,
        duration_minutes: formData.duration_minutes,
        start_time: startTime,
      })

      setShowCreateModal(false)
      setFormData({
        patient_id: '',
        session_date: new Date().toISOString().split('T')[0],
        start_time: '',
        session_type: 'individual',
        duration_minutes: 50,
      })
      await loadSessions()
    } catch (error: any) {
      setCreateError(error.response?.data?.detail || 'שגיאה ביצירת הפגישה')
    } finally {
      setCreating(false)
    }
  }

  // Lock body scroll whenever a modal is open
  useEffect(() => {
    const locked = !!deleteTarget || showCreateModal || !!prepSession
    document.body.style.overflow = locked ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [deleteTarget, showCreateModal, prepSession])

  const openPrepModal = async (session: Session) => {
    setPrepSession(session)
    setPrepBrief(null)
    setPrepError('')
    setPrepLoading(true)
    try {
      const data = await sessionsAPI.getPrepBrief(session.id)
      setPrepBrief(data)
    } catch (err: any) {
      setPrepError(err.response?.data?.detail || 'שגיאה ביצירת תדריך ההכנה')
    } finally {
      setPrepLoading(false)
    }
  }

  const closePrepModal = () => {
    setPrepSession(null)
    setPrepBrief(null)
    setPrepError('')
  }

  const filteredSessions = sessions.filter((session) => {
    if (filter === 'with_summary') return session.summary_id != null
    if (filter === 'no_summary') return session.summary_id == null
    return true
  })

  const withSummaryCount = sessions.filter((s) => s.summary_id != null).length
  const noSummaryCount = sessions.filter((s) => s.summary_id == null).length

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" dir="rtl">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-therapy-calm mx-auto mb-4"></div>
          <p className="text-gray-600">טוען פגישות...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in" dir="rtl">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">פגישות וסיכומים</h1>
          <p className="text-gray-600 mt-1 sm:mt-2 text-sm sm:text-base">כל הפגישות והסיכומים במקום אחד</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="btn-primary flex items-center gap-2 flex-shrink-0 min-h-[44px] touch-manipulation"
        >
          <PlusIcon className="h-5 w-5" />
          פגישה חדשה
        </button>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex items-center gap-4">
          <button
            onClick={() => setFilter('all')}
            className={`px-4 py-2 rounded-lg font-medium transition-all ${
              filter === 'all'
                ? 'bg-therapy-calm text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            הכל ({sessions.length})
          </button>
          <button
            onClick={() => setFilter('with_summary')}
            className={`px-4 py-2 rounded-lg font-medium transition-all ${
              filter === 'with_summary'
                ? 'bg-therapy-support text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            עם סיכום ({withSummaryCount})
          </button>
          <button
            onClick={() => setFilter('no_summary')}
            className={`px-4 py-2 rounded-lg font-medium transition-all ${
              filter === 'no_summary'
                ? 'bg-therapy-warm text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            ללא סיכום ({noSummaryCount})
          </button>
        </div>
      </div>

      {/* Sessions List */}
      <div className="space-y-4">
        {filteredSessions.map((session) => (
          <div key={session.id} className="card hover:shadow-xl transition-shadow">
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
              {/* Session Info */}
              <div className="flex items-start gap-4 flex-1 min-w-0">
                <div className="w-12 h-12 bg-therapy-calm text-white rounded-full flex items-center justify-center flex-shrink-0">
                  <DocumentTextIcon className="h-6 w-6" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2 mb-2">
                    <h3 className="text-lg font-bold">
                      {patientMap[session.patient_id] || `מטופל #${session.patient_id}`}
                    </h3>
                    {session.summary_id != null ? (
                      <span className="badge badge-approved">
                        <CheckCircleIcon className="h-4 w-4 inline ml-1" />
                        יש סיכום
                      </span>
                    ) : (
                      <span className="badge badge-draft">
                        אין סיכום
                      </span>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-3 text-sm text-gray-600">
                    <span>
                      {new Date(session.session_date).toLocaleDateString('he-IL')}
                    </span>
                    {session.duration_minutes && (
                      <span>{session.duration_minutes} דקות</span>
                    )}
                    {session.session_number && (
                      <span>פגישה #{session.session_number}</span>
                    )}
                    {session.session_type && (
                      <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full text-xs">
                        {SESSION_TYPES.find((t) => t.value === session.session_type)?.label ||
                          session.session_type}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Actions — stacked row below info on mobile, inline on desktop */}
              <div className="flex gap-2 items-center flex-shrink-0 flex-wrap sm:flex-nowrap">
                <button
                  onClick={() => openPrepModal(session)}
                  className="flex items-center gap-1.5 text-sm font-medium text-amber-700 hover:text-amber-900 border border-amber-300 hover:border-amber-500 bg-amber-50 hover:bg-amber-100 rounded-lg px-3 py-2 min-h-[44px] sm:min-h-0 transition-colors touch-manipulation flex-shrink-0"
                >
                  <SparklesIcon className="h-4 w-4" />
                  הכנה לפגישה
                </button>
                {session.summary_id == null && (
                  <button
                    onClick={() => navigate(`/sessions/${session.id}`)}
                    className="btn-primary flex-1 sm:flex-none min-h-[44px] sm:min-h-0 touch-manipulation"
                  >
                    צור סיכום
                  </button>
                )}
                {session.summary_id != null && (
                  <button
                    onClick={() => navigate(`/sessions/${session.id}`)}
                    className="btn-secondary flex-1 sm:flex-none min-h-[44px] sm:min-h-0 touch-manipulation"
                  >
                    צפה בסיכום
                  </button>
                )}
                <button
                  onClick={() => openDeleteModal(session)}
                  className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors touch-manipulation flex-shrink-0"
                  title="מחק פגישה"
                >
                  <TrashIcon className="h-5 w-5" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {filteredSessions.length === 0 && (
        <div className="card text-center py-12">
          <div className="text-6xl mb-4">📋</div>
          <h3 className="text-xl font-bold text-gray-900 mb-2">
            {sessions.length === 0 ? 'אין פגישות עדיין' : 'אין פגישות תואמות'}
          </h3>
          <p className="text-gray-600">
            {sessions.length === 0
              ? 'לחץ על "פגישה חדשה" כדי ליצור את הפגישה הראשונה'
              : 'נסה לשנות את הסינון'}
          </p>
        </div>
      )}

      {/* Delete Session Modal (2-step) */}
      {deleteTarget && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6" dir="rtl">
            {deleteStep === 1 ? (
              <>
                <h2 className="text-xl font-bold text-amber-800 mb-3">מחיקת פגישה</h2>
                <p className="text-gray-700 mb-2">
                  האם אתה בטוח שברצונך למחוק את הפגישה של{' '}
                  <strong>{patientMap[deleteTarget.patient_id] || `מטופל #${deleteTarget.patient_id}`}</strong>{' '}
                  מתאריך{' '}
                  <strong>
                    {new Date(deleteTarget.session_date).toLocaleDateString('he-IL')}
                  </strong>?
                </p>
                {deleteTarget.summary_id != null && (
                  <p className="text-sm text-amber-700 bg-amber-50 rounded-lg p-3 mb-4">
                    שים לב: לפגישה זו יש סיכום. מחיקת הפגישה תמחק גם את הסיכום לצמיתות.
                  </p>
                )}
                <div className="flex gap-3 mt-4">
                  <button
                    onClick={() => setDeleteStep(2)}
                    className="flex-1 py-2 px-4 bg-amber-600 hover:bg-amber-700 text-white font-medium rounded-lg transition-colors"
                  >
                    המשך
                  </button>
                  <button onClick={closeDeleteModal} className="btn-secondary flex-1">
                    ביטול
                  </button>
                </div>
              </>
            ) : (
              <>
                <h2 className="text-xl font-bold text-red-800 mb-3">אישור סופי — מחיקה לצמיתות</h2>
                <p className="text-gray-700 mb-4">
                  פעולה זו בלתי הפיכה. הפגישה וכל הנתונים הקשורים אליה יימחקו לצמיתות.
                </p>

                <label className="flex items-center gap-3 mb-6 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={notifyPatient}
                    onChange={(e) => setNotifyPatient(e.target.checked)}
                    className="h-4 w-4 rounded border-gray-300 text-therapy-calm"
                  />
                  <span className="text-sm text-gray-700">
                    רשום בלוג שהמטופל צריך להיות מיודע על הביטול
                  </span>
                </label>

                <div className="flex gap-3">
                  <button
                    onClick={handleDeleteSession}
                    disabled={deleting}
                    className="flex-1 py-2 px-4 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white font-medium rounded-lg transition-colors"
                  >
                    {deleting ? 'מוחק...' : 'מחק לצמיתות'}
                  </button>
                  <button onClick={closeDeleteModal} className="btn-secondary flex-1">
                    ביטול
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Prep Brief Modal */}
      {prepSession && (
        <div className="fixed inset-0 bg-black/50 flex items-start sm:items-center justify-center z-50 p-4 pt-8 sm:pt-4" dir="rtl">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg flex flex-col max-h-[calc(100vh-6rem)] sm:max-h-[85vh] animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-amber-100 flex-shrink-0 bg-amber-50 rounded-t-2xl">
              <div>
                <h2 className="text-lg font-bold text-amber-900 flex items-center gap-2">
                  <LightBulbIcon className="h-5 w-5" />
                  הכנה לפגישה
                </h2>
                <p className="text-xs text-amber-700 mt-0.5">
                  {prepSession.session_number ? `פגישה #${prepSession.session_number} · ` : ''}
                  {new Date(prepSession.session_date + 'T12:00:00').toLocaleDateString('he-IL')}
                  {prepSession.session_type && ` · ${SESSION_TYPES.find((t) => t.value === prepSession.session_type)?.label || prepSession.session_type}`}
                </p>
              </div>
              <button onClick={closePrepModal} className="text-amber-600 hover:text-amber-900 p-1 touch-manipulation">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>

            {/* Body */}
            <div className="overflow-y-auto flex-1 px-5 py-4">
              {prepLoading ? (
                <div className="flex flex-col items-center justify-center py-10 gap-3">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-600"></div>
                  <p className="text-sm text-amber-700">מכין תדריך...</p>
                </div>
              ) : prepError ? (
                <div className="text-amber-800 text-sm space-y-2">
                  <p>{prepError}</p>
                  <button
                    onClick={() => openPrepModal(prepSession)}
                    className="text-sm px-3 py-1 bg-amber-200 rounded-lg hover:bg-amber-300 transition-colors"
                  >
                    נסה שוב
                  </button>
                </div>
              ) : prepBrief ? (
                <PrepBriefContent brief={prepBrief} />
              ) : null}
            </div>

            {/* Footer */}
            <div className="px-5 py-4 border-t border-gray-100 flex-shrink-0">
              <button
                onClick={() => navigate(`/sessions/${prepSession.id}`)}
                className="btn-secondary w-full min-h-[44px] touch-manipulation"
              >
                פתח פגישה מלאה
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Session Modal
          Mobile: top-aligned with mt-8 breathing room, scrollable content, sticky header+footer
          Desktop: vertically centered, max 85vh */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-start sm:items-center justify-center z-50 p-4 pt-8 sm:pt-4" dir="rtl">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg flex flex-col max-h-[calc(100vh-6rem)] sm:max-h-[85vh] overflow-x-hidden">

            {/* Sticky header */}
            <div className="flex items-center justify-between px-3 sm:px-6 py-4 border-b border-gray-100 flex-shrink-0">
              <h2 className="text-xl font-bold text-gray-900">פגישה חדשה</h2>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-gray-400 hover:text-gray-600 p-1 touch-manipulation"
              >
                <XMarkIcon className="h-6 w-6" />
              </button>
            </div>

            {/* Scrollable form body + sticky footer */}
            <form onSubmit={handleCreateSession} className="flex flex-col flex-1 min-h-0">
              <div className="overflow-y-auto flex-1 px-3 sm:px-6 py-4 space-y-4">

                {/* Patient Select */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    מטופל/ת *
                  </label>
                  {patients.length === 0 ? (
                    <div className="text-sm text-amber-700 bg-amber-50 rounded-lg p-3">
                      לא נמצאו מטופלים.{' '}
                      <button
                        type="button"
                        onClick={() => {
                          setShowCreateModal(false)
                          navigate('/patients')
                        }}
                        className="underline font-medium"
                      >
                        צור מטופל חדש
                      </button>{' '}
                      לפני יצירת פגישה.
                    </div>
                  ) : (
                    <select
                      value={formData.patient_id}
                      onChange={(e) =>
                        setFormData((prev) => ({ ...prev, patient_id: e.target.value }))
                      }
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
                      required
                    >
                      <option value="">בחר מטופל/ת...</option>
                      {[...patients]
                        .sort((a, b) => a.full_name.localeCompare(b.full_name, 'he'))
                        .map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.full_name}
                          </option>
                        ))}
                    </select>
                  )}
                </div>

                {/* Date */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    תאריך *
                  </label>
                  <input
                    type="date"
                    value={formData.session_date}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, session_date: e.target.value }))
                    }
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
                    required
                  />
                </div>

                {/* Start Time */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    שעת התחלה
                  </label>
                  <select
                    value={formData.start_time}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, start_time: e.target.value }))
                    }
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

                {/* Duration */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    משך (דקות)
                  </label>
                  <input
                    type="number"
                    value={formData.duration_minutes}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        duration_minutes: Number(e.target.value),
                      }))
                    }
                    min={10}
                    max={180}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
                  />
                </div>

                {/* Session Type */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    סוג פגישה
                  </label>
                  <select
                    value={formData.session_type}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, session_type: e.target.value }))
                    }
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
                  >
                    {SESSION_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                </div>

                {createError && (
                  <div className="text-red-600 text-sm bg-red-50 rounded-lg p-3">
                    {createError}
                  </div>
                )}
              </div>

              {/* Sticky footer — always visible */}
              <div className="flex gap-3 px-3 sm:px-6 py-4 border-t border-gray-100 flex-shrink-0">
                <button
                  type="submit"
                  disabled={creating || patients.length === 0}
                  className="btn-primary flex-1 disabled:opacity-50 min-h-[44px] touch-manipulation"
                >
                  {creating ? 'יוצר...' : 'צור פגישה'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="btn-secondary flex-1 min-h-[44px] touch-manipulation"
                >
                  ביטול
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

function PrepBriefContent({ brief }: { brief: PrepBrief }) {
  return (
    <div className="space-y-4 text-sm">
      {/* מה היה עד עכשיו */}
      {brief.history_summary.length > 0 && (
        <div>
          <h3 className="font-semibold text-amber-900 mb-1.5">📖 מה היה עד עכשיו</h3>
          <ul className="list-disc list-inside text-gray-700 space-y-1 leading-relaxed">
            {brief.history_summary.map((item, i) => <li key={i}>{item}</li>)}
          </ul>
        </div>
      )}

      {/* מה היה בפגישה האחרונה */}
      {brief.last_session.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <h3 className="font-semibold text-blue-900 mb-1.5">🕐 מה היה בפגישה האחרונה</h3>
          <ul className="list-disc list-inside text-blue-800 space-y-1 leading-relaxed">
            {brief.last_session.map((item, i) => <li key={i}>{item}</li>)}
          </ul>
        </div>
      )}

      {/* משימות לבדיקה היום */}
      {brief.tasks_to_check.length > 0 && (
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-3">
          <h3 className="font-semibold text-orange-900 mb-1.5">✅ משימות לבדיקה היום</h3>
          <ul className="list-disc list-inside text-orange-800 space-y-1 leading-relaxed">
            {brief.tasks_to_check.map((item, i) => <li key={i}>{item}</li>)}
          </ul>
        </div>
      )}

      {/* על מה כדאי להתמקד */}
      {brief.focus_for_today.length > 0 && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3">
          <h3 className="font-semibold text-green-900 mb-1.5">🎯 על מה כדאי להתמקד היום</h3>
          <ul className="list-disc list-inside text-green-800 space-y-1 leading-relaxed">
            {brief.focus_for_today.map((item, i) => <li key={i}>{item}</li>)}
          </ul>
        </div>
      )}

      {/* שים לב */}
      {brief.watch_out_for.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3">
          <h3 className="font-semibold text-red-800 mb-1.5">⚠️ שים לב</h3>
          <ul className="list-disc list-inside text-red-700 space-y-1 leading-relaxed">
            {brief.watch_out_for.map((item, i) => <li key={i}>{item}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}
