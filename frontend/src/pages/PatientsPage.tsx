import { useState } from 'react'
import { UserGroupIcon, PlusIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline'

// Mock data - in real app, fetch from API
const mockPatients = [
  {
    id: 1,
    name: 'יוסי כהן',
    status: 'active',
    lastSession: '2024-02-14',
    nextSession: '2024-02-21',
    pendingExercises: 2,
    completedSessions: 8,
  },
  {
    id: 2,
    name: 'שרה לוי',
    status: 'active',
    lastSession: '2024-02-13',
    nextSession: '2024-02-20',
    pendingExercises: 1,
    completedSessions: 12,
  },
  {
    id: 3,
    name: 'דני מזרחי',
    status: 'active',
    lastSession: '2024-02-15',
    nextSession: '2024-02-22',
    pendingExercises: 0,
    completedSessions: 5,
  },
]

export default function PatientsPage() {
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedPatient, setSelectedPatient] = useState<number | null>(null)

  const filteredPatients = mockPatients.filter((p) =>
    p.name.includes(searchTerm)
  )

  return (
    <div className="space-y-6 animate-fade-in" dir="rtl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">מטופלים</h1>
          <p className="text-gray-600 mt-2">נהל את כל המטופלים שלך במקום אחד</p>
        </div>
        <button className="btn-primary flex items-center gap-2">
          <PlusIcon className="h-5 w-5" />
          מטופל חדש
        </button>
      </div>

      {/* Search */}
      <div className="card">
        <div className="relative">
          <MagnifyingGlassIcon className="absolute right-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="input-field pr-10"
            placeholder="חפש מטופל..."
          />
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card bg-blue-50 border border-blue-200">
          <div className="text-3xl font-bold text-blue-900">24</div>
          <div className="text-sm text-blue-700 mt-1">מטופלים פעילים</div>
        </div>
        <div className="card bg-green-50 border border-green-200">
          <div className="text-3xl font-bold text-green-900">18</div>
          <div className="text-sm text-green-700 mt-1">פגישות השבוע</div>
        </div>
        <div className="card bg-amber-50 border border-amber-200">
          <div className="text-3xl font-bold text-amber-900">5</div>
          <div className="text-sm text-amber-700 mt-1">תרגילים ממתינים</div>
        </div>
        <div className="card bg-purple-50 border border-purple-200">
          <div className="text-3xl font-bold text-purple-900">92%</div>
          <div className="text-sm text-purple-700 mt-1">שביעות רצון</div>
        </div>
      </div>

      {/* Patients List */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredPatients.map((patient) => (
          <div
            key={patient.id}
            className="card hover:shadow-xl transition-all cursor-pointer"
            onClick={() => setSelectedPatient(patient.id)}
          >
            {/* Patient Header */}
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 bg-therapy-calm text-white rounded-full flex items-center justify-center font-bold text-lg">
                {patient.name.charAt(0)}
              </div>
              <div className="flex-1">
                <div className="font-bold text-lg">{patient.name}</div>
                <div className="badge badge-approved text-xs">פעיל</div>
              </div>
            </div>

            {/* Patient Stats */}
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">פגישה אחרונה:</span>
                <span className="font-medium">
                  {new Date(patient.lastSession).toLocaleDateString('he-IL')}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">פגישה הבאה:</span>
                <span className="font-medium">
                  {new Date(patient.nextSession).toLocaleDateString('he-IL')}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">פגישות שהושלמו:</span>
                <span className="font-medium">{patient.completedSessions}</span>
              </div>
            </div>

            {/* Pending Exercises */}
            {patient.pendingExercises > 0 && (
              <div className="mt-4 bg-amber-50 border border-amber-200 rounded-lg p-3">
                <div className="text-sm text-amber-800 font-medium">
                  ⏳ {patient.pendingExercises} תרגילים ממתינים
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="mt-4 pt-4 border-t border-gray-200 grid grid-cols-2 gap-2">
              <button className="text-sm btn-secondary py-2">
                📝 סיכום חדש
              </button>
              <button className="text-sm btn-secondary py-2">
                💬 שלח הודעה
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
