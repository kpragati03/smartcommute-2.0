import { useCallback, useEffect, useState } from 'react'
import api, { errMsg, listOf } from '../services/api'
import { Button, Card, EmptyState, FormError, Input, SectionTitle, Select, StarRating, StatusBadge, Textarea, fmtDateTime } from './ui'

const COMPLAINT_CATEGORIES = [
  ['missed_bus', 'Missed bus'],
  ['wrong_eta', 'Wrong ETA'],
  ['route_issue', 'Route issue'],
  ['lost_found', 'Lost & found'],
  ['other', 'Other'],
]
const INCIDENT_TYPES = [
  ['breakdown', 'Breakdown'],
  ['accident', 'Accident'],
  ['delay', 'Major delay'],
  ['safety', 'Safety concern'],
  ['other', 'Other'],
]

// Commuter support: complaints (POST/GET /complaints/), feedback (POST /feedback/),
// incident reports (POST /incidents/). `vehicles` feeds the vehicle selects.
export default function SupportSection({ vehicles = [], say }) {
  const [tab, setTab] = useState('complaint')
  const [complaints, setComplaints] = useState([])
  const [cErr, setCErr] = useState('')
  const [busy, setBusy] = useState(false)

  const [cf, setCf] = useState({ category: 'missed_bus', subject: '', description: '' })
  const [ff, setFf] = useState({ vehicle: '', rating: 5, comment: '' })
  const [inf, setInf] = useState({ type: 'breakdown', vehicle: '', description: '' })
  const [fErr, setFErr] = useState(''); const [iErr, setIErr] = useState('')

  const loadComplaints = useCallback(async () => {
    try { const r = await api.get('/complaints/'); setComplaints(listOf(r.data)); setCErr('') }
    catch (e) { setCErr(errMsg(e)) }
  }, [])
  useEffect(() => { loadComplaints() }, [loadComplaints])

  const submitComplaint = async (e) => {
    e.preventDefault()
    if (!cf.subject.trim() || !cf.description.trim()) { setCErr('Subject and description are both required.'); return }
    setBusy(true); setCErr('')
    try {
      await api.post('/complaints/', { category: cf.category, subject: cf.subject.trim(), description: cf.description.trim() })
      setCf({ category: 'missed_bus', subject: '', description: '' })
      say('Complaint filed ✓ — track its status below.')
      loadComplaints()
    } catch (ex) { setCErr(errMsg(ex)) } finally { setBusy(false) }
  }

  const submitFeedback = async (e) => {
    e.preventDefault()
    if (!ff.rating) { setFErr('Pick a star rating.'); return }
    setBusy(true); setFErr('')
    try {
      await api.post('/feedback/', { vehicle: ff.vehicle ? Number(ff.vehicle) : undefined, rating: ff.rating, comment: ff.comment.trim() })
      setFf({ vehicle: '', rating: 5, comment: '' })
      say('Thanks — feedback sent ✓')
    } catch (ex) { setFErr(errMsg(ex)) } finally { setBusy(false) }
  }

  const submitIncident = async (e) => {
    e.preventDefault()
    if (!inf.description.trim()) { setIErr('Describe what happened.'); return }
    setBusy(true); setIErr('')
    try {
      await api.post('/incidents/', { type: inf.type, vehicle: inf.vehicle ? Number(inf.vehicle) : undefined, description: inf.description.trim() })
      setInf({ type: 'breakdown', vehicle: '', description: '' })
      say('Incident reported ✓ — the transport team has been notified.')
    } catch (ex) { setIErr(errMsg(ex)) } finally { setBusy(false) }
  }

  const tabBtn = (id, label) => (
    <button key={id} onClick={() => setTab(id)}
      className={`rounded-full border-2 border-ink px-4 py-2 text-sm font-extrabold ${tab === id ? 'bg-sun shadow-hardSm' : 'bg-white hover:bg-cream'}`}>{label}</button>
  )
  const vehicleOptions = vehicles.map(v => (
    <option key={v.id} value={v.id}>{v.registration_number}{v.route_name ? ` · ${v.route_name}` : ''}</option>
  ))

  return (
    <Card>
      <SectionTitle sub="File a complaint, rate a ride, or report an incident. Everything goes straight to your organisation’s transport team.">🛟 Support & feedback</SectionTitle>
      <div className="flex flex-wrap gap-2 mb-4">
        {tabBtn('complaint', '📨 Complaint')}
        {tabBtn('feedback', '⭐ Rate a ride')}
        {tabBtn('incident', '🚨 Report incident')}
      </div>

      {tab === 'complaint' && (
        <div className="grid gap-4">
          <form onSubmit={submitComplaint} className="grid gap-3">
            <div className="grid sm:grid-cols-2 gap-3">
              <Select label="Category" value={cf.category} onChange={e => setCf({ ...cf, category: e.target.value })}>
                {COMPLAINT_CATEGORIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </Select>
              <Input label="Subject" required value={cf.subject} onChange={e => setCf({ ...cf, subject: e.target.value })} placeholder="e.g. 8:10 bus from Law Gate never arrived" />
            </div>
            <Textarea label="What happened?" required rows={3} value={cf.description} onChange={e => setCf({ ...cf, description: e.target.value })}
              placeholder="Date, time, stop, route — anything that helps the team investigate." />
            <FormError message={cErr} />
            <Button type="submit" disabled={busy} className="justify-self-start">{busy ? 'Filing…' : 'File complaint →'}</Button>
          </form>
          <div>
            <p className="text-xs font-extrabold uppercase tracking-wider mb-2">My complaints</p>
            {complaints.length === 0
              ? <EmptyState title="No complaints filed" hint="When you file one, its status (open → in progress → resolved) shows here." />
              : <div className="grid gap-2">{complaints.map(c => (
                <div key={c.id} className="border-2 border-ink rounded-xl bg-cream/60 px-3 py-2.5">
                  <div className="flex flex-wrap items-center gap-2 justify-between">
                    <span className="text-sm font-extrabold">{c.subject || `Complaint #${c.id}`}</span>
                    <StatusBadge status={c.status || 'open'} />
                  </div>
                  <p className="text-xs font-bold text-ink/60 mt-1">{String(c.category || '').replace(/_/g, ' ')} · {fmtDateTime(c.created_at)}</p>
                  {c.description && <p className="text-sm font-medium text-ink/75 mt-1">{c.description}</p>}
                  {(c.resolution_note || c.resolution) && <p className="text-sm font-semibold mt-1.5 bg-white border-2 border-ink rounded-lg px-2.5 py-1.5">Team reply: {c.resolution_note || c.resolution}</p>}
                </div>))}
              </div>}
          </div>
        </div>
      )}

      {tab === 'feedback' && (
        <form onSubmit={submitFeedback} className="grid gap-3">
          <Select label="Vehicle (optional)" value={ff.vehicle} onChange={e => setFf({ ...ff, vehicle: e.target.value })}>
            <option value="">General feedback — no specific vehicle</option>{vehicleOptions}
          </Select>
          <div>
            <span className="block text-xs font-extrabold uppercase tracking-wider mb-1.5">Your rating</span>
            <StarRating value={ff.rating} onChange={(n) => setFf({ ...ff, rating: n })} />
          </div>
          <Textarea label="Comment" rows={3} value={ff.comment} onChange={e => setFf({ ...ff, comment: e.target.value })} placeholder="How was the ride? Cleanliness, driving, punctuality…" />
          <FormError message={fErr} />
          <Button type="submit" disabled={busy} className="justify-self-start">{busy ? 'Sending…' : 'Send feedback →'}</Button>
        </form>
      )}

      {tab === 'incident' && (
        <form onSubmit={submitIncident} className="grid gap-3">
          <div className="grid sm:grid-cols-2 gap-3">
            <Select label="Incident type" value={inf.type} onChange={e => setInf({ ...inf, type: e.target.value })}>
              {INCIDENT_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </Select>
            <Select label="Vehicle (optional)" value={inf.vehicle} onChange={e => setInf({ ...inf, vehicle: e.target.value })}>
              <option value="">Not vehicle-specific</option>{vehicleOptions}
            </Select>
          </div>
          <Textarea label="What happened?" required rows={3} value={inf.description} onChange={e => setInf({ ...inf, description: e.target.value })}
            placeholder="Where, when, and what you saw. For emergencies call local emergency services first." />
          <FormError message={iErr} />
          <Button type="submit" variant="danger" disabled={busy} className="justify-self-start">{busy ? 'Reporting…' : 'Report incident →'}</Button>
        </form>
      )}
    </Card>
  )
}
