import { useCallback, useEffect, useRef, useState } from 'react'
import api, { errMsg, listOf } from '../services/api'
import { Button, EmptyState, timeAgo } from './ui'

// Bell in the navbar: polls GET /notifications/ every 30s, shows unread count,
// dropdown list, mark one read (POST /notifications/{id}/read/) and read-all.
export default function NotificationsBell() {
  const [items, setItems] = useState([])
  const [open, setOpen] = useState(false)
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const ref = useRef(null)

  const load = useCallback(async () => {
    try {
      const r = await api.get('/notifications/')
      setItems(listOf(r.data)); setErr('')
    } catch (e) { setErr(errMsg(e)) }
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 30000)
    return () => clearInterval(t)
  }, [load])

  useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const isRead = (n) => n.is_read ?? n.read ?? false
  const unread = items.filter(n => !isRead(n)).length

  const markRead = async (n) => {
    if (isRead(n)) return
    setItems(prev => prev.map(x => x.id === n.id ? { ...x, is_read: true, read: true } : x))
    try { await api.post(`/notifications/${n.id}/read/`, {}) } catch { load() }
  }
  const markAll = async () => {
    setBusy(true)
    try { await api.post('/notifications/read-all/', {}); load() }
    catch (e) { setErr(errMsg(e)) } finally { setBusy(false) }
  }

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => { setOpen(o => !o); if (!open) load() }} aria-label={`Notifications${unread ? `, ${unread} unread` : ''}`}
        className="relative rounded-full border-2 border-ink bg-white px-3 py-1.5 text-base font-extrabold shadow-hardSm hover:bg-sun hover:shadow-none">
        🔔
        {unread > 0 && <span className="absolute -top-2 -right-2 min-w-[22px] h-[22px] grid place-items-center rounded-full bg-blush text-white border-2 border-ink text-[11px] font-black px-1">{unread > 99 ? '99+' : unread}</span>}
      </button>
      {open && (
        <div className="absolute right-0 top-[calc(100%+10px)] w-[min(92vw,380px)] bg-white border-[2.5px] border-ink rounded-2xl shadow-hard z-[9997] overflow-hidden">
          <div className="flex items-center justify-between gap-2 px-4 py-3 border-b-[2.5px] border-ink bg-cream">
            <p className="font-display font-black">Notifications</p>
            <Button variant="white" onClick={markAll} disabled={busy || unread === 0} className="!px-3 !py-1.5 !text-xs">{busy ? 'Marking…' : 'Mark all read'}</Button>
          </div>
          <div className="max-h-[55vh] overflow-auto">
            {err && <p className="text-sm font-bold text-red-700 px-4 py-3">⚠ {err}</p>}
            {!err && items.length === 0 && <div className="p-4"><EmptyState title="All caught up" hint="Trip updates, pass decisions and alerts will land here." /></div>}
            {items.map(n => (
              <button key={n.id} onClick={() => markRead(n)} className={`block w-full text-left px-4 py-3 border-b border-ink/15 hover:bg-cream ${isRead(n) ? 'opacity-70' : 'bg-sun/20'}`}>
                <span className="flex items-start gap-2">
                  <span className={`mt-1 w-2.5 h-2.5 shrink-0 rounded-full border-2 border-ink ${isRead(n) ? 'bg-white' : 'bg-lime-brand'}`} />
                  <span>
                    <span className="block text-sm font-extrabold">{n.title || n.subject || 'Notification'}</span>
                    {(n.message || n.body || n.text) && <span className="block text-sm font-medium text-ink/75 mt-0.5">{n.message || n.body || n.text}</span>}
                    <span className="block text-xs font-bold text-ink/50 mt-1">{timeAgo(n.created_at || n.created)}</span>
                  </span>
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
