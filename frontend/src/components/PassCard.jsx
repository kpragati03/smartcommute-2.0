import { useCallback, useEffect, useState } from 'react'
import QRCode from 'qrcode'
import api, { API_URL, errMsg } from '../services/api'
import { Badge, Button, Card, EmptyState, FormError, SectionTitle, Skeleton, StatusBadge, Textarea, fmtDate } from './ui'

// Transport pass: apply (POST /passes/apply/), my pass (GET /passes/mine/),
// QR image from GET /passes/{id}/qr/ (PNG) with client-side fallback rendering
// the qr_token via the `qrcode` package when the backend endpoint 404s.
export default function PassCard({ say }) {
  const [mine, setMine] = useState(null) // null = not loaded yet
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [qrSrc, setQrSrc] = useState('')
  const [qrNote, setQrNote] = useState('')

  const load = useCallback(async () => {
    try {
      const r = await api.get('/passes/mine/')
      setMine(r.data); setErr('')
    } catch (e) {
      // 404 here simply means "no pass / no application yet" on some backends.
      if (e?.response?.status === 404) { setMine({}); setErr('') }
      else setErr(errMsg(e))
    } finally { setLoading(false) }
  }, [])
  useEffect(() => { load() }, [load])

  const pass = mine?.pass || mine?.transport_pass || (mine?.qr_token ? mine : null)
  const application = mine?.application || mine?.pass_application || (mine?.status && !mine?.qr_token ? mine : null)
  const status = pass?.status || application?.status || mine?.status || null
  const qrToken = pass?.qr_token || mine?.qr_token || null
  const passId = pass?.id || mine?.id || null

  useEffect(() => {
    let alive = true
    const render = async () => {
      setQrSrc(''); setQrNote('')
      if (!qrToken) return
      // 1) Prefer the backend PNG endpoint when it exists.
      if (passId) {
        try {
          const res = await api.get(`/passes/${passId}/qr/`, { responseType: 'blob' })
          if (alive && res.data && res.data.size > 0) {
            setQrSrc(URL.createObjectURL(res.data)); setQrNote('QR served by the backend.')
            return
          }
        } catch { /* fall through to client-side rendering */ }
      }
      // 2) Fallback: render the token locally.
      try {
        const url = await QRCode.toDataURL(String(qrToken), { width: 260, margin: 1 })
        if (alive) { setQrSrc(url); setQrNote('QR rendered in your browser from the pass token (backend QR endpoint not available yet).') }
      } catch { if (alive) setQrNote('Could not render the QR image — show the token text below instead.') }
    }
    render()
    return () => { alive = false }
  }, [qrToken, passId])

  const apply = async (e) => {
    e.preventDefault()
    if (!reason.trim()) { setErr('Tell the transport office why you need a pass.'); return }
    setBusy(true); setErr('')
    try {
      await api.post('/passes/apply/', { reason: reason.trim() })
      setReason(''); say('Pass application submitted ✓ — the transport office will review it.')
      load()
    } catch (ex) { setErr(errMsg(ex)) } finally { setBusy(false) }
  }

  if (loading) return <Card><Skeleton className="h-36 border-0 shadow-none" /></Card>

  return (
    <Card>
      <SectionTitle sub="Apply for a transport pass, track its status, and show the QR at boarding.">🎫 My transport pass</SectionTitle>
      {err && <FormError message={err} />}

      {pass && (
        <div className="grid sm:grid-cols-[auto,1fr] gap-4 items-start border-[2.5px] border-ink rounded-2xl bg-cream/70 p-4">
          <div className="bg-white border-[2.5px] border-ink rounded-2xl p-3 grid place-items-center w-[180px] h-[180px] mx-auto">
            {qrSrc
              ? <img src={qrSrc} alt="Transport pass QR code" className="w-full h-full object-contain" />
              : <p className="text-xs font-bold text-ink/60 text-center px-2">Preparing QR…</p>}
          </div>
          <div className="grid gap-2">
            <div className="flex flex-wrap gap-2 items-center">
              <p className="font-display font-black text-lg">Transport pass{passId ? ` #${passId}` : ''}</p>
              <StatusBadge status={status || 'active'} />
            </div>
            <p className="text-sm font-semibold text-ink/75">
              Valid from {fmtDate(pass.valid_from || pass.starts_at || pass.created_at)} to {fmtDate(pass.valid_until || pass.expires_at || pass.valid_to)}
            </p>
            {qrToken && <p className="text-xs font-mono font-bold break-all bg-white border-2 border-ink rounded-xl px-3 py-2">Token: {qrToken}</p>}
            {qrNote && <p className="text-xs font-semibold text-ink/60">{qrNote}</p>}
            <p className="text-xs font-semibold text-ink/60">Show this QR to the conductor/driver. It is verified against the live pass record.</p>
          </div>
        </div>
      )}

      {!pass && application && (
        <div className="border-[2.5px] border-ink rounded-2xl bg-sun/25 p-4 grid gap-2">
          <div className="flex flex-wrap gap-2 items-center">
            <p className="font-display font-black">Application{application.id ? ` #${application.id}` : ''}</p>
            <StatusBadge status={status || 'pending'} />
          </div>
          {application.reason && <p className="text-sm font-semibold text-ink/75">“{application.reason}”</p>}
          <p className="text-sm font-semibold text-ink/70">
            {status === 'rejected'
              ? 'This application was not approved. You can apply again below with more detail.'
              : 'Waiting for the transport office to review. You will get a notification when it is decided.'}
          </p>
        </div>
      )}

      {!pass && !application && (
        <EmptyState title="No pass yet" hint="Apply below — once approved, your pass and QR code appear here." />
      )}

      {(!pass || status === 'rejected') && (
        <form onSubmit={apply} className="grid gap-3 mt-4">
          <Textarea label="Why do you need a pass?" required rows={3} value={reason} onChange={e => setReason(e.target.value)}
            placeholder="e.g. Daily commute from Phagwara Bus Stand to LPU Main Gate for classes, Mon–Sat." />
          <Button type="submit" disabled={busy} className="justify-self-start">{busy ? 'Submitting…' : 'Apply for a pass →'}</Button>
        </form>
      )}
      {pass && <p className="text-xs font-semibold text-ink/60 mt-3">Need to check a pass? Staff verify tokens via <code className="font-mono">GET /passes/verify/?token=…</code> ({API_URL.replace(/\/$/, '')}).</p>}
    </Card>
  )
}
