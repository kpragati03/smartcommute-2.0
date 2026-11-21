import { Link } from 'react-router-dom'
export function Button({ children, variant = 'primary', className = '', ...p }) {
  const base = 'inline-flex items-center justify-center gap-2 rounded-full border-[2.5px] border-ink px-5 py-2.5 font-bold text-sm transition-all shadow-hardSm hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none active:translate-x-[2px] active:translate-y-[2px] disabled:opacity-50 disabled:pointer-events-none cursor-pointer'
  const v = { primary: 'bg-lime-brand text-ink', sun: 'bg-sun text-ink', royal: 'bg-royal text-white', white: 'bg-white text-ink', ink: 'bg-ink text-white', danger: 'bg-blush text-white' }
  return <button className={`${base} ${v[variant] || v.primary} ${className}`} {...p}>{children}</button>
}
export function LinkButton({ to, children, variant = 'primary', className = '' }) {
  const base = 'inline-flex items-center justify-center gap-2 rounded-full border-[2.5px] border-ink px-5 py-2.5 font-bold text-sm transition-all shadow-hardSm hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-none'
  const v = { primary: 'bg-lime-brand text-ink', sun: 'bg-sun text-ink', royal: 'bg-royal text-white', white: 'bg-white text-ink', ink: 'bg-ink text-white' }
  return <Link to={to} className={`${base} ${v[variant] || v.primary} ${className}`}>{children}</Link>
}
export function Card({ children, className = '' }) {
  return <div className={`bg-white border-[2.5px] border-ink rounded-2xl shadow-hard p-5 ${className}`}>{children}</div>
}
export function Badge({ children, tone = 'lime' }) {
  const t = { lime: 'bg-lime-brand', sun: 'bg-sun', royal: 'bg-royal text-white', white: 'bg-white', blush: 'bg-blush text-white', ink: 'bg-ink text-white' }
  return <span className={`inline-flex items-center gap-1 rounded-full border-2 border-ink px-3 py-1 text-xs font-extrabold uppercase tracking-wide ${t[tone] || t.lime}`}>{children}</span>
}
export function Input({ label, error, ...p }) {
  return <label className="block">
    {label && <span className="block text-xs font-extrabold uppercase tracking-wider mb-1.5">{label}</span>}
    <input className="w-full rounded-xl border-[2.5px] border-ink bg-white px-3.5 py-2.5 text-sm font-medium placeholder:text-ink/40" {...p} />
    {error && <span className="block text-xs font-bold text-red-700 mt-1">{error}</span>}
  </label>
}
export function Select({ label, children, ...p }) {
  return <label className="block">
    {label && <span className="block text-xs font-extrabold uppercase tracking-wider mb-1.5">{label}</span>}
    <select className="w-full rounded-xl border-[2.5px] border-ink bg-white px-3.5 py-2.5 text-sm font-medium" {...p}>{children}</select>
  </label>
}
export function StatCard({ label, value, sub, tone = 'lime' }) {
  const t = { lime: 'bg-lime-brand', sun: 'bg-sun', royal: 'bg-royal text-white', white: 'bg-white' }
  return <div className={`border-[2.5px] border-ink rounded-2xl shadow-hard p-4 ${t[tone]}`}>
    <div className="text-[11px] font-extrabold uppercase tracking-widest opacity-70">{label}</div>
    <div className="font-display text-3xl md:text-4xl font-black leading-tight">{value}</div>
    {sub && <div className="text-xs font-semibold opacity-80">{sub}</div>}
  </div>
}
export function CrowdBadge({ level, percent }) {
  const map = { low: ['lime', 'Low crowd'], moderate: ['sun', 'Moderate'], high: ['blush', 'Crowded'] }
  const [tone, label] = map[level] || ['white', level || '—']
  return <Badge tone={tone}>{label}{percent != null ? ` · ${Math.round(percent)}%` : ''}</Badge>
}
export function Skeleton({ className = 'h-24' }) {
  return <div className={`rounded-2xl border-[2.5px] border-ink bg-white animate-pulse ${className}`} aria-label="Loading" />
}
export function EmptyState({ title, hint, action }) {
  return <div className="rounded-2xl border-[2.5px] border-dashed border-ink bg-white p-6 text-center">
    <p className="font-display font-black text-lg">{title}</p>
    {hint && <p className="text-sm text-ink/70 mt-1">{hint}</p>}
    {action && <div className="mt-4">{action}</div>}
  </div>
}
export function ErrorBox({ message, onRetry }) {
  return <div className="rounded-2xl border-[2.5px] border-ink bg-blush/15 p-4 flex flex-wrap items-center gap-3 justify-between">
    <p className="text-sm font-bold">⚠ {message}</p>
    {onRetry && <Button variant="white" onClick={onRetry}>Retry</Button>}
  </div>
}
export function Toast({ toast }) {
  if (!toast) return null
  return <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-[9999] bg-ink text-white font-bold text-sm px-5 py-3 rounded-full border-[2.5px] border-ink shadow-hard max-w-[92vw] text-center">{toast}</div>
}
export function Textarea({ label, error, ...p }) {
  return <label className="block">
    {label && <span className="block text-xs font-extrabold uppercase tracking-wider mb-1.5">{label}</span>}
    <textarea className="w-full rounded-xl border-[2.5px] border-ink bg-white px-3.5 py-2.5 text-sm font-medium placeholder:text-ink/40" {...p} />
    {error && <span className="block text-xs font-bold text-red-700 mt-1">{error}</span>}
  </label>
}
export function FormError({ message }) {
  if (!message) return null
  return <p className="text-sm font-bold text-red-700 bg-red-50 border-2 border-ink rounded-xl px-3 py-2">⚠ {message}</p>
}
export function SectionTitle({ children, sub }) {
  return <div className="mb-3"><h2 className="font-display font-black text-xl">{children}</h2>
    {sub && <p className="text-sm font-semibold text-ink/70 mt-0.5">{sub}</p>}</div>
}
export const tableCls = 'w-full text-sm min-w-[560px]'
export const thCls = 'text-left border-b-[2.5px] border-ink py-2 pr-3 text-xs font-extrabold uppercase tracking-wider whitespace-nowrap'
export const tdCls = 'py-2 pr-3 align-top'
export const trCls = 'border-b border-ink/20'
export function Modal({ title, onClose, children, wide }) {
  return <div className="fixed inset-0 z-[9998] bg-ink/50 flex items-start md:items-center justify-center p-3 overflow-auto" onClick={onClose}>
    <div className={`bg-cream border-[3px] border-ink rounded-2xl shadow-hardLg w-full ${wide ? 'max-w-2xl' : 'max-w-lg'} my-6`} onClick={e => e.stopPropagation()}>
      <div className="flex items-center justify-between gap-3 px-5 py-4 border-b-[2.5px] border-ink">
        <h3 className="font-display font-black text-lg">{title}</h3>
        <button onClick={onClose} aria-label="Close" className="w-9 h-9 grid place-items-center rounded-full border-[2.5px] border-ink bg-white font-black shadow-hardSm hover:shadow-none">✕</button>
      </div>
      <div className="p-5">{children}</div>
    </div>
  </div>
}
export function StarRating({ value, onChange, size = 'text-3xl' }) {
  return <div className="flex gap-1" role="radiogroup" aria-label="Rating">
    {[1, 2, 3, 4, 5].map(n => <button key={n} type="button" role="radio" aria-checked={value === n} aria-label={`${n} star${n > 1 ? 's' : ''}`}
      onClick={() => onChange && onChange(n)} className={`${size} leading-none ${onChange ? 'cursor-pointer' : 'cursor-default'}`}>{n <= value ? '⭐' : '☆'}</button>)}
  </div>
}
export function ProgressBar({ percent, tone = 'bg-lime-brand' }) {
  const p = Math.max(0, Math.min(100, Number(percent) || 0))
  return <div className="h-3.5 rounded-full border-2 border-ink bg-white overflow-hidden"><div className={`h-full ${tone}`} style={{ width: `${p}%` }} /></div>
}
export function StatusBadge({ status }) {
  const map = {
    running: 'lime', active: 'lime', approved: 'lime', resolved: 'lime', completed: 'royal', online: 'lime',
    scheduled: 'white', pending: 'sun', delayed: 'sun', in_progress: 'sun', open: 'blush', maintenance: 'sun',
    cancelled: 'blush', rejected: 'blush', inactive: 'white', offline: 'white',
  }
  return <Badge tone={map[status] || 'white'}>{String(status || '—').replace(/_/g, ' ')}</Badge>
}
export function fmtDateTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return isNaN(d) ? String(iso) : d.toLocaleString()
}
export function fmtDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return isNaN(d) ? String(iso) : d.toLocaleDateString()
}
export function timeAgo(iso) {
  if (!iso) return '—'
  const s = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000))
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ago`
}
