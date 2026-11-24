import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  Flame,
  LayoutDashboard,
  LogOut,
  MapPin,
  Menu,
  PlusCircle,
  ShieldCheck,
  Trees,
  X,
} from 'lucide-react'
import { useAuth } from '../auth'
import { Avatar } from './ui'

const MENU = [
  { to: '/', label: 'Ringkasan', icon: LayoutDashboard, exact: true },
  { to: '/insiden', label: 'Kejadian', icon: Flame },
  { to: '/titik', label: 'Titik Observasi', icon: MapPin },
  { to: '/titik/baru', label: 'Tambah Titik', icon: PlusCircle },
  { to: '/verifikasi', label: 'Verifikasi Ahli', icon: ShieldCheck },
]

function judulHalaman(path: string) {
  if (path.startsWith('/insiden/')) return 'Detail kejadian'
  if (path.startsWith('/insiden')) return 'Kejadian'
  if (path === '/titik/baru') return 'Tambah titik'
  if (path.startsWith('/titik/')) return 'Hasil klasifikasi'
  if (path.startsWith('/titik')) return 'Titik observasi'
  if (path.startsWith('/verifikasi')) return 'Verifikasi ahli'
  return 'Ringkasan'
}

export default function Layout() {
  const { user, logout } = useAuth()
  const [buka, setBuka] = useState(false)
  const lokasi = useLocation()

  useEffect(() => {
    setBuka(false)
  }, [lokasi.pathname])

  const today = new Intl.DateTimeFormat('id-ID', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(new Date())

  return (
    <div className="app-shell">
      <aside className={`sidebar ${buka ? 'sidebar-open' : ''}`}>
        <div className="brand">
          <span className="brand-mark">
            <Trees size={22} />
          </span>
          <div>
            <strong>Sipakarhutla</strong>
            <small>Sistem Pemantauan Karhutla</small>
          </div>
          <button className="icon-btn sidebar-close" onClick={() => setBuka(false)} aria-label="Tutup menu">
            <X size={18} />
          </button>
        </div>

        <nav className="nav">
          <p className="nav-label">Menu utama</p>
          {MENU.map(({ to, label, icon: Icon, exact }) => (
            <NavLink
              key={to}
              to={to}
              end={exact}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <Icon size={18} strokeWidth={2} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-note">
          <span className="pulse-dot" />
          <div>
            <strong>Data demo</strong>
            <p>Citra asli Kalimantan 2019–2023. Prediksi model nyata.</p>
          </div>
        </div>

        <div className="sidebar-foot">
          <Avatar nama={user?.nama ?? 'Pengguna'} />
          <div className="sidebar-user">
            <strong>{user?.nama}</strong>
            <small>{user?.role === 'ahli' ? 'Ahli verifikasi' : 'Petugas lapangan'}</small>
          </div>
          <button className="icon-btn" onClick={logout} aria-label="Keluar" title="Keluar">
            <LogOut size={17} />
          </button>
        </div>
      </aside>

      {buka && <div className="scrim" onClick={() => setBuka(false)} />}

      <div className="app-main">
        <header className="topbar">
          <button className="icon-btn topbar-menu" onClick={() => setBuka(true)} aria-label="Buka menu">
            <Menu size={20} />
          </button>
          <div className="crumb">
            <span>Sipakarhutla</span>
            <i>/</i>
            <strong>{judulHalaman(lokasi.pathname)}</strong>
          </div>
          <div className="topbar-right">
            <span className="demo-pill">
              <span className="pulse-dot" /> Data demo
            </span>
            <span className="topbar-date">{today}</span>
          </div>
        </header>
        <main className="page">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
