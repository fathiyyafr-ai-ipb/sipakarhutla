import type { ReactNode } from 'react'
import { AlertTriangle, CheckCircle2, Inbox } from 'lucide-react'
import type { Kelas, StatusInsiden, StatusKlasifikasi } from '../types'
import { WARNA_KELAS } from '../types'

export function KelasBadge({ kelas, kecil = false }: { kelas: Kelas; kecil?: boolean }) {
  return (
    <span className={`badge badge-kelas ${kecil ? 'badge-kecil' : ''}`} data-kelas={kelas}>
      <i />
      {kelas}
    </span>
  )
}

export function StatusKlasifikasiBadge({ status }: { status: StatusKlasifikasi }) {
  if (status === 'menunggu_ahli')
    return <span className="badge badge-menunggu">Menunggu ahli</span>
  if (status === 'terverifikasi') return <span className="badge badge-ok">Terverifikasi</span>
  return <span className="badge badge-netral">Estimasi model</span>
}

export function StatusInsidenBadge({ status }: { status: StatusInsiden }) {
  return <span className={`badge badge-status status-${status.toLowerCase()}`}>{status}</span>
}

export function ConfidenceBar({ value, kelas }: { value: number; kelas: Kelas }) {
  return (
    <div className="confidence">
      <div className="confidence-track">
        <span style={{ width: `${Math.max(2, value * 100)}%`, background: WARNA_KELAS[kelas] }} />
      </div>
      <b>{(value * 100).toFixed(1)}%</b>
    </div>
  )
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string
  title: string
  description?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="page-header">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p className="page-desc">{description}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  )
}

export function Loader({ label = 'Memuat data…' }: { label?: string }) {
  return (
    <div className="loader" role="status">
      <span className="spinner" />
      <p>{label}</p>
    </div>
  )
}

export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="skeleton" aria-hidden="true">
      {Array.from({ length: rows }).map((_, i) => (
        <span key={i} style={{ width: `${88 - i * 9}%` }} />
      ))}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state-box state-error">
      <AlertTriangle size={22} />
      <div>
        <strong>Tidak bisa memuat data</strong>
        <p>{message}</p>
      </div>
      {onRetry && (
        <button className="btn btn-ghost" onClick={onRetry}>
          Coba lagi
        </button>
      )}
    </div>
  )
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="state-box state-empty">
      <Inbox size={24} />
      <div>
        <strong>{title}</strong>
        <p>{description}</p>
      </div>
      {action}
    </div>
  )
}

export function Notice({
  tone = 'info',
  children,
}: {
  tone?: 'info' | 'success' | 'warning'
  children: ReactNode
}) {
  return (
    <div className={`notice notice-${tone}`}>
      {tone === 'success' ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
      <div>{children}</div>
    </div>
  )
}

export function Avatar({ nama }: { nama: string }) {
  const inisial = nama
    .split(' ')
    .filter((k) => k.length > 1)
    .slice(0, 2)
    .map((k) => k[0])
    .join('')
    .toUpperCase()
  return <span className="avatar">{inisial}</span>
}

export function formatTanggal(iso: string | null | undefined) {
  if (!iso) return '—'
  const tanggal = new Date(iso)
  if (Number.isNaN(tanggal.getTime())) return iso
  return new Intl.DateTimeFormat('id-ID', { day: 'numeric', month: 'short', year: 'numeric' }).format(
    tanggal,
  )
}

export function formatKoordinat(lat: number, lon: number) {
  return `${lat.toFixed(4)}°, ${lon.toFixed(4)}°`
}
