import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import {
  ArrowRightIcon,
  DocumentTextIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  PencilSquareIcon,
  LightBulbIcon,
  XMarkIcon,
  MicrophoneIcon,
  ClipboardDocumentListIcon,
} from '@heroicons/react/24/outline'
import { sessionsAPI, patientsAPI, exercisesAPI } from '@/lib/api'
import AudioRecorder from '@/components/AudioRecorder'

interface SessionSummary {
  id: number
  full_summary: string | null
  transcript: string | null
  topics_discussed: string[] | null
  interventions_used: string[] | null
  patient_progress: string | null
  homework_assigned: string[] | null
  next_session_plan: string | null
  mood_observed: string | null
  risk_assessment: string | null
  generated_from: string | null
  therapist_edited: boolean
  approved_by_therapist: boolean
  status: string
  created_at: string
}

interface PrepBrief {
  quick_overview: string
  recent_progress: string
  key_points_to_revisit: string[]
  watch_out_for: string[]
  ideas_for_this_session: string[]
}

interface Session {
  id: number
  patient_id: number
  session_date: string
  session_type?: string
  duration_minutes?: number
  session_number?: number
  summary_id?: number
}

interface Exercise {
  id: number
  description: string
  completed: boolean
  completed_at: string | null
}

type InputMode = 'text' | 'voice'

export default function SessionDetailPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const [session, setSession] = useState<Session | null>(null)
  const [patientName, setPatientName] = useState('')
  const [summary, setSummary] = useState<SessionSummary | null>(null)
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editing, setEditing] = useState(false)
  const [error, setError] = useState('')
  const [inputMode, setInputMode] = useState<InputMode>('voice')

  // Transcript toggle (for side-by-side view)
  const [showTranscript, setShowTranscript] = useState(true)

  // Prep brief state
  const [prepBrief, setPrepBrief] = useState<PrepBrief | null>(null)
  const [prepLoading, setPrepLoading] = useState(false)
  const [prepError, setPrepError] = useState('')
  const [showPrepPanel, setShowPrepPanel] = useState(searchParams.get('prep') === '1')

  // Exercise tracking (this session's summary)
  const [exercises, setExercises] = useState<Exercise[]>([])
  // Open tasks count across all patient tasks (for banner)
  const [openTasksCount, setOpenTasksCount] = useState(0)

  // Editable fields
  const [editFullSummary, setEditFullSummary] = useState('')
  const [editTopics, setEditTopics] = useState('')        // newline-separated list
  const [editInterventions, setEditInterventions] = useState('')  // newline-separated list
  const [editHomework, setEditHomework] = useState('')    // newline-separated list
  const [editProgress, setEditProgress] = useState('')
  const [editNextPlan, setEditNextPlan] = useState('')
  const [editMood, setEditMood] = useState('')
  const [editRisk, setEditRisk] = useState('')

  useEffect(() => {
    const loadSession = async () => {
      try {
        const sessionData = await sessionsAPI.get(Number(sessionId))
        setSession(sessionData)

        // Load patient name
        try {
          const patient = await patientsAPI.get(sessionData.patient_id)
          setPatientName(patient.full_name)
        } catch {
          setPatientName(`מטופל #${sessionData.patient_id}`)
        }

        // Load all patient exercises — used for open task count and summary-linked tasks
        try {
          const allExData = await exercisesAPI.list(sessionData.patient_id)
          setOpenTasksCount(allExData.filter((e: Exercise) => !e.completed).length)
          // Keep summary-linked exercises for the exercise panel (loaded after summary below)
          if (sessionData.summary_id != null) {
            try {
              const summaryData = await sessionsAPI.getSummary(Number(sessionId))
              setSummary(summaryData)
              setExercises(allExData.filter((e: Exercise & { session_summary_id?: number }) =>
                e.session_summary_id === summaryData.id
              ))
            } catch {
              // No summary yet — that's fine
            }
          }
        } catch {
          // exercises not critical; still load summary if present
          if (sessionData.summary_id != null) {
            try {
              const summaryData = await sessionsAPI.getSummary(Number(sessionId))
              setSummary(summaryData)
            } catch { /* no summary */ }
          }
        }
      } catch (err) {
        console.error('Error loading session:', err)
        setError('שגיאה בטעינת הפגישה')
      } finally {
        setLoading(false)
      }
    }
    loadSession()
  }, [sessionId])

  // Auto-load prep brief when ?prep=1
  useEffect(() => {
    if (showPrepPanel && !prepBrief && !prepLoading && sessionId) {
      loadPrepBrief()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showPrepPanel, sessionId])

  const loadPrepBrief = async () => {
    setPrepLoading(true)
    setPrepError('')
    try {
      const data = await sessionsAPI.getPrepBrief(Number(sessionId))
      setPrepBrief(data)
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'שגיאה ביצירת תדריך ההכנה'
      setPrepError(detail)
    } finally {
      setPrepLoading(false)
    }
  }

  // --- Text-based summary generation ---
  const handleGenerateSummary = async () => {
    if (!notes.trim()) return
    setGenerating(true)
    setError('')

    try {
      const result = await sessionsAPI.generateSummary(Number(sessionId), notes)
      setSummary(result)
      setSession((prev) => prev ? { ...prev, summary_id: result.id } : prev)
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'שגיאה ביצירת הסיכום'
      setError(detail)
    } finally {
      setGenerating(false)
    }
  }

  // --- Voice Recap: audio blob → upload → transcript + summary ---
  const handleAudioRecordingComplete = async (blob: Blob) => {
    setGenerating(true)
    setError('')

    try {
      const result = await sessionsAPI.generateSummaryFromAudio(Number(sessionId), blob)
      setSummary(result)
      setSession((prev) => prev ? { ...prev, summary_id: result.id } : prev)
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'שגיאה בתמלול ויצירת הסיכום'
      setError(detail)
    } finally {
      setGenerating(false)
    }
  }

  const startEditing = () => {
    if (!summary) return
    setEditFullSummary(summary.full_summary || '')
    setEditTopics((summary.topics_discussed || []).join('\n'))
    setEditInterventions((summary.interventions_used || []).join('\n'))
    setEditHomework((summary.homework_assigned || []).join('\n'))
    setEditProgress(summary.patient_progress || '')
    setEditNextPlan(summary.next_session_plan || '')
    setEditMood(summary.mood_observed || '')
    setEditRisk(summary.risk_assessment || '')
    setEditing(true)
  }

  const splitLines = (val: string): string[] =>
    val.split('\n').map((s) => s.trim()).filter(Boolean)

  const handleSaveDraft = async () => {
    setSaving(true)
    setError('')

    try {
      const updates: Record<string, unknown> = {
        full_summary: editFullSummary,
        topics_discussed: splitLines(editTopics),
        interventions_used: splitLines(editInterventions),
        homework_assigned: splitLines(editHomework),
        patient_progress: editProgress,
        next_session_plan: editNextPlan,
        mood_observed: editMood,
        risk_assessment: editRisk,
        status: 'draft',
      }
      const result = await sessionsAPI.patchSummary(Number(sessionId), updates)
      setSummary(result)
      setEditing(false)
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'שגיאה בשמירת הטיוטה'
      setError(detail)
    } finally {
      setSaving(false)
    }
  }

  const handleApprove = async () => {
    setSaving(true)
    setError('')

    try {
      const updates: Record<string, unknown> = { status: 'approved' }
      if (editing) {
        updates.full_summary = editFullSummary
        updates.topics_discussed = splitLines(editTopics)
        updates.interventions_used = splitLines(editInterventions)
        updates.homework_assigned = splitLines(editHomework)
        updates.patient_progress = editProgress
        updates.next_session_plan = editNextPlan
        updates.mood_observed = editMood
        updates.risk_assessment = editRisk
      }
      const result = await sessionsAPI.patchSummary(Number(sessionId), updates)
      setSummary(result)
      setEditing(false)
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'שגיאה באישור הסיכום'
      setError(detail)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" dir="rtl">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-therapy-calm mx-auto mb-4"></div>
          <p className="text-gray-600">טוען פגישה...</p>
        </div>
      </div>
    )
  }

  if (!session) {
    return (
      <div className="text-center py-12" dir="rtl">
        <p className="text-gray-600">פגישה לא נמצאה</p>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-fade-in" dir="rtl">
      {/* Back + Header */}
      <div>
        <button
          onClick={() => navigate('/sessions')}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowRightIcon className="h-5 w-5" />
          חזרה לפגישות
        </button>
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 bg-therapy-calm text-white rounded-full flex items-center justify-center">
            <DocumentTextIcon className="h-7 w-7" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">{patientName}</h1>
            <div className="flex items-center gap-3 text-sm text-gray-600 mt-1">
              <span>{new Date(session.session_date).toLocaleDateString('he-IL')}</span>
              {session.session_number && <span>פגישה #{session.session_number}</span>}
              {session.duration_minutes && <span>{session.duration_minutes} דקות</span>}
              {session.session_type && (
                <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full text-xs">
                  {session.session_type}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Open Tasks Reminder — visible only when patient has uncompleted tasks */}
      {openTasksCount > 0 && (
        <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
          <ClipboardDocumentListIcon className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-amber-900">
              יש {openTasksCount} משימות פתוחות למטופל הזה
            </p>
            <p className="text-xs text-amber-700 mt-0.5">
              מומלץ לעבור יחד על המשימות או לבדוק סטטוס לפני/במהלך הפגישה.
            </p>
          </div>
          <button
            onClick={() => navigate(`/patients/${session.patient_id}`, { state: { initialTab: 'sessions' } })}
            className="flex-shrink-0 text-xs font-medium text-amber-700 hover:text-amber-900 border border-amber-300 hover:border-amber-500 rounded-lg px-2.5 py-1.5 transition-colors whitespace-nowrap touch-manipulation"
          >
            צפה במשימות
          </button>
        </div>
      )}

      {/* Prep Brief Panel */}
      {showPrepPanel && (
        <div className="card border-amber-200 bg-amber-50">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-bold text-amber-900 flex items-center gap-2">
              <LightBulbIcon className="h-5 w-5" />
              הכנה לפגישה
            </h2>
            <button
              onClick={() => setShowPrepPanel(false)}
              className="text-amber-600 hover:text-amber-800"
            >
              <XMarkIcon className="h-5 w-5" />
            </button>
          </div>

          {prepLoading ? (
            <div className="flex justify-center py-6">
              <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-600 mx-auto mb-2"></div>
                <p className="text-sm text-amber-700">מכין תדריך...</p>
              </div>
            </div>
          ) : prepError ? (
            <div className="text-amber-800 text-sm">
              <p>{prepError}</p>
              <button
                onClick={loadPrepBrief}
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
                <div className="bg-red-50 border border-red-200 rounded-lg p-2">
                  <h3 className="font-semibold text-red-800 mb-1">שים לב</h3>
                  <ul className="list-disc list-inside text-red-700 space-y-0.5">
                    {prepBrief.watch_out_for.map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                </div>
              )}
              {prepBrief.ideas_for_this_session.length > 0 && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-2">
                  <h3 className="font-semibold text-green-800 mb-1">רעיונות לפגישה זו</h3>
                  <ul className="list-disc list-inside text-green-700 space-y-0.5">
                    {prepBrief.ideas_for_this_session.map((idea, i) => <li key={i}>{idea}</li>)}
                  </ul>
                </div>
              )}
            </div>
          ) : null}
        </div>
      )}

      {/* Prep Brief Toggle Button (when panel is closed) */}
      {!showPrepPanel && (
        <button
          onClick={() => { setShowPrepPanel(true) }}
          className="btn-secondary flex items-center gap-2"
        >
          <LightBulbIcon className="h-4 w-4" />
          הכנה לפגישה
        </button>
      )}

      {/* Input Section — Voice Recap or Text Notes (only when no summary yet) */}
      {!summary && (
        <div className="card">
          <h2 className="text-lg font-bold mb-3">תיעוד הפגישה</h2>

          {/* Mode Tabs */}
          <div className="flex gap-1 mb-4 bg-gray-100 rounded-lg p-1 w-fit">
            <button
              onClick={() => setInputMode('voice')}
              className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                inputMode === 'voice'
                  ? 'bg-white text-therapy-calm shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <MicrophoneIcon className="h-4 w-4" />
              סיכום קולי
            </button>
            <button
              onClick={() => setInputMode('text')}
              className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                inputMode === 'text'
                  ? 'bg-white text-therapy-calm shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <DocumentTextIcon className="h-4 w-4" />
              רשימות טקסט
            </button>
          </div>

          {/* Voice Recap Tab */}
          {inputMode === 'voice' && (
            <AudioRecorder
              onRecordingComplete={handleAudioRecordingComplete}
              processing={generating}
            />
          )}

          {/* Text Notes Tab */}
          {inputMode === 'text' && (
            <>
              <p className="text-sm text-gray-600 mb-3">
                הקלד או הדבק את הרשימות מהפגישה. ה-AI יצור סיכום מובנה בסגנון שלך.
              </p>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="input-field h-48 resize-none"
                placeholder="למשל: המטופל דיווח על שיפור קל בחרדה. עבדנו על חשיפה הדרגתית למצבים חברתיים. הטלנו משימה של יומן מחשבות..."
                disabled={generating}
              />
              <div className="flex items-center justify-between mt-4">
                <span className="text-xs text-gray-400">
                  {notes.length > 0 ? `${notes.length} תווים` : ''}
                </span>
                <button
                  onClick={handleGenerateSummary}
                  disabled={!notes.trim() || generating}
                  className="btn-primary disabled:opacity-50"
                >
                  {generating ? (
                    <span className="flex items-center gap-2">
                      <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></span>
                      יוצר סיכום...
                    </span>
                  ) : (
                    'צור סיכום AI'
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="card border-red-200 bg-red-50">
          <div className="flex items-center gap-2 text-red-700">
            <ExclamationTriangleIcon className="h-5 w-5" />
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Summary Display */}
      {summary && (
        <div className="space-y-4">
          {/* Header + Status + Actions */}
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold">סיכום הפגישה</h2>
            <div className="flex items-center gap-2">
              {summary.status === 'approved' || summary.approved_by_therapist ? (
                <span className="badge badge-approved">
                  <CheckCircleIcon className="h-4 w-4 inline ml-1" />
                  מאושר
                </span>
              ) : (
                <span className="badge badge-draft">טיוטה</span>
              )}
              <span className="text-xs text-gray-400">
                נוצר מ{summary.generated_from === 'text' ? 'טקסט' : 'הקלטה'}
              </span>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-3">
            {!editing && (
              <button onClick={startEditing} className="btn-secondary flex items-center gap-2">
                <PencilSquareIcon className="h-4 w-4" />
                ערוך סיכום
              </button>
            )}
            {!editing && summary.status !== 'approved' && !summary.approved_by_therapist && (
              <button
                onClick={handleApprove}
                disabled={saving}
                className="btn-primary flex items-center gap-2 disabled:opacity-50"
              >
                <CheckCircleIcon className="h-4 w-4" />
                {saving ? 'מאשר...' : 'אשר סיכום'}
              </button>
            )}
            {editing && (
              <>
                <button
                  onClick={handleSaveDraft}
                  disabled={saving}
                  className="btn-secondary disabled:opacity-50"
                >
                  {saving ? 'שומר...' : 'שמור טיוטה'}
                </button>
                <button
                  onClick={handleApprove}
                  disabled={saving}
                  className="btn-primary flex items-center gap-2 disabled:opacity-50"
                >
                  <CheckCircleIcon className="h-4 w-4" />
                  {saving ? 'מאשר...' : 'שמור ואשר'}
                </button>
                <button
                  onClick={() => setEditing(false)}
                  className="text-gray-500 hover:text-gray-700 text-sm"
                >
                  ביטול
                </button>
              </>
            )}
          </div>

          {/* Side-by-side: Transcript + Summary (PRD requirement for audio-generated summaries) */}
          {summary.generated_from === 'audio' && summary.transcript && (
            <div>
              <button
                onClick={() => setShowTranscript(!showTranscript)}
                className="text-sm text-blue-600 hover:text-blue-800 mb-2"
              >
                {showTranscript ? 'הסתר תמליל' : 'הצג תמליל מקורי'}
              </button>

              {showTranscript && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Transcript panel */}
                  <div className="card border-blue-200 bg-blue-50">
                    <h3 className="font-bold text-blue-800 mb-2 flex items-center gap-2">
                      <MicrophoneIcon className="h-4 w-4" />
                      תמליל מקורי
                      <span className="text-xs font-normal text-blue-500 mr-1">
                        {new Date(
                          summary.created_at.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(summary.created_at)
                            ? summary.created_at
                            : summary.created_at + 'Z'
                        ).toLocaleString('he-IL', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })}
                      </span>
                    </h3>
                    <p className="text-blue-700 whitespace-pre-line text-sm leading-relaxed">
                      {summary.transcript}
                    </p>
                  </div>
                  {/* Summary panel (side-by-side) */}
                  <div className="card">
                    <h3 className="font-bold text-gray-800 mb-2">סיכום AI</h3>
                    <p className="text-gray-700 whitespace-pre-line text-sm leading-relaxed">
                      {summary.full_summary}
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Full Summary (when not in side-by-side mode, or text-generated) */}
          {!(summary.generated_from === 'audio' && summary.transcript && showTranscript) && (
            <>
              {editing ? (
                <div className="card">
                  <h3 className="font-bold text-gray-800 mb-2">סיכום כללי</h3>
                  <textarea
                    value={editFullSummary}
                    onChange={(e) => setEditFullSummary(e.target.value)}
                    className="input-field h-32 resize-none"
                    maxLength={3000}
                  />
                  <p className="text-right text-xs text-gray-400 mt-1">{editFullSummary.length}/3000</p>
                </div>
              ) : (
                summary.full_summary && (
                  <div className="card">
                    <h3 className="font-bold text-gray-800 mb-2">סיכום כללי</h3>
                    <p className="text-gray-700 whitespace-pre-line">{summary.full_summary}</p>
                  </div>
                )
              )}
            </>
          )}

          {/* Structured Sections */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {editing ? (
              <EditableListSection title="נושאים שנדונו" value={editTopics} onChange={setEditTopics} />
            ) : (
              <SummarySection title="נושאים שנדונו" items={summary.topics_discussed} />
            )}

            {editing ? (
              <EditableListSection title="התערבויות" value={editInterventions} onChange={setEditInterventions} />
            ) : (
              <SummarySection title="התערבויות" items={summary.interventions_used} />
            )}

            {editing ? (
              <EditableListSection title="משימות בית" value={editHomework} onChange={setEditHomework} />
            ) : (
              <SummarySection title="משימות בית" items={summary.homework_assigned} />
            )}

            {editing ? (
              <EditableTextSection title="התקדמות המטופל" value={editProgress} onChange={setEditProgress} />
            ) : (
              <SummaryTextSection title="התקדמות המטופל" text={summary.patient_progress} />
            )}

            {editing ? (
              <EditableTextSection title="תוכנית לפגישה הבאה" value={editNextPlan} onChange={setEditNextPlan} />
            ) : (
              <SummaryTextSection title="תוכנית לפגישה הבאה" text={summary.next_session_plan} />
            )}

            {editing ? (
              <EditableTextSection title="מצב רוח נצפה" value={editMood} onChange={setEditMood} />
            ) : (
              <SummaryTextSection title="מצב רוח נצפה" text={summary.mood_observed} />
            )}
          </div>

          {/* Risk Assessment */}
          {editing ? (
            <div className="card border-amber-200 bg-amber-50">
              <h3 className="font-bold text-amber-800 mb-2">הערכת סיכון</h3>
              <textarea
                value={editRisk}
                onChange={(e) => setEditRisk(e.target.value)}
                className="input-field h-20 resize-none"
              />
            </div>
          ) : (
            summary.risk_assessment && (
              <div className="card border-amber-200 bg-amber-50">
                <h3 className="font-bold text-amber-800 mb-1">הערכת סיכון</h3>
                <p className="text-amber-700">{summary.risk_assessment}</p>
              </div>
            )
          )}

          {/* Exercise Tracker — interactive homework checkboxes */}
          {session && (summary.homework_assigned?.length || exercises.length > 0) && (
            <ExerciseTracker
              patientId={session.patient_id}
              summaryId={summary.id}
              homeworkSuggestions={summary.homework_assigned || []}
              exercises={exercises}
              onExercisesChange={setExercises}
            />
          )}
        </div>
      )}
    </div>
  )
}

function SummarySection({ title, items }: { title: string; items: string[] | null }) {
  if (!items || items.length === 0) return null
  return (
    <div className="card">
      <h3 className="font-bold text-gray-800 mb-2">{title}</h3>
      <ul className="list-disc list-inside space-y-1 text-gray-700">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

function SummaryTextSection({ title, text }: { title: string; text: string | null }) {
  if (!text) return null
  return (
    <div className="card">
      <h3 className="font-bold text-gray-800 mb-2">{title}</h3>
      <p className="text-gray-700">{text}</p>
    </div>
  )
}

function EditableTextSection({
  title,
  value,
  onChange,
}: {
  title: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <div className="card">
      <h3 className="font-bold text-gray-800 mb-2">{title}</h3>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="input-field h-20 resize-none text-sm"
      />
    </div>
  )
}

function EditableListSection({
  title,
  value,
  onChange,
}: {
  title: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <div className="card">
      <h3 className="font-bold text-gray-800 mb-1">{title}</h3>
      <p className="text-xs text-gray-400 mb-2">פריט אחד בכל שורה</p>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="input-field h-24 resize-none text-sm"
        placeholder="פריט אחד בכל שורה..."
      />
    </div>
  )
}

function ExerciseTracker({
  patientId,
  summaryId,
  homeworkSuggestions,
  exercises,
  onExercisesChange,
}: {
  patientId: number
  summaryId: number
  homeworkSuggestions: string[]
  exercises: Exercise[]
  onExercisesChange: (ex: Exercise[]) => void
}) {
  const [toggling, setToggling] = useState<number | null>(null)
  const [adding, setAdding] = useState<string | null>(null)
  const [newDesc, setNewDesc] = useState('')
  const [addingCustom, setAddingCustom] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editText, setEditText] = useState('')
  const [deletingId, setDeletingId] = useState<number | null>(null)

  // Suggestions from homework_assigned that aren't yet tracked
  const tracked = new Set(exercises.map((e) => e.description))
  const untracked = homeworkSuggestions.filter((s) => !tracked.has(s))

  const toggleExercise = async (ex: Exercise) => {
    setToggling(ex.id)
    try {
      const updated = await exercisesAPI.patch(ex.id, { completed: !ex.completed })
      onExercisesChange(exercises.map((e) => (e.id === ex.id ? updated : e)))
    } catch (err) {
      console.error('Error toggling exercise:', err)
    } finally {
      setToggling(null)
    }
  }

  const deleteExercise = async (ex: Exercise) => {
    setDeletingId(ex.id)
    try {
      await exercisesAPI.delete(ex.id)
      onExercisesChange(exercises.filter((e) => e.id !== ex.id))
    } catch (err) {
      console.error('Error deleting exercise:', err)
    } finally {
      setDeletingId(null)
    }
  }

  const saveEdit = async (ex: Exercise) => {
    const trimmed = editText.trim()
    if (!trimmed || trimmed === ex.description) {
      setEditingId(null)
      return
    }
    try {
      const updated = await exercisesAPI.patch(ex.id, { description: trimmed })
      onExercisesChange(exercises.map((e) => (e.id === ex.id ? updated : e)))
      setEditingId(null)
    } catch (err) {
      console.error('Error updating exercise:', err)
    }
  }

  const trackSuggestion = async (desc: string) => {
    setAdding(desc)
    try {
      const created = await exercisesAPI.create({ patient_id: patientId, description: desc, session_summary_id: summaryId })
      onExercisesChange([...exercises, created])
    } catch (err) {
      console.error('Error tracking exercise:', err)
    } finally {
      setAdding(null)
    }
  }

  const addCustom = async () => {
    if (!newDesc.trim()) return
    setAddingCustom(true)
    try {
      const created = await exercisesAPI.create({ patient_id: patientId, description: newDesc.trim(), session_summary_id: summaryId })
      onExercisesChange([...exercises, created])
      setNewDesc('')
    } catch (err) {
      console.error('Error adding custom exercise:', err)
    } finally {
      setAddingCustom(false)
    }
  }

  return (
    <div className="card border-green-200">
      <h3 className="font-bold text-gray-800 mb-3">מעקב משימות</h3>

      {/* Tracked exercises with checkboxes */}
      {exercises.length > 0 && (
        <ul className="space-y-2 mb-3">
          {exercises.map((ex) => (
            <li key={ex.id} className="flex items-center gap-2">
              {/* Toggle complete */}
              <button
                onClick={() => editingId !== ex.id && toggleExercise(ex)}
                disabled={toggling === ex.id || editingId === ex.id}
                className="mt-0.5 flex-shrink-0"
                aria-label={ex.completed ? 'סמן כלא הושלם' : 'סמן כהושלם'}
              >
                {toggling === ex.id ? (
                  <span className="w-5 h-5 rounded-full border-2 border-green-400 animate-spin border-t-transparent inline-block" />
                ) : ex.completed ? (
                  <CheckCircleIcon className="h-5 w-5 text-green-600" />
                ) : (
                  <span className="w-5 h-5 rounded-full border-2 border-gray-400 inline-block" />
                )}
              </button>

              {/* Inline edit input OR text */}
              {editingId === ex.id ? (
                <>
                  <input
                    autoFocus
                    type="text"
                    value={editText}
                    onChange={(e) => setEditText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') { e.preventDefault(); saveEdit(ex) }
                      if (e.key === 'Escape') setEditingId(null)
                    }}
                    className="input-field flex-1 text-sm py-1"
                  />
                  <button
                    onClick={() => saveEdit(ex)}
                    className="text-xs text-green-600 hover:text-green-800 flex-shrink-0"
                  >
                    שמור
                  </button>
                  <button
                    onClick={() => setEditingId(null)}
                    className="text-xs text-gray-400 hover:text-gray-600 flex-shrink-0"
                  >
                    ביטול
                  </button>
                </>
              ) : (
                <>
                  <span className={`text-sm flex-1 ${ex.completed ? 'line-through text-gray-400' : 'text-gray-700'}`}>
                    {ex.description}
                  </span>
                  {/* Edit + delete — only for non-completed tasks */}
                  {!ex.completed && (
                    <>
                      <button
                        onClick={() => { setEditingId(ex.id); setEditText(ex.description) }}
                        className="flex-shrink-0 text-gray-300 hover:text-blue-500 transition-colors"
                        aria-label="ערוך משימה"
                        title="ערוך משימה"
                      >
                        <PencilSquareIcon className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => deleteExercise(ex)}
                        disabled={deletingId === ex.id}
                        className="flex-shrink-0 text-gray-300 hover:text-red-400 transition-colors disabled:opacity-50"
                        aria-label="הסר משימה"
                        title="הסר משימה"
                      >
                        <XMarkIcon className="h-4 w-4" />
                      </button>
                    </>
                  )}
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      {/* Untracked homework suggestions — quick "add tracking" buttons */}
      {untracked.length > 0 && (
        <div className="mb-3">
          <p className="text-xs text-gray-500 mb-1">מ-AI (לחץ למעקב):</p>
          <div className="space-y-1">
            {untracked.map((s) => (
              <button
                key={s}
                onClick={() => trackSuggestion(s)}
                disabled={adding === s}
                className="w-full text-right text-sm px-3 py-1.5 border border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-green-400 hover:text-green-700 hover:bg-green-50 transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                <span className="text-green-600">+</span>
                {adding === s ? 'מוסיף...' : s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Custom exercise input — auto-expanding textarea */}
      <AutoExpandTextarea
        value={newDesc}
        onChange={setNewDesc}
        onSubmit={addCustom}
        disabled={addingCustom}
      />
    </div>
  )
}

// Auto-expanding textarea for task description input
function AutoExpandTextarea({
  value,
  onChange,
  onSubmit,
  disabled,
}: {
  value: string
  onChange: (v: string) => void
  onSubmit: () => void
  disabled: boolean
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const MAX = 500

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }, [value])

  return (
    <div className="space-y-1">
      <div className="flex gap-2 items-end">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value.slice(0, MAX))}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSubmit() }
          }}
          placeholder="הוסף משימה מותאמת... (Enter לשמירה, Shift+Enter לשורה חדשה)"
          rows={2}
          className="input-field flex-1 text-sm py-1.5 resize-none overflow-hidden min-h-[36px]"
          style={{ height: 'auto' }}
        />
        <button
          onClick={onSubmit}
          disabled={!value.trim() || disabled}
          className="btn-secondary text-sm py-1.5 px-3 disabled:opacity-50 flex-shrink-0"
        >
          {disabled ? '...' : 'הוסף'}
        </button>
      </div>
      <p className="text-right text-xs text-gray-400">{value.length}/{MAX}</p>
    </div>
  )
}
