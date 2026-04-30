/**
 * Shared axios instance + per-resource API wrappers (FE-1).
 *
 * - Request interceptor: attach the auth store's access token, if present.
 * - Response interceptor:
 *     - 401 -> clear auth state and redirect to /login.
 *     - 4xx/5xx -> bubble up so callers can show ElMessage.error(detail).
 */
import axios from 'axios'
// Direct ESM import. Pinia stores are factory functions (`useAuthStore()`)
// — they are only *called* inside the interceptor, never at module top
// level, so the circular import (auth -> api -> auth) is safe in ESM.
import { useAuthStore } from '../stores/auth'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  try {
    const auth = useAuthStore()
    if (auth.accessToken) {
      config.headers = config.headers || {}
      config.headers.Authorization = `Bearer ${auth.accessToken}`
    }
  } catch (_) {
    // Pinia not initialised yet (very early app boot, before main.js installs it).
  }
  return config
})

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status = error.response?.status
    const msg = error.response?.data?.detail || error.message || '请求失败'
    if (status === 401) {
      try {
        const auth = useAuthStore()
        auth._clear()
      } catch (_) { /* ignore */ }
      // Avoid bouncing if we're already on the login page.
      if (typeof window !== 'undefined' && !window.location.pathname.endsWith('/login')) {
        window.location.assign('/login')
      }
    }
    console.error('API Error:', status, msg)
    return Promise.reject(error)
  }
)

// --- Auth ---
export const login = (data) => api.post('/auth/login', data)
export const logout = (data) => api.post('/auth/logout', data)
export const refreshToken = (refresh) => api.post('/auth/token/refresh', { refresh_token: refresh })
export const getMe = () => api.get('/auth/me')
export const listOidcProviders = () => api.get('/auth/oidc/providers')

// --- Intelligence ---
export const getIntelligenceList = (params) => api.get('/intelligence', { params })
export const getIntelligenceDetail = (id) => api.get(`/intelligence/${id}`)
export const reanalyzeIntelligence = (id) => api.post(`/intelligence/${id}/reanalyze`)

// --- Sources ---
export const getSourceList = () => api.get('/sources')
export const createSource = (data) => api.post('/sources', data)
export const toggleSource = (id) => api.put(`/sources/${id}/toggle`)
export const triggerCollection = (id) => api.post(`/sources/${id}/collect`)

// --- Reports ---
export const getReportList = (params) => api.get('/reports', { params })
export const getReportDetail = (id) => api.get(`/reports/${id}`)
export const generateReport = (data) => api.post('/reports/generate', data)

// --- Dashboard ---
export const getDashboardStats = () => api.get('/dashboard/stats')
export const getCategoryDistribution = () => api.get('/dashboard/category-distribution')
export const getPriorityTrend = (days = 7) => api.get('/dashboard/priority-trend', { params: { days } })

// --- System ---
export const getHealth = () => api.get('/health')
export const getLLMProviderStatus = () => api.get('/system/llm-providers')
export const reloadPrompts = () => api.post('/system/reload-prompts')

// --- Admin: Users ---
export const listUsers = (params) => api.get('/users', { params })
export const createUser = (data) => api.post('/users', data)
export const updateUser = (id, data) => api.put(`/users/${id}`, data)
export const deleteUser = (id) => api.delete(`/users/${id}`)
export const resetUserPassword = (id, data) => api.post(`/users/${id}/reset-password`, data)

// --- Admin: API Keys ---
export const listApiKeys = (params) => api.get('/api-keys', { params })
export const createApiKey = (data) => api.post('/api-keys', data)
export const updateApiKey = (id, data) => api.put(`/api-keys/${id}`, data)
export const revokeApiKey = (id) => api.delete(`/api-keys/${id}`)

// --- Admin: Audit Logs ---
export const listAuditLogs = (params) => api.get('/audit-logs', { params })
export const getAuditStats = (hours = 24) => api.get('/audit-logs/stats', { params: { hours } })

// --- Admin: System ---
export const listCircuitBreakers = () => api.get('/system/circuit-breakers')
export const listStreams = () => api.get('/system/streams')
export const peekDlq = (limit = 50) => api.get('/system/dlq', { params: { limit } })
export const listSchedulerJobs = () => api.get('/system/scheduler/jobs')

export default api
