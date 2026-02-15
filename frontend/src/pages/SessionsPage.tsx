import { useState } from 'react'
import { DocumentTextIcon, CheckCircleIcon, ClockIcon } from '@heroicons/react/24/outline'

// Mock data - in real app, fetch from API
const mockSessions = [
  {
    id: 1,
    patientName: 'יוסי כהן',
    date: '2024-02-15',
    duration: 50,
    hasSummary: true,
    summaryApproved: true,
    topics: ['חרדה חברתית', 'תרגילי חשיפה'],
  },
  {
    id: 2,
    patientName: 'שרה לוי',
    date: '2024-02-14',
    duration: 45,
    hasSummary: true,
    summaryApproved: false,
    topics: ['דיכאון', 'מחשבות אוטומטיות'],
  },
  {
    id: 3,
    patientName: 'דני מזרחי',
    date: '2024-02-14',
    duration: 50,
    hasSummary: false,
    summaryApproved: false,
    topics: [],
  },
]

export default function SessionsPage() {
  const [filter, setFilter] = useState<'all' | 'pending' | 'approved'>('all')

  const filteredSessions = mockSessions.filter((session) => {
    if (filter === 'pending') return session.hasSummary && !session.summaryApproved
    if (filter === 'approved') return session.summaryApproved
    return true
  })

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
            הכל ({mockSessions.length})
          </button>
          <button
            onClick={() => setFilter('pending')}
            className={`px-4 py-2 rounded-lg font-medium transition-all ${
              filter === 'pending'
                ? 'bg-therapy-warm text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            ממתין לאישור (1)
          </button>
          <button
            onClick={() => setFilter('approved')}
            className={`px-4 py-2 rounded-lg font-medium transition-all ${
              filter === 'approved'
                ? 'bg-therapy-support text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            מאושרים (1)
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
                    <h3 className="text-lg font-bold">{session.patientName}</h3>
                    {session.summaryApproved && (
                      <span className="badge badge-approved">
                        <CheckCircleIcon className="h-4 w-4 inline ml-1" />
                        אושר
                      </span>
                    )}
                    {session.hasSummary && !session.summaryApproved && (
                      <span className="badge badge-pending">
                        <ClockIcon className="h-4 w-4 inline ml-1" />
                        ממתין לאישור
                      </span>
                    )}
                    {!session.hasSummary && (
                      <span className="badge badge-draft">
                        אין סיכום
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-4 text-sm text-gray-600 mb-3">
                    <span>📅 {new Date(session.date).toLocaleDateString('he-IL')}</span>
                    <span>⏱️ {session.duration} דקות</span>
                    <span>פגישה #{session.id}</span>
                  </div>

                  {session.topics.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {session.topics.map((topic, i) => (
                        <span
                          key={i}
                          className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm"
                        >
                          {topic}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-2">
                {!session.hasSummary && (
                  <button className="btn-primary whitespace-nowrap">
                    צור סיכום
                  </button>
                )}
                {session.hasSummary && !session.summaryApproved && (
                  <button className="btn-success whitespace-nowrap">
                    אשר סיכום
                  </button>
                )}
                {session.summaryApproved && (
                  <button className="btn-secondary whitespace-nowrap">
                    צפה בסיכום
                  </button>
                )}
              </div>
            </div>

            {/* Sample Summary Preview (if approved) */}
            {session.summaryApproved && (
              <div className="mt-4 pt-4 border-t border-gray-200">
                <div className="bg-gray-50 rounded-lg p-4 text-sm">
                  <p className="text-gray-700 leading-relaxed">
                    <strong>נושאים:</strong> דיברנו על חרדה חברתית, במיוחד בפגישות עבודה.
                    <br />
                    <strong>התערבות:</strong> ביצענו תרגיל חשיפה - סימולציה של פגישה.
                    <br />
                    <strong>התקדמות:</strong> פחות הימנעות, יותר ביטחון.
                    <br />
                    <strong>משימה:</strong> זיהוי מחשבות אוטומטיות לפגישה הבאה.
                  </p>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {filteredSessions.length === 0 && (
        <div className="card text-center py-12">
          <div className="text-6xl mb-4">📋</div>
          <h3 className="text-xl font-bold text-gray-900 mb-2">
            אין פגישות תואמות
          </h3>
          <p className="text-gray-600">
            נסה לשנות את הסינון או צור פגישה חדשה
          </p>
        </div>
      )}
    </div>
  )
}
