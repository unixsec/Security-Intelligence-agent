// ================================================================
// 安全情报分析智能体 — API 请求封装
// 版本：v1.0
// 作者：alex (unix_sec@163.com)
// ================================================================

import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

// 响应拦截器
http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const msg = error.response?.data?.detail || error.message || '请求失败'
    ElMessage.error(msg)
    return Promise.reject(error)
  },
)

// ---- 情报源 ----
export const sourcesApi = {
  list: (params) => http.get('/sources', { params }),
  create: (data) => http.post('/sources', data),
  update: (id, data) => http.put(`/sources/${id}`, data),
  delete: (id) => http.delete(`/sources/${id}`),
  health: (id) => http.get(`/sources/${id}/health`),
  import: (file) => {
    const form = new FormData()
    form.append('file', file)
    return http.post('/sources/import', form)
  },
  export: () => http.get('/sources/export', { responseType: 'blob' }),
}

// ---- 关键词 ----
export const keywordsApi = {
  list: (params) => http.get('/keywords', { params }),
  create: (data) => http.post('/keywords', data),
  update: (id, data) => http.put(`/keywords/${id}`, data),
  delete: (id) => http.delete(`/keywords/${id}`),
  import: (file) => {
    const form = new FormData()
    form.append('file', file)
    return http.post('/keywords/import', form)
  },
  export: () => http.get('/keywords/export', { responseType: 'blob' }),
}

// ---- 情报 ----
export const intelApi = {
  listRaw: (params) => http.get('/intel/raw', { params }),
  listScored: (params) => http.get('/intel/scored', { params }),
  getScored: (id) => http.get(`/intel/scored/${id}`),
  listEvents: (params) => http.get('/intel/events', { params }),
}

// ---- 报告 ----
export const reportsApi = {
  list: (params) => http.get('/reports', { params }),
  get: (id) => http.get(`/reports/${id}`),
  regenerate: (id) => http.post(`/reports/${id}/regenerate`),
}

// ---- 系统配置 ----
export const configApi = {
  get: (key) => http.get(`/config/${key}`),
  update: (key, data) => http.put(`/config/${key}`, data),
}

// ---- 仪表盘 ----
export const dashboardApi = {
  stats: () => http.get('/dashboard/stats'),
  health: () => http.get('/dashboard/health'),
  feedbacks: () => http.get('/dashboard/feedbacks'),
}

// ---- 审计日志 ----
export const auditApi = {
  list: (params) => http.get('/audit-logs', { params }),
}
