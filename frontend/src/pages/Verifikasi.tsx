import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, ShieldCheck, Users } from 'lucide-react'
import { api } from '../api'
import { useApi } from '../hooks'
import { useAuth } from '../auth'
import type { AntreanItem, VerifikasiData } from '../types'
import { KELAS, WARNA_KELAS } from '../types'
import {
  ErrorState,
  KelasBadge,
  Loader,
  Notice,
  PageHeader,
  StatusKlasifikasiBadge,
  formatKoordinat,
  formatTanggal,
} from '../components/ui'

function ReviewPanel({
  item,
  isAhli,
  onDone,
}: {
  item: AntreanItem
  isAhli: boolean
  onDone: () => void
}) {
  const [final, setFinal] = useState(item.kelas)
  const [catatan, setCatatan] = useState('')
  const [busy, setBusy] = useState(false)
  const [pesan, setPesan] = useState('')
  const [sukses, setSukses] = useState('')

  const kirim = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!isAhli) return
    setBusy(true)
    setPesan('')
    setSukses('')
    try {
      const res = await api<{ keputusan: string; kelas_final: string }>('/api/verifikasi', {
        method: 'POST',
        body: JSON.stringify({
          klasifikasi_id: item.klasifikasi_id,
          kelas_final: final,
          catatan: catatan.trim(),
        }),
      })
      setSukses(
        res.keputusan === 'dikonfirmasi'
          ? 'Hasil dikonfirmasi.'
          : `Hasil dikoreksi menjadi ${res.kelas_final}.`,
      )
      onDone()
    } catch (err) {
      setPesan(err instanceof Error ? err.message : 'Gagal menyimpan verifikasi.')
    } finally {
      setBusy(false)
    }
  }

  const terverifikasi = item.status === 'terverifikasi'

  return (
    <form className="card review-card" onSubmit={kirim} key={item.klasifikasi_id}>
      <div className="card-head">
        <div>
          <p className="eyebrow">Tinjauan ahli</p>
          <h2>{item.nama}</h2>
          <p className="page-desc">
            {item.kode} · {item.insiden} · {formatKoordinat(item.lat, item.lon)}
          </p>
        </div>
        <StatusKlasifikasiBadge status={item.status} />
      </div>

      <div className="review-media">
        <img
          src={`/api/titik/${item.point_id}/patch.png`}
          alt={`Patch citra ${item.kode}`}
        />
        <div className="review-media-caption">
          <span>Patch 330 m × 330 m (RGB)</span>
          <span>dNBR {item.dnbr.toFixed(3)} · MODIS {item.modis ? 'terbakar' : 'tidak'}</span>
        </div>
      </div>

      <div className="review-ai">
        <div className="review-ai-head">
          <span className="badge badge-netral">Estimasi AI</span>
          <KelasBadge kelas={item.kelas} />
          <b>{(item.keyakinan * 100).toFixed(1)}%</b>
        </div>
        <div className="prob-block compact">
          {KELAS.map((k) => (
            <div className="prob-row" key={k}>
              <span className="prob-name">{k}</span>
              <div className="prob-track">
                <span
                  style={{
                    width: `${Math.max(1, item.probabilitas[k] * 100)}%`,
                    background: WARNA_KELAS[k],
                  }}
                />
              </div>
              <b>{(item.probabilitas[k] * 100).toFixed(1)}%</b>
            </div>
          ))}
        </div>
        <p className="muted small">
          Label referensi dNBR (satelit): <KelasBadge kelas={item.label_referensi} kecil /> ·{' '}
          {formatTanggal(item.dibuat)}
        </p>
      </div>

      {terverifikasi && item.kelas_final ? (
        <div className="verified-box">
          <CheckCircle2 size={18} />
          <div>
            <strong>Sudah diverifikasi</strong>
            <p>
              Keputusan: {item.keputusan === 'dikonfirmasi' ? 'dikonfirmasi' : 'dikoreksi'} · kelas
              final {item.kelas_final} oleh {item.ahli} pada {formatTanggal(item.diverifikasi)}.
            </p>
            {item.catatan_verifikasi && <blockquote>{item.catatan_verifikasi}</blockquote>}
          </div>
        </div>
      ) : (
        <>
          <div className="class-choice">
            <span className="field-label">Kelas final</span>
            <div className="choice-grid">
              {KELAS.map((k) => (
                <button
                  key={k}
                  type="button"
                  className={`choice ${final === k ? 'active' : ''}`}
                  style={{ '--choice-color': WARNA_KELAS[k] } as React.CSSProperties}
                  onClick={() => setFinal(k)}
                  disabled={!isAhli || busy}
                >
                  <span className="choice-dot" />
                  {k}
                </button>
              ))}
            </div>
          </div>

          <label className="field">
            <span>Catatan verifikasi</span>
            <textarea
              value={catatan}
              onChange={(e) => setCatatan(e.target.value)}
              rows={3}
              placeholder="Bukti lapangan, alasan koreksi, atau tindak lanjut…"
              disabled={!isAhli || busy}
            />
          </label>

          {pesan && <div className="form-error">{pesan}</div>}
          {sukses && <Notice tone="success">{sukses}</Notice>}

          {!isAhli && (
            <Notice tone="warning">
              Masuk sebagai ahli untuk mengonfirmasi atau mengoreksi hasil ini. Akun petugas hanya
              dapat memantau.
            </Notice>
          )}

          <div className="review-actions">
            <button
              type="submit"
              className="btn btn-primary"
              disabled={!isAhli || busy}
            >
              {busy ? 'Menyimpan…' : final === item.kelas ? 'Konfirmasi hasil AI' : 'Simpan koreksi'}
            </button>
            <Link to={`/titik/${item.point_id}`} className="btn btn-ghost">
              Buka detail titik
            </Link>
          </div>
        </>
      )}
    </form>
  )
}

export default function VerifikasiPage() {
  const { user } = useAuth()
  const { data, loading, error, reload } = useApi<VerifikasiData>('/api/verifikasi')
  const [filter, setFilter] = useState<'menunggu' | 'semua'>('menunggu')
  const [selectedId, setSelectedId] = useState<number | null>(null)

  useEffect(() => {
    if (!data || data.daftar.length === 0) return
    if (selectedId && data.daftar.some((d) => d.klasifikasi_id === selectedId)) return
    const pertama = data.daftar.find((d) => d.status === 'menunggu_ahli') ?? data.daftar[0]
    setSelectedId(pertama.klasifikasi_id)
  }, [data, selectedId])

  if (loading) return <Loader label="Memuat antrean verifikasi…" />
  if (error || !data) return <ErrorState message={error ?? 'Data tidak tersedia.'} onRetry={reload} />

  const daftar =
    filter === 'menunggu'
      ? data.daftar.filter((d) => d.status === 'menunggu_ahli')
      : data.daftar
  const terpilih = daftar.find((d) => d.klasifikasi_id === selectedId) ?? daftar[0] ?? data.daftar[0]

  return (
    <>
      <PageHeader
        eyebrow="Verifikasi ahli"
        title="Antrean hasil estimasi"
        description="Ahli mengonfirmasi atau mengoreksi hasil model. Titik dengan keyakinan di bawah 60% diprioritaskan."
        actions={
          <span className="badge badge-soft">
            <Users size={14} /> {data.menunggu} menunggu
          </span>
        }
      />

      <div className="verify-layout">
        <aside className="card queue-card">
          <div className="card-head">
            <div>
              <h2>Daftar titik</h2>
              <p>{daftar.length} titik</p>
            </div>
          </div>
          <div className="chips chips-full">
            <button
              className={`chip ${filter === 'menunggu' ? 'active' : ''}`}
              onClick={() => setFilter('menunggu')}
            >
              Menunggu <span>{data.menunggu}</span>
            </button>
            <button
              className={`chip ${filter === 'semua' ? 'active' : ''}`}
              onClick={() => setFilter('semua')}
            >
              Semua <span>{data.daftar.length}</span>
            </button>
          </div>

          {daftar.length === 0 ? (
            <div className="state-box state-empty compact">
              <ShieldCheck size={22} />
              <div>
                <strong>Antrean kosong</strong>
                <p>Semua estimasi sudah ditinjau.</p>
              </div>
            </div>
          ) : (
            <ul className="queue-list">
              {daftar.map((item) => (
                <li key={item.klasifikasi_id}>
                  <button
                    className={`queue-item ${terpilih?.klasifikasi_id === item.klasifikasi_id ? 'active' : ''}`}
                    onClick={() => setSelectedId(item.klasifikasi_id)}
                  >
                    <div className="queue-head">
                      <strong>{item.kode}</strong>
                      <StatusKlasifikasiBadge status={item.status} />
                    </div>
                    <p className="queue-sub">
                      {item.insiden} · {item.nama}
                    </p>
                    <div className="queue-foot">
                      <KelasBadge kelas={item.kelas} kecil />
                      <span className="queue-conf">{(item.keyakinan * 100).toFixed(0)}%</span>
                      {item.keputusan && (
                        <span className={`badge badge-keputusan ${item.keputusan} badge-kecil`}>
                          {item.keputusan === 'dikonfirmasi' ? 'dikonfirmasi' : 'dikoreksi'}
                        </span>
                      )}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <div className="review-wrap">
          {terpilih ? (
            <ReviewPanel
              key={terpilih.klasifikasi_id}
              item={terpilih}
              isAhli={user?.role === 'ahli'}
              onDone={reload}
            />
          ) : (
            <div className="card state-box state-empty">
              <ShieldCheck size={24} />
              <div>
                <strong>Pilih titik untuk ditinjau</strong>
                <p>Klik salah satu titik di daftar sebelah kiri.</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {filter === 'semua' && data.daftar.some((d) => d.status === 'terverifikasi') && (
        <div className="card history-card">
          <div className="card-head">
            <div>
              <h2>Riwayat verifikasi</h2>
              <p>Titik yang sudah ditinjau ahli.</p>
            </div>
          </div>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Titik</th>
                  <th>Area</th>
                  <th>AI</th>
                  <th>Final</th>
                  <th>Keputusan</th>
                  <th>Ahli</th>
                  <th>Tanggal</th>
                </tr>
              </thead>
              <tbody>
                {data.daftar
                  .filter((d) => d.status === 'terverifikasi')
                  .map((d) => (
                    <tr key={d.klasifikasi_id}>
                      <td>
                        <Link to={`/titik/${d.point_id}`} className="table-link">
                          {d.kode}
                        </Link>
                      </td>
                      <td>{d.insiden}</td>
                      <td>
                        <KelasBadge kelas={d.kelas} kecil />
                      </td>
                      <td>
                        <KelasBadge kelas={d.kelas_final ?? d.kelas} kecil />
                      </td>
                      <td>
                        <span className={`badge badge-keputusan ${d.keputusan} badge-kecil`}>
                          {d.keputusan === 'dikonfirmasi' ? 'dikonfirmasi' : 'dikoreksi'}
                        </span>
                      </td>
                      <td>{d.ahli ?? '—'}</td>
                      <td>{formatTanggal(d.diverifikasi)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  )
}
