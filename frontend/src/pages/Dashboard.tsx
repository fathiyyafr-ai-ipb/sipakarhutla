import { Link } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  ArrowRight,
  ClipboardCheck,
  Flame,
  MapPinned,
  PlusCircle,
  ShieldQuestion,
  Sparkles,
  TriangleAlert,
} from 'lucide-react'
import { useApi } from '../hooks'
import type { DashboardData } from '../types'
import { KELAS, WARNA_KELAS } from '../types'
import InsidenCard from '../components/InsidenCard'
import {
  ConfidenceBar,
  EmptyState,
  ErrorState,
  KelasBadge,
  Loader,
  PageHeader,
  StatusKlasifikasiBadge,
} from '../components/ui'

const TOOLTIP_STYLE = {
  borderRadius: 12,
  border: '1px solid #e6e0d1',
  fontSize: 12,
  boxShadow: '0 12px 30px rgba(23, 48, 38, 0.12)',
}

function Stat({
  label,
  value,
  hint,
  icon: Ikon,
  tone,
  to,
}: {
  label: string
  value: number
  hint: string
  icon: typeof Flame
  tone: string
  to?: string
}) {
  const isi = (
    <>
      <span className={`stat-icon ${tone}`}>
        <Ikon size={19} />
      </span>
      <div className="stat-body">
        <p>{label}</p>
        <strong>{value.toLocaleString('id-ID')}</strong>
        <small>{hint}</small>
      </div>
      {to && <ArrowRight className="stat-arrow" size={16} />}
    </>
  )
  return to ? (
    <Link to={to} className="stat-card stat-link">
      {isi}
    </Link>
  ) : (
    <div className="stat-card">{isi}</div>
  )
}

export default function Dashboard() {
  const { data, loading, error, reload } = useApi<DashboardData>('/api/dashboard')

  if (loading) return <Loader label="Menyiapkan ringkasan pemantauan…" />
  if (error || !data) return <ErrorState message={error ?? 'Data tidak tersedia.'} onRetry={reload} />

  const totalKelas = data.distribusi.reduce((n, d) => n + d.jumlah, 0)
  const { statistik, model } = data

  return (
    <>
      <PageHeader
        eyebrow="Ringkasan pemantauan"
        title={`Selamat datang, ${data.pengguna.nama.split(' ')[0]}.`}
        description="Pantau keparahan karhutla di enam area citra Kalimantan dan tinjau estimasi model yang belum meyakinkan."
        actions={
          <Link to="/titik/baru" className="btn btn-primary">
            <PlusCircle size={17} /> Tambah titik
          </Link>
        }
      />

      <section className="stats-grid">
        <Stat
          label="Kejadian dipantau"
          value={statistik.kejadian}
          hint="Area citra Kalimantan"
          icon={Flame}
          tone="forest"
          to="/insiden"
        />
        <Stat
          label="Titik observasi"
          value={statistik.titik}
          hint="Titik dengan hasil klasifikasi"
          icon={MapPinned}
          tone="sage"
          to="/titik"
        />
        <Stat
          label="Menunggu verifikasi"
          value={statistik.menunggu}
          hint="Keyakinan model di bawah 60%"
          icon={ShieldQuestion}
          tone="amber"
          to="/verifikasi"
        />
        <Stat
          label="Titik keparahan tinggi"
          value={statistik.tinggi}
          hint="Perlu perhatian prioritas"
          icon={TriangleAlert}
          tone="rust"
          to="/titik?kelas=Tinggi"
        />
      </section>

      <section className="dash-grid">
        <div className="card chart-card">
          <div className="card-head">
            <div>
              <h2>Titik per area</h2>
              <p>Sebaran hasil klasifikasi model pada tiap kejadian.</p>
            </div>
            <span className="chip-soft">{statistik.titik} titik</span>
          </div>
          <div className="chart-body">
            <ResponsiveContainer width="100%" height={248}>
              <BarChart data={data.sebaran} margin={{ top: 8, right: 6, left: -22, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke="#e9e4d7" strokeDasharray="3 5" />
                <XAxis dataKey="kode" tickLine={false} axisLine={false} tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: 'rgba(20, 80, 60, 0.06)' }} />
                {KELAS.map((k) => (
                  <Bar
                    key={k}
                    dataKey={k}
                    stackId="kelas"
                    fill={WARNA_KELAS[k]}
                    radius={k === 'Tinggi' ? [5, 5, 0, 0] : undefined}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="chart-legend">
            {KELAS.map((k) => (
              <span key={k}>
                <i style={{ background: WARNA_KELAS[k] }} /> {k}
              </span>
            ))}
          </div>
        </div>

        <div className="card chart-card">
          <div className="card-head">
            <div>
              <h2>Distribusi keparahan</h2>
              <p>Estimasi model untuk seluruh titik.</p>
            </div>
          </div>
          <div className="donut-wrap">
            <ResponsiveContainer width="100%" height={210}>
              <PieChart>
                <Pie
                  data={data.distribusi}
                  dataKey="jumlah"
                  nameKey="kelas"
                  innerRadius={62}
                  outerRadius={92}
                  paddingAngle={3}
                  stroke="none"
                >
                  {data.distribusi.map((d) => (
                    <Cell key={d.kelas} fill={WARNA_KELAS[d.kelas]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={TOOLTIP_STYLE} />
              </PieChart>
            </ResponsiveContainer>
            <div className="donut-center">
              <strong>{totalKelas}</strong>
              <span>titik</span>
            </div>
          </div>
          <ul className="dist-list">
            {data.distribusi.map((d) => (
              <li key={d.kelas}>
                <span className="dot" style={{ background: WARNA_KELAS[d.kelas] }} />
                <span>{d.kelas}</span>
                <b>{d.jumlah}</b>
                <small>{totalKelas ? Math.round((d.jumlah / totalKelas) * 100) : 0}%</small>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <div className="section-head">
        <div>
          <h2>Kejadian terpantau</h2>
          <p>Enam area citra Sentinel-2 dari dataset Sipakarhutla.</p>
        </div>
        <Link to="/insiden" className="link-arrow">
          Lihat semua <ArrowRight size={15} />
        </Link>
      </div>
      <section className="incident-grid">
        {data.insiden.slice(0, 3).map((i) => (
          <InsidenCard key={i.id} insiden={i} />
        ))}
      </section>

      <section className="dash-grid bottom">
        <div className="card">
          <div className="card-head">
            <div>
              <h2>Titik terbaru</h2>
              <p>Hasil klasifikasi yang paling akhir masuk.</p>
            </div>
            <Link to="/titik" className="link-arrow">
              Semua titik <ArrowRight size={15} />
            </Link>
          </div>
          {data.terbaru.length === 0 ? (
            <EmptyState
              title="Belum ada titik"
              description="Tambahkan titik observasi untuk menjalankan klasifikasi."
            />
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Titik</th>
                    <th>Area</th>
                    <th>Kelas AI</th>
                    <th>Keyakinan</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.terbaru.map((t) => (
                    <tr key={t.id}>
                      <td>
                        <Link to={`/titik/${t.id}`} className="table-link">
                          {t.kode}
                        </Link>
                        <small className="cell-sub">{t.nama}</small>
                      </td>
                      <td>{t.insiden}</td>
                      <td>
                        <KelasBadge kelas={t.kelas} kecil />
                      </td>
                      <td>
                        <ConfidenceBar value={t.keyakinan} kelas={t.kelas} />
                      </td>
                      <td>
                        <StatusKlasifikasiBadge status={t.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="card model-panel">
          <div className="model-head">
            <span className="model-icon">
              <Sparkles size={17} />
            </span>
            <div>
              <h2>Kualitas model</h2>
              <p>{model.nama}</p>
            </div>
          </div>
          <div className="metric-grid">
            <div>
              <strong>{(model.akurasi * 100).toFixed(1)}%</strong>
              <span>Akurasi uji</span>
            </div>
            <div>
              <strong>{model.macro_f1.toFixed(3)}</strong>
              <span>Macro-F1</span>
            </div>
            <div>
              <strong>{model.auc_tinggi.toFixed(3)}</strong>
              <span>AUC kelas Tinggi</span>
            </div>
          </div>
          <ul className="model-notes">
            <li>
              <ClipboardCheck size={15} /> Ambang {Math.round(model.ambang * 100)}%: estimasi di bawahnya
              masuk antrean ahli.
            </li>
            {model.porsi_diputuskan !== undefined && (
              <li>
                <ClipboardCheck size={15} /> {(model.porsi_diputuskan * 100).toFixed(1)}% titik diputuskan
                model pada uji; {(model.akurasi_diputuskan! * 100).toFixed(1)}% di antaranya benar.
              </li>
            )}
          </ul>
          <p className="disclaimer">{model.catatan}</p>
        </div>
      </section>
    </>
  )
}
