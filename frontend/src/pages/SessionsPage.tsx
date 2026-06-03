import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  DocumentTextIcon,
  CheckCircleIcon,
  PlusIcon,
  XMarkIcon,
  TrashIcon,
  SparklesIcon,
  LightBulbIcon,
  PencilIcon,
} from '@heroicons/react/24/outline'
import { sessionsAPI, patientsAPI, therapistAPI } from '@/lib/api'
import { usePrepStream } from '@/hooks/usePrepStream'
import { formatDateIL } from '@/lib/dateUtils'
import { strings } from '@/i18n/he'

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
  summary_status?: string | null
  created_at: string
  is_paid?: boolean
  recurrence_rule?: string | null
  recurrence_parent_id?: number | null
}

interface Patient {
  id: number
  full_name: string
}

const SESSION_TYPES = [
  { value: 'individual', label: strings.patients.session_type_individual },
  { value: 'couples', label: strings.patients.session_type_couples },
  { value: 'family', label: strings.patients.session_type_family },
  { value: 'group', label: strings.patients.session_type_group },
  { value: 'intake', label: strings.patients.session_type_intake },
  { value: 'follow_up', label: strings.patients.session_type_followup },
]

const todayStr = new Date().toISOString().split('T')[0]

export default function SessionsPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [sessions, setSessions] = useState<Session[]>([])
  const [patients, setPatients] = useState<Patient[]>([])
  const [patientMap, setPatientMap] = useState<Record<number, string>>({})
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'all' | 'with_summary' | 'no_summary'>(
    (searchParams.get('filter') as 'all' | 'with_summary' | 'no_summary') || 'all'
  )

  // Delete session modal state
  const [deleteTarget, setDeleteTarget] = useState<Session | null>(null)
  const [deleteStep, setDeleteStep] = useState<1 | 2>(1)
  const [deleting, setDeleting] = useState(false)
  const [notifyPatient, setNotifyPatient] = useState(false)

  // Inline prep accordion state — one session at a time
  const [expandedPrepSessionId, setExpandedPrepSessionId] = useState<number | null>(null)
  const prepStream = usePrepStream()

  // Edit session modal state
  const [editTarget, setEditTarget] = useState<Session | null>(null)
  const [editDate, setEditDate] = useState('')
  const [editTime, setEditTime] = useState('')
  const [editDurMinutes, setEditDurMinutes] = useState('50')
  const [saving, setSaving] = useState(false)

  // Create session modal state
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')
  const [formData, setFormData] = useState({
    patient_id: '',
    session_date: new Date().toISOString().split('T')[0],
    start_time: '',
    session_type: 'individual',
    duration_minutes: '50',
    notify_patient: false,
    recurrence_rule: '' as '' | 'weekly' | 'biweekly' | 'monthly',
    recurrence_ends_at: '',
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
      const [, , profile] = await Promise.all([
        loadSessions(),
        loadPatients(),
        therapistAPI.getProfile().catch(() => null),
      ])
      if ((profile as any)?.default_session_duration) {
        setFormData((prev) => ({ ...prev, duration_minutes: String((profile as any).default_session_duration) }))
      }
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
      setCreateError(strings.sessions.error_patient_required)
      return
    }
    const dur = parseInt(formData.duration_minutes, 10)
    if (!formData.duration_minutes || isNaN(dur) || dur <= 0) {
      setCreateError(strings.sessions.error_duration_required)
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
        duration_minutes: dur,
        start_time: startTime,
        notify_patient: formData.notify_patient,
        recurrence_rule: formData.recurrence_rule || null,
        recurrence_ends_at: formData.recurrence_rule && formData.recurrence_ends_at ? formData.recurrence_ends_at : null,
      })

      setShowCreateModal(false)
      setFormData((prev) => ({
        patient_id: '',
        session_date: new Date().toISOString().split('T')[0],
        start_time: '',
        session_type: 'individual',
        duration_minutes: prev.duration_minutes, // preserve default from profile
        notify_patient: false,
        recurrence_rule: '',
        recurrence_ends_at: '',
      }))
      await loadSessions()
    } catch (error: any) {
      setCreateError(error.response?.data?.detail || strings.sessions.error_create_generic)
    } finally {
      setCreating(false)
    }
  }

  // Lock body scroll whenever a modal is open
  useEffect(() => {
    const locked = !!deleteTarget || showCreateModal || !!editTarget
    document.body.style.overflow = locked ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [deleteTarget, showCreateModal, editTarget])

  const togglePrepAccordion = (session: Session) => {
    if (expandedPrepSessionId === session.id) {
      setExpandedPrepSessionId(null)
      prepStream.reset()
    } else {
      setExpandedPrepSessionId(session.id)
      prepStream.start(session.id)
    }
  }

  const openEditModal = (session: Session) => {
    setEditTarget(session)
    setEditDate(session.session_date)
    const timeStr = session.session_date ? '' : ''
    setEditTime(timeStr)
    setEditDurMinutes(session.duration_minutes ? String(session.duration_minutes) : '50')
  }

  const handleSaveEdit = async () => {
    if (!editTarget) return
    setSaving(true)
    try {
      const startTime = editTime ? `${editDate}T${editTime}:00` : undefined
      await sessionsAPI.update(editTarget.id, {
        session_date: editDate,
        ...(startTime ? { start_time: startTime } : {}),
        ...(editDurMinutes ? { duration_minutes: parseInt(editDurMinutes, 10) } : {}),
      })
      setSessions((prev) => prev.map((s) =>
        s.id === editTarget.id
          ? {
              ...s,
              session_date: editDate,
              ...(startTime ? { start_time: startTime } : {}),
              ...(editDurMinutes ? { duration_minutes: parseInt(editDurMinutes, 10) } : {}),
            }
          : s
      ))
      setEditTarget(null)
    } catch (error) {
      console.error('Error updating session:', error)
    } finally {
      setSaving(false)
    }
  }

  const [creatingNext, setCreatingNext] = useState<number | null>(null)
  const handleCreateNextOccurrence = async (sessionId: number) => {
    setCreatingNext(sessionId)
    try {
      await sessionsAPI.createNextOccurrence(sessionId)
      await loadSessions()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'שגיאה ביצירת הפגישה הבאה')
    } finally {
      setCreatingNext(null)
    }
  }

  const handleTogglePaid = async (session: Session) => {
    try {
      await sessionsAPI.setPaid(session.id, !session.is_paid)
      setSessions((prev) => prev.map((s) =>
        s.id === session.id ? { ...s, is_paid: !s.is_paid } : s
      ))
    } catch (error) {
      console.error('Error toggling paid status:', error)
    }
  }

  const filteredSessions = sessions.filter((session) => {
    if (filter === 'with_summary') return session.summary_id != null
    if (filter === 'no_summary') return session.summary_id == null
    return true
  })

  const noSummaryCount = sessions.filter((s) => s.summary_id == null).length
  const approvedCount = sessions.filter((s) => s.summary_status === 'approved').length
  const draftCount = sessions.filter((s) => s.summary_id != null && s.summary_status !== 'approved').length

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" dir="rtl">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-therapy-calm mx-auto mb-4"></div>
          <p className="text-gray-600">{strings.sessions.loading}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in" dir="rtl">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">{strings.sessions.page_title}</h1>
          <p className="text-gray-600 mt-1 sm:mt-2 text-sm sm:text-base">{strings.sessions.page_subtitle}</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="btn-primary flex items-center gap-2 flex-shrink-0 min-h-[44px] touch-manipulation"
        >
          <PlusIcon className="h-5 w-5" />
          {strings.sessions.new_session_button}
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
            {strings.sessions.filter_all} ({sessions.length})
          </button>
          <button
            onClick={() => setFilter('with_summary')}
            className={`px-4 py-2 rounded-lg font-medium transition-all ${
              filter === 'with_summary'
                ? 'bg-therapy-support text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {strings.sessions.filter_with_summary} ({approvedCount} מאושר{approvedCount !== 1 ? 'ים' : ''} · {draftCount} טיוטה)
          </button>
          <button
            onClick={() => setFilter('no_summary')}
            className={`px-4 py-2 rounded-lg font-medium transition-all ${
              filter === 'no_summary'
                ? 'bg-therapy-warm text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {strings.sessions.filter_no_summary} ({noSummaryCount})
          </button>
        </div>
      </div>

      {/* Sessions List */}
      <div className="space-y-4">
        {filteredSessions.map((session) => {
          const isPast = session.session_date < todayStr
          const warnPast = session.summary_id == null && isPast
          const isPrepExpanded = expandedPrepSessionId === session.id

          return (
            <div
              key={session.id}
              className={`card hover:shadow-xl transition-shadow ${
                warnPast ? 'border-l-4 border-l-amber-400 bg-amber-50' : ''
              }`}
            >
              {warnPast && (
                <div className="mb-3">
                  <span className="text-xs font-medium text-amber-700 bg-amber-100 border border-amber-200 rounded-md px-2 py-0.5">
                    {strings.sessions.badge_past_no_summary}
                  </span>
                </div>
              )}

              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                {/* Session Info */}
                <div className="flex items-start gap-4 flex-1 min-w-0">
                  <div className={`w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0 ${
                    warnPast ? 'bg-amber-500 text-white' : 'bg-therapy-calm text-white'
                  }`}>
                    <DocumentTextIcon className="h-6 w-6" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-2">
                      <h3 className="text-lg font-bold">
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); navigate(`/patients/${session.patient_id}`) }}
                          className="hover:text-therapy-calm hover:underline transition-colors"
                        >
                          {patientMap[session.patient_id] || `מטופל #${session.patient_id}`}
                        </button>
                      </h3>
                      {session.summary_status === 'approved' ? (
                        <span className="badge badge-approved text-xs">
                          <CheckCircleIcon className="h-3 w-3 inline ml-1" />
                          {strings.sessions.badge_approved}
                        </span>
                      ) : session.summary_id != null ? (
                        <span className="badge badge-draft text-xs">
                          {strings.sessions.badge_draft}
                        </span>
                      ) : (
                        <span className="badge text-xs bg-gray-100 text-gray-500">
                          {strings.sessions.badge_none}
                        </span>
                      )}
                      {/* Paid toggle — only for sessions with a summary */}
                      {session.summary_id != null && (
                        <button
                          onClick={() => handleTogglePaid(session)}
                          title={session.is_paid ? 'שולם — לחץ לביטול' : 'לא שולם — לחץ לסימון כשולם'}
                          className="flex items-center gap-1.5 touch-manipulation group"
                        >
                          <span className={`relative inline-flex h-5 w-9 flex-shrink-0 rounded-full border-2 border-transparent transition-colors duration-200 ${
                            session.is_paid ? 'bg-green-500' : 'bg-gray-300 group-hover:bg-gray-400'
                          }`}>
                            <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform duration-200 ${
                              session.is_paid ? 'translate-x-4' : 'translate-x-0'
                            }`} />
                          </span>
                          <span className={`text-xs font-medium ${session.is_paid ? 'text-green-700' : 'text-gray-500'}`}>
                            {session.is_paid ? 'שולם' : 'לא שולם'}
                          </span>
                        </button>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-3 text-sm text-gray-600">
                      <span>{formatDateIL(session.session_date)}</span>
                      {session.duration_minutes && (
                        <span>{session.duration_minutes} {strings.sessions.minutes_label}</span>
                      )}
                      {session.session_number && (
                        <span>{strings.sessions.session_number_prefix}{session.session_number}</span>
                      )}
                      {session.session_type && (
                        <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full text-xs">
                          {SESSION_TYPES.find((t) => t.value === session.session_type)?.label ||
                            session.session_type}
                        </span>
                      )}
                      {session.recurrence_rule && (
                        <span className="px-2 py-0.5 bg-purple-50 text-purple-700 rounded-full text-xs">
                          🔁 {session.recurrence_rule === 'weekly' ? 'שבועי' : session.recurrence_rule === 'biweekly' ? 'דו-שבועי' : 'חודשי'}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex gap-2 items-center flex-shrink-0 flex-wrap sm:flex-nowrap">
                  {/* Prep toggle button: only for upcoming/today sessions without an approved summary */}
                  {session.session_date >= todayStr && session.summary_status !== 'approved' && (
                    <button
                      onClick={() => togglePrepAccordion(session)}
                      className={`flex items-center gap-1.5 text-sm font-medium border rounded-lg px-3 py-2 min-h-[44px] sm:min-h-0 transition-colors touch-manipulation flex-shrink-0 ${
                        isPrepExpanded
                          ? 'text-amber-900 border-amber-500 bg-amber-100'
                          : 'text-amber-700 hover:text-amber-900 border-amber-300 hover:border-amber-500 bg-amber-50 hover:bg-amber-100'
                      }`}
                    >
                      <SparklesIcon className="h-4 w-4" />
                      {strings.sessions.prep_button}
                    </button>
                  )}
                  {session.summary_id == null && (
                    <button
                      onClick={() => navigate(`/sessions/${session.id}`)}
                      className="btn-primary flex-1 sm:flex-none min-h-[44px] sm:min-h-0 touch-manipulation"
                    >
                      {strings.sessions.create_summary_button}
                    </button>
                  )}
                  {session.summary_status === 'approved' && (
                    <button
                      onClick={() => navigate(`/sessions/${session.id}`)}
                      className="btn-success flex-1 sm:flex-none min-h-[44px] sm:min-h-0 touch-manipulation"
                    >
                      {strings.sessions.view_summary_button}
                    </button>
                  )}
                  {session.summary_id != null && session.summary_status !== 'approved' && (
                    <button
                      onClick={() => navigate(`/sessions/${session.id}`)}
                      className="btn-primary flex-1 sm:flex-none min-h-[44px] sm:min-h-0 touch-manipulation"
                    >
                      {strings.sessions.edit_draft_button}
                    </button>
                  )}
                  {/* Next occurrence button — for past recurring sessions */}
                  {session.recurrence_rule && session.session_date < todayStr && (
                    <button
                      onClick={() => handleCreateNextOccurrence(session.id)}
                      disabled={creatingNext === session.id}
                      className="flex items-center gap-1 text-xs font-medium text-purple-700 border border-purple-300 bg-purple-50 hover:bg-purple-100 rounded-lg px-2.5 py-1.5 transition-colors touch-manipulation flex-shrink-0 disabled:opacity-50"
                      title="צור פגישה הבאה בסדרה"
                    >
                      {creatingNext === session.id ? '...' : '🔁 הבאה'}
                    </button>
                  )}
                  {/* Edit session button */}
                  <button
                    onClick={() => openEditModal(session)}
                    className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors touch-manipulation flex-shrink-0"
                    title="ערוך תאריך/שעה"
                  >
                    <PencilIcon className="h-5 w-5" />
                  </button>
                  <button
                    onClick={() => openDeleteModal(session)}
                    className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors touch-manipulation flex-shrink-0"
                    title="מחק פגישה"
                  >
                    <TrashIcon className="h-5 w-5" />
                  </button>
                </div>
              </div>

              {/* Inline prep accordion */}
              {isPrepExpanded && (
                <div className="mt-4 pt-4 border-t border-amber-200 bg-amber-50 rounded-lg p-4 -mx-1">
                  <div className="flex items-center gap-2 mb-3">
                    <LightBulbIcon className="h-4 w-4 text-amber-700" />
                    <span className="text-sm font-bold text-amber-900">{strings.sessions.prep_modal_title}</span>
                  </div>
                  {prepStream.phase === 'extracting' || (prepStream.phase === 'rendering') ? (
                    <div className="flex items-center gap-2 text-amber-700 text-sm py-4 justify-center">
                      <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-amber-600"></div>
                      <span>
                        {prepStream.phase === 'extracting'
                          ? strings.sessions.extracting_summaries
                          : strings.sessions.generating_brief}
                      </span>
                    </div>
                  ) : prepStream.phase === 'done' ? (
                    <p className="text-sm text-amber-900 leading-relaxed whitespace-pre-wrap">{prepStream.text}</p>
                  ) : prepStream.phase === 'error' ? (
                    <div className="text-amber-800 text-sm space-y-2">
                      <p>{prepStream.error}</p>
                      <button
                        onClick={() => { prepStream.reset(); prepStream.start(session.id) }}
                        className="text-sm px-3 py-1 bg-amber-200 rounded-lg hover:bg-amber-300 transition-colors"
                      >
                        {strings.sessions.retry_button}
                      </button>
                    </div>
                  ) : null}
                  <div className="mt-3 pt-3 border-t border-amber-200">
                    <button
                      onClick={() => navigate(`/sessions/${session.id}`)}
                      className="btn-secondary text-sm w-full min-h-[36px]"
                    >
                      {strings.sessions.create_summary_button}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {filteredSessions.length === 0 && (
        <div className="card text-center py-12">
          <div className="text-6xl mb-4">📋</div>
          <h3 className="text-xl font-bold text-gray-900 mb-2">
            {sessions.length === 0 ? strings.sessions.empty_no_sessions_title : strings.sessions.empty_no_match_title}
          </h3>
          <p className="text-gray-600">
            {sessions.length === 0
              ? strings.sessions.empty_no_sessions_subtitle
              : strings.sessions.empty_no_match_subtitle}
          </p>
        </div>
      )}

      {/* Delete Session Modal (2-step) */}
      {deleteTarget && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6" dir="rtl">
            {deleteStep === 1 ? (
              <>
                <h2 className="text-xl font-bold text-amber-800 mb-3">{strings.sessions.delete_title}</h2>
                <p className="text-gray-700 mb-2">
                  {strings.sessions.delete_confirm_prefix}{' '}
                  <strong>{patientMap[deleteTarget.patient_id] || `מטופל #${deleteTarget.patient_id}`}</strong>{' '}
                  {strings.sessions.delete_date_label}{' '}
                  <strong>{formatDateIL(deleteTarget.session_date)}</strong>?
                </p>
                {deleteTarget.summary_id != null && (
                  <p className="text-sm text-amber-700 bg-amber-50 rounded-lg p-3 mb-4">
                    {strings.sessions.delete_summary_warning}
                  </p>
                )}
                <div className="flex gap-3 mt-4">
                  <button
                    onClick={() => setDeleteStep(2)}
                    className="flex-1 py-2 px-4 bg-amber-600 hover:bg-amber-700 text-white font-medium rounded-lg transition-colors"
                  >
                    {strings.sessions.continue_button}
                  </button>
                  <button onClick={closeDeleteModal} className="btn-secondary flex-1">
                    ביטול
                  </button>
                </div>
              </>
            ) : (
              <>
                <h2 className="text-xl font-bold text-red-800 mb-3">{strings.sessions.delete_title_final}</h2>
                <p className="text-gray-700 mb-4">
                  {strings.sessions.delete_irreversible_warning}
                </p>

                <label className="flex items-center gap-3 mb-6 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={notifyPatient}
                    onChange={(e) => setNotifyPatient(e.target.checked)}
                    className="h-4 w-4 rounded border-gray-300 text-therapy-calm"
                  />
                  <span className="text-sm text-gray-700">
                    {strings.sessions.delete_notify_checkbox}
                  </span>
                </label>

                <div className="flex gap-3">
                  <button
                    onClick={handleDeleteSession}
                    disabled={deleting}
                    className="flex-1 py-2 px-4 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white font-medium rounded-lg transition-colors"
                  >
                    {deleting ? strings.sessions.deleting_loading : strings.sessions.delete_permanently_button}
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

      {/* Edit Session Modal */}
      {editTarget && (
        <div className="fixed inset-0 bg-black/50 flex items-start sm:items-center justify-center z-50 p-4 pt-8 sm:pt-4" dir="rtl">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <h2 className="text-xl font-bold text-gray-900">עריכת פגישה</h2>
              <button onClick={() => setEditTarget(null)} className="text-gray-400 hover:text-gray-600 p-1 touch-manipulation">
                <XMarkIcon className="h-6 w-6" />
              </button>
            </div>

            <div className="px-6 py-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{strings.sessions.date_label}</label>
                <input
                  type="date"
                  value={editDate}
                  onChange={(e) => setEditDate(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{strings.sessions.start_time_label}</label>
                <select
                  value={editTime}
                  onChange={(e) => setEditTime(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
                >
                  <option value="">{strings.sessions.time_placeholder}</option>
                  {Array.from({ length: 14 }, (_, i) => i + 7).map((hour) =>
                    [0, 30].map((min) => {
                      const val = `${String(hour).padStart(2, '0')}:${String(min).padStart(2, '0')}`
                      return <option key={val} value={val}>{val}</option>
                    })
                  )}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{strings.sessions.duration_label}</label>
                <input
                  type="number"
                  value={editDurMinutes}
                  onChange={(e) => setEditDurMinutes(e.target.value)}
                  min={1}
                  max={360}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
                />
              </div>
            </div>

            <div className="flex gap-3 px-6 py-4 border-t border-gray-100">
              <button
                onClick={handleSaveEdit}
                disabled={saving || !editDate}
                className="btn-primary flex-1 disabled:opacity-50 min-h-[44px] touch-manipulation"
              >
                {saving ? 'שומר...' : 'שמור'}
              </button>
              <button
                onClick={() => setEditTarget(null)}
                className="btn-secondary flex-1 min-h-[44px] touch-manipulation"
              >
                ביטול
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create Session Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-start sm:items-center justify-center z-50 p-4 pt-8 sm:pt-4" dir="rtl">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg flex flex-col max-h-[calc(100vh-6rem)] sm:max-h-[85vh] overflow-x-hidden">

            <div className="flex items-center justify-between px-3 sm:px-6 py-4 border-b border-gray-100 flex-shrink-0">
              <h2 className="text-xl font-bold text-gray-900">{strings.sessions.create_modal_title}</h2>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-gray-400 hover:text-gray-600 p-1 touch-manipulation"
              >
                <XMarkIcon className="h-6 w-6" />
              </button>
            </div>

            <form onSubmit={handleCreateSession} className="flex flex-col flex-1 min-h-0">
              <div className="overflow-y-auto flex-1 px-3 sm:px-6 py-4 space-y-4">

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {strings.sessions.patient_label}
                  </label>
                  {patients.length === 0 ? (
                    <div className="text-sm text-amber-700 bg-amber-50 rounded-lg p-3">
                      {strings.sessions.no_patients_message}{' '}
                      <button
                        type="button"
                        onClick={() => {
                          setShowCreateModal(false)
                          navigate('/patients')
                        }}
                        className="underline font-medium"
                      >
                        {strings.sessions.create_patient_link}
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
                      <option value="">{strings.sessions.patient_placeholder}</option>
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

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {strings.sessions.date_label}
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

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {strings.sessions.start_time_label}
                  </label>
                  <select
                    value={formData.start_time}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, start_time: e.target.value }))
                    }
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
                  >
                    <option value="">{strings.sessions.time_placeholder}</option>
                    {Array.from({ length: 14 }, (_, i) => i + 7).map((hour) =>
                      [0, 30].map((min) => {
                        const val = `${String(hour).padStart(2, '0')}:${String(min).padStart(2, '0')}`
                        return <option key={val} value={val}>{val}</option>
                      })
                    )}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {strings.sessions.duration_label}
                  </label>
                  <input
                    type="number"
                    value={formData.duration_minutes}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, duration_minutes: e.target.value }))
                    }
                    min={1}
                    max={360}
                    placeholder={strings.sessions.duration_placeholder}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {strings.sessions.session_type_label}
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

                {/* Recurrence */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">חזרתיות</label>
                  <select
                    value={formData.recurrence_rule}
                    onChange={(e) => setFormData((prev) => ({ ...prev, recurrence_rule: e.target.value as any }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
                  >
                    <option value="">פגישה חד-פעמית</option>
                    <option value="weekly">כל שבוע</option>
                    <option value="biweekly">כל שבועיים</option>
                    <option value="monthly">כל חודש</option>
                  </select>
                </div>
                {formData.recurrence_rule && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">עד תאריך (אופציונלי)</label>
                    <input
                      type="date"
                      value={formData.recurrence_ends_at}
                      onChange={(e) => setFormData((prev) => ({ ...prev, recurrence_ends_at: e.target.value }))}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
                    />
                  </div>
                )}

                <div className="flex items-center justify-between py-1">
                  <div>
                    <div className="text-sm font-medium text-gray-700">{strings.sessions.notify_patient_label}</div>
                    <div className="text-xs text-gray-400 mt-0.5">{strings.sessions.notify_patient_sublabel}</div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, notify_patient: !prev.notify_patient }))}
                    className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none ${
                      formData.notify_patient ? 'bg-therapy-calm' : 'bg-gray-200'
                    }`}
                  >
                    <span
                      className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition duration-200 ${
                        formData.notify_patient ? '-translate-x-5' : 'translate-x-0'
                      }`}
                    />
                  </button>
                </div>

                {createError && (
                  <div className="text-red-600 text-sm bg-red-50 rounded-lg p-3">
                    {createError}
                  </div>
                )}
              </div>

              <div className="flex gap-3 px-3 sm:px-6 py-4 border-t border-gray-100 flex-shrink-0">
                <button
                  type="submit"
                  disabled={creating || patients.length === 0}
                  className="btn-primary flex-1 disabled:opacity-50 min-h-[44px] touch-manipulation"
                >
                  {creating ? strings.sessions.create_loading : strings.sessions.create_button}
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
