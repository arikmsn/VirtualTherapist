import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowRightIcon,
  CheckCircleIcon,
  DocumentTextIcon,
  SparklesIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline'
import { patientsAPI, patientSummariesAPI } from '@/lib/api'

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

interface PatientInsightSummary {
  overview: string
  progress: string
  patterns: string[]
  risks: string[]
  suggestions_for_next_sessions: string[]
}

export default function PatientSummariesPage() {
  const { patientId } = useParams<{ patientId: string }>()
  const navigate = useNavigate()

  const [patientName, setPatientName] = useState('')
  const [summaries, setSummaries] = useState<SummaryItem[]>([])
  const [loading, setLoading] = useState(true)

  // Insight state
  const [insight, setInsight] = useState<PatientInsightSummary | null>(null)
  const [insightLoading, setInsightLoading] = useState(false)
  const [insightError, setInsightError] = useState('')

  const approvedCount = summaries.filter(
    (s) => s.summary.status === 'approved' || s.summary.approved_by_therapist
  ).length

  useEffect(() => {
    const load = async () => {
      try {
        const [patient, data] = await Promise.all([
          patientsAPI.get(Number(patientId)),
          patientSummariesAPI.list(Number(patientId)),
        ])
        setPatientName(patient.full_name)
        setSummaries(data)
      } catch (err) {
        console.error('Error loading patient summaries:', err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [patientId])

  const handleGenerateInsight = async () => {
    setInsightLoading(true)
    setInsightError('')
    setInsight(null)

    try {
      const result = await patientSummariesAPI.generateInsight(Number(patientId))
      setInsight(result)
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'שגיאה ביצירת סיכום העומק'
      setInsightError(detail)
    } finally {
      setInsightLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" dir="rtl">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-therapy-calm mx-auto mb-4"></div>
          <p className="text-gray-600">טוען סיכומים...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-fade-in" dir="rtl">
      {/* Back + Header */}
      <div>
        <button
          onClick={() => navigate('/patients')}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowRightIcon className="h-5 w-5" />
          חזרה למטופלים
        </button>
        <h1 className="text-2xl font-bold">סיכומי פגישות — {patientName}</h1>
        <p className="text-gray-600 mt-1">
          {summaries.length} סיכומים ({approvedCount} מאושרים)
        </p>
      </div>

      {/* Insight Section */}
      <div className="card border-purple-200 bg-purple-50">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <SparklesIcon className="h-5 w-5 text-purple-600" />
            <h2 className="text-lg font-bold text-purple-900">סיכום עומק AI</h2>
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
          <div className="space-y-4 mt-4">
            {/* Overview */}
            <div className="bg-white rounded-lg p-4">
              <h3 className="font-bold text-gray-800 mb-2">סקירה כללית</h3>
              <p className="text-gray-700 whitespace-pre-line">{insight.overview}</p>
            </div>

            {/* Progress */}
            <div className="bg-white rounded-lg p-4">
              <h3 className="font-bold text-gray-800 mb-2">התקדמות לאורך זמן</h3>
              <p className="text-gray-700 whitespace-pre-line">{insight.progress}</p>
            </div>

            {/* Patterns */}
            {insight.patterns.length > 0 && (
              <div className="bg-white rounded-lg p-4">
                <h3 className="font-bold text-gray-800 mb-2">דפוסים מרכזיים</h3>
                <ul className="list-disc list-inside space-y-1 text-gray-700">
                  {insight.patterns.map((p, i) => (
                    <li key={i}>{p}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Risks */}
            {insight.risks.length > 0 && (
              <div className="bg-white rounded-lg p-4 border border-amber-200">
                <h3 className="font-bold text-amber-800 mb-2">נקודות סיכון למעקב</h3>
                <ul className="list-disc list-inside space-y-1 text-amber-700">
                  {insight.risks.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Suggestions */}
            {insight.suggestions_for_next_sessions.length > 0 && (
              <div className="bg-white rounded-lg p-4 border border-green-200">
                <h3 className="font-bold text-green-800 mb-2">רעיונות לפגישות הבאות</h3>
                <ul className="list-disc list-inside space-y-1 text-green-700">
                  {insight.suggestions_for_next_sessions.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Summaries List */}
      {summaries.length === 0 ? (
        <div className="card text-center py-12">
          <div className="text-6xl mb-4">📋</div>
          <h3 className="text-xl font-bold text-gray-900 mb-2">אין סיכומים עדיין</h3>
          <p className="text-gray-600">צור פגישה וייצר סיכום AI כדי לראות אותו כאן</p>
        </div>
      ) : (
        <div className="space-y-4">
          {summaries.map((item) => (
            <div
              key={item.summary.id}
              className="card hover:shadow-xl transition-shadow cursor-pointer"
              onClick={() => navigate(`/sessions/${item.session_id}`)}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-4 flex-1">
                  <div className="w-10 h-10 bg-therapy-calm text-white rounded-full flex items-center justify-center">
                    <DocumentTextIcon className="h-5 w-5" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <span className="font-bold">
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
                      <p className="text-gray-600 text-sm line-clamp-2">
                        {item.summary.full_summary}
                      </p>
                    )}

                    {item.summary.topics_discussed && item.summary.topics_discussed.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {item.summary.topics_discussed.map((topic, i) => (
                          <span
                            key={i}
                            className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full text-xs"
                          >
                            {topic}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
