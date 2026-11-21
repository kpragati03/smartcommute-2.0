import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import NotificationsBell from './NotificationsBell'
export default function Navbar() {
  const { user, logout, isOrgAdmin, isDriver } = useAuth()
  const nav = useNavigate()
  const link = ({ isActive }) => `rounded-full border-2 border-ink px-3.5 py-1.5 text-sm font-extrabold ${isActive ? 'bg-lime-brand shadow-hardSm' : 'bg-white hover:bg-sun'}`
  return (
    <header className="sticky top-0 z-50 bg-cream/95 backdrop-blur border-b-[2.5px] border-ink">
      <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center gap-3">
        <Link to="/" className="flex items-center gap-2">
          <span className="w-9 h-9 grid place-items-center rounded-xl bg-lime-brand border-[2.5px] border-ink shadow-hardSm font-display font-black text-lg">S</span>
          <span className="font-display font-black text-lg leading-none">SmartCommute <span className="bg-ink text-white rounded-md px-1.5 py-0.5 text-xs align-middle">2.0</span></span>
        </Link>
        <nav className="flex flex-wrap items-center gap-2 ml-auto">
          <NavLink to="/" className={link}>Home</NavLink>
          {user && <NavLink to="/app" className={link}>Commuter</NavLink>}
          {user && isDriver && <NavLink to="/driver" className={link}>Driver</NavLink>}
          {user && isOrgAdmin && <NavLink to="/admin" className={link}>Admin</NavLink>}
          {!user && <>
            <NavLink to="/login" className={link}>Login</NavLink>
            <NavLink to="/register" className={link}>Register</NavLink>
            <NavLink to="/register-organisation" className={link}>For Organisations</NavLink>
          </>}
          {user && <>
            <NotificationsBell />
            <span className="hidden md:inline text-sm font-bold bg-sun border-2 border-ink rounded-full px-3 py-1.5">{user.full_name || user.email}</span>
            <button onClick={() => { logout(); nav('/') }} className="rounded-full border-2 border-ink bg-ink text-white px-3.5 py-1.5 text-sm font-extrabold shadow-hardSm hover:shadow-none">Logout</button>
          </>}
        </nav>
      </div>
    </header>
  )
}
export function Footer() {
  return <footer className="border-t-[2.5px] border-ink bg-ink text-white mt-14">
    <div className="max-w-7xl mx-auto px-4 py-8 flex flex-wrap gap-4 items-center justify-between">
      <div><p className="font-display font-black text-lg">SmartCommute 2.0</p><p className="text-sm text-white/70">Live transport intelligence — demo data is labelled DEMO. Maps © OpenStreetMap contributors.</p></div>
      <div className="flex gap-2 flex-wrap">
        <Link to="/register-organisation" className="rounded-full border-2 border-white px-4 py-2 text-sm font-extrabold hover:bg-lime-brand hover:text-ink hover:border-ink">Register your organisation</Link>
        <Link to="/login" className="rounded-full border-2 border-white px-4 py-2 text-sm font-extrabold hover:bg-sun hover:text-ink hover:border-ink">Sign in</Link>
      </div>
    </div>
  </footer>
}
export function ProtectedRoute({ children, require }) {
  const { user, loading, isOrgAdmin, isDriver } = useAuth()
  if (loading) return <div className="max-w-7xl mx-auto px-4 py-16 text-center font-display font-black text-xl">Loading…</div>
  if (!user) return <div className="max-w-xl mx-auto px-4 py-16 text-center">
    <p className="font-display font-black text-2xl mb-3">Please sign in</p>
    <Link to="/login" className="inline-block rounded-full border-[2.5px] border-ink bg-lime-brand px-6 py-3 font-extrabold shadow-hardSm">Go to login</Link>
  </div>
  if (require === 'admin' && !isOrgAdmin) return <Denied msg="This area is for organisation admins." />
  if (require === 'driver' && !isDriver && !isOrgAdmin) return <Denied msg="This area is for drivers." />
  return children
}
function Denied({ msg }) {
  return <div className="max-w-xl mx-auto px-4 py-16 text-center"><p className="font-display font-black text-2xl mb-2">Not your console</p><p className="text-ink/70 font-semibold">{msg}</p><Link to="/app" className="inline-block mt-4 rounded-full border-[2.5px] border-ink bg-sun px-6 py-3 font-extrabold shadow-hardSm">Open commuter app</Link></div>
}
