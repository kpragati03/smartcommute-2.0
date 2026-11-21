import { useCallback, useEffect, useMemo, useState } from 'react'
import api, { errMsg, listOf } from '../services/api'
import MapView from '../components/MapView'
import PassCard from '../components/PassCard'
import SupportSection from '../components/SupportSection'
import { Badge, Button, Card, CrowdBadge, EmptyState, ErrorBox, Input, Select, Skeleton, StatCard, Toast, timeAgo } from '../components/ui'
export default function CommuterApp() {
  const [vehicles, setVehicles] = useState([]); const [routes, setRoutes] = useState([]); const [stops, setStops] = useState([])
  const [loading, setLoading] = useState(true); const [err, setErr] = useState(''); const [toast, setToast] = useState('')
  const [query, setQuery] = useState(''); const [selStop, setSelStop] = useState(null); const [etas, setEtas] = useState(null); const [etaErr, setEtaErr] = useState('')
  const [fromStop, setFromStop] = useState(''); const [toStop, setToStop] = useState(''); const [plan, setPlan] = useState(null); const [planErr, setPlanErr] = useState(''); const [planning, setPlanning] = useState(false)
  const [favRoutes, setFavRoutes] = useState([]); const [favStops, setFavStops] = useState([]); const [saved, setSaved] = useState([])
  const say = (m) => { setToast(m); setTimeout(() => setToast(''), 3200) }
  const load = useCallback(async () => {
    try {
      const [v, r, s, fr, fs, sv] = await Promise.allSettled([
        api.get('/live/vehicles/'), api.get('/routes/'), api.get('/stops/'),
        api.get('/favourites/routes/'), api.get('/favourites/stops/'), api.get('/journeys/saved/')])
      if (v.status === 'fulfilled') setVehicles(listOf(v.value.data))
      if (r.status === 'fulfilled') setRoutes(listOf(r.value.data))
      if (s.status === 'fulfilled') setStops(listOf(s.value.data))
      if (fr.status === 'fulfilled') setFavRoutes(listOf(fr.value.data))
      if (fs.status === 'fulfilled') setFavStops(listOf(fs.value.data))
      if (sv.status === 'fulfilled') setSaved(listOf(sv.value.data))
      if (v.status === 'rejected') setErr(errMsg(v.reason)); else setErr('')
    } finally { setLoading(false) }
  }, [])
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t) }, [load])
  const shownStops = useMemo(() => stops.filter(s => s.name.toLowerCase().includes(query.toLowerCase())), [stops, query])
  const routeName = (id) => routes.find(r => r.id === id)?.name || `Route ${id}`
  const stopName = (id) => stops.find(s => s.id === id)?.name || `Stop ${id}`
  const favRouteIds = favRoutes.map(f => f.route); const favStopIds = favStops.map(f => f.stop)
  const pickStop = async (stop) => {
    setSelStop(stop); setEtas(null); setEtaErr('')
    try { const r = await api.get(`/live/eta/?stop_id=${stop.id}`); setEtas(listOf(r.data)) }
    catch (e) { setEtaErr(errMsg(e)) }
  }
  const doPlan = async () => {
    if (!fromStop || !toStop) { setPlanErr('Pick both a start and a destination stop.'); return }
    if (fromStop === toStop) { setPlanErr('Start and destination are the same stop.'); return }
    setPlanning(true); setPlanErr(''); setPlan(null)
    try { const r = await api.get(`/journey/plan/?from_stop=${fromStop}&to_stop=${toStop}`); setPlan(r.data) }
    catch (e) { setPlanErr(errMsg(e)) } finally { setPlanning(false) }
  }
  const toggleFavRoute = async (routeId) => {
    const ex = favRoutes.find(f => f.route === routeId)
    try { if (ex) await api.delete(`/favourites/routes/${ex.id}/`); else await api.post('/favourites/routes/', { route: routeId }); say(ex ? 'Route removed from favourites' : '⭐ Route favourited'); load() }
    catch (e) { say(errMsg(e)) }
  }
  const toggleFavStop = async (stopId) => {
    const ex = favStops.find(f => f.stop === stopId)
    try { if (ex) await api.delete(`/favourites/stops/${ex.id}/`); else await api.post('/favourites/stops/', { stop: stopId }); say(ex ? 'Stop removed from favourites' : '⭐ Stop favourited'); load() }
    catch (e) { say(errMsg(e)) }
  }
  const saveJourney = async () => {
    if (!fromStop || !toStop) { say('Pick start + destination first'); return }
    try { await api.post('/journeys/saved/', { source_stop: Number(fromStop), destination_stop: Number(toStop), label: `${stopName(Number(fromStop))} → ${stopName(Number(toStop))}` }); say('Journey saved ✓'); load() }
    catch (e) { say(errMsg(e)) }
  }
  const delSaved = async (id) => { try { await api.delete(`/journeys/saved/${id}/`); say('Saved journey removed'); load() } catch (e) { say(errMsg(e)) } }
  if (loading) return <main className="max-w-7xl mx-auto px-4 py-8 grid gap-4"><Skeleton className="h-40" /><Skeleton className="h-64" /><Skeleton className="h-40" /></main>
  return <main className="max-w-7xl mx-auto px-4 py-6 grid gap-5">
    <div className="flex flex-wrap items-center gap-3 justify-between">
      <div><h1 className="font-display font-black text-3xl">Commuter dashboard</h1><p className="text-sm font-semibold text-ink/70">Live positions refresh every 5 seconds. Stale buses are flagged, never hidden.</p></div>
      <Badge tone="lime">● {vehicles.filter(v => !v.is_stale).length} live now</Badge>
    </div>
    {err && <ErrorBox message={err} onRetry={load} />}
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <StatCard label="Vehicles tracked" value={vehicles.length} tone="lime" />
      <StatCard label="Routes" value={routes.length} tone="sun" />
      <StatCard label="Stops" value={stops.length} tone="royal" />
      <StatCard label="Stale signals" value={vehicles.filter(v => v.is_stale).length} sub=">60s without update" tone="white" />
    </div>
    <MapView vehicles={vehicles} routes={routes} stops={stops} height="440px" onStopClick={pickStop} />
    <div className="grid lg:grid-cols-2 gap-5 items-start">
      <Card>
        <h2 className="font-display font-black text-xl mb-3">🚌 Vehicles right now</h2>
        {vehicles.length === 0 ? <EmptyState title="No vehicles reporting" hint="When a device posts telemetry, buses appear here within seconds." /> : <div className="grid gap-3">
          {vehicles.map(v => <div key={v.id} className="border-[2.5px] border-ink rounded-xl p-3 bg-cream/60">
            <div className="flex flex-wrap items-center gap-2 justify-between">
              <span className="font-display font-black">{v.registration_number}</span><CrowdBadge level={v.crowd_level} percent={v.occupancy_percent} />
            </div>
            <p className="text-sm font-semibold text-ink/75 mt-1">{v.route_name || 'No route assigned'} · {v.speed_kmph ?? '—'} km/h · {v.seats_available ?? '—'} of {v.capacity ?? '—'} seats free</p>
            <p className="text-xs font-bold mt-1">{v.is_stale ? <span className="text-red-700">⚠ Stale — last update {timeAgo(v.last_updated)}</span> : <span className="text-green-800">Updated {timeAgo(v.last_updated)}</span>}</p>
            <div className="h-3 rounded-full border-2 border-ink bg-white mt-2 overflow-hidden"><div className="h-full bg-lime-brand" style={{ width: `${Math.min(100, v.occupancy_percent || 0)}%` }} /></div>
          </div>)}
        </div>}
      </Card>
      <div className="grid gap-5">
        <Card>
          <h2 className="font-display font-black text-xl mb-3">🔎 Find your stop & ETA</h2>
          <Input placeholder="Search stops…" value={query} onChange={e => setQuery(e.target.value)} />
          <div className="flex flex-wrap gap-2 mt-3 max-h-44 overflow-auto">
            {shownStops.length === 0 ? <p className="text-sm font-semibold text-ink/60">No stops match.</p> : shownStops.map(s => (
              <span key={s.id} className="inline-flex items-center gap-1">
                <button onClick={() => pickStop(s)} className={`rounded-full border-2 border-ink px-3 py-1.5 text-sm font-extrabold ${selStop?.id === s.id ? 'bg-sun shadow-hardSm' : 'bg-white hover:bg-cream'}`}>{s.name}</button>
                <button title="Favourite stop" onClick={() => toggleFavStop(s.id)} className="text-lg leading-none">{favStopIds.includes(s.id) ? '⭐' : '☆'}</button>
              </span>))}
          </div>
          {selStop && <div className="mt-4 border-[2.5px] border-ink rounded-xl bg-cream/70 p-3">
            <p className="font-display font-black">Next buses at {selStop.name}</p>
            {etaErr && <p className="text-sm font-bold text-red-700 mt-1">{etaErr}</p>}
            {!etas && !etaErr && <p className="text-sm font-semibold mt-1">Checking live ETAs…</p>}
            {etas && etas.length === 0 && <p className="text-sm font-semibold mt-1">No bus is heading to this stop right now.</p>}
            {etas && etas.map((e, i) => <p key={i} className="text-sm font-bold mt-1.5">🚌 {e.registration_number} — <span className="bg-lime-brand border border-ink rounded-md px-1.5">{e.eta_minutes} min</span> <span className="text-ink/60 font-semibold">({e.distance_remaining_km} km away · {e.method})</span></p>)}
          </div>}
        </Card>
        <Card>
          <h2 className="font-display font-black text-xl mb-3">🧭 Journey planner</h2>
          <div className="grid sm:grid-cols-2 gap-3">
            <Select label="From" value={fromStop} onChange={e => setFromStop(e.target.value)}><option value="">Choose start stop…</option>{stops.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</Select>
            <Select label="To" value={toStop} onChange={e => setToStop(e.target.value)}><option value="">Choose destination…</option>{stops.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</Select>
          </div>
          <div className="flex flex-wrap gap-2 mt-3">
            <Button onClick={doPlan} disabled={planning}>{planning ? 'Planning…' : 'Plan journey →'}</Button>
            <Button variant="white" onClick={saveJourney}>💾 Save this journey</Button>
          </div>
          {planErr && <p className="text-sm font-bold text-red-700 mt-2">{planErr}</p>}
          {plan && (plan.options?.length ? <div className="grid gap-3 mt-4">{plan.options.map((o, i) => (
            <div key={i} className="border-[2.5px] border-ink rounded-xl bg-cream/70 p-3">
              <p className="font-display font-black">Option {i + 1} — {o.total_duration_minutes} min · {o.transfers} transfer{o.transfers === 1 ? '' : 's'}{o.walking_km ? ` · walk ${o.walking_km} km` : ''}</p>
              {o.legs.map((l, j) => <p key={j} className="text-sm font-semibold mt-1">↳ {l.route_name || routeName(l.route_id)}: {l.from_stop_name || stopName(l.from_stop_id)} → {l.to_stop_name || stopName(l.to_stop_id)} ({l.duration_minutes} min)</p>)}
            </div>))}</div> : <p className="text-sm font-semibold mt-3">No route found between those stops yet.</p>)}
        </Card>
        <Card>
          <h2 className="font-display font-black text-xl mb-3">⭐ Favourites & saved journeys</h2>
          <p className="text-xs font-extrabold uppercase tracking-wider mb-2">Routes — tap ☆ to favourite</p>
          <div className="flex flex-wrap gap-2">{routes.map(r => <button key={r.id} onClick={() => toggleFavRoute(r.id)} className={`rounded-full border-2 border-ink px-3 py-1.5 text-sm font-extrabold ${favRouteIds.includes(r.id) ? 'bg-sun shadow-hardSm' : 'bg-white'}`}>{favRouteIds.includes(r.id) ? '⭐' : '☆'} {r.name}</button>)}</div>
          <p className="text-xs font-extrabold uppercase tracking-wider mt-4 mb-2">Saved journeys</p>
          {saved.length === 0 ? <p className="text-sm font-semibold text-ink/60">None yet — plan a journey above and save it.</p> : saved.map(j => (
            <div key={j.id} className="flex items-center justify-between gap-2 border-2 border-ink rounded-xl px-3 py-2 mt-2 bg-white">
              <span className="text-sm font-bold">{j.label || `${stopName(j.source_stop)} → ${stopName(j.destination_stop)}`}</span>
              <button onClick={() => delSaved(j.id)} className="text-sm font-extrabold underline">Remove</button>
            </div>))}
        </Card>
      </div>
    </div>
    <div className="grid lg:grid-cols-2 gap-5 items-start">
      <PassCard say={say} />
      <SupportSection vehicles={vehicles} say={say} />
    </div>
    <Toast toast={toast} />
  </main>
}
