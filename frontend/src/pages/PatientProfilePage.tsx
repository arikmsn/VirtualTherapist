/**
 * PatientProfilePage — hub for a single patient.
 *
 * Tabs:
 *   - פגישות (Sessions timeline)
 *   - סיכומים + תובנות (Summaries + AI Insight)
 *   - זרימה בין פגישות (In-Between Flow — placeholder for Phase C)
 *
 * PRD reference: Feature 1 (Patient Profile hub), Feature 3 (Insight Summary)
 */

import { useState, useEffect } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import MessagesCenter from '@/components/MessagesCenter'
import PhoneInput from '@/components/PhoneInput'
import {
  ArrowRightIcon,
  CalendarIcon,
  DocumentTextIcon,
  SparklesIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  PlusIcon,
  ChatBubbleLeftRightIcon,
  XMarkIcon,
  PencilSquareIcon,
  PhoneIcon,
  EnvelopeIcon,
  TrashIcon,
  BookOpenIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline'
import { patientsAPI, sessionsAPI, patientSummariesAPI, exercisesAPI, patientNotesAPI } from '@/lib/api'

const SESSION_TYPES = [
  { value: 'individual', label: 'פרטני' },
  { value: 'couples', label: 'זוגי' },
  { value: 'family', label: 'משפחתי' },
  { value: 'group', label: 'קבוצתי' },
  { value: 'intake', label: 'אינטייק' },
  { value: 'follow_up', label: 'מעקב' },
]

// --- Types ---

interface ExerciseItem {
  id: number
  description: string
  completed: boolean
  completed_at: string | null
  session_summary_id: number | null
  created_at: string
}

interface Patient {
  id: number
  full_name: string
  phone?: string
  email?: string
  status: string
  start_date?: string
  primary_concerns?: string
  allow_ai_contact: boolean
  completed_exercises_count: number
  created_at: string
}

interface Session {
  id: number
  session_date: string
  session_type?: string
  duration_minutes?: number
  session_number?: number
  has_recording: boolean
  summary_id?: number
  created_at: string
}

interface SummaryItem {
  session_id: number
  session_date: string
  session_number: number | null
  summary: {
    id: number
    full_summary: string | null
    status: string
    approved_by_therapist: boolean
    topics_discussed: string[] | null
    mood_observed: string | null
    created_at: string
  }
}

interface PatientInsight {
  overview: string
  progress: string
  patterns: string[]
  risks: string[]
  suggestions_for_next_sessions: string[]
}

interface NoteItem {
  id: number
  content: string
  created_at: string
}

interface PrepBrief {
  quick_overview: string
  recent_progress: string
  key_points_to_revisit: string[]
  watch_out_for: string[]
  ideas_for_this_session: string[]
}

interface PrepModalSession {
  id: number
  session_date: string
  session_number?: number
}

type Tab = 'sessions' | 'summaries' | 'inbetween' | 'notes'

// --- Component ---

export default function PatientProfilePage() {
  const { patientId } = useParams<{ patientId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const pid = Number(patientId)

  const initialTab = (location.state as { initialTab?: Tab } | null)?.initialTab ?? 'sessions'
  const [tab, setTab] = useState<Tab>(initialTab)

  // Notebook state
  const [notebookText, setNotebookText] = useState('')
  const [notebookSaving, setNotebookSaving] = useState(false)
  const [notes, setNotes] = useState<NoteItem[]>([])
  const [notesLoading, setNotesLoading] = useState(false)
  const [viewingNote, setViewingNote] = useState<NoteItem | null>(null)

  // AI toggle saving state + mobile info popover
  const [toggleAiSaving, setToggleAiSaving] = useState(false)
  const [showAiInfo, setShowAiInfo] = useState(false)

  // Edit patient modal
  const [showEditPatient, setShowEditPatient] = useState(false)
  const [editForm, setEditForm] = useState({ full_name: '', phone: '', email: '' })
  const [editSaving, setEditSaving] = useState(false)
  const [editError, setEditError] = useState('')

  // Mark inactive modal (2-step)
  const [showInactiveConfirm, setShowInactiveConfirm] = useState(false)
  const [inactiveStep, setInactiveStep] = useState(1)
  const [inactiveSaving, setInactiveSaving] = useState(false)

  // Exercises
  const [exercises, setExercises] = useState<ExerciseItem[]>([])

  // New Session modal
  const [showNewSession, setShowNewSession] = useState(false)
  const [newSessionForm, setNewSessionForm] = useState({
    session_date: new Date().toISOString().split('T')[0],
    start_time: '',
    session_type: 'individual',
    duration_minutes: 50,
  })
  const [newSessionCreating, setNewSessionCreating] = useState(false)
  const [newSessionError, setNewSessionError] = useState('')

  // Patient data
  const [patient, setPatient] = useState<Patient | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Sessions
  const [sessions, setSessions] = useState<Session[]>([])
  const [sessionsLoading, setSessionsLoading] = useState(false)

  // Summaries
  const [summaries, setSummaries] = useState<SummaryItem[]>([])
  const [summariesLoading, setSummariesLoading] = useState(false)

  // Insight
  const [insight, setInsight] = useState<PatientInsight | null>(null)
  const [insightLoading, setInsightLoading] = useState(false)
  const [insightError, setInsightError] = useState('')

  // Prep brief modal
  const [prepModalSession, setPrepModalSession] = useState<PrepModalSession | null>(null)
  const [prepBrief, setPrepBrief] = useState<PrepBrief | null>(null)
  const [prepLoading, setPrepLoading] = useState(false)
  const [prepError, setPrepError] = useState('')

  const approvedCount = summaries.filter(
    (s) => s.summary.status === 'approved' || s.summary.approved_by_therapist
  ).length

  // Lock body scroll when any modal is open
  useEffect(() => {
    const locked = showEditPatient || showInactiveConfirm || showNewSession || prepModalSession !== null
    document.body.style.overflow = locked ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [showEditPatient, showInactiveConfirm, showNewSession, prepModalSession])

  // Load patient + sessions on mount
  useEffect(() => {
    const load = async () => {
      try {
        const p = await patientsAPI.get(pid)
        setPatient(p)
      } catch (err: any) {
        setError(err.response?.data?.detail || 'שגיאה בטעינת המטופל')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [pid])

  // Load sessions when sessions tab is active
  useEffect(() => {
    if (tab !== 'sessions') return
    const load = async () => {
      setSessionsLoading(true)
      try {
        const data = await sessionsAPI.getPatientSessions(pid)
        // Sort newest first
        setSessions([...data].sort((a: Session, b: Session) => {
          // Compare YYYY-MM-DD strings directly — timezone-safe and correct
          if (b.session_date > a.session_date) return 1
          if (b.session_date < a.session_date) return -1
          // Same date: newer session (higher id) first
          return b.id - a.id
        }))
      } catch (err) {
        console.error('Error loading sessions:', err)
      } finally {
        setSessionsLoading(false)
      }
    }
    load()
  }, [pid, tab])

  // Load summaries when summaries tab is active
  useEffect(() => {
    if (tab !== 'summaries') return
    const load = async () => {
      setSummariesLoading(true)
      try {
        const data = await patientSummariesAPI.list(pid)
        setSummaries([...data].sort((a, b) => {
          if (b.session_date > a.session_date) return 1
          if (b.session_date < a.session_date) return -1
          return b.session_id - a.session_id
        }))
      } catch (err) {
        console.error('Error loading summaries:', err)
      } finally {
        setSummariesLoading(false)
      }
    }
    load()
  }, [pid, tab])

  // Load exercises for this patient
  useEffect(() => {
    const loadEx = async () => {
      try {
        const data = await exercisesAPI.list(pid)
        setExercises(data)
      } catch { /* not critical */ }
    }
    loadEx()
  }, [pid])

  // Load notebook notes when notes tab is active
  useEffect(() => {
    if (tab !== 'notes') return
    const loadNotes = async () => {
      setNotesLoading(true)
      try {
        const data = await patientNotesAPI.list(pid)
        setNotes(data)
      } catch { /* not critical */ } finally {
        setNotesLoading(false)
      }
    }
    loadNotes()
  }, [pid, tab])

  const openPrepModal = async (session: PrepModalSession) => {
    setPrepModalSession(session)
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
    setPrepModalSession(null)
    setPrepBrief(null)
    setPrepError('')
  }

  const handleToggleAiContact = async () => {
    if (!patient) return
    setToggleAiSaving(true)
    try {
      const updated = await patientsAPI.update(pid, { allow_ai_contact: !patient.allow_ai_contact })
      setPatient((prev) => prev ? { ...prev, allow_ai_contact: updated.allow_ai_contact } : prev)
    } catch (err) {
      console.error('Toggle AI error:', err)
    } finally {
      setToggleAiSaving(false)
    }
  }

  const handleSaveNote = async () => {
    if (!notebookText.trim()) return
    setNotebookSaving(true)
    try {
      const newNote = await patientNotesAPI.create(pid, notebookText)
      setNotes((prev) => [newNote, ...prev])
      setNotebookText('')
    } catch (err) {
      console.error('Save note error:', err)
    } finally {
      setNotebookSaving(false)
    }
  }

  const handleDeleteNote = async (noteId: number) => {
    try {
      await patientNotesAPI.delete(pid, noteId)
      setNotes((prev) => prev.filter((n) => n.id !== noteId))
    } catch (err) {
      console.error('Delete note error:', err)
    }
  }

  const handleEditOpen = () => {
    if (!patient) return
    setEditForm({ full_name: patient.full_name, phone: patient.phone || '', email: patient.email || '' })
    setEditError('')
    setShowEditPatient(true)
  }

  const handleEditSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editForm.full_name.trim()) return
    setEditSaving(true)
    setEditError('')
    try {
      const updated = await patientsAPI.update(pid, {
        full_name: editForm.full_name,
        phone: editForm.phone || null,
        email: editForm.email || null,
      })
      setPatient((prev) => prev ? { ...prev, ...updated } : prev)
      setShowEditPatient(false)
    } catch (err: any) {
      setEditError(err.response?.data?.detail || 'שגיאה בעדכון פרטים')
    } finally {
      setEditSaving(false)
    }
  }

  const handleMarkInactive = async () => {
    setInactiveSaving(true)
    try {
      const updated = await patientsAPI.update(pid, { status: 'inactive' })
      setPatient((prev) => prev ? { ...prev, status: updated.status } : prev)
      setShowInactiveConfirm(false)
      setInactiveStep(1)
    } catch (err: any) {
      console.error('Error marking inactive:', err)
    } finally {
      setInactiveSaving(false)
    }
  }

  const handleReactivate = async () => {
    try {
      const updated = await patientsAPI.update(pid, { status: 'active' })
      setPatient((prev) => prev ? { ...prev, status: updated.status } : prev)
    } catch (err: any) {
      console.error('Error reactivating:', err)
    }
  }

  const handleToggleExercise = async (ex: ExerciseItem) => {
    try {
      const updated = await exercisesAPI.patch(ex.id, { completed: !ex.completed })
      setExercises((prev) => prev.map((e) => (e.id === ex.id ? updated : e)))
      setPatient((prev) => prev ? {
        ...prev,
        completed_exercises_count: prev.completed_exercises_count + (updated.completed ? 1 : -1),
      } : prev)
    } catch (err) {
      console.error('Error toggling exercise:', err)
    }
  }

  const handleDeleteExercise = async (ex: ExerciseItem) => {
    try {
      await exercisesAPI.delete(ex.id)
      setExercises((prev) => prev.filter((e) => e.id !== ex.id))
      if (ex.completed) {
        setPatient((prev) => prev ? {
          ...prev,
          completed_exercises_count: Math.max(0, prev.completed_exercises_count - 1),
        } : prev)
      }
    } catch (err) {
      console.error('Error deleting exercise:', err)
    }
  }

  const handleGenerateInsight = async () => {
    setInsightLoading(true)
    setInsightError('')
    setInsight(null)
    try {
      const result = await patientSummariesAPI.generateInsight(pid)
      setInsight(result)
    } catch (err: any) {
      setInsightError(err.response?.data?.detail || 'שגיאה ביצירת סיכום העומק')
    } finally {
      setInsightLoading(false)
    }
  }

  const handleCreateSession = async (e: React.FormEvent) => {
    e.preventDefault()
    setNewSessionError('')
    setNewSessionCreating(true)
    try {
      let startTime: string | undefined
      if (newSessionForm.start_time) {
        startTime = `${newSessionForm.session_date}T${newSessionForm.start_time}:00`
      }
      const created = await sessionsAPI.create({
        patient_id: pid,
        session_date: newSessionForm.session_date,
        session_type: newSessionForm.session_type,
        duration_minutes: newSessionForm.duration_minutes,
        start_time: startTime,
      })
      setShowNewSession(false)
      setNewSessionForm({
        session_date: new Date().toISOString().split('T')[0],
        start_time: '',
        session_type: 'individual',
        duration_minutes: 50,
      })
      navigate(`/sessions/${created.id}`)
    } catch (err: any) {
      setNewSessionError(err.response?.data?.detail || 'שגיאה ביצירת הפגישה')
    } finally {
      setNewSessionCreating(false)
    }
  }

  // --- Render helpers ---

  const sessionTypeLabel = (t?: string) => {
    if (!t) return ''
    const map: Record<string, string> = {
      individual: 'אישי',
      group: 'קבוצה',
      couples: 'זוגי',
      family: 'משפחה',
    }
    return map[t] || t
  }

  const statusLabel = (s: string) => {
    const map: Record<string, string> = {
      active: 'פעיל',
      paused: 'מושהה',
      completed: 'הושלם',
      inactive: 'לא פעיל',
    }
    return map[s] || s
  }

  // --- Loading / Error states ---

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" dir="rtl">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-therapy-calm mx-auto mb-4"></div>
          <p className="text-gray-600">טוען פרטי מטופל...</p>
        </div>
      </div>
    )
  }

  if (error || !patient) {
    return (
      <div className="max-w-4xl mx-auto py-8" dir="rtl">
        <button
          onClick={() => navigate('/patients')}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowRightIcon className="h-5 w-5" />
          חזרה למטופלים
        </button>
        <div className="card text-center py-12">
          <ExclamationTriangleIcon className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <p className="text-red-700">{error || 'מטופל לא נמצא'}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-fade-in" dir="rtl">
      {/* Back nav */}
      <button
        onClick={() => navigate('/patients')}
        className="flex items-center gap-2 text-gray-600 hover:text-gray-900"
      >
        <ArrowRightIcon className="h-5 w-5" />
        חזרה למטופלים
      </button>

      {/* Patient header card */}
      <div className="card">
        <div className="flex items-start gap-4 sm:gap-5">
          {/* Avatar */}
          <div className="w-12 h-12 sm:w-16 sm:h-16 bg-therapy-calm text-white rounded-full flex items-center justify-center font-bold text-xl sm:text-2xl flex-shrink-0">
            {patient.full_name.charAt(0)}
          </div>

          <div className="flex-1 min-w-0">
            {/* Name row — wraps on mobile */}
            <div className="flex items-start gap-2 sm:gap-3 flex-wrap">
              <h1 className="text-xl sm:text-2xl font-bold text-gray-900 leading-tight">{patient.full_name}</h1>
              <span className={`badge text-xs mt-0.5 ${patient.status === 'active' ? 'badge-approved' : 'badge-draft'}`}>
                {statusLabel(patient.status)}
              </span>
            </div>
            {/* Action buttons — edit only (inactive action moved to Danger Zone) */}
            <div className="flex items-center gap-2 flex-wrap mt-2">
              <button
                onClick={handleEditOpen}
                className="flex items-center gap-1 text-xs text-gray-500 hover:text-therapy-calm border border-gray-200 rounded-lg px-2 py-1.5 hover:border-therapy-calm transition-colors min-h-[32px] touch-manipulation"
              >
                <PencilSquareIcon className="h-3.5 w-3.5" />
                ערוך פרטים
              </button>
              {patient.status === 'inactive' && (
                <button
                  onClick={handleReactivate}
                  className="text-xs text-green-600 hover:text-green-800 border border-green-200 rounded-lg px-2 py-1.5 hover:border-green-400 transition-colors min-h-[32px] touch-manipulation"
                >
                  הפעל מחדש
                </button>
              )}
            </div>

            {/* Contact info — single column on mobile to prevent overlap */}
            <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-y-1.5 gap-x-6 text-sm text-gray-600">
              {patient.phone && (
                <div className="flex items-center gap-1.5">
                  <PhoneIcon className="h-4 w-4 text-gray-400 flex-shrink-0" />
                  <span>{patient.phone}</span>
                </div>
              )}
              {patient.email && (
                <div className="flex items-center gap-1.5 min-w-0">
                  <EnvelopeIcon className="h-4 w-4 text-gray-400 flex-shrink-0" />
                  <span className="truncate">{patient.email}</span>
                </div>
              )}
              {patient.start_date && (
                <div className="flex gap-1">
                  <span className="text-gray-400">תחילת טיפול:</span>
                  <span>{new Date(patient.start_date).toLocaleDateString('he-IL')}</span>
                </div>
              )}
              <div className="flex gap-1">
                <span className="text-gray-400">נוצר:</span>
                <span>{new Date(patient.created_at).toLocaleDateString('he-IL')}</span>
              </div>
            </div>

            {/* AI toggle */}
            <div className="mt-3 flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
              <button
                onClick={handleToggleAiContact}
                disabled={toggleAiSaving}
                aria-label={patient.allow_ai_contact ? 'כבה AI' : 'הפעל AI'}
                className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out disabled:opacity-50 ${
                  patient.allow_ai_contact ? 'bg-therapy-calm' : 'bg-gray-300'
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                    patient.allow_ai_contact ? '-translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
              <div className="flex-1">
                <div className="flex items-center gap-1">
                  <span className="text-sm font-medium text-gray-900">ניתוח AI</span>
                  {/* Info icon — mobile only; tapping reveals description */}
                  <button
                    type="button"
                    className="sm:hidden text-gray-400 hover:text-gray-600 touch-manipulation"
                    onClick={() => setShowAiInfo((v) => !v)}
                    aria-label="מידע על ניתוח AI"
                  >
                    <InformationCircleIcon className="h-4 w-4" />
                  </button>
                </div>
                <div className={`text-xs text-gray-500 mt-0.5 leading-relaxed ${showAiInfo ? 'block' : 'hidden sm:block'}`}>
                  כאשר AI פעיל, המערכת יכולה לעזור לך בסיכומים, רעיונות לפגישות ומשימות בין-מפגשים עבור מטופל זה.
                </div>
              </div>
            </div>

            {patient.primary_concerns && (
              <div className="mt-3 text-sm text-gray-700 bg-gray-50 rounded-lg p-3">
                <span className="font-medium text-gray-500 block mb-1">נושאים עיקריים:</span>
                {patient.primary_concerns}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Tab navigation + content */}
      <div className="space-y-0">

      {/* Tab navigation — horizontally scrollable on mobile */}
      <div className="border-b border-gray-200 -mx-4 sm:mx-0 px-4 sm:px-0">
        <nav className="flex gap-0 -mb-px overflow-x-auto scrollbar-none">
          {([
            { key: 'sessions', label: 'פגישות', icon: CalendarIcon },
            { key: 'summaries', label: 'סיכומים ותובנות', icon: SparklesIcon },
            { key: 'inbetween', label: 'הודעות ותזכורות', icon: ChatBubbleLeftRightIcon },
            { key: 'notes', label: 'הערות', icon: BookOpenIcon },
          ] as const).map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`flex items-center gap-2 px-4 sm:px-5 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap min-h-[44px] touch-manipulation flex-shrink-0 ${
                tab === key
                  ? 'border-therapy-calm text-therapy-calm'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </nav>
      </div>

      {/* ── Sessions Tab ── */}
      {tab === 'sessions' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-600">
              {sessions.length > 0 ? `${sessions.length} פגישות` : 'אין פגישות עדיין'}
            </p>
            <button
              onClick={() => setShowNewSession(true)}
              className="btn-primary flex items-center gap-2 text-sm"
            >
              <PlusIcon className="h-4 w-4" />
              פגישה חדשה
            </button>
          </div>

          {sessionsLoading ? (
            <div className="flex items-center justify-center h-32">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-therapy-calm"></div>
            </div>
          ) : sessions.length === 0 ? (
            <div className="card text-center py-12">
              <CalendarIcon className="h-12 w-12 text-gray-300 mx-auto mb-3" />
              <h3 className="font-bold text-gray-700 mb-1">אין פגישות עדיין</h3>
              <p className="text-sm text-gray-500">צור פגישה חדשה דרך עמוד הפגישות</p>
            </div>
          ) : (
            <div className="space-y-3">
              {sessions.map((session) => (
                <div
                  key={session.id}
                  className="card hover:shadow-md transition-shadow cursor-pointer"
                  onClick={() => navigate(`/sessions/${session.id}`)}
                >
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 bg-blue-50 text-blue-600 rounded-full flex items-center justify-center flex-shrink-0">
                      <DocumentTextIcon className="h-5 w-5" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-3 flex-wrap">
                        <span className="font-medium">
                          {session.session_number ? `פגישה #${session.session_number}` : 'פגישה'}
                        </span>
                        <span className="text-sm text-gray-500">
                          {new Date(session.session_date).toLocaleDateString('he-IL')}
                        </span>
                        {session.session_type && (
                          <span className="text-xs px-2 py-0.5 bg-gray-100 rounded-full text-gray-600">
                            {sessionTypeLabel(session.session_type)}
                          </span>
                        )}
                        {session.summary_id ? (
                          <span className="badge badge-approved text-xs">
                            <CheckCircleIcon className="h-3 w-3 inline ml-1" />
                            יש סיכום
                          </span>
                        ) : (
                          <span className="badge badge-draft text-xs">ללא סיכום</span>
                        )}
                      </div>
                      {session.duration_minutes && (
                        <div className="flex items-center gap-1 text-xs text-gray-400 mt-1">
                          <ClockIcon className="h-3 w-3" />
                          {session.duration_minutes} דקות
                        </div>
                      )}
                    </div>
                    <button
                      onClick={(e) => { e.stopPropagation(); openPrepModal(session) }}
                      className="flex items-center gap-1 text-xs text-therapy-warm font-medium hover:text-amber-700 px-2 py-1 rounded hover:bg-amber-50 transition-colors whitespace-nowrap touch-manipulation flex-shrink-0"
                    >
                      <SparklesIcon className="h-3.5 w-3.5" />
                      הכנה
                    </button>
                    <ArrowRightIcon className="h-4 w-4 text-gray-400 flex-shrink-0 rotate-180" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Summaries + Insight Tab ── */}
      {tab === 'summaries' && (
        <div className="space-y-5">
          {/* AI Insight panel */}
          <div className="card border-purple-200 bg-purple-50">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-3">
              <div className="flex items-center gap-2 flex-wrap">
                <SparklesIcon className="h-5 w-5 text-purple-600" />
                <h2 className="text-lg font-bold text-purple-900">סיכום עומק AI</h2>
                <span className="text-xs text-purple-600">({approvedCount} סיכומים מאושרים)</span>
              </div>
              <button
                onClick={handleGenerateInsight}
                disabled={approvedCount === 0 || insightLoading}
                className="btn-primary disabled:opacity-50 flex items-center gap-2 text-sm self-start sm:self-auto min-h-[40px] touch-manipulation"
              >
                {insightLoading ? (
                  <>
                    <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></span>
                    מייצר...
                  </>
                ) : (
                  'צור סיכום עומק'
                )}
              </button>
            </div>

            {approvedCount === 0 && !insight && (
              <p className="text-sm text-purple-700">
                יש לאשר לפחות סיכום פגישה אחד כדי לייצר סיכום עומק.
              </p>
            )}

            {insightError && (
              <div className="flex items-center gap-2 text-red-700 bg-red-50 rounded-lg p-3 mt-2">
                <ExclamationTriangleIcon className="h-5 w-5" />
                <span className="text-sm">{insightError}</span>
              </div>
            )}

            {insight && (
              <div className="space-y-3 mt-4">
                <div className="bg-white rounded-lg p-4">
                  <h3 className="font-bold text-gray-800 mb-2">סקירה כללית</h3>
                  <p className="text-gray-700 whitespace-pre-line">{insight.overview}</p>
                </div>
                <div className="bg-white rounded-lg p-4">
                  <h3 className="font-bold text-gray-800 mb-2">התקדמות לאורך זמן</h3>
                  <p className="text-gray-700 whitespace-pre-line">{insight.progress}</p>
                </div>
                {insight.patterns.length > 0 && (
                  <div className="bg-white rounded-lg p-4">
                    <h3 className="font-bold text-gray-800 mb-2">דפוסים מרכזיים</h3>
                    <ul className="list-disc list-inside space-y-1 text-gray-700">
                      {insight.patterns.map((p, i) => <li key={i}>{p}</li>)}
                    </ul>
                  </div>
                )}
                {insight.risks.length > 0 && (
                  <div className="bg-white rounded-lg p-4 border border-amber-200">
                    <h3 className="font-bold text-amber-800 mb-2">נקודות סיכון למעקב</h3>
                    <ul className="list-disc list-inside space-y-1 text-amber-700">
                      {insight.risks.map((r, i) => <li key={i}>{r}</li>)}
                    </ul>
                  </div>
                )}
                {insight.suggestions_for_next_sessions.length > 0 && (
                  <div className="bg-white rounded-lg p-4 border border-green-200">
                    <h3 className="font-bold text-green-800 mb-2">רעיונות לפגישות הבאות</h3>
                    <ul className="list-disc list-inside space-y-1 text-green-700">
                      {insight.suggestions_for_next_sessions.map((s, i) => <li key={i}>{s}</li>)}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Summaries list */}
          {summariesLoading ? (
            <div className="flex items-center justify-center h-32">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-therapy-calm"></div>
            </div>
          ) : summaries.length === 0 ? (
            <div className="card text-center py-12">
              <DocumentTextIcon className="h-12 w-12 text-gray-300 mx-auto mb-3" />
              <h3 className="font-bold text-gray-700 mb-1">אין סיכומים עדיין</h3>
              <p className="text-sm text-gray-500">צור פגישה וייצר סיכום AI כדי לראות אותו כאן</p>
            </div>
          ) : (
            <div className="space-y-3">
              {summaries.map((item) => (
                <div
                  key={item.summary.id}
                  className="card hover:shadow-md transition-shadow cursor-pointer"
                  onClick={() => navigate(`/sessions/${item.session_id}`)}
                >
                  <div className="flex items-start gap-4">
                    <div className="w-10 h-10 bg-therapy-calm text-white rounded-full flex items-center justify-center flex-shrink-0">
                      <DocumentTextIcon className="h-5 w-5" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-3 flex-wrap mb-1">
                        <span className="font-medium">
                          {item.session_number ? `פגישה #${item.session_number}` : 'פגישה'}
                        </span>
                        <span className="text-sm text-gray-500">
                          {new Date(item.session_date).toLocaleDateString('he-IL')}
                        </span>
                        {item.summary.status === 'approved' || item.summary.approved_by_therapist ? (
                          <span className="badge badge-approved text-xs">
                            <CheckCircleIcon className="h-3 w-3 inline ml-1" />
                            מאושר
                          </span>
                        ) : (
                          <span className="badge badge-draft text-xs">טיוטה</span>
                        )}
                      </div>
                      {item.summary.full_summary && (
                        <p className="text-gray-600 text-sm line-clamp-2">{item.summary.full_summary}</p>
                      )}
                      {item.summary.topics_discussed && item.summary.topics_discussed.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {item.summary.topics_discussed.map((topic, i) => (
                            <span key={i} className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full text-xs">
                              {topic}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Exercises Section (shown in sessions tab if any exercises exist) ── */}
      {tab === 'sessions' && exercises.length > 0 && (
        <div className="card border-green-200">
          <h3 className="font-bold text-gray-800 mb-3">
            משימות ({exercises.filter((e) => e.completed).length}/{exercises.length} הושלמו)
          </h3>
          <ul className="space-y-2">
            {exercises.map((ex) => (
              <li key={ex.id} className="flex items-start gap-3">
                <button
                  onClick={() => handleToggleExercise(ex)}
                  className="mt-0.5 flex-shrink-0"
                  aria-label={ex.completed ? 'בטל השלמה' : 'סמן כהושלם'}
                >
                  {ex.completed
                    ? <CheckCircleIcon className="h-5 w-5 text-green-600" />
                    : <span className="w-5 h-5 rounded-full border-2 border-gray-400 inline-block" />
                  }
                </button>
                <span className={`text-sm flex-1 ${ex.completed ? 'line-through text-gray-400' : 'text-gray-700'}`}>
                  {ex.description}
                </span>
                <button
                  onClick={() => handleDeleteExercise(ex)}
                  className="flex-shrink-0 text-gray-300 hover:text-red-400 transition-colors"
                  aria-label="הסר משימה"
                  title="הסר משימה"
                >
                  <XMarkIcon className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Messages Center Tab ── */}
      {tab === 'inbetween' && patient && (
        <MessagesCenter
          patientId={pid}
          patientName={patient.full_name}
          patientPhone={patient.phone}
        />
      )}

      {/* ── Notes Tab ── */}
      {tab === 'notes' && (
        <div className="card space-y-4">
          <div className="flex items-center gap-2">
            <BookOpenIcon className="h-5 w-5 text-gray-500" />
            <h2 className="font-bold text-gray-800">הערות</h2>
            <span className="text-xs text-gray-400 mr-auto">גלוי למטפל בלבד</span>
          </div>

          <div>
            <textarea
              value={notebookText}
              onChange={(e) => setNotebookText(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm resize-none"
              rows={3}
              maxLength={1000}
              placeholder="רשום מחשבות, השערות, רעיונות על המטופל..."
            />
            <p className="text-right text-xs text-gray-400 -mt-1">{notebookText.length}/1000</p>
          </div>

          <div className="flex justify-end">
            <button
              onClick={handleSaveNote}
              disabled={!notebookText.trim() || notebookSaving}
              className="btn-primary text-sm disabled:opacity-50"
            >
              {notebookSaving ? 'שומר...' : 'שמור'}
            </button>
          </div>

          {notesLoading ? (
            <div className="flex items-center justify-center py-4">
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-therapy-calm"></div>
            </div>
          ) : notes.length > 0 ? (
            <div className="space-y-2 border-t border-gray-100 pt-3">
              <h3 className="text-xs font-medium text-gray-500">הערות שמורות</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {notes.map((note) => (
                  <div
                    key={note.id}
                    className="bg-gray-50 rounded-lg p-3 cursor-pointer hover:bg-gray-100 transition-colors"
                    onClick={() => setViewingNote(note)}
                  >
                    <p className="text-sm text-gray-700 whitespace-pre-line line-clamp-3">{note.content}</p>
                    <div className="flex items-center justify-between mt-1.5">
                      <span className="text-xs text-gray-400">
                        {new Date(note.created_at).toLocaleDateString('he-IL', {
                          day: 'numeric', month: 'short', year: 'numeric',
                        })}
                      </span>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDeleteNote(note.id) }}
                        className="text-gray-300 hover:text-red-400 transition-colors touch-manipulation"
                        title="מחק הערה"
                      >
                        <TrashIcon className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-gray-400">
              <BookOpenIcon className="h-10 w-10 mx-auto mb-2 text-gray-300" />
              <p className="text-sm">אין הערות עדיין</p>
              <p className="text-xs mt-1">הוסף הערות, השערות ורעיונות על המטופל</p>
            </div>
          )}
        </div>
      )}

      </div>{/* end tab content column */}

      {/* ── Danger Zone (only when patient is active/paused) ── */}
      {patient.status !== 'inactive' && (
        <div className="border border-red-200 rounded-xl p-4">
          <h3 className="text-sm font-semibold text-red-700 mb-1">⚠️ אזור מסוכן</h3>
          <p className="text-xs text-gray-500 mb-3 leading-relaxed">
            פעולה זו תסמן את המטופל כלא פעיל ותסתיר אותו מרשימת המטופלים הפעילים. כל ההיסטוריה תישמר וניתן לשחזר בכל עת.
          </p>
          <button
            onClick={() => { setInactiveStep(1); setShowInactiveConfirm(true) }}
            className="text-sm text-red-600 hover:text-red-800 border border-red-300 hover:border-red-500 rounded-lg px-3 py-2 transition-colors touch-manipulation"
          >
            סמן כלא פעיל
          </button>
        </div>
      )}

      {/* ── Prep Brief Modal ── */}
      {prepModalSession && (
        <div className="fixed inset-0 bg-black/50 flex items-start sm:items-center justify-center z-50 p-4 pt-8 sm:pt-4" dir="rtl">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg flex flex-col max-h-[calc(100vh-6rem)] sm:max-h-[85vh] animate-fade-in">
            <div className="flex items-center justify-between px-5 py-4 border-b border-amber-100 flex-shrink-0 bg-amber-50 rounded-t-2xl">
              <div>
                <h2 className="text-lg font-bold text-amber-900">הכנה לפגישה</h2>
                <p className="text-xs text-amber-700 mt-0.5">
                  {prepModalSession.session_number ? `פגישה #${prepModalSession.session_number} · ` : ''}
                  {new Date(prepModalSession.session_date + 'T12:00:00').toLocaleDateString('he-IL')}
                </p>
              </div>
              <button onClick={closePrepModal} className="text-amber-600 hover:text-amber-800 p-1 touch-manipulation">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <div className="overflow-y-auto flex-1 p-4 sm:p-5">
              {prepLoading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500"></div>
                  <span className="mr-3 text-amber-700 text-sm">מכין תדריך...</span>
                </div>
              ) : prepError ? (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-amber-800">
                  <p className="text-sm">{prepError}</p>
                  <button
                    onClick={() => openPrepModal(prepModalSession)}
                    className="mt-2 text-sm px-3 py-1 bg-amber-200 rounded-lg hover:bg-amber-300 transition-colors"
                  >
                    נסה שוב
                  </button>
                </div>
              ) : prepBrief ? (
                <div className="space-y-3 text-sm">
                  <div>
                    <h3 className="font-semibold text-amber-900 mb-1">סקירה מהירה</h3>
                    <p className="text-amber-800">{prepBrief.quick_overview}</p>
                  </div>
                  <div>
                    <h3 className="font-semibold text-amber-900 mb-1">התקדמות אחרונה</h3>
                    <p className="text-amber-800">{prepBrief.recent_progress}</p>
                  </div>
                  {prepBrief.key_points_to_revisit.length > 0 && (
                    <div>
                      <h3 className="font-semibold text-amber-900 mb-1">נקודות לחזור אליהן</h3>
                      <ul className="list-disc list-inside text-amber-800 space-y-0.5">
                        {prepBrief.key_points_to_revisit.map((p, i) => <li key={i}>{p}</li>)}
                      </ul>
                    </div>
                  )}
                  {prepBrief.watch_out_for.length > 0 && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                      <h3 className="font-semibold text-red-800 mb-1">שים לב</h3>
                      <ul className="list-disc list-inside text-red-700 space-y-0.5">
                        {prepBrief.watch_out_for.map((w, i) => <li key={i}>{w}</li>)}
                      </ul>
                    </div>
                  )}
                  {prepBrief.ideas_for_this_session.length > 0 && (
                    <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                      <h3 className="font-semibold text-green-800 mb-1">רעיונות לפגישה זו</h3>
                      <ul className="list-disc list-inside text-green-700 space-y-0.5">
                        {prepBrief.ideas_for_this_session.map((idea, i) => <li key={i}>{idea}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              ) : null}
            </div>
            <div className="px-5 py-4 border-t border-gray-100 flex-shrink-0">
              <button onClick={closePrepModal} className="btn-secondary w-full min-h-[44px] touch-manipulation">סגור</button>
            </div>
          </div>
        </div>
      )}

      {/* ── View Note Modal ── */}
      {viewingNote && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" dir="rtl">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg flex flex-col max-h-[80vh]">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 flex-shrink-0">
              <h2 className="text-lg font-bold text-gray-900">פתק</h2>
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-400">
                  {new Date(viewingNote.created_at).toLocaleDateString('he-IL', {
                    day: 'numeric', month: 'long', year: 'numeric',
                  })}
                </span>
                <button
                  onClick={() => setViewingNote(null)}
                  className="text-gray-400 hover:text-gray-600 p-1 touch-manipulation"
                >
                  <XMarkIcon className="h-5 w-5" />
                </button>
              </div>
            </div>
            <div className="overflow-y-auto flex-1 px-5 py-4">
              <p className="text-sm text-gray-700 whitespace-pre-line leading-relaxed">{viewingNote.content}</p>
            </div>
            <div className="flex gap-3 px-5 py-4 border-t border-gray-100 flex-shrink-0">
              <button
                onClick={() => { handleDeleteNote(viewingNote.id); setViewingNote(null) }}
                className="flex items-center gap-1.5 text-sm text-red-500 hover:text-red-700 border border-red-200 hover:border-red-400 rounded-lg px-3 py-2 transition-colors"
              >
                <TrashIcon className="h-4 w-4" />
                מחק
              </button>
              <button
                onClick={() => setViewingNote(null)}
                className="btn-secondary flex-1 min-h-[40px] touch-manipulation"
              >
                סגור
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Edit Patient Modal ── */}
      {showEditPatient && patient && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 p-6" dir="rtl">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-gray-900">עריכת פרטי מטופל</h2>
              <button onClick={() => setShowEditPatient(false)} className="text-gray-400 hover:text-gray-600">
                <XMarkIcon className="h-6 w-6" />
              </button>
            </div>
            <form onSubmit={handleEditSave} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">שם מלא *</label>
                <input
                  type="text"
                  value={editForm.full_name}
                  onChange={(e) => setEditForm((f) => ({ ...f, full_name: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">טלפון</label>
                <PhoneInput
                  value={editForm.phone}
                  onChange={(e164) => setEditForm((f) => ({ ...f, phone: e164 }))}
                  className="w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">אימייל</label>
                <input
                  type="email"
                  value={editForm.email}
                  onChange={(e) => setEditForm((f) => ({ ...f, email: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
                  placeholder="patient@example.com"
                />
              </div>
              {editError && (
                <div className="text-red-600 text-sm bg-red-50 rounded-lg p-3">{editError}</div>
              )}
              <div className="flex gap-3 pt-2">
                <button type="submit" disabled={editSaving} className="btn-primary flex-1 disabled:opacity-50">
                  {editSaving ? 'שומר...' : 'שמור שינויים'}
                </button>
                <button type="button" onClick={() => setShowEditPatient(false)} className="btn-secondary flex-1">
                  ביטול
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Mark Inactive Modal (2-step) ── */}
      {showInactiveConfirm && patient && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6" dir="rtl">
            {inactiveStep === 1 ? (
              <>
                <h2 className="text-xl font-bold text-amber-800 mb-3">סימון מטופל כלא פעיל</h2>
                <p className="text-gray-700 mb-6">
                  האם אתה בטוח שברצונך לסמן את <strong>{patient.full_name}</strong> כלא פעיל?
                  המטופל לא יופיע ברשימת המטופלים הפעילים, אך כל ההיסטוריה תישמר.
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={() => setInactiveStep(2)}
                    className="btn-primary flex-1 bg-amber-600 hover:bg-amber-700"
                  >
                    המשך
                  </button>
                  <button onClick={() => setShowInactiveConfirm(false)} className="btn-secondary flex-1">
                    ביטול
                  </button>
                </div>
              </>
            ) : (
              <>
                <h2 className="text-xl font-bold text-red-800 mb-3">אישור סופי</h2>
                <p className="text-gray-700 mb-6">
                  לחיצה על "אשר" תסמן את <strong>{patient.full_name}</strong> כלא פעיל.
                  פעולה זו הפיכה — ניתן להפעיל מחדש בכל עת.
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={handleMarkInactive}
                    disabled={inactiveSaving}
                    className="btn-primary flex-1 bg-red-600 hover:bg-red-700 disabled:opacity-50"
                  >
                    {inactiveSaving ? 'מעדכן...' : 'אשר — סמן כלא פעיל'}
                  </button>
                  <button onClick={() => { setShowInactiveConfirm(false); setInactiveStep(1) }} className="btn-secondary flex-1">
                    ביטול
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ── New Session Modal ──
          Mobile: top-aligned with mt-8 breathing room, scrollable content, sticky header+footer
          Desktop: vertically centered, max 85vh */}
      {showNewSession && patient && (
        <div className="fixed inset-0 bg-black/50 flex items-start sm:items-center justify-center z-50 p-4 pt-8 sm:pt-4" dir="rtl">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg flex flex-col max-h-[calc(100vh-6rem)] sm:max-h-[85vh]">

            {/* Sticky header */}
            <div className="flex items-center justify-between px-4 sm:px-6 py-4 border-b border-gray-100 flex-shrink-0">
              <h2 className="text-xl font-bold text-gray-900">פגישה חדשה</h2>
              <button
                onClick={() => setShowNewSession(false)}
                className="text-gray-400 hover:text-gray-600 p-1 touch-manipulation"
              >
                <XMarkIcon className="h-6 w-6" />
              </button>
            </div>

            {/* Scrollable form body + sticky footer */}
            <form onSubmit={handleCreateSession} className="flex flex-col flex-1 min-h-0">
              <div className="overflow-y-auto flex-1 px-4 sm:px-6 py-4 space-y-4">

                {/* Patient — read-only */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">מטופל/ת</label>
                  <div className="input-field bg-gray-50 text-gray-700 cursor-not-allowed">
                    {patient.full_name}
                  </div>
                </div>

                {/* Date */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">תאריך *</label>
                  <input
                    type="date"
                    value={newSessionForm.session_date}
                    onChange={(e) => setNewSessionForm((f) => ({ ...f, session_date: e.target.value }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
                    required
                  />
                </div>

                {/* Start Time */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">שעת התחלה</label>
                  <select
                    value={newSessionForm.start_time}
                    onChange={(e) => setNewSessionForm((f) => ({ ...f, start_time: e.target.value }))}
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
                  <label className="block text-sm font-medium text-gray-700 mb-1">משך (דקות)</label>
                  <input
                    type="number"
                    value={newSessionForm.duration_minutes}
                    onChange={(e) => setNewSessionForm((f) => ({ ...f, duration_minutes: Number(e.target.value) }))}
                    min={10} max={180}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
                  />
                </div>

                {/* Session Type */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">סוג פגישה</label>
                  <select
                    value={newSessionForm.session_type}
                    onChange={(e) => setNewSessionForm((f) => ({ ...f, session_type: e.target.value }))}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
                  >
                    {SESSION_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>

                {newSessionError && (
                  <div className="text-red-600 text-sm bg-red-50 rounded-lg p-3">{newSessionError}</div>
                )}
              </div>

              {/* Sticky footer — always visible */}
              <div className="flex gap-3 px-4 sm:px-6 py-4 border-t border-gray-100 flex-shrink-0">
                <button
                  type="submit"
                  disabled={newSessionCreating}
                  className="btn-primary flex-1 disabled:opacity-50 min-h-[44px] touch-manipulation"
                >
                  {newSessionCreating ? 'יוצר...' : 'צור פגישה'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowNewSession(false)}
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
