import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  Eye,
  EyeOff,
  Flame,
  LockKeyhole,
  ShieldCheck,
  Trees,
  UserRound,
} from 'lucide-react'
import { useAuth } from '../auth'
import { ApiError } from '../api'

const AKUN = [
  {
    peran: 'Petugas lapangan',
    username: 'petugas',
    password: 'petugas123',
    ikon: UserRound,
    keterangan: 'Pantau area & tambah titik',
  },
  {
    peran: 'Ahli verifikasi',
    username: 'ahli',
    password: 'ahli123',
    ikon: ShieldCheck,
    keterangan: 'Konfirmasi atau koreksi hasil AI',
  },
]

export default function Login() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [lihat, setLihat] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (user) return <Navigate to="/" replace />

  const masuk = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await login(username.trim(), password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Tidak bisa masuk. Coba lagi.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login">
      <section className="login-hero">
        <svg className="contour" viewBox="0 0 900 900" aria-hidden="true">
          <circle className="sun" cx="690" cy="210" r="150" />
          <path d="M-80 560 C 120 430, 240 620, 430 520 S 760 470, 980 600" />
          <path d="M-80 640 C 130 500, 260 700, 450 590 S 780 540, 990 670" />
          <path d="M-80 720 C 140 570, 280 780, 470 660 S 800 610, 1000 740" />
          <path d="M-80 800 C 150 640, 300 860, 490 730 S 820 680, 1010 810" />
        </svg>

        <div className="login-brand">
          <span className="brand-mark light">
            <Trees size={22} />
          </span>
          <div>
            <strong>Sipakarhutla</strong>
            <small>Sistem Pemantauan Karhutla</small>
          </div>
        </div>

        <div className="hero-copy">
          <p className="eyebrow light">Kalimantan · 2019–2023</p>
          <h1>
            Menilai keparahan kebakaran <em>sebelum</em> api membesar.
          </h1>
          <p className="hero-lead">
            Klasifikasi tingkat keparahan dari citra Sentinel-2, dipadukan dengan verifikasi ahli.
            Satu alur kerja untuk memantau titik panas, meninjau estimasi model, dan menetapkan
            keputusan akhir.
          </p>
          <div className="hero-stats">
            <div>
              <strong>84,1%</strong>
              <span>akurasi uji antar-kejadian</span>
            </div>
            <div>
              <strong>6</strong>
              <span>area citra Kalimantan</span>
            </div>
            <div>
              <strong>60%</strong>
              <span>ambang keyakinan untuk ahli</span>
            </div>
          </div>
        </div>

        <p className="hero-foot">
          <Flame size={15} /> Label referensi berasal dari dNBR satelit, bukan pengamatan lapangan.
        </p>
      </section>

      <section className="login-panel">
        <div className="login-card">
          <p className="eyebrow">Masuk ke dashboard</p>
          <h2>Selamat datang kembali</h2>
          <p className="login-sub">Gunakan akun petugas atau ahli untuk melanjutkan pemantauan.</p>

          <form onSubmit={masuk} className="login-form">
            <label className="field">
              <span>Nama pengguna</span>
              <div className="input-wrap">
                <UserRound size={17} />
                <input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="petugas"
                  autoComplete="username"
                  required
                />
              </div>
            </label>

            <label className="field">
              <span>Kata sandi</span>
              <div className="input-wrap">
                <LockKeyhole size={17} />
                <input
                  type={lihat ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  className="input-action"
                  onClick={() => setLihat((v) => !v)}
                  aria-label={lihat ? 'Sembunyikan kata sandi' : 'Tampilkan kata sandi'}
                >
                  {lihat ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </label>

            {error && <div className="form-error">{error}</div>}

            <button className="btn btn-primary btn-block" disabled={busy}>
              {busy ? 'Memeriksa akun…' : 'Masuk'}
              {!busy && <ArrowRight size={17} />}
            </button>
          </form>

          <div className="demo-accounts">
            <p>
              <span>Akun demo</span> — klik untuk mengisi formulir
            </p>
            {AKUN.map(({ peran, username: u, password: p, ikon: Ikon, keterangan }) => (
              <button
                key={u}
                type="button"
                className="demo-account"
                onClick={() => {
                  setUsername(u)
                  setPassword(p)
                  setError('')
                }}
              >
                <span className="demo-icon">
                  <Ikon size={16} />
                </span>
                <span className="demo-text">
                  <strong>{peran}</strong>
                  <small>{keterangan}</small>
                </span>
                <code>
                  {u} / {p}
                </code>
              </button>
            ))}
          </div>

          <p className="login-foot">
            Aplikasi demo. Data titik dan verifikasi bersifat contoh; prediksi dihitung dari citra
            asli.
          </p>
        </div>
      </section>
    </div>
  )
}
