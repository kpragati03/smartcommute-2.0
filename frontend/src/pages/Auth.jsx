import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api, { errMsg } from '../services/api'
import { useAuth } from '../context/AuthContext'
import { Button, Card, Input, Select, Badge } from '../components/ui'
function Shell({ title, sub, children }) {
  return <main className="max-w-md mx-auto px-4 py-10">
    <Card><h1 className="font-display font-black text-3xl">{title}</h1><p className="text-sm font-semibold text-ink/70 mt-1 mb-5">{sub}</p>{children}</Card>
  </main>
}
export function Login() {
  const [email, setEmail] = useState(''); const [password, setPassword] = useState('')
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false)
  const { login, homeFor } = useAuth(); const nav = useNavigate()
  const submit = async (e) => { e.preventDefault(); setBusy(true); setErr('')
    try { const u = await login(email, password); nav(homeFor(u)) }
    catch (ex) { setErr(errMsg(ex)) } finally { setBusy(false) } }
  return <Shell title="Welcome back" sub="Sign in — we’ll route you to your console (commuter, driver or admin).">
    <form onSubmit={submit} className="grid gap-3">
      <Input label="Email" type="email" required value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" autoComplete="email" />
      <Input label="Password" type="password" required value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" />
      {err && <p className="text-sm font-bold text-red-700 bg-red-50 border-2 border-ink rounded-xl px-3 py-2">{err}</p>}
      <Button type="submit" disabled={busy} className="w-full">{busy ? 'Signing in…' : 'Sign in →'}</Button>
    </form>
    <p className="text-sm font-semibold mt-4">New commuter? <Link className="underline font-extrabold" to="/register">Create an account</Link><br />Running a fleet? <Link className="underline font-extrabold" to="/register-organisation">Register your organisation</Link></p>
    <div className="mt-4 bg-cream border-2 border-dashed border-ink rounded-xl p-3 text-xs font-semibold">
      <Badge tone="sun">Demo logins (local dev only)</Badge>
      <p className="mt-2">student1@lpu.demo / Student@12345<br />driver1@lpu.demo / Driver@12345<br />transport@lpu.demo / Admin@12345 (org admin)</p>
    </div>
  </Shell>
}
export function Register() {
  const [f, setF] = useState({ full_name: '', email: '', phone: '', password: '' })
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false)
  const nav = useNavigate(); const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const submit = async (e) => { e.preventDefault(); setBusy(true); setErr('')
    try { await api.post('/auth/register/', { email: f.email, password: f.password, full_name: f.full_name, phone: f.phone || undefined }); nav('/login') }
    catch (ex) { setErr(errMsg(ex)) } finally { setBusy(false) } }
  return <Shell title="Create your account" sub="For commuters — students, staff and riders.">
    <form onSubmit={submit} className="grid gap-3">
      <Input label="Full name" required value={f.full_name} onChange={set('full_name')} autoComplete="name" />
      <Input label="Email" type="email" required value={f.email} onChange={set('email')} autoComplete="email" />
      <Input label="Phone (optional)" value={f.phone} onChange={set('phone')} autoComplete="tel" />
      <Input label="Password" type="password" required value={f.password} onChange={set('password')} autoComplete="new-password" />
      {err && <p className="text-sm font-bold text-red-700 bg-red-50 border-2 border-ink rounded-xl px-3 py-2">{err}</p>}
      <Button type="submit" disabled={busy} className="w-full">{busy ? 'Creating…' : 'Create account →'}</Button>
    </form>
    <p className="text-sm font-semibold mt-4">Already have an account? <Link className="underline font-extrabold" to="/login">Sign in</Link></p>
  </Shell>
}
export function RegisterOrganisation() {
  const [f, setF] = useState({ name: '', type: 'university', city: '', email: '', phone: '', admin_name: '', admin_email: '', admin_password: '' })
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false); const [done, setDone] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const submit = async (e) => { e.preventDefault(); setBusy(true); setErr('')
    try { await api.post('/organisations/register/', f); setDone(true) }
    catch (ex) { setErr(errMsg(ex)) } finally { setBusy(false) } }
  if (done) return <Shell title="Organisation created 🎉" sub="Your admin account is ready. Sign in to add routes, vehicles and devices.">
    <Link to="/login" className="inline-block rounded-full border-[2.5px] border-ink bg-lime-brand px-6 py-3 font-extrabold shadow-hardSm">Sign in as admin →</Link></Shell>
  return <main className="max-w-2xl mx-auto px-4 py-10"><Card>
    <Badge tone="royal">For organisations</Badge>
    <h1 className="font-display font-black text-3xl mt-3">Register your organisation</h1>
    <p className="text-sm font-semibold text-ink/70 mt-1 mb-5">Creates your organisation plus its first admin account. You can add routes and vehicles right after signing in.</p>
    <form onSubmit={submit} className="grid md:grid-cols-2 gap-3">
      <Input label="Organisation name" required value={f.name} onChange={set('name')} placeholder="e.g. Green Valley University" />
      <Select label="Type" value={f.type} onChange={set('type')}>
        <option value="university">University / Campus</option><option value="school">School</option>
        <option value="company">Company shuttle</option><option value="city">City transit</option><option value="other">Other</option>
      </Select>
      <Input label="City" required value={f.city} onChange={set('city')} />
      <Input label="Organisation email" type="email" required value={f.email} onChange={set('email')} />
      <Input label="Phone" required value={f.phone} onChange={set('phone')} />
      <span className="hidden md:block" />
      <Input label="Admin full name" required value={f.admin_name} onChange={set('admin_name')} />
      <Input label="Admin email" type="email" required value={f.admin_email} onChange={set('admin_email')} />
      <Input label="Admin password" type="password" required value={f.admin_password} onChange={set('admin_password')} autoComplete="new-password" />
      <span className="hidden md:block" />
      {err && <p className="md:col-span-2 text-sm font-bold text-red-700 bg-red-50 border-2 border-ink rounded-xl px-3 py-2">{err}</p>}
      <Button type="submit" disabled={busy} className="md:col-span-2 w-full">{busy ? 'Registering…' : 'Register organisation →'}</Button>
    </form>
  </Card></main>
}
