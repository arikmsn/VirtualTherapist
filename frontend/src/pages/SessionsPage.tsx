import { useState, useEffect } from 'react'
import { DocumentTextIcon, CheckCircleIcon } from '@heroicons/react/24/outline'
import { sessionsAPI, patientsAPI } from '@/lib/api'

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

export default function SessionsPage() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [patientMap, setPatientMap] = useState<Record<number, string>>({})
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'all' | 'with_summary' | 'no_summary'>('all')

  useEffect(() => {
    const loadData = async () => {
      try {
        const [sessionsData, patientsData] = await Promise.all([
          sessionsAPI.list(),
          patientsAPI.list(),
        ])
        setSessions(sessionsData)
        const map: Record<number, string> = {}
        patientsData.forEach((p: Patient) => {
          map[p.id] = p.full_name
        })
        setPatientMap(map)
      } catch (error) {
        console.error('Error loading sessions:', error)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [])

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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">פגישות וסיכומים</h1>
          <p className="text-gray-600 mt-2">כל הפגישות והסיכומים במקום אחד</p>
        </div>
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
            <div className="flex items-start justify-between">
              {/* Session Info */}
              <div className="flex items-start gap-4 flex-1">
                <div className="w-12 h-12 bg-therapy-calm text-white rounded-full flex items-center justify-center">
                  <DocumentTextIcon className="h-6 w-6" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
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

                  <div className="flex items-center gap-4 text-sm text-gray-600 mb-3">
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
                        {session.session_type}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-2">
                {session.summary_id == null && (
                  <button className="btn-primary whitespace-nowrap">
                    צור סיכום
                  </button>
                )}
                {session.summary_id != null && (
                  <button className="btn-secondary whitespace-nowrap">
                    צפה בסיכום
                  </button>
                )}
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
              ? 'צור פגישה חדשה דרך לוח הבקרה'
              : 'נסה לשנות את הסינון'}
          </p>
        </div>
      )}
    </div>
  )
}
