import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Crosshair, Loader2, MapPin, Sparkles } from 'lucide-react'
import { api, ApiError } from '../api'
import { useApi } from '../hooks'
import type { Insiden, SceneArea, TitikBaruHasil, TitikDuplikatDetail } from '../types'

const NAMA_MIN = 3
const NAMA_MAKS = 120

/** Sama dengan validator backend: pangkas dan rapikan spasi ganda. */
const rapikanNama = (s: string) => s.trim().replace(/\s+/g, ' ')

function adalahDuplikat(detail: unknown): detail is TitikDuplikatDetail {
  return (
    typeof detail === 'object' &&
    detail !== null &&
    (detail as { kode?: unknown }).kode === 'titik_duplikat'
  )
}

function pesanGalat(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 409 && adalahDuplikat(err.detail)) {
      const jarak = err.detail.jarak_m.toLocaleString('id-ID', { maximumFractionDigits: 1 })
      return `Titik ini berdekatan (± ${jarak} m) dengan titik ${err.detail.titik_ada} yang sudah ada.`
    }
    if (err.status === 422) return 'Periksa kembali isian: nama lokasi minimal 3 karakter.'
  }
  return err instanceof Error ? err.message : 'Gagal menambahkan titik.'
}
import {
  ErrorState,
  KelasBadge,
  Loader,
  Notice,
  PageHeader,
  StatusKlasifikasiBadge,
} from '../components/ui'

export default function TitikBaru() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const awal = Number(params.get('insiden')) || undefined
  const { data: area, loading: loadingArea, error: errorArea, reload } = useApi<SceneArea[]>(
    '/api/scene-areas',
  )
  const { data: insidenList } = useApi<Insiden[]>('/api/insiden')

  const [nama, setNama] = useState('')
  const [insiden, setInsiden] = useState<number | undefined>(awal)
  const [lat, setLat] = useState('')
  const [lon, setLon] = useState('')
  const [catatan, setCatatan] = useState('')
  const [busy, setBusy] = useState(false)
  const [pesan, setPesan] = useState('')
  const [hasil, setHasil] = useState<TitikBaruHasil | null>(null)
  const [namaDisentuh, setNamaDisentuh] = useState(false)

  const namaRapi = rapikanNama(nama)
  const namaValid = namaRapi.length >= NAMA_MIN && namaRapi.length <= NAMA_MAKS
  const galatNama =
    namaDisentuh && !namaValid
      ? namaRapi.length === 0
        ? 'Nama lokasi wajib diisi.'
        : `Nama lokasi minimal ${NAMA_MIN} karakter.`
      : ''

  if (loadingArea) return <Loader label="Memuat area citra…" />
  if (errorArea || !area) return <ErrorState message={errorArea ?? 'Area tidak tersedia.'} onRetry={reload} />

  const insidenDariScene = (kode: string) =>
    insidenList?.find((i) => i.scene === kode)?.id

  const pilihContoh = (a: SceneArea) => {
    setLat(String(a.contoh?.lat ?? ''))
    setLon(String(a.contoh?.lon ?? ''))
    setInsiden(insidenDariScene(a.kode))
  }

  const kirim = async (e: React.FormEvent) => {
    e.preventDefault()
    setPesan('')
    setHasil(null)
    setNamaDisentuh(true)
    if (!namaValid) return
    const latN = Number(lat)
    const lonN = Number(lon)
    if (!Number.isFinite(latN) || !Number.isFinite(lonN)) {
      setPesan('Latitude dan longitude harus berupa angka.')
      return
    }
    setBusy(true)
    try {
      const res = await api<TitikBaruHasil>('/api/titik', {
        method: 'POST',
        body: JSON.stringify({
          nama: namaRapi,
          lat: latN,
          lon: lonN,
          insiden_id: insiden ?? null,
          catatan: catatan.trim(),
        }),
      })
      setHasil(res)
    } catch (err) {
      setPesan(pesanGalat(err))
    } finally {
      setBusy(false)
    }
  }

  if (hasil) {
    return (
      <>
        <PageHeader
          eyebrow="Titik berhasil ditambahkan"
          title={`${hasil.kode} · ${hasil.nama} sudah diklasifikasi`}
          description="Patch citra di sekitar koordinat sudah diambil dan dinilai model. Lanjutkan ke halaman hasil untuk melihat probabilitas lengkap."
        />
        <div className="card success-card">
          <div className="success-head">
            <span className="success-icon">
              <Sparkles size={20} />
            </span>
            <div>
              <h2>Estimasi model</h2>
              <p>
                Area {hasil.scene} · keyakinan {(hasil.keyakinan * 100).toFixed(1)}%
              </p>
            </div>
            <KelasBadge kelas={hasil.kelas} />
          </div>
          <StatusKlasifikasiBadge status={hasil.status} />
          {hasil.status === 'menunggu_ahli' && (
            <Notice tone="warning">
              Keyakinan model di bawah 60%. Titik ini otomatis masuk antrean verifikasi ahli.
            </Notice>
          )}
          <div className="success-actions">
            <Link to={`/titik/${hasil.id}?baru=1`} className="btn btn-primary">
              Lihat hasil klasifikasi
            </Link>
            <button className="btn btn-ghost" onClick={() => navigate('/titik')}>
              Kembali ke daftar titik
            </button>
          </div>
        </div>
      </>
    )
  }

  return (
    <>
      <Link to="/titik" className="back-link">
        <ArrowLeft size={15} /> Titik observasi
      </Link>
      <PageHeader
        eyebrow="Tambah titik"
        title="Klasifikasi titik baru"
        description="Masukkan koordinat di dalam salah satu area citra. Sistem mengambil patch 330 m dan menjalankan model CNN pada citra asli."
      />

      <div className="form-grid">
        <form className="card form-card" onSubmit={kirim}>
          <div className="card-head">
            <div>
              <h2>Detail titik</h2>
              <p>Nama dan koordinat wajib diisi.</p>
            </div>
          </div>

          <label className="field">
            <span>
              Nama lokasi (desa/kecamatan)
              <span className="field-wajib" aria-hidden="true">*</span>
            </span>
            <input
              value={nama}
              onChange={(e) => setNama(e.target.value)}
              onBlur={() => setNamaDisentuh(true)}
              placeholder="mis. Desa Sungai Tuan, Kec. Karang Intan"
              maxLength={NAMA_MAKS}
              required
              aria-required="true"
              aria-invalid={galatNama ? true : undefined}
            />
            {galatNama ? (
              <small className="form-error">{galatNama}</small>
            ) : (
              <small className="field-hint">Kode dibuat otomatis, mis. K002-07</small>
            )}
          </label>

          <label className="field">
            <span>Kejadian / area (opsional)</span>
            <select
              value={insiden ?? ''}
              onChange={(e) => setInsiden(e.target.value ? Number(e.target.value) : undefined)}
            >
              <option value="">Deteksi otomatis dari koordinat</option>
              {area.map((a) => {
                const id = insidenDariScene(a.kode)
                return id ? (
                  <option key={a.kode} value={id}>
                    Area {a.kode} · {a.tahun}
                  </option>
                ) : null
              })}
            </select>
            <small className="field-hint">
              Pilih area agar koordinat divalidasi terhadap citra kejadian tersebut.
            </small>
          </label>

          <div className="field-row">
            <label className="field">
              <span>Latitude</span>
              <input
                value={lat}
                onChange={(e) => setLat(e.target.value)}
                placeholder="-3.1590"
                inputMode="decimal"
                required
              />
            </label>
            <label className="field">
              <span>Longitude</span>
              <input
                value={lon}
                onChange={(e) => setLon(e.target.value)}
                placeholder="114.8390"
                inputMode="decimal"
                required
              />
            </label>
          </div>

          <label className="field">
            <span>Catatan (opsional)</span>
            <textarea
              value={catatan}
              onChange={(e) => setCatatan(e.target.value)}
              placeholder="Kondisi lapangan, akses, atau informasi tambahan…"
              rows={3}
              maxLength={500}
            />
          </label>

          {pesan && <div className="form-error">{pesan}</div>}

          <button className="btn btn-primary btn-block" disabled={busy || !namaValid}>
            {busy ? (
              <>
                <Loader2 size={17} className="spin" /> Menganalisis citra…
              </>
            ) : (
              <>
                <Crosshair size={17} /> Jalankan klasifikasi
              </>
            )}
          </button>
          <p className="form-foot">
            Model membutuhkan minimal 80% piksel valid dalam patch. Titik di tepi citra atau area
            berkabut akan ditolak.
          </p>
        </form>

        <aside className="card area-card">
          <div className="card-head">
            <div>
              <h2>Area yang tersedia</h2>
              <p>Klik salah satu untuk mengisi koordinat contoh.</p>
            </div>
          </div>
          <ul className="area-list">
            {area.map((a) => (
              <li key={a.kode}>
                <div className="area-head">
                  <span className="area-mark">
                    <MapPin size={15} />
                  </span>
                  <div>
                    <strong>Area {a.kode}</strong>
                    <small>
                      {a.tahun} · {a.zona_utm}
                    </small>
                  </div>
                  <span className="chip-soft">{a.cakupan_ha.toLocaleString('id-ID')} ha</span>
                </div>
                <p className="area-bounds">
                  {a.lat_min.toFixed(4)}–{a.lat_max.toFixed(4)} L · {a.lon_min.toFixed(4)}–
                  {a.lon_max.toFixed(4)} B
                </p>
                <button
                  type="button"
                  className="btn btn-tiny"
                  onClick={() => pilihContoh(a)}
                  disabled={!a.contoh}
                >
                  <Crosshair size={13} /> Gunakan contoh
                  {a.contoh ? ` (${a.contoh.kode})` : ''}
                </button>
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </>
  )
}
