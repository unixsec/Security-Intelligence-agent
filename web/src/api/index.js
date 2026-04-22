import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const msg = error.response?.data?.detail || error.message || '请求失败'
    console.error('API Error:', msg)
    return Promise.reject(error)
  }
)

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

export default api
