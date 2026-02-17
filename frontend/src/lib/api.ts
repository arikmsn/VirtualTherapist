import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

// Create axios instance
export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add token to requests
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Handle 401 errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
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
}

// Patient Summaries API
export const patientSummariesAPI = {
  list: async (patientId: number) => {
    const response = await api.get(`/patients/${patientId}/summaries`)
    return response.data
  },
}

export default api
