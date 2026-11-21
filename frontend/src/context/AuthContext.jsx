import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import api from '../services/api'
const Ctx = createContext(null)
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const loadMe = useCallback(async () => {
    if (!localStorage.getItem('sc_access')) { setLoading(false); return null }
    try { const r = await api.get('/auth/me/'); setUser(r.data); return r.data }
    catch { setUser(null); return null } finally { setLoading(false) }
  }, [])
  useEffect(() => { loadMe() }, [loadMe])
  const login = async (email, password) => {
    const r = await api.post('/auth/login/', { email, password })
    localStorage.setItem('sc_access', r.data.access)
    if (r.data.refresh) localStorage.setItem('sc_refresh', r.data.refresh)
    return loadMe()
  }
  const logout = () => { localStorage.removeItem('sc_access'); localStorage.removeItem('sc_refresh'); setUser(null) }
  const roles = (user?.memberships || []).map(m => m.role)
  const isPlatformAdmin = !!user?.is_platform_admin
  const isOrgAdmin = isPlatformAdmin || roles.includes('org_admin')
  const isDriver = roles.includes('driver')
  const homeFor = (u = user) => {
    if (!u) return '/login'
    const r = (u.memberships || []).map(m => m.role)
    if (u.is_platform_admin || r.includes('org_admin')) return '/admin'
    if (r.includes('driver')) return '/driver'
    return '/app'
  }
  return <Ctx.Provider value={{ user, loading, login, logout, loadMe, isOrgAdmin, isDriver, isPlatformAdmin, homeFor }}>{children}</Ctx.Provider>
}
export const useAuth = () => useContext(Ctx)
