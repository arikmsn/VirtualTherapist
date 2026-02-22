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
} from '@heroicons/react/24/outline'
import { patientsAPI, sessionsAPI, patientSummariesAPI, exercisesAPI } from '@/lib/api'

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

type Tab = 'sessions' | 'summaries' | 'inbetween'

// --- Component ---

export default function PatientProfilePage() {
  const { patientId } = useParams<{ patientId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const pid = Number(patientId)

  const initialTab = (location.state as { initialTab?: Tab } | null)?.initialTab ?? 'sessions'
  const [tab, setTab] = useState<Tab>(initialTab)

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

  const approvedCount = summaries.filter(
    (s) => s.summary.status === 'approved' || s.summary.approved_by_therapist
  ).length

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
        setSessions([...data].sort((a: Session, b: Session) =>
          new Date(b.session_date).getTime() - new Date(a.session_date).getTime()
        ))
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
        setSummaries(data)
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
        <div className="flex items-start gap-5">
          {/* Avatar */}
          <div className="w-16 h-16 bg-therapy-calm text-white rounded-full flex items-center justify-center font-bold text-2xl flex-shrink-0">
            {patient.full_name.charAt(0)}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl font-bold text-gray-900">{patient.full_name}</h1>
              <span className={`badge text-xs ${patient.status === 'active' ? 'badge-approved' : 'badge-draft'}`}>
                {statusLabel(patient.status)}
              </span>
              {/* Edit + status actions */}
              <button
                onClick={handleEditOpen}
                className="flex items-center gap-1 text-xs text-gray-500 hover:text-therapy-calm border border-gray-200 rounded-lg px-2 py-1 hover:border-therapy-calm transition-colors"
              >
                <PencilSquareIcon className="h-3.5 w-3.5" />
                ערוך פרטים
              </button>
              {patient.status !== 'inactive' ? (
                <button
                  onClick={() => { setInactiveStep(1); setShowInactiveConfirm(true) }}
                  className="text-xs text-amber-600 hover:text-amber-800 border border-amber-200 rounded-lg px-2 py-1 hover:border-amber-400 transition-colors"
                >
                  סמן כלא פעיל
                </button>
              ) : (
                <button
                  onClick={handleReactivate}
                  className="text-xs text-green-600 hover:text-green-800 border border-green-200 rounded-lg px-2 py-1 hover:border-green-400 transition-colors"
                >
                  הפעל מחדש
                </button>
              )}
            </div>

            <div className="mt-3 grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-1 text-sm text-gray-600">
              {patient.phone && (
                <div className="flex gap-1">
                  <span className="text-gray-400">טלפון:</span>
                  <span>{patient.phone}</span>
                </div>
              )}
              {patient.email && (
                <div className="flex gap-1">
                  <span className="text-gray-400">אימייל:</span>
                  <span>{patient.email}</span>
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
              <div className="flex gap-1">
                <span className="text-gray-400">אפשר AI:</span>
                <span>{patient.allow_ai_contact ? 'כן' : 'לא'}</span>
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

      {/* Tab navigation */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-0 -mb-px">
          {([
            { key: 'sessions', label: 'פגישות', icon: CalendarIcon },
            { key: 'summaries', label: 'סיכומים ותובנות', icon: SparklesIcon },
            { key: 'inbetween', label: 'הודעות ותזכורות', icon: ChatBubbleLeftRightIcon },
          ] as const).map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 transition-colors ${
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
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <SparklesIcon className="h-5 w-5 text-purple-600" />
                <h2 className="text-lg font-bold text-purple-900">סיכום עומק AI</h2>
                <span className="text-xs text-purple-600">({approvedCount} סיכומים מאושרים)</span>
              </div>
              <button
                onClick={handleGenerateInsight}
                disabled={approvedCount === 0 || insightLoading}
                className="btn-primary disabled:opacity-50 flex items-center gap-2 text-sm"
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
                <span className={`text-sm ${ex.completed ? 'line-through text-gray-400' : 'text-gray-700'}`}>
                  {ex.description}
                </span>
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
                <input
                  type="text"
                  value={editForm.phone}
                  onChange={(e) => setEditForm((f) => ({ ...f, phone: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-therapy-calm focus:border-therapy-calm"
                  placeholder="050-1234567"
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

      {/* ── New Session Modal ── */}
      {showNewSession && patient && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 p-6" dir="rtl">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-gray-900">פגישה חדשה</h2>
              <button
                onClick={() => setShowNewSession(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <XMarkIcon className="h-6 w-6" />
              </button>
            </div>

            <form onSubmit={handleCreateSession} className="space-y-4">
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

              {/* Start Time — select, consistent with SessionsPage */}
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

              <div className="flex gap-3 pt-2">
                <button
                  type="submit"
                  disabled={newSessionCreating}
                  className="btn-primary flex-1 disabled:opacity-50"
                >
                  {newSessionCreating ? 'יוצר...' : 'צור פגישה'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowNewSession(false)}
                  className="btn-secondary flex-1"
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
