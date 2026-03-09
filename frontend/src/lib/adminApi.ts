/**
 * Admin Panel API client.
 * All requests use the admin JWT from sessionStorage['admin_token'].
 */

const BASE = (import.meta.env.VITE_API_URL as string | undefined) || 'http://localhost:8000/api/v1'

function adminHeaders(): Record<string, string> {
  const token = sessionStorage.getItem('admin_token') || ''
  return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: adminHeaders() })
  if (!res.ok) throw new Error(`${res.status}`)
  return res.json()
}

async function patch<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PATCH',
    headers: adminHeaders(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`${res.status}`)
  return res.json()
}

export interface DashboardStats {
  total_therapists: number
  active_last_30_days: number
  total_ai_calls: number
  total_tokens: number
  unread_alerts: number
  new_signups_last_7_days: number
}

export interface TherapistRow {
  id: number
  email: string
  full_name: string
  is_active: boolean
  is_admin: boolean
  is_blocked: boolean
  last_login: string | null
  created_at: string
  session_count: number
  ai_call_count: number
}

export interface AlertRow {
  id: number
  alert_type: string
  message: string
  therapist_id: number | null
  therapist_name: string | null
  is_read: boolean
  created_at: string
}

export interface UsageDay {
  date: string
  calls: number
  tokens: number
}

export interface UsageStats {
  by_day: UsageDay[]
  by_flow: { flow_type: string; count: number }[]
  by_model: { model: string; count: number }[]
  total_calls: number
  total_tokens: number
}

export const adminAPI = {
  /** Get admin JWT — call from easter egg handler */
  async getToken(email: string, password: string): Promise<string> {
    const res = await fetch(`${BASE}/auth/admin-token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (!res.ok) throw new Error(`${res.status}`)
    const data = await res.json()
    return data.admin_token
  },

  getDashboard: () => get<DashboardStats>('/admin-panel/dashboard'),
  getTherapists: () => get<TherapistRow[]>('/admin-panel/therapists'),
  blockTherapist: (id: number, is_blocked: boolean) =>
    patch<TherapistRow>(`/admin-panel/therapists/${id}/block`, { is_blocked }),
  getUsage: (days = 30) => get<UsageStats>(`/admin-panel/usage?days=${days}`),
  getAlerts: (unreadOnly = false) =>
    get<AlertRow[]>(`/admin-panel/alerts${unreadOnly ? '?unread_only=true' : ''}`),
  markAlertRead: (id: number) => patch<{ ok: boolean }>(`/admin-panel/alerts/${id}/read`),
  markAllRead: () => patch<{ ok: boolean }>('/admin-panel/alerts/read-all'),
}
