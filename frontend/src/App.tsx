import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Insiden from './pages/Insiden'
import InsidenDetail from './pages/InsidenDetail'
import Titik from './pages/Titik'
import TitikBaru from './pages/TitikBaru'
import Klasifikasi from './pages/Klasifikasi'
import Verifikasi from './pages/Verifikasi'
import { Loader } from './components/ui'

function ProtectedRoute() {
  const { user, loading } = useAuth()
  if (loading) return <Loader label="Memeriksa sesi…" />
  if (!user) return <Navigate to="/login" replace />
  return <Outlet />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="insiden" element={<Insiden />} />
          <Route path="insiden/:id" element={<InsidenDetail />} />
          <Route path="titik" element={<Titik />} />
          <Route path="titik/baru" element={<TitikBaru />} />
          <Route path="titik/:id" element={<Klasifikasi />} />
          <Route path="verifikasi" element={<Verifikasi />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
  )
}
