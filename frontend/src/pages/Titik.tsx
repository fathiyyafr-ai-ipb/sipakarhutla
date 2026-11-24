import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowUpRight, PlusCircle, Search } from 'lucide-react'
import { useApi } from '../hooks'
import type { Kelas, StatusKlasifikasi, TitikRingkas } from '../types'
import { KELAS } from '../types'
import {
  ConfidenceBar,
  DikoreksiTag,
  EmptyState,
  ErrorState,
  KelasBadge,
  Loader,
  PageHeader,
  StatusKlasifikasiBadge,
  formatKoordinat,
} from '../components/ui'

const STATUS: Array<{ value: StatusKlasifikasi | ''; label: string }> = [
  { value: '', label: 'Semua status' },
  { value: 'menunggu_ahli', label: 'Menunggu ahli' },
  { value: 'terverifikasi_model', label: 'Estimasi model' },
  { value: 'terverifikasi', label: 'Terverifikasi' },
]

export default function TitikPage() {
  const [params] = useSearchParams()
  const { data, loading, error, reload } = useApi<TitikRingkas[]>('/api/titik')
  const [q, setQ] = useState('')
  const [kelas, setKelas] = useState<Kelas | ''>(() => {
    const awal = params.get('kelas')
    return KELAS.includes(awal as Kelas) ? (awal as Kelas) : ''
  })
  const [insiden, setInsiden] = useState(params.get('insiden') ?? '')
  const [status, setStatus] = useState<StatusKlasifikasi | ''>('')

  const area = useMemo(
    () => Array.from(new Set((data ?? []).map((t) => t.insiden))).sort(),
    [data],
  )

  const daftar = useMemo(() => {
    if (!data) return []
    const kata = q.trim().toLowerCase()
    return data.filter(
      (t) =>
        (!kelas || t.kelas === kelas) &&
        (!insiden || t.insiden === insiden) &&
        (!status || t.status === status) &&
        (!kata ||
          t.kode.toLowerCase().includes(kata) ||
          t.nama.toLowerCase().includes(kata)),
    )
  }, [data, q, kelas, insiden, status])

  if (loading) return <Loader label="Memuat titik observasi…" />
  if (error || !data) return <ErrorState message={error ?? 'Data tidak tersedia.'} onRetry={reload} />

  return (
    <>
      <PageHeader
        eyebrow="Titik observasi"
        title="Hasil klasifikasi per titik"
        description="Setiap titik mewakili patch 330 × 330 m dari citra Sentinel-2 yang dinilai CNN. Keyakinan di bawah 60% otomatis masuk antrean ahli."
        actions={
          <Link to="/titik/baru" className="btn btn-primary">
            <PlusCircle size={17} /> Tambah titik
          </Link>
        }
      />

      <div className="toolbar toolbar-wrap">
        <div className="search">
          <Search size={17} />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Cari kode atau nama titik…"
            aria-label="Cari titik"
          />
        </div>
        <div className="chips">
          <button className={`chip ${!kelas ? 'active' : ''}`} onClick={() => setKelas('')}>
            Semua kelas
          </button>
          {KELAS.map((k) => (
            <button key={k} className={`chip ${kelas === k ? 'active' : ''}`} onClick={() => setKelas(k)}>
              {k}
              <span>{data.filter((t) => t.kelas === k).length}</span>
            </button>
          ))}
        </div>
        <div className="toolbar-selects">
          <select value={insiden} onChange={(e) => setInsiden(e.target.value)} aria-label="Filter area">
            <option value="">Semua area</option>
            {area.map((a) => (
              <option key={a} value={a}>
                Area {a}
              </option>
            ))}
          </select>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as StatusKlasifikasi | '')}
            aria-label="Filter status"
          >
            {STATUS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="result-line">
        <span>
          Menampilkan <strong>{daftar.length}</strong> dari {data.length} titik
        </span>
      </div>

      {daftar.length === 0 ? (
        <EmptyState
          title="Tidak ada titik yang cocok"
          description="Ubah filter atau tambahkan titik baru pada area citra yang tersedia."
          action={
            <button
              className="btn btn-ghost"
              onClick={() => {
                setQ('')
                setKelas('')
                setInsiden('')
                setStatus('')
              }}
            >
              Reset filter
            </button>
          }
        />
      ) : (
        <div className="card table-card">
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Titik</th>
                  <th>Area</th>
                  <th>Koordinat</th>
                  <th>Kelas</th>
                  <th>Keyakinan</th>
                  <th>Status</th>
                  <th aria-label="Aksi" />
                </tr>
              </thead>
              <tbody>
                {daftar.map((t) => (
                  <tr key={t.id}>
                    <td>
                      <Link to={`/titik/${t.id}`} className="table-link">
                        {t.kode}
                      </Link>
                      <small className="cell-sub">{t.nama}</small>
                    </td>
                    <td>
                      <span className="area-tag">{t.insiden}</span>
                    </td>
                    <td className="mono">{formatKoordinat(t.lat, t.lon)}</td>
                    <td>
                      <KelasBadge kelas={t.kelas} kecil />
                      {t.dikoreksi && <DikoreksiTag kelasModel={t.kelas_model} />}
                    </td>
                    <td>
                      <ConfidenceBar value={t.keyakinan} kelas={t.kelas} />
                    </td>
                    <td>
                      <StatusKlasifikasiBadge status={t.status} />
                    </td>
                    <td className="cell-action">
                      <Link to={`/titik/${t.id}`} className="row-action">
                        Buka <ArrowUpRight size={14} />
                      </Link>
                    </td>
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
