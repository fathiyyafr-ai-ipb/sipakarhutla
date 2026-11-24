export type Kelas = 'Rendah' | 'Sedang' | 'Tinggi'
export type Role = 'petugas' | 'ahli'
export type StatusInsiden = 'Siaga' | 'Waspada' | 'Pantau'
export type StatusKlasifikasi = 'menunggu_ahli' | 'terverifikasi_model' | 'terverifikasi'

export const KELAS: Kelas[] = ['Rendah', 'Sedang', 'Tinggi']

export const WARNA_KELAS: Record<Kelas, string> = {
  Rendah: '#2f7d5b',
  Sedang: '#d99a2b',
  Tinggi: '#c0502f',
}

export interface User {
  id: number
  username: string
  nama: string
  role: Role
  dibuat?: string
}

export interface SceneInfo {
  kode: string
  nama: string
  tahun: number
  lat_min: number
  lat_max: number
  lon_min: number
  lon_max: number
  cakupan_ha: number
  zona_utm: string
}

export interface Insiden {
  id: number
  kode: string
  nama: string
  tahun: number
  provinsi: string
  lat: number
  lon: number
  cakupan_ha: number
  scene: string
  ringkasan: string
  titik: number
  tinggi: number
  sedang: number
  rendah: number
  status: StatusInsiden
}

export interface Distribusi {
  kelas: Kelas
  jumlah: number
}

export interface ModelInfo {
  nama: string
  ambang: number
  akurasi: number
  macro_f1: number
  recall_sedang: number
  auc_tinggi: number
  catatan: string
  porsi_diputuskan?: number
  akurasi_diputuskan?: number
}

export interface TitikRingkas {
  id: number
  kode: string
  nama: string
  lat: number
  lon: number
  scene: string
  dibuat: string
  insiden_id: number
  insiden: string
  klasifikasi_id: number
  /** Kelas efektif: keputusan ahli terakhir bila ada, selain itu kelas model. */
  kelas: Kelas
  kelas_model: Kelas
  dikoreksi: boolean
  keyakinan: number
  status: StatusKlasifikasi
  label_referensi: Kelas
  dnbr: number
}

export interface TitikTerbaru {
  id: number
  kode: string
  nama: string
  lat: number
  lon: number
  insiden: string
  kelas: Kelas
  kelas_model: Kelas
  dikoreksi: boolean
  keyakinan: number
  status: StatusKlasifikasi
}

export interface DashboardData {
  pengguna: User
  statistik: {
    kejadian: number
    titik: number
    menunggu: number
    terverifikasi: number
    tinggi: number
  }
  insiden: Insiden[]
  distribusi: Distribusi[]
  sebaran: Array<{ kode: string } & Record<Kelas, number>>
  terbaru: TitikTerbaru[]
  model: ModelInfo
}

export interface TitikInsiden extends TitikRingkas {
  probabilitas: Record<Kelas, number>
  modis: number
  model: string
}

export interface DetailInsiden extends Omit<Insiden, 'titik'> {
  distribusi: Distribusi[]
  menunggu: number
  scene_info: SceneInfo
  titik: TitikInsiden[]
}

export interface VerifikasiRecord {
  id: number
  classification_id: number
  user_id: number
  kelas_final: Kelas
  catatan: string
  keputusan: 'dikonfirmasi' | 'dikoreksi'
  dibuat: string
  ahli: string
}

export interface DetailTitik {
  id: number
  kode: string
  nama: string
  lat: number
  lon: number
  scene: string
  catatan: string
  dibuat: string
  insiden_id: number
  insiden: string
  insiden_nama: string
  provinsi: string
  tahun: number
  klasifikasi_id: number
  kelas: Kelas
  kelas_model: Kelas
  dikoreksi: boolean
  probabilitas: Record<Kelas, number>
  keyakinan: number
  status: StatusKlasifikasi
  label_referensi: Kelas
  dnbr: number
  modis: number
  model: string
  diklasifikasi: string
  verifikasi: VerifikasiRecord[]
  scene_info: SceneInfo
}

export interface AntreanItem {
  klasifikasi_id: number
  kelas: Kelas
  keyakinan: number
  probabilitas: Record<Kelas, number>
  status: StatusKlasifikasi
  label_referensi: Kelas
  dnbr: number
  modis: number
  dibuat: string
  point_id: number
  kode: string
  nama: string
  lat: number
  lon: number
  insiden: string
  kelas_final: Kelas | null
  catatan_verifikasi: string | null
  keputusan: 'dikonfirmasi' | 'dikoreksi' | null
  ahli: string | null
  diverifikasi: string | null
}

export interface VerifikasiData {
  pengguna: User
  menunggu: number
  daftar: AntreanItem[]
}

export interface SceneArea extends SceneInfo {
  contoh: { lat: number; lon: number; kode: string } | null
}

export interface TitikDuplikatDetail {
  kode: 'titik_duplikat'
  titik_ada: string
  jarak_m: number
}

export interface TitikBaruHasil {
  id: number
  kode: string
  nama: string
  klasifikasi_id: number
  kelas: Kelas
  keyakinan: number
  status: StatusKlasifikasi
  scene: string
}
