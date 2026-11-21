import { useCallback, useEffect, useMemo, useState } from 'react'
import api, { errMsg, listOf } from '../services/api'
import { Badge, Button, Card, EmptyState, ErrorBox, FormError, Input, ProgressBar, Skeleton, StatusBadge, Textarea, Toast, fmtDateTime } from '../components/ui'

// Driver portal: GET /driver/my-trip/, POST start/end/delay/breakdown/passengers,
// GET /driver/history/. Big touch-friendly controls for use on the road.
export default function DriverPortal() {
  const [data, setData] = useState(null)
  const [history, setHistory] = useState([])
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState('')
  const [busy, setBusy] = useState('')
  const [delayMin, setDelayMin] = useState('10')
  const [delayNote, setDelayNote] = useState('')
  const [breakNote, setBreakNote] = useState('')
  const [pax, setPax] = useState(0)
  const [formErr, setFormErr] = useState('')

  const say = (m) => { setToast(m); setTimeout(() => setToast(''), 3400) }

  const load = useCallback(async () => {
    const [trip, hist] = await Promise.allSettled([api.get('/driver/my-trip/'), api.get('/driver/history/')])
    if (trip.status === 'fulfilled') { setData(trip.value.data); setErr('') }
    else setErr(errMsg(trip.reason))
    if (hist.status === 'fulfilled') setHistory(listOf(hist.value.data))
    setLoading(false)
  }, [])
  useEffect(() => { load() }, [load])

  const trip = data?.trip || data?.current_trip || data?.next_trip || (data?.id ? data : null)
  const stops = useMemo(() => {
    const s = data?.stops || data?.stop_sequence || trip?.stops || trip?.stop_sequence || []
    return [...s].sort((a, b) => (a.order || 0) - (b.order || 0))
  }, [data, trip])
  const progress = data?.progress || trip?.progress || {}
  const distanceCovered = Number(progress.distance_covered_km ?? trip?.distance_covered_km ?? data?.distance_covered_km ?? 0)
  const totalDistance = Number(progress.total_distance_km ?? trip?.total_distance_km ?? (stops.length ? stops[stops.length - 1].distance_from_start_km : 0) ?? 0)
  const onboard = progress.passengers_onboard ?? trip?.passengers_onboard ?? data?.passengers_onboard
  const capacity = trip?.vehicle_capacity ?? trip?.capacity ?? progress.capacity ?? null

  useEffect(() => { if (onboard != null) setPax(Number(onboard) || 0) }, [onboard])

  const stopsPassed = stops.filter(s => s.distance_from_start_km != null && Number(s.distance_from_start_km) <= distanceCovered).length
  const nextStop = stops[stopsPassed] || null
  const pct = totalDistance > 0 ? (distanceCovered / totalDistance) * 100 : (stops.length ? (stopsPassed / stops.length) * 100 : 0)
  const tid = trip?.id
  const running = trip?.status === 'running' || trip?.status === 'delayed'

  const act = async (key, path, body, msg) => {
    setBusy(key); setFormErr('')
    try { await api.post(path, body || {}); say(msg); load() }
    catch (e) { setFormErr(errMsg(e)); say(errMsg(e)) }
    finally { setBusy('') }
  }

  const reportDelay = () => {
    const m = parseInt(delayMin, 10)
    if (!m || m < 1 || m > 600) { setFormErr('Enter delay minutes between 1 and 600.'); return }
    act('delay', `/driver/trips/${tid}/delay/`, { minutes: m, note: delayNote.trim() }, `Delay of ${m} min reported ⏱`)
  }
  const reportBreakdown = () => {
    if (!breakNote.trim()) { setFormErr('Describe the breakdown so dispatch can send help.'); return }
    act('breakdown', `/driver/trips/${tid}/breakdown/`, { note: breakNote.trim() }, 'Breakdown reported 🚨 — dispatch notified')
  }
  const sendPax = (n) => {
    const v = Math.max(0, capacity ? Math.min(n, Number(capacity)) : n)
    setPax(v)
    act('pax', `/driver/trips/${tid}/passengers/`, { passengers_onboard: v }, `Passenger count updated: ${v} onboard`)
  }

  if (loading) return <main className="max-w-5xl mx-auto px-4 py-8 grid gap-4"><Skeleton className="h-44" /><Skeleton className="h-64" /></main>

  return (
    <main className="max-w-5xl mx-auto px-4 py-6 grid gap-5">
      <div className="flex flex-wrap items-center gap-3 justify-between">
        <div>
          <h1 className="font-display font-black text-3xl">Driver console</h1>
          <p className="text-sm font-semibold text-ink/70">Your current or next trip, live from dispatch. Buttons are sized for quick taps.</p>
        </div>
        <Button variant="white" onClick={load}>↻ Refresh</Button>
      </div>
      {err && <ErrorBox message={err} onRetry={load} />}
      {!err && !tid && <EmptyState title="No trip assigned yet" hint="When dispatch assigns you a trip it appears here with its stop sequence and controls." action={<Button variant="white" onClick={load}>Check again</Button>} />}

      {tid && (
        <>
          <Card>
            <div className="flex flex-wrap gap-2 items-center justify-between">
              <h2 className="font-display font-black text-2xl">Trip #{tid} — {trip.route_name || `Route ${trip.route || ''}`}</h2>
              <StatusBadge status={trip.status || 'scheduled'} />
            </div>
            <p className="text-sm font-semibold text-ink/75 mt-2">
              Vehicle: <b>{trip.vehicle_registration || trip.vehicle || '—'}</b>
              {' · '}Scheduled: {fmtDateTime(trip.scheduled_start)}
              {trip.actual_start ? ` · Started ${new Date(trip.actual_start).toLocaleTimeString()}` : ''}
              {trip.actual_end ? ` · Ended ${new Date(trip.actual_end).toLocaleTimeString()}` : ''}
            </p>

            <div className="mt-4">
              <div className="flex flex-wrap justify-between gap-2 text-sm font-extrabold mb-1.5">
                <span>{distanceCovered} km covered{totalDistance ? ` of ${totalDistance} km` : ''}</span>
                <span>{stopsPassed} / {stops.length} stops passed</span>
              </div>
              <ProgressBar percent={pct} />
              {nextStop && <p className="text-sm font-bold mt-2">Next stop: <span className="bg-sun border-2 border-ink rounded-md px-1.5">{nextStop.name}</span>{nextStop.distance_from_start_km != null ? ` · at ${nextStop.distance_from_start_km} km` : ''}</p>}
              {!nextStop && stops.length > 0 && <p className="text-sm font-bold mt-2">All stops passed — you can end the trip.</p>}
            </div>

            <FormError message={formErr} />
            <div className="grid grid-cols-2 gap-3 mt-4">
              <Button onClick={() => act('start', `/driver/trips/${tid}/start/`, {}, 'Trip started ▶')} disabled={!!busy || running} className="w-full !py-4 !text-base">{busy === 'start' ? 'Starting…' : '▶ Start trip'}</Button>
              <Button variant="white" onClick={() => act('end', `/driver/trips/${tid}/end/`, {}, 'Trip ended ✓')} disabled={!!busy || trip.status === 'completed'} className="w-full !py-4 !text-base">{busy === 'end' ? 'Ending…' : '■ End trip'}</Button>
            </div>

            <div className="grid md:grid-cols-2 gap-4 mt-5">
              <div className="border-[2.5px] border-ink rounded-2xl bg-sun/25 p-4 grid gap-3">
                <p className="font-display font-black text-lg">⏱ Report delay</p>
                <div className="flex gap-2 items-end">
                  <Input label="Minutes late" type="number" min="1" max="600" value={delayMin} onChange={e => setDelayMin(e.target.value)} />
                  {[5, 10, 15].map(m => <button key={m} onClick={() => setDelayMin(String(m))} className={`rounded-full border-2 border-ink px-3 py-2 text-sm font-extrabold ${delayMin === String(m) ? 'bg-sun shadow-hardSm' : 'bg-white'}`}>{m}m</button>)}
                </div>
                <Input label="Note (optional)" value={delayNote} onChange={e => setDelayNote(e.target.value)} placeholder="e.g. Traffic at Phagwara Bus Stand" />
                <Button variant="sun" onClick={reportDelay} disabled={!!busy} className="w-full !py-3">{busy === 'delay' ? 'Reporting…' : 'Report delay'}</Button>
              </div>
              <div className="border-[2.5px] border-ink rounded-2xl bg-blush/15 p-4 grid gap-3">
                <p className="font-display font-black text-lg">🚨 Report breakdown</p>
                <Textarea label="What happened?" rows={2} value={breakNote} onChange={e => setBreakNote(e.target.value)} placeholder="e.g. Engine overheating near Chaheru, need replacement bus" />
                <Button variant="danger" onClick={reportBreakdown} disabled={!!busy} className="w-full !py-3">{busy === 'breakdown' ? 'Reporting…' : 'Report breakdown'}</Button>
              </div>
            </div>

            <div className="border-[2.5px] border-ink rounded-2xl bg-cream/70 p-4 mt-4">
              <p className="font-display font-black text-lg">🧑‍🤝‍🧑 Passengers onboard</p>
              <p className="text-xs font-semibold text-ink/60 mt-0.5">Tap + / − as riders board and leave. Each tap updates dispatch and the commuter crowd level.{capacity ? ` Vehicle capacity: ${capacity}.` : ''}</p>
              <div className="flex items-center gap-3 mt-3">
                <button onClick={() => sendPax(pax - 1)} disabled={!!busy || pax <= 0} aria-label="One passenger left"
                  className="w-16 h-16 rounded-2xl border-[3px] border-ink bg-white font-display font-black text-3xl shadow-hardSm hover:shadow-none disabled:opacity-40">−</button>
                <div className="flex-1 text-center">
                  <span className="font-display font-black text-5xl">{pax}</span>
                  <span className="block text-xs font-extrabold uppercase tracking-wider text-ink/60">onboard now</span>
                </div>
                <button onClick={() => sendPax(pax + 1)} disabled={!!busy || (capacity && pax >= Number(capacity))} aria-label="One passenger boarded"
                  className="w-16 h-16 rounded-2xl border-[3px] border-ink bg-lime-brand font-display font-black text-3xl shadow-hardSm hover:shadow-none disabled:opacity-40">+</button>
              </div>
              {busy === 'pax' && <p className="text-xs font-bold text-ink/60 mt-2 text-center">Updating…</p>}
            </div>
          </Card>

          <Card>
            <h2 className="font-display font-black text-xl mb-3">Stop sequence</h2>
            {stops.length === 0
              ? <p className="text-sm font-semibold text-ink/60">No stop sequence returned for this trip yet.</p>
              : <ol className="grid gap-2">{stops.map((s, i) => {
                const passed = s.distance_from_start_km != null && Number(s.distance_from_start_km) <= distanceCovered
                const isNext = nextStop && (s.id === nextStop.id || i === stopsPassed)
                return (
                  <li key={s.id || i} className={`flex items-center gap-3 border-2 border-ink rounded-xl px-3 py-2.5 ${isNext ? 'bg-sun shadow-hardSm' : passed ? 'bg-lime-brand/30 opacity-80' : 'bg-cream/60'}`}>
                    <span className="w-8 h-8 grid place-items-center rounded-full bg-white border-2 border-ink font-black text-sm shrink-0">{passed ? '✓' : (s.order || i + 1)}</span>
                    <span className="font-bold text-sm">{s.name}</span>
                    {isNext && <Badge tone="ink">Next</Badge>}
                    <span className="text-xs font-semibold text-ink/60 ml-auto">{s.distance_from_start_km != null ? `${s.distance_from_start_km} km` : ''}</span>
                  </li>
                )
              })}</ol>}
          </Card>
        </>
      )}

      <Card>
        <h2 className="font-display font-black text-xl mb-3">🗂 Trip history</h2>
        {history.length === 0
          ? <EmptyState title="No past trips yet" hint="Completed trips will be listed here with their final status." />
          : <div className="overflow-auto"><table className="w-full text-sm min-w-[520px]">
            <thead><tr className="text-left border-b-[2.5px] border-ink"><th className="py-2 pr-3 text-xs font-extrabold uppercase">Trip</th><th className="pr-3 text-xs font-extrabold uppercase">Route</th><th className="pr-3 text-xs font-extrabold uppercase">Scheduled</th><th className="pr-3 text-xs font-extrabold uppercase">Started</th><th className="text-xs font-extrabold uppercase">Status</th></tr></thead>
            <tbody>{history.map(t => (
              <tr key={t.id} className="border-b border-ink/20">
                <td className="py-2 pr-3 font-bold">#{t.id}</td>
                <td className="pr-3">{t.route_name || `Route ${t.route || '—'}`}</td>
                <td className="pr-3">{fmtDateTime(t.scheduled_start)}</td>
                <td className="pr-3">{t.actual_start ? new Date(t.actual_start).toLocaleTimeString() : '—'}</td>
                <td><StatusBadge status={t.status} /></td>
              </tr>))}
            </tbody></table></div>}
      </Card>
      <Toast toast={toast} />
    </main>
  )
}
