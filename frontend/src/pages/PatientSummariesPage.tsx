import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowRightIcon,
  CheckCircleIcon,
  DocumentTextIcon,
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

export default function PatientSummariesPage() {
  const { patientId } = useParams<{ patientId: string }>()
  const navigate = useNavigate()

  const [patientName, setPatientName] = useState('')
  const [summaries, setSummaries] = useState<SummaryItem[]>([])
  const [loading, setLoading] = useState(true)

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
          {summaries.length} סיכומים
        </p>
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
