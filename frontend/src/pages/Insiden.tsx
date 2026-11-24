import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { PlusCircle, Search } from 'lucide-react'
import { useApi } from '../hooks'
import type { Insiden, StatusInsiden } from '../types'
import InsidenCard from '../components/InsidenCard'
import { EmptyState, ErrorState, Loader, PageHeader } from '../components/ui'

const FILTER: Array<{ label: string; value: StatusInsiden | '' }> = [
  { label: 'Semua', value: '' },
  { label: 'Siaga', value: 'Siaga' },
  { label: 'Waspada', value: 'Waspada' },
  { label: 'Pantau', value: 'Pantau' },
]

export default function InsidenPage() {
  const { data, loading, error, reload } = useApi<Insiden[]>('/api/insiden')
  const [q, setQ] = useState('')
  const [status, setStatus] = useState<StatusInsiden | ''>('')

  const daftar = useMemo(() => {
    if (!data) return []
    const kata = q.trim().toLowerCase()
    return data.filter(
      (i) =>
        (!status || i.status === status) &&
        (!kata ||
          i.kode.toLowerCase().includes(kata) ||
          i.nama.toLowerCase().includes(kata) ||
          i.provinsi.toLowerCase().includes(kata)),
    )
  }, [data, q, status])

  if (loading) return <Loader label="Memuat daftar kejadian…" />
  if (error || !data) return <ErrorState message={error ?? 'Data tidak tersedia.'} onRetry={reload} />

  return (
    <>
      <PageHeader
        eyebrow="Kejadian"
        title="Area pemantauan karhutla"
        description="Enam kejadian dari citra Sentinel-2 Kalimantan. Status area mengikuti kelas keparahan tertinggi dari titik yang sudah diklasifikasi."
        actions={
          <Link to="/titik/baru" className="btn btn-primary">
            <PlusCircle size={17} /> Tambah titik
          </Link>
        }
      />

      <div className="toolbar">
        <div className="search">
          <Search size={17} />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Cari kode, nama, atau provinsi…"
            aria-label="Cari kejadian"
          />
        </div>
        <div className="chips">
          {FILTER.map((f) => {
            const jumlah = f.value ? data.filter((i) => i.status === f.value).length : data.length
            return (
              <button
                key={f.label}
                className={`chip ${status === f.value ? 'active' : ''}`}
                onClick={() => setStatus(f.value)}
              >
                {f.label}
                <span>{jumlah}</span>
              </button>
            )
          })}
        </div>
      </div>

      {daftar.length === 0 ? (
        <EmptyState
          title="Tidak ada kejadian yang cocok"
          description="Ubah kata pencarian atau pilih status lain."
          action={
            <button
              className="btn btn-ghost"
              onClick={() => {
                setQ('')
                setStatus('')
              }}
            >
              Reset filter
            </button>
          }
        />
      ) : (
        <section className="incident-grid">
          {daftar.map((i) => (
            <InsidenCard key={i.id} insiden={i} />
          ))}
        </section>
      )}
    </>
  )
}
