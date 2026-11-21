import { useEffect, useState } from 'react'
import api, { listOf } from '../services/api'
import MapView from '../components/MapView'
import { Badge, Card, LinkButton, StatCard, CrowdBadge, timeAgo } from '../components/ui'
export default function Landing() {
  const [vehicles, setVehicles] = useState(null) // null = connecting
  const [routes, setRoutes] = useState([])
  const [stops, setStops] = useState([])
  const [err, setErr] = useState('')
  useEffect(() => {
    let alive = true
    const load = async () => {
      try {
        const [v, r, s] = await Promise.allSettled([api.get('/live/vehicles/'), api.get('/routes/'), api.get('/stops/')])
        if (!alive) return
        if (v.status === 'fulfilled') { setVehicles(listOf(v.value.data)); setErr('') }
        else setErr('Live feed connecting… (sign in to see your organisation’s buses)')
        if (r.status === 'fulfilled') setRoutes(listOf(r.value.data))
        if (s.status === 'fulfilled') setStops(listOf(s.value.data))
      } catch { if (alive) setErr('Live feed connecting…') }
    }
    load()
    const t = setInterval(load, 5000)
    return () => { alive = false; clearInterval(t) }
  }, [])
  const live = vehicles ? vehicles.filter(v => !v.is_stale).length : null
  const corridors = routes.length ? new Set(routes.map(r => r.id)).size : null
  return <main>
    <section className="max-w-7xl mx-auto px-4 pt-10 pb-8 grid lg:grid-cols-2 gap-8 items-start">
      <div>
        <div className="flex flex-wrap gap-2 mb-4">
          <Badge tone="lime">● Live tracking</Badge><Badge tone="sun">Demo data labelled</Badge><Badge tone="royal">Multi-organisation</Badge>
        </div>
        <h1 className="font-display font-black text-4xl md:text-6xl leading-[1.02]">Know where your bus <span className="bg-lime-brand border-[3px] border-ink rounded-xl px-2 shadow-hardSm inline-block -rotate-1">actually</span> is.</h1>
        <p className="mt-4 text-base md:text-lg font-medium text-ink/80 max-w-xl">SmartCommute 2.0 brings live vehicle positions, honest ETAs, crowd levels and journey planning to campuses and city fleets — one platform for commuters, drivers and transport teams.</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <LinkButton to="/login" variant="primary">🎓 Enter Student Portal</LinkButton>
          <LinkButton to="/login" variant="sun">🚌 Driver Console</LinkButton>
          <LinkButton to="/login" variant="royal">🛠 Admin Console</LinkButton>
        </div>
        <p className="mt-3 text-xs font-bold text-ink/60">After sign-in you’re routed to your own console automatically. New here? <a className="underline" href="/register">Create a commuter account</a>.</p>
        <div className="grid grid-cols-3 gap-3 mt-8">
          <StatCard label="Buses live" value={live == null ? '—' : live} sub={vehicles == null ? 'connecting…' : 'updated every 5s'} tone="lime" />
          <StatCard label="Corridors" value={corridors == null ? '—' : corridors} sub="routes in your org" tone="sun" />
          <StatCard label="Stops mapped" value={stops.length || '—'} sub="with coordinates" tone="royal" />
        </div>
      </div>
      <div>
        <Card className="!p-3">
          <div className="flex items-center justify-between px-2 py-1">
            <span className="font-display font-black">📡 Live radar</span>
            <Badge tone={vehicles == null ? 'sun' : 'lime'}>{vehicles == null ? 'Connecting…' : `${vehicles.length} vehicles`}</Badge>
          </div>
          <MapView vehicles={vehicles || []} routes={routes} stops={stops} height="380px" />
          {err && <p className="text-xs font-bold text-ink/60 px-2 pt-2">{err} We never show fake buses.</p>}
          {vehicles && vehicles.length === 0 && <p className="text-xs font-bold text-ink/60 px-2 pt-2">No vehicles reporting yet — start the simulator or check back shortly.</p>}
        </Card>
        {vehicles && vehicles.length > 0 && <div className="mt-4 grid gap-3">
          {vehicles.slice(0, 3).map(v => <Card key={v.id} className="!p-4 flex flex-wrap items-center gap-3 justify-between">
            <div><span className="font-display font-black">{v.registration_number}</span> <span className="text-sm font-semibold text-ink/70">{v.route_name || ''}</span>
            <div className="text-xs font-bold text-ink/60">{v.speed_kmph ?? '—'} km/h · {v.seats_available ?? '—'} seats free · updated {timeAgo(v.last_updated)}{v.is_stale ? ' · ⚠ stale' : ''}</div></div>
            <CrowdBadge level={v.crowd_level} percent={v.occupancy_percent} />
          </Card>)}
        </div>}
      </div>
    </section>
    <section className="max-w-7xl mx-auto px-4 py-8">
      <h2 className="font-display font-black text-3xl mb-5">Built for the whole commute</h2>
      <div className="grid md:grid-cols-3 gap-4">
        {[['🗺 Live map & ETAs','Real positions from device telemetry, staleness warnings, and ETAs that say how they were computed.'],
          ['🧭 Journey planner','Source → destination across routes with transfers and honest durations.'],
          ['⭐ Favourites & saved journeys','Pin your routes and stops; save the trips you take every day.'],
          ['🎫 Digital passes','Apply, get approved, carry a QR pass — verified at the gate.'],
          ['📊 Fleet analytics','Occupancy, delays and ETA accuracy (baseline vs ML) from real data.'],
          ['🏢 Multi-organisation SaaS','Each campus or operator sees only its own fleet. Plans and limits built in.']].map(([t,d]) => (
          <Card key={t}><h3 className="font-display font-black text-lg">{t}</h3><p className="text-sm font-medium text-ink/75 mt-1">{d}</p></Card>
        ))}
      </div>
    </section>
    <section className="max-w-7xl mx-auto px-4 py-6">
      <div className="bg-royal text-white border-[3px] border-ink rounded-2xl shadow-hardLg p-6 md:p-8 flex flex-wrap gap-4 items-center justify-between">
        <div><h2 className="font-display font-black text-2xl md:text-3xl">Run a campus or city fleet?</h2><p className="font-medium text-white/85 mt-1">Register your organisation, add routes and vehicles, and go live in minutes.</p></div>
        <LinkButton to="/register-organisation" variant="sun">Register your organisation →</LinkButton>
      </div>
      <p className="text-center text-xs font-bold text-ink/50 mt-6">Seeded demo organisations (“LPU Campus Transit (Demo)”) are labelled DEMO everywhere they appear.</p>
    </section>
  </main>
}
