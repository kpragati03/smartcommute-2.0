import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import Navbar, { Footer, ProtectedRoute } from './components/Navbar'
import Landing from './pages/Landing'
import { Login, Register, RegisterOrganisation } from './pages/Auth'
import CommuterApp from './pages/CommuterApp'
import DriverPortal from './pages/DriverPortal'
import AdminConsole from './pages/AdminConsole'
function NotFound() {
  return <main className="max-w-xl mx-auto px-4 py-20 text-center">
    <p className="font-display font-black text-6xl">404</p><p className="font-semibold text-ink/70 mt-2">This stop doesn’t exist on any route.</p>
    <a href="/" className="inline-block mt-5 rounded-full border-[2.5px] border-ink bg-lime-brand px-6 py-3 font-extrabold shadow-hardSm">Back home</a></main>
}
export default function App() {
  return <AuthProvider><BrowserRouter>
    <Navbar />
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/register-organisation" element={<RegisterOrganisation />} />
      <Route path="/app" element={<ProtectedRoute><CommuterApp /></ProtectedRoute>} />
      <Route path="/driver" element={<ProtectedRoute require="driver"><DriverPortal /></ProtectedRoute>} />
      <Route path="/admin" element={<ProtectedRoute require="admin"><AdminConsole /></ProtectedRoute>} />
      <Route path="*" element={<NotFound />} />
    </Routes>
    <Footer />
  </BrowserRouter></AuthProvider>
}
