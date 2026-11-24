import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import {
  ArrowLeft,
  ShieldCheck,
} from 'lucide-react'
import { useApi } from '../hooks'
import { useAuth } from '../auth'
import type { DetailTitik } from '../types'
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

export default function KlasifikasiPage() {
  const { id } = useParams()
  const [params] = useSearchParams()
  const baru = params.get('baru') === '1'
  const navigate = useNavigate()
  const { user } = useAuth()
  const { data, loading, error, reload } = useApi<DetailTitik>(id ? `/api/titik/${id}` : null)

  if (loading) return <Loader label="Memuat hasil klasifikasi…" />
  if (error || !data) return <ErrorState message={error ?? 'Titik tidak ditemukan.'} onRetry={reload} />

  const confidence = data.keyakinan

  return (
    <>
      <Link to="/titik" className="back-link">
        <ArrowLeft size={15} /> Titik observasi
      </Link>

      {baru && (
        <Notice tone="success">
          Titik {data.kode} berhasil ditambahkan. Hasil di bawah ini adalah estimasi model, belum
          merupakan verifikasi lapangan.
        </Notice>
      )}

      <PageHeader
        eyebrow={`Hasil klasifikasi · ${data.insiden}`}
        title={data.nama}
        description={`Patch 330 m × 330 m dari citra Sentinel-2 yang dinilai CNN. Kode titik ${data.kode}.`}
        actions={
          <>
            <StatusKlasifikasiBadge status={data.status} />
            {user?.role === 'ahli' && data.status !== 'terverifikasi' && (
              <Link to="/verifikasi" className="btn btn-primary">
                <ShieldCheck size={17} /> Verifikasi
              </Link>
            )}
          </>
        }
      />

      <section className="result-grid">
        <div className="card result-main">
          <div className="patch-wrap">
            <img
              src={`/api/titik/${data.id}/patch.png`}
              alt={`Patch citra 330 m area ${data.insiden}`}
              className="patch-img"
            />
            <span className="patch-tag">Patch 330 m × 330 m · RGB</span>
          </div>

          <div className="result-summary">
            <div className="result-class">
              <KelasBadge kelas={data.kelas} />
              <div>
                <p className="result-label">Kelas keparahan (estimasi model)</p>
                <h2 style={{ color: WARNA_KELAS[data.kelas] }}>{data.kelas}</h2>
              </div>
            </div>

            <div
              className="confidence-ring"
              style={
                {
                  '--p': `${confidence * 100}%`,
                  '--ring-color': WARNA_KELAS[data.kelas],
                } as React.CSSProperties
              }
            >
              <div className="ring-inner">
                <strong>{Math.round(confidence * 100)}%</strong>
                <span>keyakinan</span>
              </div>
            </div>
          </div>

          {data.status === 'menunggu_ahli' && (
            <Notice tone="warning">
              Keyakinan model di bawah 60%. Titik ini masuk antrean verifikasi ahli; hasil di
              samping adalah estimasi, bukan keputusan final.
            </Notice>
          )}

          <div className="prob-block">
            <h3>Probabilitas per kelas</h3>
            {KELAS.map((k) => (
              <div className="prob-row" key={k}>
                <span className="prob-name">{k}</span>
                <div className="prob-track">
                  <span
                    style={{ width: `${Math.max(1, data.probabilitas[k] * 100)}%`, background: WARNA_KELAS[k] }}
                  />
                </div>
                <b>{(data.probabilitas[k] * 100).toFixed(1)}%</b>
              </div>
            ))}
          </div>
        </div>

        <div className="card result-side">
          <div className="card-head">
            <div>
              <h2>Informasi titik</h2>
              <p>Metadata dan referensi dari citra.</p>
            </div>
          </div>
          <dl className="info-list">
            <div>
              <dt>Kode titik</dt>
              <dd>{data.kode}</dd>
            </div>
            <div>
              <dt>Area / kejadian</dt>
              <dd>
                {data.insiden} · {data.tahun}
              </dd>
            </div>
            <div>
              <dt>Koordinat</dt>
              <dd className="mono">{formatKoordinat(data.lat, data.lon)}</dd>
            </div>
            <div>
              <dt>Label referensi dNBR</dt>
              <dd>
                <KelasBadge kelas={data.label_referensi} kecil /> <span className="muted-inline">dari satelit</span>
              </dd>
            </div>
            <div>
              <dt>dNBR</dt>
              <dd>{data.dnbr.toFixed(3)}</dd>
            </div>
            <div>
              <dt>MODIS terbakar</dt>
              <dd>{data.modis ? 'Ya' : 'Tidak'}</dd>
            </div>
            <div>
              <dt>Model</dt>
              <dd>{data.model}</dd>
            </div>
            <div>
              <dt>Diklasifikasi</dt>
              <dd>{formatTanggal(data.diklasifikasi)}</dd>
            </div>
          </dl>

          {user?.role === 'ahli' ? (
            <button
              className="btn btn-primary btn-block"
              onClick={() => navigate('/verifikasi')}
            >
              <ShieldCheck size={17} /> Buka antrean verifikasi
            </button>
          ) : (
            <Notice tone="info">
              Masuk sebagai ahli untuk mengonfirmasi atau mengoreksi hasil ini.
            </Notice>
          )}

          {data.verifikasi.length > 0 && (
            <div className="verify-history">
              <h3>Riwayat verifikasi</h3>
              {data.verifikasi.map((v) => (
                <div className="verify-item" key={v.id}>
                  <div className="verify-head">
                    <span className={`badge badge-keputusan ${v.keputusan}`}>
                      {v.keputusan === 'dikonfirmasi' ? 'Dikonfirmasi' : 'Dikoreksi'}
                    </span>
                    <strong>{v.kelas_final}</strong>
                  </div>
                  <p>{v.ahli} · {formatTanggal(v.dibuat)}</p>
                  {v.catatan && <blockquote>{v.catatan}</blockquote>}
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </>
  )
}
