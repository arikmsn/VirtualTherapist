/**
 * PrintSessionPage — clean print view for a session summary.
 *
 * Route: /sessions/:sessionId/print
 *
 * Fetches session + summary + patient + therapist name, then renders a
 * print-friendly document. Calling window.print() (or the "הדפסה" button)
 * opens the browser print dialog which also supports "Save as PDF".
 *
 * CSS @media print hides the print button and navigation chrome automatically.
 */

import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { sessionsAPI, patientsAPI, therapistAPI } from '@/lib/api'
import { formatDateIL } from '@/lib/dateUtils'
import { sessionSummaryToText } from '@/lib/docText'
import AppLogo from '@/components/common/AppLogo'

interface Session {
  id: number
  patient_id: number
  session_date: string
  session_type?: string
  session_number?: number
  duration_minutes?: number
}

interface SessionSummary {
  full_summary: string | null
  topics_discussed: string[] | null
  interventions_used: string[] | null
  patient_progress: string | null
  homework_assigned: string[] | null
  next_session_plan: string | null
  mood_observed: string | null
  risk_assessment: string | null
  status: string
  approved_by_therapist: boolean
}

interface Patient {
  id: number
  full_name: string
}

const SESSION_TYPE_LABELS: Record<string, string> = {
  individual: 'פרטני',
  couples: 'זוגי',
  family: 'משפחתי',
  group: 'קבוצתי',
  intake: 'אינטייק',
  follow_up: 'מעקב',
}

function stripAiArtifacts(text: string | null): string {
  if (!text) return ''
  return text
    .replace(/^```(?:json)?\s*/gm, '')
    .replace(/^```\s*/gm, '')
    .replace(/^\*\*[^*]+\*\*\s*$/gm, '')
    .trim()
}

export default function PrintSessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const id = Number(sessionId)

  const [session, setSession] = useState<Session | null>(null)
  const [summary, setSummary] = useState<SessionSummary | null>(null)
  const [patient, setPatient] = useState<Patient | null>(null)
  const [therapistName, setTherapistName] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const load = async () => {
      try {
        const [sessionData, summaryData, profileData] = await Promise.all([
          sessionsAPI.get(id),
          sessionsAPI.getSummary(id).catch(() => null),
          therapistAPI.getProfile().catch(() => null),
        ])
        setSession(sessionData)
        setSummary(summaryData)
        if (profileData) {
          // therapist profile doesn't expose full_name directly; use email as fallback
          setTherapistName((profileData as any).full_name || (profileData as any).email || '')
        }
        const patientData = await patientsAPI.get(sessionData.patient_id)
        setPatient(patientData)
      } catch (err: any) {
        setError(err.response?.data?.detail || 'שגיאה בטעינת הנתונים')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [id])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" dir="rtl">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600"></div>
      </div>
    )
  }

  if (error || !session) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4" dir="rtl">
        <p className="text-red-600">{error || 'לא נמצא סיכום'}</p>
        <Link to={`/sessions/${id}`} className="text-indigo-600 underline text-sm">חזרה לפגישה</Link>
      </div>
    )
  }

  const summaryText = summary ? sessionSummaryToText(summary) : ''

  return (
    <div className="min-h-screen bg-white" dir="rtl">
      {/* ── Print controls (hidden in print) ── */}
      <div className="no-print sticky top-0 z-10 bg-gray-50 border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <Link to={`/sessions/${id}`} className="text-sm text-gray-600 hover:text-gray-900 flex items-center gap-1">
          ← חזרה לפגישה
        </Link>
        <button
          onClick={() => window.print()}
          className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors flex items-center gap-2"
        >
          🖨 הדפסה / שמור PDF
        </button>
      </div>

      {/* ── Document body ── */}
      <div className="max-w-2xl mx-auto px-8 py-10 print:px-0 print:py-4">
        {/* Header */}
        <div className="flex items-start justify-between mb-8 pb-4 border-b border-gray-200">
          <div>
            <AppLogo variant="full" size="sm" />
          </div>
          <div className="text-left text-xs text-gray-400 print:text-gray-600">
            <p>{new Date().toLocaleDateString('he-IL')}</p>
          </div>
        </div>

        {/* Document meta */}
        <div className="mb-6 space-y-1">
          <h1 className="text-2xl font-bold text-gray-900">סיכום פגישה</h1>
          <div className="text-sm text-gray-600 space-y-0.5">
            {patient && <p><span className="font-medium">מטופל/ת:</span> {patient.full_name}</p>}
            {therapistName && <p><span className="font-medium">מטפל/ת:</span> {therapistName}</p>}
            <p>
              <span className="font-medium">תאריך:</span> {formatDateIL(session.session_date)}
              {session.session_number && <span className="mr-3">פגישה #{session.session_number}</span>}
              {session.session_type && (
                <span className="mr-3">סוג: {SESSION_TYPE_LABELS[session.session_type] || session.session_type}</span>
              )}
              {session.duration_minutes && <span className="mr-3">{session.duration_minutes} דקות</span>}
            </p>
            {summary && (
              <p>
                <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${
                  summary.approved_by_therapist
                    ? 'bg-green-100 text-green-700'
                    : 'bg-amber-100 text-amber-700'
                }`}>
                  {summary.approved_by_therapist ? '✓ מאושר' : 'טיוטה'}
                </span>
              </p>
            )}
          </div>
        </div>

        {/* Summary content */}
        {!summary && (
          <p className="text-gray-400 text-sm">אין סיכום לפגישה זו.</p>
        )}

        {summary && (
          <div className="space-y-6 text-sm leading-relaxed">
            {summary.full_summary && (
              <section>
                <h2 className="font-bold text-gray-900 mb-2 text-base border-b border-gray-100 pb-1">סיכום כללי</h2>
                <p className="text-gray-800 whitespace-pre-line">{stripAiArtifacts(summary.full_summary)}</p>
              </section>
            )}

            {(summary.topics_discussed ?? []).length > 0 && (
              <section>
                <h2 className="font-bold text-gray-900 mb-2 text-base border-b border-gray-100 pb-1">נושאים שעלו</h2>
                <ul className="list-disc list-inside space-y-1 text-gray-800">
                  {(summary.topics_discussed ?? []).map((t, i) => <li key={i}>{t}</li>)}
                </ul>
              </section>
            )}

            {(summary.interventions_used ?? []).length > 0 && (
              <section>
                <h2 className="font-bold text-gray-900 mb-2 text-base border-b border-gray-100 pb-1">התערבויות</h2>
                <ul className="list-disc list-inside space-y-1 text-gray-800">
                  {(summary.interventions_used ?? []).map((i, idx) => <li key={idx}>{i}</li>)}
                </ul>
              </section>
            )}

            {summary.patient_progress && (
              <section>
                <h2 className="font-bold text-gray-900 mb-2 text-base border-b border-gray-100 pb-1">התקדמות</h2>
                <p className="text-gray-800 whitespace-pre-line">{summary.patient_progress}</p>
              </section>
            )}

            {(summary.homework_assigned ?? []).length > 0 && (
              <section>
                <h2 className="font-bold text-gray-900 mb-2 text-base border-b border-gray-100 pb-1">משימות לבית</h2>
                <ul className="list-disc list-inside space-y-1 text-gray-800">
                  {(summary.homework_assigned ?? []).map((h, i) => <li key={i}>{h}</li>)}
                </ul>
              </section>
            )}

            {summary.next_session_plan && (
              <section>
                <h2 className="font-bold text-gray-900 mb-2 text-base border-b border-gray-100 pb-1">תוכנית לפגישה הבאה</h2>
                <p className="text-gray-800 whitespace-pre-line">{summary.next_session_plan}</p>
              </section>
            )}

            {summary.mood_observed && (
              <section>
                <h2 className="font-bold text-gray-900 mb-2 text-base border-b border-gray-100 pb-1">מצב רוח שנצפה</h2>
                <p className="text-gray-800">{summary.mood_observed}</p>
              </section>
            )}

            {summary.risk_assessment && (
              <section>
                <h2 className="font-bold text-gray-900 mb-2 text-base border-b border-gray-100 pb-1">הערכת סיכון</h2>
                <p className="text-gray-800">{summary.risk_assessment}</p>
              </section>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="mt-12 pt-4 border-t border-gray-200 text-xs text-gray-400 text-center">
          <p>מסמך זה הופק על ידי TherapyCompanion.AI · סודי</p>
          {!summaryText && null}
        </div>
      </div>

      {/* Print-specific styles */}
      <style>{`
        @media print {
          .no-print { display: none !important; }
          body { background: white; }
        }
      `}</style>
    </div>
  )
}
