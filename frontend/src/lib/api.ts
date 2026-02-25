import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

// Create axios instance
export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Single localStorage key for the JWT — matches AuthProvider.tsx
const TOKEN_KEY = 'access_token'

// Add token to requests
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(TOKEN_KEY)
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Handle 401 errors — save current path, clear token, redirect to login
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Save the current page so LoginPage can redirect back after login
      const currentPath = window.location.pathname + window.location.search
      if (currentPath !== '/login') {
        sessionStorage.setItem('redirect_after_login', currentPath)
      }
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem('auth_user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Auth API
export const authAPI = {
  login: async (email: string, password: string) => {
    const formData = new FormData()
    formData.append('username', email)
    formData.append('password', password)

    const response = await api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    return response.data
  },

  register: async (email: string, password: string, fullName: string, phone?: string) => {
    const response = await api.post('/auth/register', {
      email,
      password,
      full_name: fullName,
      phone,
    })
    return response.data
  },

  // Silent token refresh — called proactively by AuthProvider before expiry.
  // Uses the current Authorization header (set by request interceptor).
  // Returns 401 if token is already expired → interceptor handles logout.
  refresh: async (): Promise<{ access_token: string; therapist_id: number; email: string; full_name: string }> => {
    const response = await api.post('/auth/refresh')
    return response.data
  },
}

// Agent API
export const agentAPI = {
  chat: async (message: string, context?: any) => {
    const response = await api.post('/agent/chat', { message, context })
    return response.data
  },

  executeCommand: async (command: string, args?: string) => {
    const response = await api.post('/agent/command', { command, args })
    return response.data
  },

  startOnboarding: async () => {
    const response = await api.post('/agent/onboarding/start')
    return response.data
  },

  completeOnboardingStep: async (step: number, data: any) => {
    const response = await api.post('/agent/onboarding/complete-step', { step, data })
    return response.data
  },
}

// Messages API
export const messagesAPI = {
  create: async (patientId: number, messageType: string, context?: any) => {
    const response = await api.post('/messages/create', {
      patient_id: patientId,
      message_type: messageType,
      context,
    })
    return response.data
  },

  getPending: async () => {
    const response = await api.get('/messages/pending')
    return response.data
  },

  approve: async (messageId: number) => {
    const response = await api.post('/messages/approve', { message_id: messageId })
    return response.data
  },

  reject: async (messageId: number, reason?: string) => {
    const response = await api.post('/messages/reject', { message_id: messageId, reason })
    return response.data
  },

  edit: async (messageId: number, newContent: string) => {
    const response = await api.post('/messages/edit', {
      message_id: messageId,
      new_content: newContent,
    })
    return response.data
  },

  send: async (messageId: number) => {
    const response = await api.post(`/messages/send/${messageId}`)
    return response.data
  },

  getPatientHistory: async (patientId: number) => {
    const response = await api.get(`/messages/patient/${patientId}`)
    return response.data
  },

  // Messages Center v1 (Phase C)
  // Returns { content: string, message_type: string } — no DB record created
  generateDraft: async (patientId: number, messageType: string, context?: Record<string, string>) => {
    const response = await api.post('/messages/generate', {
      patient_id: patientId,
      message_type: messageType,
      context,
    })
    return response.data as { content: string; message_type: string }
  },

  // Create + send/schedule atomically (replaces draft two-step flow)
  compose: async (data: {
    patient_id: number
    message_type: string
    content: string
    recipient_phone?: string
    send_at?: string | null
    related_session_id?: number   // links session_reminder to a specific session
  }) => {
    const response = await api.post('/messages/compose', {
      patient_id: data.patient_id,
      message_type: data.message_type,
      content: data.content,
      recipient_phone: data.recipient_phone || null,
      send_at: data.send_at || null,
      related_session_id: data.related_session_id ?? null,
    })
    return response.data
  },

  sendOrSchedule: async (messageId: number, data: {
    content?: string           // omitted for session_reminder (template-only)
    recipient_phone?: string
    send_at?: string | null    // ISO datetime string or null
  }) => {
    const response = await api.post(`/messages/${messageId}/send-or-schedule`, {
      content: data.content ?? null,
      recipient_phone: data.recipient_phone || null,
      send_at: data.send_at || null,
    })
    return response.data
  },

  cancelMessage: async (messageId: number) => {
    const response = await api.post(`/messages/${messageId}/cancel`)
    return response.data
  },

  editScheduled: async (messageId: number, data: {
    content?: string
    recipient_phone?: string
    send_at?: string | null
  }) => {
    const response = await api.patch(`/messages/${messageId}`, data)
    return response.data
  },

  deleteMessage: async (messageId: number) => {
    const response = await api.delete(`/messages/${messageId}`)
    return response.data
  },

  // Message Control Center: all messages across all patients
  getAll: async (params?: {
    patient_id?: number
    status?: string
    date_from?: string
    date_to?: string
  }) => {
    const response = await api.get('/messages/', { params })
    return response.data
  },
}

// Patients API
export const patientsAPI = {
  list: async (status?: string) => {
    const params = status ? { status } : {}
    const response = await api.get('/patients/', { params })
    return response.data
  },

  get: async (patientId: number) => {
    const response = await api.get(`/patients/${patientId}`)
    return response.data
  },

  create: async (data: {
    full_name: string
    phone?: string
    email?: string
    start_date?: string
    primary_concerns?: string
    diagnosis?: string
    treatment_goals?: string[]
    preferred_contact_time?: string
    allow_ai_contact?: boolean
  }) => {
    const response = await api.post('/patients/', data)
    return response.data
  },

  update: async (patientId: number, data: Record<string, unknown>) => {
    const response = await api.put(`/patients/${patientId}`, data)
    return response.data
  },

  delete: async (patientId: number) => {
    const response = await api.delete(`/patients/${patientId}`)
    return response.data
  },
}

// Patient Notes API
export const patientNotesAPI = {
  list: async (patientId: number) => {
    const response = await api.get(`/patients/${patientId}/notes`)
    return response.data
  },

  create: async (patientId: number, content: string) => {
    const response = await api.post(`/patients/${patientId}/notes`, { content })
    return response.data
  },

  delete: async (patientId: number, noteId: number) => {
    const response = await api.delete(`/patients/${patientId}/notes/${noteId}`)
    return response.data
  },
}

// Sessions API
export const sessionsAPI = {
  list: async (limit?: number) => {
    const params = limit ? { limit } : {}
    const response = await api.get('/sessions/', { params })
    return response.data
  },

  get: async (sessionId: number) => {
    const response = await api.get(`/sessions/${sessionId}`)
    return response.data
  },

  create: async (data: {
    patient_id: number
    session_date: string
    session_type?: string
    duration_minutes?: number
    start_time?: string
    end_time?: string
    notify_patient?: boolean   // send WhatsApp appointment reminder (default false)
  }) => {
    const response = await api.post('/sessions/', data)
    return response.data
  },

  update: async (sessionId: number, data: Record<string, unknown>) => {
    const response = await api.put(`/sessions/${sessionId}`, data)
    return response.data
  },

  getPatientSessions: async (patientId: number) => {
    const response = await api.get(`/sessions/patient/${patientId}`)
    return response.data
  },

  generateSummary: async (sessionId: number, notes: string) => {
    const response = await api.post(`/sessions/${sessionId}/summary/from-text`, {
      notes,
    })
    return response.data
  },

  generateSummaryFromAudio: async (sessionId: number, audioBlob: Blob, language?: string) => {
    const formData = new FormData()
    formData.append('audio', audioBlob, 'recording.webm')
    if (language) {
      formData.append('language', language)
    }
    const response = await api.post(
      `/sessions/${sessionId}/summary/from-audio`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
    return response.data
  },

  getSummary: async (sessionId: number) => {
    const response = await api.get(`/sessions/${sessionId}/summary`)
    return response.data
  },

  patchSummary: async (sessionId: number, updates: Record<string, unknown>) => {
    const response = await api.patch(`/sessions/${sessionId}/summary`, updates)
    return response.data
  },

  approveSummary: async (sessionId: number) => {
    const response = await api.post('/sessions/summary/approve', {
      session_id: sessionId,
    })
    return response.data
  },

  listByDate: async (dateStr?: string) => {
    const params = dateStr ? { date: dateStr } : {}
    const response = await api.get('/sessions/by-date', { params })
    return response.data
  },

  getPrepBrief: async (sessionId: number) => {
    const response = await api.post(`/sessions/${sessionId}/prep-brief`)
    return response.data
  },

  delete: async (sessionId: number, notifyPatient = false) => {
    await api.delete(`/sessions/${sessionId}`, { params: { notify_patient: notifyPatient } })
  },
}

// Patient Summaries API
export const patientSummariesAPI = {
  list: async (patientId: number) => {
    const response = await api.get(`/patients/${patientId}/summaries`)
    return response.data
  },

  generateInsight: async (patientId: number) => {
    const response = await api.post(`/patients/${patientId}/insight-summary`)
    return response.data
  },

  generateDeepSummary: async (patientId: number) => {
    const response = await api.post(`/patients/${patientId}/deep-summary`)
    return response.data as {
      overall_treatment_picture: string
      timeline_highlights: string[]
      goals_and_tasks: string
      measurable_progress: string
      directions_for_next_phase: string
    }
  },
}

// Treatment Plan API
export const treatmentPlanAPI = {
  preview: async (patientId: number) => {
    const response = await api.post(`/patients/${patientId}/treatment-plan/preview`)
    return response.data as {
      goals: Array<{ id: string; title: string; description: string }>
      focus_areas: string[]
      suggested_interventions: string[]
    }
  },
}

// Exercises API
export const exercisesAPI = {
  list: async (patientId: number) => {
    const response = await api.get('/exercises/', { params: { patient_id: patientId } })
    return response.data
  },

  create: async (data: { patient_id: number; description: string; session_summary_id?: number }) => {
    const response = await api.post('/exercises/', data)
    return response.data
  },

  patch: async (exerciseId: number, data: { completed?: boolean; description?: string }) => {
    const response = await api.patch(`/exercises/${exerciseId}`, data)
    return response.data
  },

  delete: async (exerciseId: number) => {
    await api.delete(`/exercises/${exerciseId}`)
  },

  getOpenCount: async (): Promise<number> => {
    const response = await api.get('/exercises/open-count')
    return response.data.open_count as number
  },
}

// Therapist Side Notebook API
export const therapistNotesAPI = {
  list: async () => {
    const response = await api.get('/therapist/notes')
    return response.data
  },

  create: async (data: { title?: string; content: string; tags?: string[] }) => {
    const response = await api.post('/therapist/notes', data)
    return response.data
  },

  update: async (noteId: number, data: { title?: string; content?: string; tags?: string[] }) => {
    const response = await api.patch(`/therapist/notes/${noteId}`, data)
    return response.data
  },

  delete: async (noteId: number) => {
    const response = await api.delete(`/therapist/notes/${noteId}`)
    return response.data
  },
}

// Therapist Profile API (Twin v0.1)
export const therapistAPI = {
  getProfile: async () => {
    const response = await api.get('/therapist/profile')
    return response.data
  },

  updateTwinControls: async (data: {
    tone_warmth?: number
    directiveness?: number
    prohibitions?: string[]
    custom_rules?: string | null
    approach_description?: string | null
    education?: string | null
    certifications?: string | null
    years_of_experience?: string | null
    areas_of_expertise?: string | null
  }) => {
    const response = await api.patch('/therapist/profile', data)
    return response.data
  },

  resetTwinControls: async () => {
    const response = await api.post('/therapist/profile/reset')
    return response.data
  },

  getTodayInsights: async () => {
    const response = await api.get('/therapist/today-insights')
    return response.data as {
      insights: Array<{ patient_id: number; title: string; body: string }>
    }
  },
}

export default api
