import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  ArrowUpRight,
  CalendarDays,
  Compass,
  Layers,
  MapPin,
  PlusCircle,
  Satellite,
  ShieldQuestion,
} from 'lucide-react'
import { useApi } from '../hooks'
import type { DetailInsiden } from '../types'
import { KELAS, WARNA_KELAS } from '../types'
import {
  ConfidenceBar,
  EmptyState,
  ErrorState,
  KelasBadge,
  Loader,
  PageHeader,
  StatusInsidenBadge,
  StatusKlasifikasiBadge,
  formatKoordinat,
} from '../components/ui'

export default function InsidenDetail() {
  const { id } = useParams()
  const { data, loading, error, reload } = useApi<DetailInsiden>(id ? `/api/insiden/${id}` : null)

  if (loading) return <Loader label="Memuat detail kejadian…" />
  if (error || !data) return <ErrorState message={error ?? 'Kejadian tidak ditemukan.'} onRetry={reload} />

  const { scene_info: scene } = data

  return (
    <>
      <Link to="/insiden" className="back-link">
        <ArrowLeft size={15} /> Semua kejadian
      </Link>

      <PageHeader
        eyebrow={`Kejadian ${data.kode} · ${data.tahun}`}
        title={data.nama}
        description={data.ringkasan}
        actions={
          <>
            <StatusInsidenBadge status={data.status} />
            <Link to={`/titik/baru?insiden=${data.id}`} className="btn btn-primary">
              <PlusCircle size={17} /> Tambah titik
            </Link>
          </>
        }
      />

      <div className="meta-row">
        <span>
          <MapPin size={14} /> {data.provinsi}
        </span>
        <span>
          <CalendarDays size={14} /> {data.tahun}
        </span>
        <span>
          <Layers size={14} /> {data.cakupan_ha.toLocaleString('id-ID')} ha cakupan
        </span>
        <span>
          <Satellite size={14} /> Sentinel-2 · {scene.zona_utm}
        </span>
      </div>

      <section className="detail-grid">
        <div className="card scene-card">
          <div className="scene-frame">
            <img
              src={`/api/insiden/${data.id}/thumbnail`}
              alt={`Citra RGB area ${data.kode}`}
            />
            <span className="scene-tag">Komposit RGB</span>
          </div>
          <div className="scene-caption">
            <div>
              <strong>Citra area {data.kode}</strong>
              <p>
                {scene.lat_min.toFixed(4)}–{scene.lat_max.toFixed(4)} L ·{' '}
                {scene.lon_min.toFixed(4)}–{scene.lon_max.toFixed(4)} B
              </p>
            </div>
            <span className="chip-soft">{scene.cakupan_ha.toLocaleString('id-ID')} ha</span>
          </div>
        </div>

        <div className="card summary-card">
          <div className="card-head">
            <div>
              <h2>Ringkasan keparahan</h2>
              <p>{data.titik.length} titik sudah diklasifikasi model.</p>
            </div>
          </div>
          <div className="class-rows">
            {KELAS.map((k) => {
              const jumlah = data.distribusi.find((d) => d.kelas === k)?.jumlah ?? 0
              const porsi = data.titik.length ? (jumlah / data.titik.length) * 100 : 0
              return (
                <div className="class-row" key={k}>
                  <span className="dot" style={{ background: WARNA_KELAS[k] }} />
                  <span className="class-name">{k}</span>
                  <div className="class-bar">
                    <span style={{ width: `${porsi}%`, background: WARNA_KELAS[k] }} />
                  </div>
                  <b>{jumlah}</b>
                </div>
              )
            })}
          </div>

          {data.menunggu > 0 ? (
            <Link to="/verifikasi" className="inline-alert">
              <ShieldQuestion size={17} />
              <span>
                <strong>{data.menunggu} titik menunggu ahli</strong>
                <small>Keyakinan model di bawah 60%.</small>
              </span>
              <ArrowUpRight size={15} />
            </Link>
          ) : (
            <div className="inline-ok">Semua titik sudah cukup yakin atau terverifikasi.</div>
          )}

          <dl className="coord-list">
            <div>
              <dt>Pusat area</dt>
              <dd>{formatKoordinat(data.lat, data.lon)}</dd>
            </div>
            <div>
              <dt>Zona UTM</dt>
              <dd>{scene.zona_utm}</dd>
            </div>
            <div>
              <dt>Tahun citra</dt>
              <dd>{data.tahun}</dd>
            </div>
          </dl>
        </div>
      </section>

      <div className="card">
        <div className="card-head">
          <div>
            <h2>Titik observasi</h2>
            <p>Klik titik untuk melihat probabilitas dan riwayat verifikasi.</p>
          </div>
          <span className="chip-soft">{data.titik.length} titik</span>
        </div>

        {data.titik.length === 0 ? (
          <EmptyState
            title="Belum ada titik di area ini"
            description="Tambahkan titik untuk menjalankan model pada citra area ini."
            action={
              <Link className="btn btn-primary" to={`/titik/baru?insiden=${data.id}`}>
                <PlusCircle size={16} /> Tambah titik
              </Link>
            }
          />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Titik</th>
                  <th>Kelas AI</th>
                  <th>Keyakinan</th>
                  <th>dNBR</th>
                  <th>Status</th>
                  <th aria-label="Aksi" />
                </tr>
              </thead>
              <tbody>
                {data.titik.map((t) => (
                  <tr key={t.id}>
                    <td>
                      <Link to={`/titik/${t.id}`} className="table-link">
                        {t.kode}
                      </Link>
                      <small className="cell-sub">
                        {formatKoordinat(t.lat, t.lon)}
                      </small>
                    </td>
                    <td>
                      <KelasBadge kelas={t.kelas} kecil />
                    </td>
                    <td>
                      <ConfidenceBar value={t.keyakinan} kelas={t.kelas} />
                    </td>
                    <td>{t.dnbr.toFixed(3)}</td>
                    <td>
                      <StatusKlasifikasiBadge status={t.status} />
                    </td>
                    <td className="cell-action">
                      <Link to={`/titik/${t.id}`} className="icon-btn" aria-label={`Buka ${t.kode}`}>
                        <Compass size={16} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  )
}
