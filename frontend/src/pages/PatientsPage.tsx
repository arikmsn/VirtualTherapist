import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { PlusIcon, MagnifyingGlassIcon, XMarkIcon, EyeIcon, EyeSlashIcon } from '@heroicons/react/24/outline'
import { patientsAPI, sessionsAPI } from '@/lib/api'
import PhoneInput from '@/components/PhoneInput'

interface Patient {
  id: number
  therapist_id: number
  full_name: string
  phone?: string
  email?: string
  status: string
  start_date?: string
  allow_ai_contact: boolean
  preferred_contact_time?: string
  completed_exercises_count: number
  missed_exercises_count: number
  created_at: string
}

interface Session {
  id: number
  session_date: string
}

export default function PatientsPage() {
  const navigate = useNavigate()
  const [patients, setPatients] = useState<Patient[]>([])
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [showInactive, setShowInactive] = useState(false)
  const [showCreateForm, setShowCreateForm] = useState(false)

  // Create form state
  const [newPatient, setNewPatient] = useState({
    full_name: '',
    phone: '',
    email: '',
    primary_concerns: '',
  })
  const [creating, setCreating] = useState(false)

  const loadPatients = async () => {
    try {
      const data = await patientsAPI.list()
      setPatients(data)
    } catch (error) {
      console.error('Error loading patients:', error)
    }
  }

  const loadSessions = async () => {
    try {
      const data = await sessionsAPI.list()
      setSessions(data)
    } catch (error) {
      console.error('Error loading sessions:', error)
    }
  }

  useEffect(() => {
    const init = async () => {
      await Promise.all([loadPatients(), loadSessions()])
      setLoading(false)
    }
    init()
  }, [])

  const handleCreatePatient = async () => {
    if (!newPatient.full_name.trim()) return
    setCreating(true)
    try {
      await patientsAPI.create({
        full_name: newPatient.full_name,
        phone: newPatient.phone || undefined,
        email: newPatient.email || undefined,
        primary_concerns: newPatient.primary_concerns || undefined,
      })
      setNewPatient({ full_name: '', phone: '', email: '', primary_concerns: '' })
      setShowCreateForm(false)
      await loadPatients()
    } catch (error) {
      console.error('Error creating patient:', error)
    } finally {
      setCreating(false)
    }
  }

  // Sessions this week
  const now = new Date()
  const dayOfWeek = now.getDay()
  const startOfWeek = new Date(now)
  startOfWeek.setDate(now.getDate() - dayOfWeek)
  startOfWeek.setHours(0, 0, 0, 0)
  const endOfWeek = new Date(startOfWeek)
  endOfWeek.setDate(startOfWeek.getDate() + 7)
  const sessionsThisWeek = sessions.filter((s) => {
    const d = new Date(s.session_date)
    return d >= startOfWeek && d < endOfWeek
  }).length

  const activeCount = patients.filter((p) => p.status === 'active').length
  const completedExercisesCount = patients.reduce((sum, p) => sum + p.completed_exercises_count, 0)

  const filteredPatients = patients
    .filter((p) => showInactive || p.status !== 'inactive')
    .filter((p) => p.full_name.includes(searchTerm))
    .sort((a, b) => a.full_name.localeCompare(b.full_name, 'he'))

  const inactiveCount = patients.filter((p) => p.status === 'inactive').length

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64" dir="rtl">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-therapy-calm mx-auto mb-4"></div>
          <p className="text-gray-600">טוען מטופלים...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in" dir="rtl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">מטופלים</h1>
          <p className="text-gray-600 mt-2">נהל את כל המטופלים שלך במקום אחד</p>
        </div>
        <button
          onClick={() => setShowCreateForm(true)}
          className="btn-primary flex items-center gap-2"
        >
          <PlusIcon className="h-5 w-5" />
          מטופל חדש
        </button>
      </div>

      {/* Search + inactive toggle */}
      <div className="card">
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <MagnifyingGlassIcon className="absolute right-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="input-field pr-10"
              placeholder="חפש מטופל..."
            />
          </div>
          {inactiveCount > 0 && (
            <button
              onClick={() => setShowInactive((v) => !v)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${
                showInactive
                  ? 'bg-gray-200 text-gray-800 hover:bg-gray-300'
                  : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
              }`}
            >
              {showInactive ? (
                <EyeSlashIcon className="h-4 w-4" />
              ) : (
                <EyeIcon className="h-4 w-4" />
              )}
              {showInactive ? 'הסתר לא פעילים' : `הצג לא פעילים (${inactiveCount})`}
            </button>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card bg-blue-50 border border-blue-200">
          <div className="text-3xl font-bold text-blue-900">{activeCount}</div>
          <div className="text-sm text-blue-700 mt-1">מטופלים פעילים</div>
        </div>
        <div className="card bg-green-50 border border-green-200">
          <div className="text-3xl font-bold text-green-900">{sessionsThisWeek}</div>
          <div className="text-sm text-green-700 mt-1">פגישות השבוע</div>
        </div>
        <div className="card bg-purple-50 border border-purple-200">
          <div className="text-3xl font-bold text-purple-900">{completedExercisesCount}</div>
          <div className="text-sm text-purple-700 mt-1">תרגילים שהושלמו</div>
        </div>
      </div>

      {/* Patients List */}
      {filteredPatients.length === 0 ? (
        <div className="card text-center py-12">
          <div className="text-6xl mb-4">👥</div>
          <h3 className="text-xl font-bold text-gray-900 mb-2">
            {patients.length === 0
              ? 'אין מטופלים עדיין'
              : !showInactive && inactiveCount > 0 && activeCount === 0
              ? 'כל המטופלים לא פעילים'
              : 'לא נמצאו תוצאות'}
          </h3>
          <p className="text-gray-600">
            {patients.length === 0
              ? 'לחץ על "מטופל חדש" כדי להוסיף את המטופל הראשון'
              : !showInactive && inactiveCount > 0 && activeCount === 0
              ? 'לחץ על "הצג לא פעילים" כדי לראות את כל המטופלים'
              : 'נסה לחפש עם מונח אחר'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredPatients.map((patient) => (
            <div
              key={patient.id}
              className="card hover:shadow-xl transition-all cursor-pointer"
              onClick={() => navigate(`/patients/${patient.id}`)}
            >
              {/* Patient Header */}
              <div className="flex items-center gap-3 mb-4">
                <div className="w-12 h-12 bg-therapy-calm text-white rounded-full flex items-center justify-center font-bold text-lg">
                  {patient.full_name.charAt(0)}
                </div>
                <div className="flex-1">
                  <div className="font-bold text-lg">{patient.full_name}</div>
                  <div className={`badge text-xs ${
                    patient.status === 'active' ? 'badge-approved' : 'badge-draft'
                  }`}>
                    {patient.status === 'active' ? 'פעיל' :
                     patient.status === 'paused' ? 'מושהה' :
                     patient.status === 'completed' ? 'הושלם' : 'לא פעיל'}
                  </div>
                </div>
              </div>

              {/* Patient Stats */}
              <div className="space-y-2 text-sm">
                {patient.phone && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">טלפון:</span>
                    <span className="font-medium">{patient.phone}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-gray-600">תרגילים שהושלמו:</span>
                  <span className="font-medium">{patient.completed_exercises_count}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">נוצר בתאריך:</span>
                  <span className="font-medium">
                    {new Date(patient.created_at).toLocaleDateString('he-IL')}
                  </span>
                </div>
              </div>

              {/* Actions */}
              <div className="mt-4 pt-4 border-t border-gray-200 grid grid-cols-2 gap-2">
                <button
                  className="text-sm btn-secondary py-2"
                  onClick={(e) => {
                    e.stopPropagation()
                    navigate(`/patients/${patient.id}`, { state: { initialTab: 'summaries' } })
                  }}
                >
                  סיכומים
                </button>
                <button
                  className="text-sm btn-secondary py-2"
                  onClick={(e) => {
                    e.stopPropagation()
                    navigate(`/patients/${patient.id}`, { state: { initialTab: 'inbetween' } })
                  }}
                >
                  שלח הודעה
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Patient Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" dir="rtl">
          <div className="bg-white rounded-xl p-8 max-w-lg w-full mx-4 animate-fade-in">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold">מטופל חדש</h2>
              <button onClick={() => setShowCreateForm(false)}>
                <XMarkIcon className="h-6 w-6 text-gray-500 hover:text-gray-700" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">שם מלא *</label>
                <input
                  type="text"
                  value={newPatient.full_name}
                  onChange={(e) => setNewPatient({ ...newPatient, full_name: e.target.value })}
                  className="input-field"
                  placeholder="שם מלא של המטופל"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">טלפון</label>
                <PhoneInput
                  value={newPatient.phone}
                  onChange={(e164) => setNewPatient({ ...newPatient, phone: e164 })}
                  className="w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">אימייל</label>
                <input
                  type="email"
                  value={newPatient.email}
                  onChange={(e) => setNewPatient({ ...newPatient, email: e.target.value })}
                  className="input-field"
                  placeholder="patient@example.com"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">נושאים עיקריים</label>
                <textarea
                  value={newPatient.primary_concerns}
                  onChange={(e) => setNewPatient({ ...newPatient, primary_concerns: e.target.value })}
                  className="input-field h-20 resize-none"
                  placeholder="תיאור קצר של הנושאים העיקריים..."
                />
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={handleCreatePatient}
                disabled={!newPatient.full_name.trim() || creating}
                className="btn-primary flex-1 disabled:opacity-50"
              >
                {creating ? 'יוצר...' : 'צור מטופל'}
              </button>
              <button
                onClick={() => setShowCreateForm(false)}
                className="btn-secondary flex-1"
              >
                ביטול
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
