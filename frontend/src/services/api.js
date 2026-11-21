import axios from 'axios'
export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'
const api = axios.create({ baseURL: API_URL, headers: { 'Content-Type': 'application/json' }, timeout: 15000 })
api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem('sc_access')
  if (t) cfg.headers.Authorization = `Bearer ${t}`
  return cfg
})
let refreshing = null
api.interceptors.response.use((r) => r, async (err) => {
  const orig = err.config
  if (err.response?.status === 401 && orig && !orig._retry) {
    orig._retry = true
    const refresh = localStorage.getItem('sc_refresh')
    if (!refresh) { localStorage.removeItem('sc_access'); return Promise.reject(err) }
    try {
      if (!refreshing) refreshing = axios.post(`${API_URL}/auth/refresh/`, { refresh })
      const res = await refreshing
      refreshing = null
      const access = res.data.access
      localStorage.setItem('sc_access', access)
      orig.headers.Authorization = `Bearer ${access}`
      return api(orig)
    } catch (e) {
      refreshing = null
      localStorage.removeItem('sc_access'); localStorage.removeItem('sc_refresh')
      if (!window.location.pathname.startsWith('/login')) window.location.href = '/login'
      return Promise.reject(err)
    }
  }
  return Promise.reject(err)
})
export function errMsg(e) {
  if (!e?.response) return 'Cannot reach the server. Is the backend running?'
  const d = e.response.data
  if (typeof d === 'string') return d
  if (d?.detail) return d.detail
  if (d && typeof d === 'object') {
    const parts = Object.entries(d).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
    return parts.join(' · ') || `Request failed (${e.response.status})`
  }
  return `Request failed (${e.response.status})`
}
export function listOf(data) { return Array.isArray(data) ? data : (data?.results || []) }
export default api
