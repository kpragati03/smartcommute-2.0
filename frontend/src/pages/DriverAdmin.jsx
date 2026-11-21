import { useCallback, useEffect, useState } from 'react'
import api, { errMsg, listOf } from '../services/api'
import { Badge, Button, Card, EmptyState, ErrorBox, Skeleton, StatCard, Toast } from '../components/ui'
export function DriverPage() {
  const [data, setData] = useState(null); const [err, setErr] = useState(''); const [loading, setLoading] = useState(true); const [toast, setToast] = useState('')
  const say = (m) => { setToast(m); setTimeout(() => setToast(''), 3200) }
  const load = useCallback(async () => {
    try { const r = await api.get('/driver/my-trip/'); setData(r.data); setErr('') }
    catch (e) { setErr(errMsg(e)) } finally { setLoading(false) }
  }, [])
  useEffect(() => { load() }, [load])
  const act = async (path, body, msg) => { try { await api.post(path, body || {}); say(msg); load() } catch (e) { say(errMsg(e)) } }
  if (loading) return <main className="max-w-5xl mx-auto px-4 py-8 grid gap-4"><Skeleton className="h-40" /><Skeleton className="h-40" /></main>
  const trip = data?.trip || data?.current_trip || data
  const stops = data?.stops || data?.stop_sequence || trip?.stops || []
  const tid = trip?.id
  return <main className="max-w-5xl mx-auto px-4 py-6 grid gap-5">
    <div><h1 className="font-display font-black text-3xl">Driver console</h1><p className="text-sm font-semibold text-ink/70">Your current or next assigned trip, live from dispatch.</p></div>
    {err && <ErrorBox message={err} onRetry={load} />}
    {!err && !tid && <EmptyState title="No trip assigned yet" hint="When dispatch assigns you a trip it will appear here with its stop sequence." action={<Button variant="white" onClick={load}>Refresh</Button>} />}
    {tid && <>
      <Card>
        <div className="flex flex-wrap gap-2 items-center justify-between">
          <h2 className="font-display font-black text-xl">Trip #{tid} — {trip.route_name || `Route ${trip.route || ''}`}</h2>
          <Badge tone={trip.status === 'running' ? 'lime' : trip.status === 'delayed' ? 'sun' : 'white'}>{trip.status || 'scheduled'}</Badge>
        </div>
        <p className="text-sm font-semibold text-ink/75 mt-2">Vehicle: {trip.vehicle_registration || trip.vehicle || '—'} · Scheduled start: {trip.scheduled_start ? new Date(trip.scheduled_start).toLocaleString() : '—'}{trip.actual_start ? ` · Started ${new Date(trip.actual_start).toLocaleTimeString()}` : ''}</p>
        <div className="flex flex-wrap gap-2 mt-4">
          <Button onClick={() => act(`/driver/trips/${tid}/start/`, {}, 'Trip started ▶')}>▶ Start trip</Button>
          <Button variant="sun" onClick={() => act(`/driver/trips/${tid}/delay/`, { minutes: 5, note: 'Delayed 5 min (from driver console)' }, 'Delay reported')}>⏱ Report 5-min delay</Button>
          <Button variant="white" onClick={() => act(`/driver/trips/${tid}/end/`, {}, 'Trip ended ✓')}>■ End trip</Button>
        </div>
      </Card>
      <Card>
        <h2 className="font-display font-black text-xl mb-3">Stop sequence</h2>
        {stops.length === 0 ? <p className="text-sm font-semibold text-ink/60">No stop sequence returned for this trip.</p> : <ol className="grid gap-2">
          {stops.map((s, i) => <li key={s.id || i} className="flex items-center gap-3 border-2 border-ink rounded-xl px-3 py-2 bg-cream/60">
            <span className="w-7 h-7 grid place-items-center rounded-full bg-lime-brand border-2 border-ink font-black text-sm">{s.order || i + 1}</span>
            <span className="font-bold text-sm">{s.name}</span><span className="text-xs font-semibold text-ink/60 ml-auto">{s.distance_from_start_km ?? ''}{s.distance_from_start_km != null ? ' km' : ''}</span>
          </li>)}
        </ol>}
      </Card>
    </>}
    <Toast toast={toast} />
  </main>
}
export function AdminPage() {
  const [ov, setOv] = useState(null); const [routes, setRoutes] = useState([]); const [vehicles, setVehicles] = useState([]); const [trips, setTrips] = useState([])
  const [err, setErr] = useState(''); const [loading, setLoading] = useState(true)
  const load = useCallback(async () => {
    const [o, r, v, t] = await Promise.allSettled([api.get('/analytics/overview/'), api.get('/routes/'), api.get('/vehicles/'), api.get('/trips/')])
    if (o.status === 'fulfilled') setOv(o.value.data)
    if (r.status === 'fulfilled') setRoutes(listOf(r.value.data))
    if (v.status === 'fulfilled') setVehicles(listOf(v.value.data))
    if (t.status === 'fulfilled') setTrips(listOf(t.value.data))
    if ([o, r, v, t].every(x => x.status === 'rejected')) setErr(errMsg(o.reason)); else setErr('')
    setLoading(false)
  }, [])
  useEffect(() => { load() }, [load])
  if (loading) return <main className="max-w-7xl mx-auto px-4 py-8 grid gap-4"><Skeleton className="h-32" /><Skeleton className="h-64" /></main>
  const tbl = 'w-full text-sm'
  return <main className="max-w-7xl mx-auto px-4 py-6 grid gap-5">
    <div className="flex flex-wrap items-center gap-3 justify-between">
      <div><h1 className="font-display font-black text-3xl">Admin overview</h1><p className="text-sm font-semibold text-ink/70">Live operations for your organisation. Full fleet management arrives next wave — everything below is real API data.</p></div>
      <Button variant="white" onClick={load}>↻ Refresh</Button>
    </div>
    {err && <ErrorBox message={err} onRetry={load} />}
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <StatCard label="Total vehicles" value={ov?.total_vehicles ?? vehicles.length} tone="lime" />
      <StatCard label="Active vehicles" value={ov?.active_vehicles ?? vehicles.filter(v => v.status === 'active').length} tone="sun" />
      <StatCard label="Running trips" value={ov?.running_trips ?? trips.filter(t => t.status === 'running').length} tone="royal" />
      <StatCard label="Delayed trips" value={ov?.delayed_trips ?? trips.filter(t => t.status === 'delayed').length} tone="white" />
      <StatCard label="Avg occupancy" value={ov?.avg_occupancy_percent != null ? `${Math.round(ov.avg_occupancy_percent)}%` : '—'} tone="sun" />
      <StatCard label="Passengers today" value={ov?.total_passengers_today ?? '—'} tone="lime" />
      <StatCard label="Open complaints" value={ov?.open_complaints ?? '—'} tone="white" />
      <StatCard label="Devices online" value={ov ? `${ov.devices_online ?? '—'} / ${(ov.devices_online ?? 0) + (ov.devices_offline ?? 0)}` : '—'} tone="royal" />
    </div>
    <div className="grid lg:grid-cols-2 gap-5 items-start">
      <Card className="overflow-auto"><h2 className="font-display font-black text-xl mb-3">Routes ({routes.length})</h2>
        {routes.length === 0 ? <p className="text-sm font-semibold text-ink/60">No routes yet.</p> : <table className={tbl}><thead><tr className="text-left border-b-2 border-ink"><th className="py-2 pr-2">Name</th><th className="pr-2">From → To</th><th>Distance</th></tr></thead>
        <tbody>{routes.map(r => <tr key={r.id} className="border-b border-ink/20"><td className="py-2 pr-2 font-bold">{r.name}</td><td className="pr-2">{r.start_point} → {r.end_point}</td><td>{r.total_distance_km} km</td></tr>)}</tbody></table>}
      </Card>
      <Card className="overflow-auto"><h2 className="font-display font-black text-xl mb-3">Vehicles ({vehicles.length})</h2>
        {vehicles.length === 0 ? <p className="text-sm font-semibold text-ink/60">No vehicles yet.</p> : <table className={tbl}><thead><tr className="text-left border-b-2 border-ink"><th className="py-2 pr-2">Registration</th><th className="pr-2">Capacity</th><th>Status</th></tr></thead>
        <tbody>{vehicles.map(v => <tr key={v.id} className="border-b border-ink/20"><td className="py-2 pr-2 font-bold">{v.registration_number}</td><td className="pr-2">{v.capacity}</td><td><Badge tone={v.status === 'active' ? 'lime' : 'sun'}>{v.status}</Badge></td></tr>)}</tbody></table>}
      </Card>
    </div>
    <Card className="overflow-auto"><h2 className="font-display font-black text-xl mb-3">Trips ({trips.length})</h2>
      {trips.length === 0 ? <p className="text-sm font-semibold text-ink/60">No trips scheduled yet.</p> : <table className={tbl}><thead><tr className="text-left border-b-2 border-ink"><th className="py-2 pr-2">#</th><th className="pr-2">Route</th><th className="pr-2">Scheduled start</th><th>Status</th></tr></thead>
      <tbody>{trips.slice(0, 20).map(t => <tr key={t.id} className="border-b border-ink/20"><td className="py-2 pr-2 font-bold">{t.id}</td><td className="pr-2">{t.route_name || t.route}</td><td className="pr-2">{t.scheduled_start ? new Date(t.scheduled_start).toLocaleString() : '—'}</td><td><Badge tone={t.status === 'running' ? 'lime' : t.status === 'delayed' ? 'sun' : 'white'}>{t.status}</Badge></td></tr>)}</tbody></table>}
    </Card>
  </main>
}
