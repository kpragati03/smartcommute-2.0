import { useCallback, useEffect, useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import api, { errMsg, listOf } from '../services/api'
import { useAuth } from '../context/AuthContext'
import {
  Badge, Button, Card, EmptyState, ErrorBox, FormError, Input, Modal, ProgressBar, SectionTitle,
  Select, Skeleton, StarRating, StatCard, StatusBadge, Textarea, Toast, fmtDate, fmtDateTime, tableCls, tdCls, thCls, trCls,
} from '../components/ui'

const TABS = [
  ['overview', '📊 Overview'],
  ['fleet', '🚌 Fleet & devices'],
  ['routes', '🗺 Routes & stops'],
  ['trips', '🕐 Trips & schedules'],
  ['drivers', '🧑‍✈️ Drivers'],
  ['passes', '🎫 Pass applications'],
  ['complaints', '📨 Complaints'],
  ['incidents', '🚨 Incidents'],
  ['subscription', '💳 Subscription'],
  ['organisations', '🏢 Organisations'],
]

export default function AdminConsole() {
  const { isPlatformAdmin } = useAuth()
  const [tab, setTab] = useState('overview')
  const [toast, setToast] = useState('')
  const say = (m) => { setToast(m); setTimeout(() => setToast(''), 3400) }
  const tabs = TABS.filter(([id]) => id !== 'organisations' || isPlatformAdmin)

  return (
    <main className="max-w-7xl mx-auto px-4 py-6 grid gap-5">
      <div>
        <h1 className="font-display font-black text-3xl">Admin console</h1>
        <p className="text-sm font-semibold text-ink/70">Full operations for your organisation — fleet, routes, trips, passes, support and billing. Everything below is live API data.</p>
      </div>
      <nav className="flex flex-wrap gap-2" aria-label="Admin sections">
        {tabs.map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)}
            className={`rounded-full border-2 border-ink px-4 py-2 text-sm font-extrabold ${tab === id ? 'bg-lime-brand shadow-hardSm' : 'bg-white hover:bg-sun'}`}>{label}</button>
        ))}
      </nav>
      {tab === 'overview' && <Overview say={say} />}
      {tab === 'fleet' && <Fleet say={say} />}
      {tab === 'routes' && <RoutesStops say={say} />}
      {tab === 'trips' && <TripsSchedules say={say} />}
      {tab === 'drivers' && <Drivers say={say} />}
      {tab === 'passes' && <PassApplications say={say} />}
      {tab === 'complaints' && <ComplaintsInbox say={say} />}
      {tab === 'incidents' && <IncidentsList say={say} />}
      {tab === 'subscription' && <Subscription say={say} />}
      {tab === 'organisations' && isPlatformAdmin && <Organisations say={say} />}
      <Toast toast={toast} />
    </main>
  )
}

function useLoad(loader, deps = []) {
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(true)
  const reload = useCallback(async () => {
    setLoading(true)
    try { const d = await loader(); setData(d); setErr('') }
    catch (e) { setErr(errMsg(e)) } finally { setLoading(false) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  useEffect(() => { reload() }, [reload])
  return { data, err, loading, reload, setData }
}

function LoadingOrError({ loading, err, reload, children }) {
  if (loading) return <div className="grid gap-4"><Skeleton className="h-32" /><Skeleton className="h-48" /></div>
  if (err) return <ErrorBox message={err} onRetry={reload} />
  return children
}

/* ---------------- Overview ---------------- */
function Overview({ say }) {
  const { data, err, loading, reload } = useLoad(async () => {
    const [ov, crowd, routes, eta] = await Promise.allSettled([
      api.get('/analytics/overview/'), api.get('/analytics/crowd/'),
      api.get('/analytics/routes/'), api.get('/analytics/eta-accuracy/'),
    ])
    if (ov.status === 'rejected') throw ov.reason
    return {
      ov: ov.value.data,
      crowd: crowd.status === 'fulfilled' ? listOf(crowd.value.data) : null,
      crowdErr: crowd.status === 'rejected' ? errMsg(crowd.reason) : '',
      routes: routes.status === 'fulfilled' ? listOf(routes.value.data) : null,
      routesErr: routes.status === 'rejected' ? errMsg(routes.reason) : '',
      eta: eta.status === 'fulfilled' ? eta.value.data : null,
      etaErr: eta.status === 'rejected' ? errMsg(eta.reason) : '',
    }
  })
  if (loading) return <div className="grid gap-4"><Skeleton className="h-32" /><Skeleton className="h-64" /></div>
  if (err) return <ErrorBox message={err} onRetry={reload} />
  const { ov, crowd, routes, eta } = data

  const crowdData = (crowd || []).map(c => ({
    hour: c.hour != null ? `${String(c.hour).padStart(2, '0')}:00` : (c.label || ''),
    occupancy: Math.round(Number(c.avg_occupancy_percent ?? c.avg_occupancy ?? c.occupancy_percent ?? c.occupancy ?? 0)),
  }))
  const routeData = (routes || []).map(r => ({
    name: r.route_name || r.name || `Route ${r.route_id ?? r.route ?? ''}`,
    trips: Number(r.trips ?? r.trip_count ?? 0),
    delay: Math.round(Number(r.avg_delay_minutes ?? 0) * 10) / 10,
    occupancy: Math.round(Number(r.avg_occupancy ?? r.avg_occupancy_percent ?? 0)),
    passengers: Number(r.passengers ?? r.total_passengers ?? 0),
  }))
  const etaN = Number(eta?.baseline?.n || 0) + Number(eta?.ml?.n || 0)

  return (
    <div className="grid gap-5">
      <div className="flex justify-end"><Button variant="white" onClick={() => { reload(); say('Overview refreshed') }}>↻ Refresh</Button></div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Total vehicles" value={ov?.total_vehicles ?? '—'} tone="lime" />
        <StatCard label="Active vehicles" value={ov?.active_vehicles ?? '—'} tone="sun" />
        <StatCard label="Running trips" value={ov?.running_trips ?? '—'} tone="royal" />
        <StatCard label="Delayed trips" value={ov?.delayed_trips ?? '—'} tone="white" />
        <StatCard label="Avg occupancy" value={ov?.avg_occupancy_percent != null ? `${Math.round(ov.avg_occupancy_percent)}%` : '—'} tone="sun" />
        <StatCard label="Passengers today" value={ov?.total_passengers_today ?? '—'} tone="lime" />
        <StatCard label="Open complaints" value={ov?.open_complaints ?? '—'} tone="white" />
        <StatCard label="Devices online" value={ov ? `${ov.devices_online ?? '—'} / ${(ov.devices_online ?? 0) + (ov.devices_offline ?? 0)}` : '—'} sub={ov?.devices_offline ? `${ov.devices_offline} offline` : 'all reporting'} tone="royal" />
      </div>

      <div className="grid lg:grid-cols-2 gap-5 items-start">
        <Card>
          <SectionTitle sub="Average occupancy by hour of day, from stored occupancy records.">👥 Crowd by hour</SectionTitle>
          {data.crowdErr && <FormError message={data.crowdErr} />}
          {!data.crowdErr && crowdData.length === 0 && <EmptyState title="No occupancy history yet" hint="As devices report passengers, the hourly crowd pattern appears here." />}
          {crowdData.length > 0 && (
            <div className="h-[280px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={crowdData} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
                  <CartesianGrid stroke="#141414" strokeOpacity={0.15} />
                  <XAxis dataKey="hour" tick={{ fontSize: 11, fontWeight: 700 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11, fontWeight: 700 }} unit="%" />
                  <Tooltip formatter={(v) => [`${v}%`, 'Avg occupancy']} contentStyle={{ border: '2px solid #141414', borderRadius: 12, fontWeight: 700 }} />
                  <Line type="monotone" dataKey="occupancy" stroke="#141414" strokeWidth={3} dot={{ fill: '#B9E62E', stroke: '#141414', strokeWidth: 2, r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card>
          <SectionTitle sub="Trips run and average delay per route.">🛣 Route performance</SectionTitle>
          {data.routesErr && <FormError message={data.routesErr} />}
          {!data.routesErr && routeData.length === 0 && <EmptyState title="No route analytics yet" hint="Run some trips and per-route performance shows up here." />}
          {routeData.length > 0 && (
            <>
              <div className="h-[240px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={routeData} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
                    <CartesianGrid stroke="#141414" strokeOpacity={0.15} />
                    <XAxis dataKey="name" tick={{ fontSize: 11, fontWeight: 700 }} interval={0} angle={routeData.length > 3 ? -18 : 0} textAnchor={routeData.length > 3 ? 'end' : 'middle'} height={routeData.length > 3 ? 56 : 30} />
                    <YAxis tick={{ fontSize: 11, fontWeight: 700 }} />
                    <Tooltip contentStyle={{ border: '2px solid #141414', borderRadius: 12, fontWeight: 700 }} />
                    <Bar dataKey="trips" name="Trips" stroke="#141414" strokeWidth={2} radius={[6, 6, 0, 0]}>
                      {routeData.map((_, i) => <Cell key={i} fill={['#B9E62E', '#FFD93D', '#2F6BFF'][i % 3]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="overflow-auto mt-3">
                <table className={tableCls}>
                  <thead><tr><th className={thCls}>Route</th><th className={thCls}>Trips</th><th className={thCls}>Avg delay</th><th className={thCls}>Avg occupancy</th><th className={thCls}>Passengers</th></tr></thead>
                  <tbody>{routeData.map((r, i) => (
                    <tr key={i} className={trCls}><td className={`${tdCls} font-bold`}>{r.name}</td><td className={tdCls}>{r.trips}</td><td className={tdCls}>{r.delay} min</td><td className={tdCls}>{r.occupancy}%</td><td className={tdCls}>{r.passengers}</td></tr>
                  ))}</tbody>
                </table>
              </div>
            </>
          )}
        </Card>
      </div>

      <Card>
        <SectionTitle sub="Computed from stored ETA evaluations — shown honestly, including when the ML model has no advantage yet.">🎯 ETA accuracy — baseline vs ML</SectionTitle>
        {data.etaErr && <FormError message={data.etaErr} />}
        {!data.etaErr && (!eta || etaN === 0) && (
          <EmptyState title="Not enough data yet" hint="ETA accuracy appears once buses have completed trips and predictions have been scored against actual arrivals." />
        )}
        {eta && etaN > 0 && (
          <div className="grid md:grid-cols-2 gap-4">
            {[['Baseline (distance ÷ speed)', eta.baseline, 'bg-sun'], ['ML model', eta.ml, 'bg-lime-brand']].map(([label, m, bg]) => (
              <div key={label} className={`border-[2.5px] border-ink rounded-2xl ${bg} p-4`}>
                <p className="font-display font-black">{label}</p>
                {Number(m?.n || 0) === 0
                  ? <p className="text-sm font-bold mt-2">No scored predictions yet (n = 0).</p>
                  : <div className="grid grid-cols-3 gap-2 mt-3 text-center">
                    <div className="bg-white border-2 border-ink rounded-xl py-2"><p className="font-display font-black text-xl">{m.mae}</p><p className="text-[11px] font-extrabold uppercase">MAE (min)</p></div>
                    <div className="bg-white border-2 border-ink rounded-xl py-2"><p className="font-display font-black text-xl">{m.rmse}</p><p className="text-[11px] font-extrabold uppercase">RMSE (min)</p></div>
                    <div className="bg-white border-2 border-ink rounded-xl py-2"><p className="font-display font-black text-xl">{m.n}</p><p className="text-[11px] font-extrabold uppercase">Samples</p></div>
                  </div>}
              </div>
            ))}
            <p className="md:col-span-2 text-sm font-semibold text-ink/70">
              Lower MAE/RMSE = more accurate. {Number(eta.ml?.n || 0) > 0 && Number(eta.baseline?.n || 0) > 0
                ? (Number(eta.ml.mae) < Number(eta.baseline.mae)
                  ? `ML is currently ahead by ${(Number(eta.baseline.mae) - Number(eta.ml.mae)).toFixed(2)} min MAE.`
                  : 'ML has not beaten the baseline yet on this data — the numbers above are the honest score.')
                : 'Both methods need scored trips before a fair comparison is possible.'}
            </p>
          </div>
        )}
      </Card>
    </div>
  )
}

/* ---------------- Fleet & devices ---------------- */
function Fleet({ say }) {
  const { data, err, loading, reload } = useLoad(async () => {
    const [v, d] = await Promise.allSettled([api.get('/vehicles/'), api.get('/devices/')])
    if (v.status === 'rejected') throw v.reason
    return { vehicles: listOf(v.value.data), devices: d.status === 'fulfilled' ? listOf(d.value.data) : null, devErr: d.status === 'rejected' ? errMsg(d.reason) : '' }
  })
  const [vehForm, setVehForm] = useState(null) // {id?, registration_number, capacity, status}
  const [devForm, setDevForm] = useState(null) // {vehicle, name}
  const [rawKey, setRawKey] = useState('')
  const [formErr, setFormErr] = useState('')
  const [busy, setBusy] = useState(false)

  const saveVehicle = async (e) => {
    e.preventDefault()
    if (!vehForm.registration_number.trim()) { setFormErr('Registration number is required.'); return }
    const cap = parseInt(vehForm.capacity, 10)
    if (!cap || cap < 1 || cap > 300) { setFormErr('Capacity must be between 1 and 300.'); return }
    setBusy(true); setFormErr('')
    try {
      const body = { registration_number: vehForm.registration_number.trim().toUpperCase(), capacity: cap, status: vehForm.status }
      if (vehForm.id) await api.patch(`/vehicles/${vehForm.id}/`, body)
      else await api.post('/vehicles/', body)
      setVehForm(null); say(vehForm.id ? 'Vehicle updated ✓' : 'Vehicle added ✓'); reload()
    } catch (ex) { setFormErr(errMsg(ex)) } finally { setBusy(false) }
  }

  const createDevice = async (e) => {
    e.preventDefault()
    if (!devForm.vehicle) { setFormErr('Pick the vehicle this device is installed in.'); return }
    setBusy(true); setFormErr('')
    try {
      const r = await api.post('/devices/', { vehicle: Number(devForm.vehicle), name: devForm.name.trim() || undefined })
      const key = r.data?.key || r.data?.raw_key || r.data?.api_key || r.data?.device_key || ''
      setRawKey(key || JSON.stringify(r.data))
      setDevForm(null); say('Device created ✓ — copy its key now, it is shown only once.'); reload()
    } catch (ex) { setFormErr(errMsg(ex)) } finally { setBusy(false) }
  }

  const deactivate = async (d) => {
    try { await api.patch(`/devices/${d.id}/`, { is_active: false }) }
    catch { try { await api.post(`/devices/${d.id}/deactivate/`, {}) } catch (e2) { say(errMsg(e2)); return } }
    say('Device deactivated'); reload()
  }

  const copyKey = async () => {
    try { await navigator.clipboard.writeText(rawKey); say('Key copied ✓') }
    catch { say('Copy failed — select the key text and copy manually.') }
  }

  return (
    <LoadingOrError loading={loading} err={err} reload={reload}>
      <div className="grid gap-5">
        <Card className="overflow-auto">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <SectionTitle>🚌 Vehicles ({data?.vehicles.length ?? 0})</SectionTitle>
            <Button onClick={() => { setFormErr(''); setVehForm({ registration_number: '', capacity: '40', status: 'active' }) }}>+ Add vehicle</Button>
          </div>
          {data?.vehicles.length === 0
            ? <EmptyState title="No vehicles yet" hint="Add your first vehicle, then create a device for it so it can report live positions." />
            : <table className={tableCls}>
              <thead><tr><th className={thCls}>Registration</th><th className={thCls}>Capacity</th><th className={thCls}>Status</th><th className={thCls}>Actions</th></tr></thead>
              <tbody>{data.vehicles.map(v => (
                <tr key={v.id} className={trCls}>
                  <td className={`${tdCls} font-bold`}>{v.registration_number}</td>
                  <td className={tdCls}>{v.capacity}</td>
                  <td className={tdCls}><StatusBadge status={v.status} /></td>
                  <td className={tdCls}><Button variant="white" className="!px-3 !py-1.5 !text-xs" onClick={() => { setFormErr(''); setVehForm({ id: v.id, registration_number: v.registration_number, capacity: String(v.capacity), status: v.status }) }}>Edit</Button></td>
                </tr>))}
              </tbody></table>}
        </Card>

        <Card className="overflow-auto">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <SectionTitle sub="Each device authenticates with its own key (X-Device-Key). Keys are stored hashed — the raw key is shown once at creation.">📡 Devices ({data?.devices?.length ?? 0})</SectionTitle>
            <Button variant="sun" onClick={() => { setFormErr(''); setDevForm({ vehicle: '', name: '' }) }}>+ Create device</Button>
          </div>
          {data?.devErr && <FormError message={data.devErr} />}
          {rawKey && (
            <div className="border-[3px] border-ink rounded-2xl bg-sun p-4 mb-4">
              <p className="font-display font-black">🔑 New device key — copy it now</p>
              <p className="text-sm font-bold mt-1">⚠ This key is shown ONCE. It cannot be recovered later — if lost, deactivate this device and create a new one. Put it in the vehicle device / simulator config.</p>
              <div className="flex flex-wrap gap-2 mt-3 items-center">
                <code className="flex-1 min-w-[220px] bg-white border-2 border-ink rounded-xl px-3 py-2.5 font-mono text-sm font-bold break-all">{rawKey}</code>
                <Button variant="ink" onClick={copyKey}>Copy key</Button>
                <Button variant="white" onClick={() => setRawKey('')}>Done</Button>
              </div>
            </div>
          )}
          {data?.devices && data.devices.length === 0 && <EmptyState title="No devices yet" hint="Create a device for a vehicle to start receiving GPS telemetry." />}
          {data?.devices && data.devices.length > 0 && (
            <table className={tableCls}>
              <thead><tr><th className={thCls}>Device</th><th className={thCls}>Vehicle</th><th className={thCls}>Last seen</th><th className={thCls}>Status</th><th className={thCls}>Actions</th></tr></thead>
              <tbody>{data.devices.map(d => {
                const veh = data.vehicles.find(v => v.id === d.vehicle)
                const active = d.is_active !== false && d.status !== 'inactive'
                return (
                  <tr key={d.id} className={trCls}>
                    <td className={`${tdCls} font-bold`}>{d.name || d.device_name || `Device #${d.id}`}</td>
                    <td className={tdCls}>{d.vehicle_registration || veh?.registration_number || d.vehicle || '—'}</td>
                    <td className={tdCls}>{d.last_seen ? fmtDateTime(d.last_seen) : 'Never'}</td>
                    <td className={tdCls}><StatusBadge status={active ? 'active' : 'inactive'} /></td>
                    <td className={tdCls}>{active && <Button variant="danger" className="!px-3 !py-1.5 !text-xs" onClick={() => deactivate(d)}>Deactivate</Button>}</td>
                  </tr>
                )
              })}</tbody>
            </table>
          )}
        </Card>
      </div>

      {vehForm && (
        <Modal title={vehForm.id ? 'Edit vehicle' : 'Add vehicle'} onClose={() => setVehForm(null)}>
          <form onSubmit={saveVehicle} className="grid gap-3">
            <Input label="Registration number" required value={vehForm.registration_number} onChange={e => setVehForm({ ...vehForm, registration_number: e.target.value })} placeholder="e.g. PB-10-AX-101" />
            <Input label="Capacity (seats)" type="number" min="1" max="300" required value={vehForm.capacity} onChange={e => setVehForm({ ...vehForm, capacity: e.target.value })} />
            <Select label="Status" value={vehForm.status} onChange={e => setVehForm({ ...vehForm, status: e.target.value })}>
              <option value="active">Active</option><option value="inactive">Inactive</option><option value="maintenance">Maintenance</option>
            </Select>
            <FormError message={formErr} />
            <Button type="submit" disabled={busy} className="w-full">{busy ? 'Saving…' : vehForm.id ? 'Save changes' : 'Add vehicle'}</Button>
            <p className="text-xs font-semibold text-ink/60">Your plan limits how many vehicles you can add — the server will say so if you hit the cap.</p>
          </form>
        </Modal>
      )}
      {devForm && (
        <Modal title="Create device" onClose={() => setDevForm(null)}>
          <form onSubmit={createDevice} className="grid gap-3">
            <Select label="Vehicle" required value={devForm.vehicle} onChange={e => setDevForm({ ...devForm, vehicle: e.target.value })}>
              <option value="">Choose vehicle…</option>
              {(data?.vehicles || []).map(v => <option key={v.id} value={v.id}>{v.registration_number} · {v.capacity} seats</option>)}
            </Select>
            <Input label="Device name (optional)" value={devForm.name} onChange={e => setDevForm({ ...devForm, name: e.target.value })} placeholder="e.g. GPS unit 1" />
            <FormError message={formErr} />
            <Button type="submit" variant="sun" disabled={busy} className="w-full">{busy ? 'Creating…' : 'Create device & reveal key'}</Button>
          </form>
        </Modal>
      )}
    </LoadingOrError>
  )
}

/* ---------------- Routes & stops ---------------- */
function parsePolyline(text) {
  const pts = []
  for (const line of String(text || '').split('\n')) {
    const t = line.trim()
    if (!t) continue
    const parts = t.split(/[,\s]+/).filter(Boolean)
    if (parts.length !== 2) throw new Error(`Polyline line "${t}" must be "lat,lng".`)
    const lat = Number(parts[0]); const lng = Number(parts[1])
    if (isNaN(lat) || isNaN(lng) || lat < -90 || lat > 90 || lng < -180 || lng > 180) throw new Error(`Invalid coordinate "${t}".`)
    pts.push([lat, lng])
  }
  return pts
}

function RoutesStops({ say }) {
  const { data: routes, err, loading, reload } = useLoad(async () => listOf((await api.get('/routes/')).data))
  const [routeForm, setRouteForm] = useState(null)
  const [stopsFor, setStopsFor] = useState(null) // route object
  const [stops, setStops] = useState([])
  const [stopsErr, setStopsErr] = useState('')
  const [stopForm, setStopForm] = useState(null)
  const [formErr, setFormErr] = useState('')
  const [busy, setBusy] = useState(false)

  const loadStops = useCallback(async (routeId) => {
    try { const r = await api.get(`/stops/?route=${routeId}`); setStops(listOf(r.data).sort((a, b) => (a.order || 0) - (b.order || 0))); setStopsErr('') }
    catch (e) { setStopsErr(errMsg(e)) }
  }, [])

  const openStops = (route) => { setStopsFor(route); setStops([]); loadStops(route.id) }

  const saveRoute = async (e) => {
    e.preventDefault()
    let polyline
    try { polyline = parsePolyline(routeForm.polylineText) } catch (ex) { setFormErr(ex.message); return }
    const dist = Number(routeForm.total_distance_km)
    if (!routeForm.name.trim() || !routeForm.start_point.trim() || !routeForm.end_point.trim()) { setFormErr('Name, start point and end point are required.'); return }
    if (!dist || dist <= 0) { setFormErr('Total distance must be a positive number of km.'); return }
    setBusy(true); setFormErr('')
    try {
      const body = { name: routeForm.name.trim(), start_point: routeForm.start_point.trim(), end_point: routeForm.end_point.trim(), total_distance_km: dist, polyline, is_active: routeForm.is_active }
      if (routeForm.id) await api.patch(`/routes/${routeForm.id}/`, body)
      else await api.post('/routes/', body)
      setRouteForm(null); say(routeForm.id ? 'Route updated ✓' : 'Route created ✓'); reload()
    } catch (ex) { setFormErr(errMsg(ex)) } finally { setBusy(false) }
  }

  const saveStop = async (e) => {
    e.preventDefault()
    const order = parseInt(stopForm.order, 10)
    const dist = Number(stopForm.distance_from_start_km)
    const lat = Number(stopForm.latitude); const lng = Number(stopForm.longitude)
    if (!stopForm.name.trim()) { setFormErr('Stop name is required.'); return }
    if (!order || order < 1) { setFormErr('Order must be 1 or higher.'); return }
    if (isNaN(dist) || dist < 0) { setFormErr('Distance from start must be 0 or more.'); return }
    if (isNaN(lat) || lat < -90 || lat > 90 || isNaN(lng) || lng < -180 || lng > 180) { setFormErr('Enter a valid latitude (-90…90) and longitude (-180…180).'); return }
    setBusy(true); setFormErr('')
    try {
      const body = { route: stopsFor.id, name: stopForm.name.trim(), order, distance_from_start_km: dist, latitude: lat, longitude: lng }
      if (stopForm.id) await api.patch(`/stops/${stopForm.id}/`, body)
      else await api.post('/stops/', body)
      setStopForm(null); say(stopForm.id ? 'Stop updated ✓' : 'Stop added ✓'); loadStops(stopsFor.id)
    } catch (ex) { setFormErr(errMsg(ex)) } finally { setBusy(false) }
  }

  const deleteStop = async (s) => {
    try { await api.delete(`/stops/${s.id}/`); say(`Stop "${s.name}" deleted`); loadStops(stopsFor.id) }
    catch (ex) { say(errMsg(ex)) }
  }

  return (
    <LoadingOrError loading={loading} err={err} reload={reload}>
      <div className="grid gap-5">
        <Card className="overflow-auto">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <SectionTitle>🗺 Routes ({routes?.length ?? 0})</SectionTitle>
            <Button onClick={() => { setFormErr(''); setRouteForm({ name: '', start_point: '', end_point: '', total_distance_km: '', polylineText: '', is_active: true }) }}>+ New route</Button>
          </div>
          {routes?.length === 0
            ? <EmptyState title="No routes yet" hint="Create a route, then add its stops in order so ETAs and journey planning work." />
            : <table className={tableCls}>
              <thead><tr><th className={thCls}>Name</th><th className={thCls}>From → To</th><th className={thCls}>Distance</th><th className={thCls}>Polyline pts</th><th className={thCls}>Active</th><th className={thCls}>Actions</th></tr></thead>
              <tbody>{routes.map(r => (
                <tr key={r.id} className={trCls}>
                  <td className={`${tdCls} font-bold`}>{r.name}</td>
                  <td className={tdCls}>{r.start_point} → {r.end_point}</td>
                  <td className={tdCls}>{r.total_distance_km} km</td>
                  <td className={tdCls}>{Array.isArray(r.polyline) ? r.polyline.length : 0}</td>
                  <td className={tdCls}><StatusBadge status={r.is_active === false ? 'inactive' : 'active'} /></td>
                  <td className={tdCls}><div className="flex gap-2 flex-wrap">
                    <Button variant="white" className="!px-3 !py-1.5 !text-xs" onClick={() => { setFormErr(''); setRouteForm({ id: r.id, name: r.name, start_point: r.start_point, end_point: r.end_point, total_distance_km: String(r.total_distance_km ?? ''), polylineText: (r.polyline || []).map(p => `${p[0]},${p[1]}`).join('\n'), is_active: r.is_active !== false }) }}>Edit</Button>
                    <Button variant="sun" className="!px-3 !py-1.5 !text-xs" onClick={() => openStops(r)}>Stops</Button>
                  </div></td>
                </tr>))}
              </tbody></table>}
        </Card>

        {stopsFor && (
          <Card className="overflow-auto">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
              <SectionTitle sub="Stops in travel order. Order + distance drive ETAs and next-stop logic.">🚏 Stops on {stopsFor.name} ({stops.length})</SectionTitle>
              <div className="flex gap-2">
                <Button onClick={() => { setFormErr(''); setStopForm({ name: '', order: String(stops.length + 1), distance_from_start_km: '', latitude: '', longitude: '' }) }}>+ Add stop</Button>
                <Button variant="white" onClick={() => setStopsFor(null)}>Close</Button>
              </div>
            </div>
            {stopsErr && <FormError message={stopsErr} />}
            {stops.length === 0 && !stopsErr
              ? <EmptyState title="No stops on this route yet" hint="Add stops in order, starting at order 1 (distance 0 km)." />
              : <table className={tableCls}>
                <thead><tr><th className={thCls}>#</th><th className={thCls}>Name</th><th className={thCls}>Distance from start</th><th className={thCls}>Coordinates</th><th className={thCls}>Actions</th></tr></thead>
                <tbody>{stops.map(s => (
                  <tr key={s.id} className={trCls}>
                    <td className={`${tdCls} font-bold`}>{s.order}</td>
                    <td className={`${tdCls} font-bold`}>{s.name}</td>
                    <td className={tdCls}>{s.distance_from_start_km} km</td>
                    <td className={tdCls}>{s.latitude}, {s.longitude}</td>
                    <td className={tdCls}><div className="flex gap-2 flex-wrap">
                      <Button variant="white" className="!px-3 !py-1.5 !text-xs" onClick={() => { setFormErr(''); setStopForm({ id: s.id, name: s.name, order: String(s.order), distance_from_start_km: String(s.distance_from_start_km ?? ''), latitude: String(s.latitude ?? ''), longitude: String(s.longitude ?? '') }) }}>Edit</Button>
                      <Button variant="danger" className="!px-3 !py-1.5 !text-xs" onClick={() => deleteStop(s)}>Delete</Button>
                    </div></td>
                  </tr>))}
                </tbody></table>}
          </Card>
        )}
      </div>

      {routeForm && (
        <Modal wide title={routeForm.id ? 'Edit route' : 'New route'} onClose={() => setRouteForm(null)}>
          <form onSubmit={saveRoute} className="grid gap-3">
            <div className="grid sm:grid-cols-2 gap-3">
              <Input label="Route name" required value={routeForm.name} onChange={e => setRouteForm({ ...routeForm, name: e.target.value })} placeholder="e.g. Route 1 — Campus to City Centre" />
              <Input label="Total distance (km)" type="number" step="0.1" min="0" required value={routeForm.total_distance_km} onChange={e => setRouteForm({ ...routeForm, total_distance_km: e.target.value })} />
              <Input label="Start point" required value={routeForm.start_point} onChange={e => setRouteForm({ ...routeForm, start_point: e.target.value })} />
              <Input label="End point" required value={routeForm.end_point} onChange={e => setRouteForm({ ...routeForm, end_point: e.target.value })} />
            </div>
            <Textarea label="Polyline — one lat,lng per line" rows={6} value={routeForm.polylineText} onChange={e => setRouteForm({ ...routeForm, polylineText: e.target.value })}
              placeholder={'31.2550,75.7050\n31.2490,75.7010\n31.2240,75.7700'} />
            <label className="flex items-center gap-2 text-sm font-bold">
              <input type="checkbox" checked={routeForm.is_active} onChange={e => setRouteForm({ ...routeForm, is_active: e.target.checked })} className="w-5 h-5 accent-[#B9E62E]" /> Route is active
            </label>
            <FormError message={formErr} />
            <Button type="submit" disabled={busy} className="w-full">{busy ? 'Saving…' : routeForm.id ? 'Save route' : 'Create route'}</Button>
          </form>
        </Modal>
      )}
      {stopForm && stopsFor && (
        <Modal title={stopForm.id ? 'Edit stop' : `Add stop to ${stopsFor.name}`} onClose={() => setStopForm(null)}>
          <form onSubmit={saveStop} className="grid gap-3">
            <Input label="Stop name" required value={stopForm.name} onChange={e => setStopForm({ ...stopForm, name: e.target.value })} />
            <div className="grid grid-cols-2 gap-3">
              <Input label="Order (1 = first)" type="number" min="1" required value={stopForm.order} onChange={e => setStopForm({ ...stopForm, order: e.target.value })} />
              <Input label="Distance from start (km)" type="number" step="0.01" min="0" required value={stopForm.distance_from_start_km} onChange={e => setStopForm({ ...stopForm, distance_from_start_km: e.target.value })} />
              <Input label="Latitude" type="number" step="0.000001" required value={stopForm.latitude} onChange={e => setStopForm({ ...stopForm, latitude: e.target.value })} placeholder="31.2550" />
              <Input label="Longitude" type="number" step="0.000001" required value={stopForm.longitude} onChange={e => setStopForm({ ...stopForm, longitude: e.target.value })} placeholder="75.7050" />
            </div>
            <FormError message={formErr} />
            <Button type="submit" disabled={busy} className="w-full">{busy ? 'Saving…' : stopForm.id ? 'Save stop' : 'Add stop'}</Button>
          </form>
        </Modal>
      )}
    </LoadingOrError>
  )
}

/* ---------------- Trips & schedules ---------------- */
const DAY_LABELS = [['1', 'Mon'], ['2', 'Tue'], ['3', 'Wed'], ['4', 'Thu'], ['5', 'Fri'], ['6', 'Sat'], ['7', 'Sun']]

function TripsSchedules({ say }) {
  const { data, err, loading, reload } = useLoad(async () => {
    const [t, s, r, v, d] = await Promise.allSettled([api.get('/trips/'), api.get('/schedules/'), api.get('/routes/'), api.get('/vehicles/'), api.get('/drivers/')])
    if (t.status === 'rejected') throw t.reason
    return {
      trips: listOf(t.value.data),
      schedules: s.status === 'fulfilled' ? listOf(s.value.data) : [],
      routes: r.status === 'fulfilled' ? listOf(r.value.data) : [],
      vehicles: v.status === 'fulfilled' ? listOf(v.value.data) : [],
      drivers: d.status === 'fulfilled' ? listOf(d.value.data) : [],
    }
  })
  const [tripForm, setTripForm] = useState(null)
  const [schedForm, setSchedForm] = useState(null)
  const [formErr, setFormErr] = useState('')
  const [busy, setBusy] = useState(false)

  const routeName = (id) => data?.routes.find(r => r.id === id)?.name || `Route ${id}`
  const vehicleReg = (id) => data?.vehicles.find(v => v.id === id)?.registration_number || `Vehicle ${id}`
  const driverLabel = (d) => d.user_email || d.email || d.full_name || d.user_name || `Driver #${d.id}`

  const saveTrip = async (e) => {
    e.preventDefault()
    if (!tripForm.route || !tripForm.vehicle || !tripForm.driver || !tripForm.scheduled_start) { setFormErr('Route, vehicle, driver and scheduled start are all required.'); return }
    setBusy(true); setFormErr('')
    try {
      await api.post('/trips/', { route: Number(tripForm.route), vehicle: Number(tripForm.vehicle), driver: Number(tripForm.driver), scheduled_start: new Date(tripForm.scheduled_start).toISOString() })
      setTripForm(null); say('Trip scheduled ✓'); reload()
    } catch (ex) { setFormErr(errMsg(ex)) } finally { setBusy(false) }
  }

  const saveSchedule = async (e) => {
    e.preventDefault()
    if (!schedForm.route || !schedForm.departure_time || schedForm.days.length === 0) { setFormErr('Pick a route, a departure time and at least one day.'); return }
    setBusy(true); setFormErr('')
    try {
      await api.post('/schedules/', { route: Number(schedForm.route), departure_time: schedForm.departure_time, days_of_week: schedForm.days.join(',') })
      setSchedForm(null); say('Schedule created ✓'); reload()
    } catch (ex) { setFormErr(errMsg(ex)) } finally { setBusy(false) }
  }

  const dayNames = (csv) => String(csv || '').split(',').map(x => DAY_LABELS.find(([v]) => v === x.trim())?.[1] || x).join(' · ')

  return (
    <LoadingOrError loading={loading} err={err} reload={reload}>
      <div className="grid gap-5">
        <Card className="overflow-auto">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <SectionTitle>🚌 Trips ({data?.trips.length ?? 0})</SectionTitle>
            <Button onClick={() => { setFormErr(''); setTripForm({ route: '', vehicle: '', driver: '', scheduled_start: '' }) }}>+ Schedule trip</Button>
          </div>
          {data?.trips.length === 0
            ? <EmptyState title="No trips yet" hint="Schedule a trip with a route, vehicle and driver — the driver sees it in their portal." />
            : <table className={tableCls}>
              <thead><tr><th className={thCls}>#</th><th className={thCls}>Route</th><th className={thCls}>Vehicle</th><th className={thCls}>Driver</th><th className={thCls}>Scheduled</th><th className={thCls}>Actual</th><th className={thCls}>Status</th></tr></thead>
              <tbody>{data.trips.map(t => (
                <tr key={t.id} className={trCls}>
                  <td className={`${tdCls} font-bold`}>{t.id}</td>
                  <td className={tdCls}>{t.route_name || routeName(t.route)}</td>
                  <td className={tdCls}>{t.vehicle_registration || vehicleReg(t.vehicle)}</td>
                  <td className={tdCls}>{t.driver_name || (t.driver ? `Driver #${t.driver}` : '—')}</td>
                  <td className={tdCls}>{fmtDateTime(t.scheduled_start)}</td>
                  <td className={tdCls}>{t.actual_start ? `${new Date(t.actual_start).toLocaleTimeString()}${t.actual_end ? ` → ${new Date(t.actual_end).toLocaleTimeString()}` : ''}` : '—'}</td>
                  <td className={tdCls}><StatusBadge status={t.status} /></td>
                </tr>))}
              </tbody></table>}
        </Card>

        <Card className="overflow-auto">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <SectionTitle sub="Recurring departure templates per route.">🕐 Schedules ({data?.schedules.length ?? 0})</SectionTitle>
            <Button variant="sun" onClick={() => { setFormErr(''); setSchedForm({ route: '', departure_time: '', days: ['1', '2', '3', '4', '5'] }) }}>+ New schedule</Button>
          </div>
          {data?.schedules.length === 0
            ? <EmptyState title="No schedules yet" hint="Create a recurring departure, e.g. Route 1 at 08:00 on weekdays." />
            : <table className={tableCls}>
              <thead><tr><th className={thCls}>Route</th><th className={thCls}>Departs</th><th className={thCls}>Days</th></tr></thead>
              <tbody>{data.schedules.map(s => (
                <tr key={s.id} className={trCls}>
                  <td className={`${tdCls} font-bold`}>{s.route_name || routeName(s.route)}</td>
                  <td className={tdCls}>{String(s.departure_time || '').slice(0, 5)}</td>
                  <td className={tdCls}>{dayNames(s.days_of_week)}</td>
                </tr>))}
              </tbody></table>}
        </Card>
      </div>

      {tripForm && (
        <Modal title="Schedule a trip" onClose={() => setTripForm(null)}>
          <form onSubmit={saveTrip} className="grid gap-3">
            <Select label="Route" required value={tripForm.route} onChange={e => setTripForm({ ...tripForm, route: e.target.value })}>
              <option value="">Choose route…</option>{(data?.routes || []).map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
            </Select>
            <Select label="Vehicle" required value={tripForm.vehicle} onChange={e => setTripForm({ ...tripForm, vehicle: e.target.value })}>
              <option value="">Choose vehicle…</option>{(data?.vehicles || []).map(v => <option key={v.id} value={v.id}>{v.registration_number} · {v.status}</option>)}
            </Select>
            <Select label="Driver" required value={tripForm.driver} onChange={e => setTripForm({ ...tripForm, driver: e.target.value })}>
              <option value="">Choose driver…</option>{(data?.drivers || []).map(d => <option key={d.id} value={d.id}>{driverLabel(d)}</option>)}
            </Select>
            {(data?.drivers || []).length === 0 && <p className="text-sm font-bold text-red-700">No drivers yet — add one in the Drivers tab first.</p>}
            <Input label="Scheduled start" type="datetime-local" required value={tripForm.scheduled_start} onChange={e => setTripForm({ ...tripForm, scheduled_start: e.target.value })} />
            <FormError message={formErr} />
            <Button type="submit" disabled={busy} className="w-full">{busy ? 'Scheduling…' : 'Schedule trip'}</Button>
          </form>
        </Modal>
      )}
      {schedForm && (
        <Modal title="New schedule" onClose={() => setSchedForm(null)}>
          <form onSubmit={saveSchedule} className="grid gap-3">
            <Select label="Route" required value={schedForm.route} onChange={e => setSchedForm({ ...schedForm, route: e.target.value })}>
              <option value="">Choose route…</option>{(data?.routes || []).map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
            </Select>
            <Input label="Departure time" type="time" required value={schedForm.departure_time} onChange={e => setSchedForm({ ...schedForm, departure_time: e.target.value })} />
            <div>
              <span className="block text-xs font-extrabold uppercase tracking-wider mb-1.5">Days of week</span>
              <div className="flex flex-wrap gap-2">
                {DAY_LABELS.map(([v, l]) => {
                  const on = schedForm.days.includes(v)
                  return <button key={v} type="button" onClick={() => setSchedForm({ ...schedForm, days: on ? schedForm.days.filter(x => x !== v) : [...schedForm.days, v] })}
                    className={`rounded-full border-2 border-ink px-3.5 py-1.5 text-sm font-extrabold ${on ? 'bg-lime-brand shadow-hardSm' : 'bg-white'}`}>{l}</button>
                })}
              </div>
            </div>
            <FormError message={formErr} />
            <Button type="submit" variant="sun" disabled={busy} className="w-full">{busy ? 'Creating…' : 'Create schedule'}</Button>
          </form>
        </Modal>
      )}
    </LoadingOrError>
  )
}

/* ---------------- Drivers ---------------- */
function Drivers({ say }) {
  const { data: drivers, err, loading, reload } = useLoad(async () => listOf((await api.get('/drivers/')).data))
  const [form, setForm] = useState(null)
  const [formErr, setFormErr] = useState('')
  const [busy, setBusy] = useState(false)

  const save = async (e) => {
    e.preventDefault()
    if (!form.email.trim() || !form.license_number.trim() || !form.phone.trim()) { setFormErr('User email, licence number and phone are all required.'); return }
    setBusy(true); setFormErr('')
    try {
      // Contract: POST /drivers/ links an existing user. Send the email under the
      // keys backends commonly accept; the server resolves it to the user account.
      await api.post('/drivers/', { user_email: form.email.trim(), email: form.email.trim(), license_number: form.license_number.trim(), phone: form.phone.trim() })
      setForm(null); say('Driver added ✓ — they can now sign in to the driver portal.'); reload()
    } catch (ex) { setFormErr(errMsg(ex)) } finally { setBusy(false) }
  }

  return (
    <LoadingOrError loading={loading} err={err} reload={reload}>
      <Card className="overflow-auto">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <SectionTitle sub="Drivers are existing user accounts linked by email — ask the driver to register first, then link them here.">🧑‍✈️ Drivers ({drivers?.length ?? 0})</SectionTitle>
          <Button onClick={() => { setFormErr(''); setForm({ email: '', license_number: '', phone: '' }) }}>+ Add driver</Button>
        </div>
        {drivers?.length === 0
          ? <EmptyState title="No drivers yet" hint="Link a registered user by email to give them the driver portal." />
          : <table className={tableCls}>
            <thead><tr><th className={thCls}>Driver</th><th className={thCls}>Licence</th><th className={thCls}>Phone</th><th className={thCls}>Status</th></tr></thead>
            <tbody>{drivers.map(d => (
              <tr key={d.id} className={trCls}>
                <td className={`${tdCls} font-bold`}>{d.full_name || d.user_name || d.user_email || d.email || `User #${d.user}`}</td>
                <td className={tdCls}>{d.license_number || '—'}</td>
                <td className={tdCls}>{d.phone || '—'}</td>
                <td className={tdCls}><StatusBadge status={d.status || 'active'} /></td>
              </tr>))}
            </tbody></table>}
      </Card>
      {form && (
        <Modal title="Add driver" onClose={() => setForm(null)}>
          <form onSubmit={save} className="grid gap-3">
            <Input label="Driver's account email" type="email" required value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} placeholder="driver@example.com" />
            <Input label="Licence number" required value={form.license_number} onChange={e => setForm({ ...form, license_number: e.target.value })} />
            <Input label="Phone" required value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} autoComplete="tel" />
            <FormError message={formErr} />
            <Button type="submit" disabled={busy} className="w-full">{busy ? 'Adding…' : 'Add driver'}</Button>
          </form>
        </Modal>
      )}
    </LoadingOrError>
  )
}

/* ---------------- Pass applications ---------------- */
function PassApplications({ say }) {
  const { data: apps, err, loading, reload } = useLoad(async () => listOf((await api.get('/passes/applications/')).data))
  const [busyId, setBusyId] = useState(null)

  const decide = async (app, action) => {
    setBusyId(app.id)
    try {
      await api.post(`/passes/applications/${app.id}/${action}/`, {})
      say(action === 'approve' ? `Application #${app.id} approved ✓ — pass + QR issued.` : `Application #${app.id} rejected.`)
      reload()
    } catch (e) { say(errMsg(e)) } finally { setBusyId(null) }
  }

  const pending = (apps || []).filter(a => (a.status || 'pending') === 'pending')
  const decided = (apps || []).filter(a => (a.status || 'pending') !== 'pending')

  const row = (a) => (
    <div key={a.id} className="border-[2.5px] border-ink rounded-2xl bg-cream/60 p-4 grid gap-2">
      <div className="flex flex-wrap items-center gap-2 justify-between">
        <p className="font-display font-black">{a.applicant_name || a.user_name || a.applicant_email || a.email || `Applicant #${a.user ?? a.id}`}</p>
        <StatusBadge status={a.status || 'pending'} />
      </div>
      <p className="text-xs font-bold text-ink/60">Application #{a.id} · {fmtDateTime(a.created_at)}</p>
      {a.reason && <p className="text-sm font-medium text-ink/80">“{a.reason}”</p>}
      {(a.status || 'pending') === 'pending' && (
        <div className="flex flex-wrap gap-2 mt-1">
          <Button onClick={() => decide(a, 'approve')} disabled={busyId === a.id}>{busyId === a.id ? 'Working…' : '✓ Approve & issue pass'}</Button>
          <Button variant="danger" onClick={() => decide(a, 'reject')} disabled={busyId === a.id}>✕ Reject</Button>
        </div>
      )}
    </div>
  )

  return (
    <LoadingOrError loading={loading} err={err} reload={reload}>
      <div className="grid gap-5">
        <Card>
          <SectionTitle sub="Approving issues a transport pass with a QR token the commuter sees instantly.">🎫 Pending applications ({pending.length})</SectionTitle>
          {pending.length === 0 ? <EmptyState title="Inbox zero" hint="New pass applications from commuters land here for review." /> : <div className="grid gap-3">{pending.map(row)}</div>}
        </Card>
        {decided.length > 0 && (
          <Card>
            <SectionTitle>Decided ({decided.length})</SectionTitle>
            <div className="grid gap-3">{decided.map(row)}</div>
          </Card>
        )}
      </div>
    </LoadingOrError>
  )
}

/* ---------------- Complaints + feedback ---------------- */
function ComplaintsInbox({ say }) {
  const { data, err, loading, reload } = useLoad(async () => {
    const [c, f] = await Promise.allSettled([api.get('/complaints/'), api.get('/feedback/')])
    if (c.status === 'rejected') throw c.reason
    return { complaints: listOf(c.value.data), feedback: f.status === 'fulfilled' ? listOf(f.value.data) : null, fbErr: f.status === 'rejected' ? errMsg(f.reason) : '' }
  })
  const [edit, setEdit] = useState(null) // {id, status, resolution_note}
  const [formErr, setFormErr] = useState('')
  const [busy, setBusy] = useState(false)

  const save = async (e) => {
    e.preventDefault()
    setBusy(true); setFormErr('')
    try {
      await api.patch(`/complaints/${edit.id}/`, { status: edit.status, resolution_note: edit.resolution_note.trim() })
      setEdit(null); say('Complaint updated ✓'); reload()
    } catch (ex) { setFormErr(errMsg(ex)) } finally { setBusy(false) }
  }

  return (
    <LoadingOrError loading={loading} err={err} reload={reload}>
      <div className="grid gap-5">
        <Card>
          <SectionTitle sub="Update status and leave a resolution note — the commuter sees both.">📨 Complaints inbox ({data?.complaints.length ?? 0})</SectionTitle>
          {data?.complaints.length === 0
            ? <EmptyState title="No complaints" hint="Commuter complaints (including lost & found) appear here." />
            : <div className="grid gap-3">{data.complaints.map(c => (
              <div key={c.id} className="border-[2.5px] border-ink rounded-2xl bg-cream/60 p-4 grid gap-1.5">
                <div className="flex flex-wrap items-center gap-2 justify-between">
                  <p className="font-display font-black">{c.subject || `Complaint #${c.id}`}</p>
                  <div className="flex gap-2 items-center">
                    <Badge tone="white">{String(c.category || 'other').replace(/_/g, ' ')}</Badge>
                    <StatusBadge status={c.status || 'open'} />
                  </div>
                </div>
                <p className="text-xs font-bold text-ink/60">{c.reporter_name || c.user_name || c.reporter_email || ''} · {fmtDateTime(c.created_at)}</p>
                {c.description && <p className="text-sm font-medium text-ink/80">{c.description}</p>}
                {(c.resolution_note || c.resolution) && <p className="text-sm font-semibold bg-white border-2 border-ink rounded-lg px-2.5 py-1.5">Resolution: {c.resolution_note || c.resolution}</p>}
                <div><Button variant="white" className="!px-3 !py-1.5 !text-xs" onClick={() => { setFormErr(''); setEdit({ id: c.id, status: c.status || 'open', resolution_note: c.resolution_note || c.resolution || '' }) }}>Update status</Button></div>
              </div>))}
            </div>}
        </Card>

        <Card>
          <SectionTitle sub="Star ratings and comments from riders.">⭐ Rider feedback ({data?.feedback?.length ?? 0})</SectionTitle>
          {data?.fbErr && <FormError message={data.fbErr} />}
          {data?.feedback && data.feedback.length === 0 && <EmptyState title="No feedback yet" hint="Ratings from the commuter app appear here." />}
          {data?.feedback && data.feedback.length > 0 && (
            <div className="grid gap-2">{data.feedback.map(f => (
              <div key={f.id} className="flex flex-wrap items-center gap-3 border-2 border-ink rounded-xl bg-white px-3 py-2.5">
                <StarRating value={Number(f.rating) || 0} size="text-lg" />
                <span className="text-sm font-medium flex-1 min-w-[180px]">{f.comment || '(no comment)'}</span>
                <span className="text-xs font-bold text-ink/60">{f.vehicle_registration || (f.vehicle ? `Vehicle #${f.vehicle}` : 'General')} · {fmtDateTime(f.created_at)}</span>
              </div>))}
            </div>
          )}
        </Card>
      </div>

      {edit && (
        <Modal title={`Complaint #${edit.id}`} onClose={() => setEdit(null)}>
          <form onSubmit={save} className="grid gap-3">
            <Select label="Status" value={edit.status} onChange={e => setEdit({ ...edit, status: e.target.value })}>
              <option value="open">Open</option><option value="in_progress">In progress</option><option value="resolved">Resolved</option>
            </Select>
            <Textarea label="Resolution note (shown to the commuter)" rows={3} value={edit.resolution_note} onChange={e => setEdit({ ...edit, resolution_note: e.target.value })}
              placeholder="e.g. Found your umbrella — collect it from the transport office with your ID." />
            <FormError message={formErr} />
            <Button type="submit" disabled={busy} className="w-full">{busy ? 'Saving…' : 'Save update'}</Button>
          </form>
        </Modal>
      )}
    </LoadingOrError>
  )
}

/* ---------------- Incidents ---------------- */
function IncidentsList({ say }) {
  const { data: incidents, err, loading, reload } = useLoad(async () => listOf((await api.get('/incidents/')).data))
  return (
    <LoadingOrError loading={loading} err={err} reload={reload}>
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <SectionTitle sub="Breakdowns, safety reports and other incidents from drivers and commuters.">🚨 Incidents ({incidents?.length ?? 0})</SectionTitle>
          <Button variant="white" onClick={() => { reload(); say('Incidents refreshed') }}>↻ Refresh</Button>
        </div>
        {incidents?.length === 0
          ? <EmptyState title="No incidents reported" hint="Driver breakdowns and commuter incident reports land here." />
          : <div className="grid gap-3">{incidents.map(i => (
            <div key={i.id} className="border-[2.5px] border-ink rounded-2xl bg-blush/10 p-4 grid gap-1.5">
              <div className="flex flex-wrap items-center gap-2 justify-between">
                <p className="font-display font-black capitalize">{String(i.type || 'incident').replace(/_/g, ' ')}</p>
                <StatusBadge status={i.status || 'open'} />
              </div>
              <p className="text-xs font-bold text-ink/60">
                {i.vehicle_registration || (i.vehicle ? `Vehicle #${i.vehicle}` : 'No vehicle')} · reported by {i.reporter_name || i.user_name || i.reporter_email || '—'} · {fmtDateTime(i.created_at)}
              </p>
              {i.description && <p className="text-sm font-medium text-ink/80">{i.description}</p>}
            </div>))}
          </div>}
      </Card>
    </LoadingOrError>
  )
}

/* ---------------- Subscription ---------------- */
function Subscription({ say }) {
  const { data, err, loading, reload } = useLoad(async () => {
    const [sub, plans] = await Promise.allSettled([api.get('/subscription/'), api.get('/plans/')])
    if (plans.status === 'rejected' && sub.status === 'rejected') throw plans.reason
    // Invoices: the contract defines no invoices endpoint. Try the obvious
    // candidates once and only show the section if the server actually has one.
    let invoices = null
    for (const path of ['/subscription/invoices/', '/invoices/']) {
      try { const r = await api.get(path); invoices = listOf(r.data); break } catch { /* not available */ }
    }
    return {
      sub: sub.status === 'fulfilled' ? sub.value.data : null,
      subErr: sub.status === 'rejected' ? errMsg(sub.reason) : '',
      plans: plans.status === 'fulfilled' ? listOf(plans.value.data) : [],
      invoices,
    }
  })
  const [busyId, setBusyId] = useState(null)

  const upgrade = async (plan) => {
    setBusyId(plan.id)
    try {
      await api.post('/subscription/upgrade/', { plan_id: plan.id })
      say(`Switched to ${plan.name} ✓ — a pending invoice was created (no real payment is taken).`)
      reload()
    } catch (e) { say(errMsg(e)) } finally { setBusyId(null) }
  }

  const currentPlanId = data?.sub?.plan_id ?? data?.sub?.plan?.id ?? data?.sub?.plan
  const currentPlan = (data?.plans || []).find(p => p.id === currentPlanId) || data?.sub?.plan || null

  return (
    <LoadingOrError loading={loading} err={err} reload={reload}>
      <div className="grid gap-5">
        <Card>
          <SectionTitle>💳 Current subscription</SectionTitle>
          {data?.subErr && <FormError message={data.subErr} />}
          {data?.sub && (
            <div className="grid sm:grid-cols-3 gap-3">
              <StatCard label="Plan" value={currentPlan?.name || data.sub.plan_name || '—'} tone="lime" />
              <StatCard label="Vehicle limit" value={currentPlan?.max_vehicles ?? data.sub.max_vehicles ?? '—'} sub="vehicles allowed on this plan" tone="sun" />
              <StatCard label="Status" value={data.sub.status || 'active'} sub={data.sub.current_period_end || data.sub.expires_at ? `until ${fmtDate(data.sub.current_period_end || data.sub.expires_at)}` : ''} tone="royal" />
            </div>
          )}
          {!data?.sub && !data?.subErr && <EmptyState title="No subscription record" hint="Pick a plan below to get started." />}
        </Card>

        <div>
          <SectionTitle sub="Upgrading switches your plan immediately and creates a pending invoice — no real payment is processed in this demo.">Plans</SectionTitle>
          <div className="grid md:grid-cols-3 gap-4">
            {(data?.plans || []).map(p => {
              const isCurrent = p.id === currentPlanId
              return (
                <Card key={p.id} className={isCurrent ? '!bg-lime-brand/30' : ''}>
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-display font-black text-xl">{p.name}</p>
                    {isCurrent && <Badge tone="lime">Current</Badge>}
                  </div>
                  <p className="font-display font-black text-3xl mt-2">₹{Number(p.price_monthly).toLocaleString('en-IN')}<span className="text-sm font-bold text-ink/60">/mo</span></p>
                  <p className="text-sm font-bold mt-1">Up to {Number(p.max_vehicles) >= 1000 ? 'unlimited' : p.max_vehicles} vehicles</p>
                  {p.features && <p className="text-sm font-medium text-ink/75 mt-2 whitespace-pre-line">{Array.isArray(p.features) ? p.features.join('\n• ') : String(p.features)}</p>}
                  <Button className="w-full mt-4" variant={isCurrent ? 'white' : 'primary'} disabled={isCurrent || busyId === p.id} onClick={() => upgrade(p)}>
                    {isCurrent ? 'Current plan' : busyId === p.id ? 'Switching…' : `Switch to ${p.name}`}
                  </Button>
                </Card>
              )
            })}
          </div>
          {(data?.plans || []).length === 0 && <EmptyState title="No plans available" hint="Plans are configured by the platform team." />}
        </div>

        {data?.invoices && (
          <Card className="overflow-auto">
            <SectionTitle>🧾 Invoices ({data.invoices.length})</SectionTitle>
            {data.invoices.length === 0
              ? <EmptyState title="No invoices yet" hint="Invoices appear here after a plan switch." />
              : <table className={tableCls}>
                <thead><tr><th className={thCls}>#</th><th className={thCls}>Plan</th><th className={thCls}>Amount</th><th className={thCls}>Status</th><th className={thCls}>Issued</th></tr></thead>
                <tbody>{data.invoices.map(inv => (
                  <tr key={inv.id} className={trCls}>
                    <td className={`${tdCls} font-bold`}>{inv.id}</td>
                    <td className={tdCls}>{inv.plan_name || inv.plan || '—'}</td>
                    <td className={tdCls}>{inv.amount != null ? `₹${Number(inv.amount).toLocaleString('en-IN')}` : '—'}</td>
                    <td className={tdCls}><StatusBadge status={inv.status || 'pending'} /></td>
                    <td className={tdCls}>{fmtDateTime(inv.created_at)}</td>
                  </tr>))}
                </tbody></table>}
          </Card>
        )}
      </div>
    </LoadingOrError>
  )
}

/* ---------------- Organisations (platform admin) ---------------- */
function Organisations({ say }) {
  const { data: orgs, err, loading, reload } = useLoad(async () => listOf((await api.get('/organisations/')).data))
  return (
    <LoadingOrError loading={loading} err={err} reload={reload}>
      <Card className="overflow-auto">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <SectionTitle sub="Platform-admin view across every organisation on SmartCommute 2.0.">🏢 Organisations ({orgs?.length ?? 0})</SectionTitle>
          <Button variant="white" onClick={() => { reload(); say('Organisations refreshed') }}>↻ Refresh</Button>
        </div>
        {orgs?.length === 0
          ? <EmptyState title="No organisations" hint="Organisations register via the public sign-up page." />
          : <table className={tableCls}>
            <thead><tr><th className={thCls}>Name</th><th className={thCls}>Type</th><th className={thCls}>City</th><th className={thCls}>Email</th><th className={thCls}>Phone</th></tr></thead>
            <tbody>{orgs.map(o => (
              <tr key={o.id} className={trCls}>
                <td className={`${tdCls} font-bold`}>{o.name}</td>
                <td className={tdCls}>{o.type || '—'}</td>
                <td className={tdCls}>{o.city || '—'}</td>
                <td className={tdCls}>{o.email || '—'}</td>
                <td className={tdCls}>{o.phone || '—'}</td>
              </tr>))}
            </tbody></table>}
      </Card>
    </LoadingOrError>
  )
}
