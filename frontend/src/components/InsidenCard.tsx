import { Link } from 'react-router-dom'
import { ArrowUpRight, MapPin } from 'lucide-react'
import type { Insiden } from '../types'
import { KELAS } from '../types'
import { StatusInsidenBadge } from './ui'

export default function InsidenCard({ insiden }: { insiden: Insiden }) {
  const total = Math.max(1, insiden.rendah + insiden.sedang + insiden.tinggi)
  const jumlah = { Rendah: insiden.rendah, Sedang: insiden.sedang, Tinggi: insiden.tinggi }

  return (
    <Link to={`/insiden/${insiden.id}`} className="insiden-card">
      <div className="insiden-thumb">
        <img
          src={`/api/insiden/${insiden.id}/thumbnail`}
          alt={`Citra Sentinel-2 area ${insiden.kode}`}
          loading="lazy"
        />
        <StatusInsidenBadge status={insiden.status} />
        <span className="thumb-year">{insiden.tahun}</span>
      </div>
      <div className="insiden-body">
        <div className="insiden-title">
          <h3>{insiden.nama}</h3>
          <span>{insiden.kode}</span>
        </div>
        <p className="insiden-meta">
          <MapPin size={14} /> {insiden.provinsi} · {insiden.cakupan_ha.toLocaleString('id-ID')} ha
        </p>
        <div className="class-split" aria-hidden="true">
          {KELAS.map((k) => (
            <span key={k} className={`split-${k.toLowerCase()}`} style={{ width: `${(jumlah[k] / total) * 100}%` }} />
          ))}
        </div>
        <div className="insiden-foot">
          <span>
            {insiden.titik} titik · {insiden.tinggi} tinggi
          </span>
          <span className="link">
            Detail <ArrowUpRight size={14} />
          </span>
        </div>
      </div>
    </Link>
  )
}
