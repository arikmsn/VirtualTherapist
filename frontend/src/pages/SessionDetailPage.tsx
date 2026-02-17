import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowRightIcon,
  DocumentTextIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline'
import { sessionsAPI, patientsAPI } from '@/lib/api'

interface SessionSummary {
  id: number
  full_summary: string | null
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
  created_at: string
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

export default function SessionDetailPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()

  const [session, setSession] = useState<Session | null>(null)
  const [patientName, setPatientName] = useState('')
  const [summary, setSummary] = useState<SessionSummary | null>(null)
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')

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

        // Load existing summary if present
        if (sessionData.summary_id != null) {
          try {
            const summaryData = await sessionsAPI.getSummary(Number(sessionId))
            setSummary(summaryData)
          } catch {
            // No summary yet — that's fine
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

  const handleGenerateSummary = async () => {
    if (!notes.trim()) return
    setGenerating(true)
    setError('')

    try {
      const result = await sessionsAPI.generateSummary(Number(sessionId), notes)
      setSummary(result)
      // Update session to reflect new summary_id
      setSession((prev) => prev ? { ...prev, summary_id: result.id } : prev)
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'שגיאה ביצירת הסיכום'
      setError(detail)
    } finally {
      setGenerating(false)
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

      {/* Notes Input */}
      {!summary && (
        <div className="card">
          <h2 className="text-lg font-bold mb-3">רשימות הפגישה</h2>
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
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold">סיכום הפגישה</h2>
            <div className="flex items-center gap-2">
              {summary.approved_by_therapist ? (
                <span className="badge badge-approved">
                  <CheckCircleIcon className="h-4 w-4 inline ml-1" />
                  מאושר
                </span>
              ) : (
                <span className="badge badge-draft">ממתין לבדיקה</span>
              )}
              <span className="text-xs text-gray-400">
                נוצר מ{summary.generated_from === 'text' ? 'טקסט' : 'הקלטה'}
              </span>
            </div>
          </div>

          {/* Full Summary */}
          {summary.full_summary && (
            <div className="card">
              <h3 className="font-bold text-gray-800 mb-2">סיכום כללי</h3>
              <p className="text-gray-700 whitespace-pre-line">{summary.full_summary}</p>
            </div>
          )}

          {/* Structured Sections */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <SummarySection
              title="נושאים שנדונו"
              items={summary.topics_discussed}
            />
            <SummarySection
              title="התערבויות"
              items={summary.interventions_used}
            />
            <SummarySection
              title="משימות בית"
              items={summary.homework_assigned}
            />
            <SummaryTextSection
              title="התקדמות המטופל"
              text={summary.patient_progress}
            />
            <SummaryTextSection
              title="תוכנית לפגישה הבאה"
              text={summary.next_session_plan}
            />
            <SummaryTextSection
              title="מצב רוח נצפה"
              text={summary.mood_observed}
            />
          </div>

          {/* Risk Assessment */}
          {summary.risk_assessment && (
            <div className="card border-amber-200 bg-amber-50">
              <h3 className="font-bold text-amber-800 mb-1">הערכת סיכון</h3>
              <p className="text-amber-700">{summary.risk_assessment}</p>
            </div>
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
