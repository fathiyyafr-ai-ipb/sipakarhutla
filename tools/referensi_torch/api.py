"""API Sipakarhutla (FastAPI).

Menjalankan:
    uvicorn api:create_app --factory --reload
lalu buka http://127.0.0.1:8000/docs untuk mencoba semua endpoint.

Variabel lingkungan (opsional):
    SIPAKARHUTLA_DATA   folder berisi model_indo.pt dan berkas K*_data.tif   (bawaan: ./data)
    SIPAKARHUTLA_DB     berkas SQLite                                          (bawaan: ./sipakarhutla.db)
    SIPAKARHUTLA_CORS   daftar asal frontend dipisah koma                      (bawaan: *, ketatkan saat produksi)
"""
from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from inferensi import (CATATAN, NAMA_KELAS, DiLuarArea, GalatInferensi, KejadianTidakDikenal,
                       KoordinatTidakValid, Penduga)

SKEMA = """
CREATE TABLE IF NOT EXISTS titik (
  id TEXT PRIMARY KEY, kejadian_id TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL,
  status TEXT NOT NULL, alasan TEXT, kelas TEXT, kelas_model TEXT, keyakinan REAL,
  p_rendah REAL, p_sedang REAL, p_tinggi REAL, piksel_valid REAL, ambang REAL,
  dibuat_pada TEXT, diverifikasi_pada TEXT, catatan_ahli TEXT, dikoreksi INTEGER
);
CREATE INDEX IF NOT EXISTS idx_titik_kejadian ON titik(kejadian_id, status);
"""


class TitikBaru(BaseModel):
    kejadian_id: str = Field(..., examples=["K003"])
    lat: float = Field(..., ge=-90, le=90, examples=[-2.78])
    lon: float = Field(..., ge=-180, le=180, examples=[114.09])


class Verifikasi(BaseModel):
    kelas: str = Field(..., examples=["Tinggi"])
    catatan: Optional[str] = None


def _baris_ke_json(r: sqlite3.Row) -> dict:
    peluang = None if r["p_rendah"] is None else {
        "Rendah": r["p_rendah"], "Sedang": r["p_sedang"], "Tinggi": r["p_tinggi"]}
    return {
        "titik_id": r["id"], "kejadian_id": r["kejadian_id"],
        "koordinat": {"lat": r["lat"], "lon": r["lon"]},
        "status": r["status"], "alasan": r["alasan"],
        "kelas": r["kelas"], "kelas_model": r["kelas_model"],
        "keyakinan": r["keyakinan"], "peluang": peluang, "ambang": r["ambang"],
        "piksel_valid": r["piksel_valid"], "dikoreksi_ahli": None if r["dikoreksi"] is None else bool(r["dikoreksi"]),
        "catatan_ahli": r["catatan_ahli"],
        "dibuat_pada": r["dibuat_pada"], "diverifikasi_pada": r["diverifikasi_pada"],
        "pratinjau_citra": f"/titik/{r['id']}/pratinjau.png", "catatan": CATATAN,
    }


def create_app(penduga: Optional[Penduga] = None, db_path: Optional[str] = None) -> FastAPI:
    folder = os.environ.get("SIPAKARHUTLA_DATA", "./data")
    if penduga is None:
        penduga = Penduga(os.path.join(folder, "model_indo.pt"), folder)
    db_path = db_path or os.environ.get("SIPAKARHUTLA_DB", "./sipakarhutla.db")

    app = FastAPI(title="Sipakarhutla API", version="0.1.0",
                  description="Taksiran tingkat keparahan pascakarhutla dari citra satelit.")
    asal = [a.strip() for a in os.environ.get("SIPAKARHUTLA_CORS", "*").split(",")]
    app.add_middleware(CORSMiddleware, allow_origins=asal, allow_methods=["*"], allow_headers=["*"])

    def db():
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        return con

    with db() as con:
        con.executescript(SKEMA)

    @app.get("/kesehatan")
    def kesehatan():
        return {"status": "ok", "model_dimuat": True, "jumlah_kejadian": len(penduga.kejadian), "ambang": penduga.ambang}

    @app.get("/kejadian")
    def daftar_kejadian():
        with db() as con:
            jml = dict(con.execute("SELECT kejadian_id, COUNT(*) FROM titik GROUP BY kejadian_id").fetchall())
        return [{"id": k["id"], "nama": k["nama"], "kotak": k["kotak"], "jumlah_titik": jml.get(k["id"], 0)}
                for k in penduga.kejadian.values()]

    @app.post("/titik", status_code=201)
    def tambah_titik(t: TitikBaru):
        try:
            h = penduga.prediksi(t.kejadian_id, t.lat, t.lon)
        except KejadianTidakDikenal as e:
            raise HTTPException(404, {"kode": e.kode, "pesan": str(e)})
        except (DiLuarArea, KoordinatTidakValid) as e:
            raise HTTPException(422, {"kode": e.kode, "pesan": str(e)})
        tid = "T-" + uuid.uuid4().hex[:8]
        p = h["peluang"] or {}
        with db() as con:
            con.execute(
                "INSERT INTO titik (id,kejadian_id,lat,lon,status,alasan,kelas,kelas_model,keyakinan,p_rendah,p_sedang,p_tinggi,"
                "piksel_valid,ambang,dibuat_pada) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (tid, t.kejadian_id, t.lat, t.lon, h["status"], h["alasan"], h["kelas"], h["kelas_model"], h["keyakinan"],
                 p.get("Rendah"), p.get("Sedang"), p.get("Tinggi"), h["piksel_valid"], h["ambang"],
                 datetime.now(timezone.utc).isoformat(timespec="seconds")))
            r = con.execute("SELECT * FROM titik WHERE id=?", (tid,)).fetchone()
        return _baris_ke_json(r)

    @app.get("/titik")
    def daftar_titik(kejadian_id: Optional[str] = None, status: Optional[str] = None,
                     batas: int = Query(200, ge=1, le=1000)):
        q, a = "SELECT * FROM titik WHERE 1=1", []
        if kejadian_id: q += " AND kejadian_id=?"; a.append(kejadian_id)
        if status: q += " AND status=?"; a.append(status)
        with db() as con:
            return [_baris_ke_json(r) for r in con.execute(q + " ORDER BY dibuat_pada DESC LIMIT ?", (*a, batas))]

    @app.get("/titik/{titik_id}")
    def detail_titik(titik_id: str):
        with db() as con:
            r = con.execute("SELECT * FROM titik WHERE id=?", (titik_id,)).fetchone()
        if r is None:
            raise HTTPException(404, {"kode": "titik_tidak_ada", "pesan": "Titik tidak ditemukan"})
        return _baris_ke_json(r)

    @app.get("/titik/{titik_id}/pratinjau.png")
    def pratinjau(titik_id: str):
        with db() as con:
            r = con.execute("SELECT kejadian_id, lat, lon FROM titik WHERE id=?", (titik_id,)).fetchone()
        if r is None:
            raise HTTPException(404, {"kode": "titik_tidak_ada", "pesan": "Titik tidak ditemukan"})
        return Response(penduga.pratinjau_png(r["kejadian_id"], r["lat"], r["lon"]), media_type="image/png")

    @app.get("/antrean-ahli")
    def antrean_ahli(kejadian_id: Optional[str] = None):
        return daftar_titik(kejadian_id=kejadian_id, status="menunggu_ahli", batas=1000)

    @app.post("/titik/{titik_id}/verifikasi")
    def verifikasi(titik_id: str, v: Verifikasi):
        if v.kelas not in NAMA_KELAS:
            raise HTTPException(422, {"kode": "kelas_tidak_valid", "pesan": f"Kelas harus salah satu dari {NAMA_KELAS}"})
        with db() as con:
            r = con.execute("SELECT * FROM titik WHERE id=?", (titik_id,)).fetchone()
            if r is None:
                raise HTTPException(404, {"kode": "titik_tidak_ada", "pesan": "Titik tidak ditemukan"})
            koreksi = int(r["kelas_model"] is not None and r["kelas_model"] != v.kelas)
            con.execute("UPDATE titik SET status='terverifikasi', kelas=?, dikoreksi=?, catatan_ahli=?, diverifikasi_pada=? WHERE id=?",
                        (v.kelas, koreksi, v.catatan, datetime.now(timezone.utc).isoformat(timespec="seconds"), titik_id))
            r = con.execute("SELECT * FROM titik WHERE id=?", (titik_id,)).fetchone()
        return _baris_ke_json(r)

    @app.get("/kejadian/{kejadian_id}/ringkasan")
    def ringkasan(kejadian_id: str):
        if kejadian_id not in penduga.kejadian:
            raise HTTPException(404, {"kode": "kejadian_tidak_dikenal", "pesan": f"Kejadian '{kejadian_id}' tidak dikenal"})
        jumlah = {k: 0 for k in NAMA_KELAS}; jumlah["menunggu_ahli"] = 0
        with db() as con:
            for r in con.execute("SELECT status, kelas, COUNT(*) n FROM titik WHERE kejadian_id=? GROUP BY status, kelas", (kejadian_id,)):
                if r["status"] == "menunggu_ahli": jumlah["menunggu_ahli"] += r["n"]
                elif r["kelas"] in jumlah: jumlah[r["kelas"]] += r["n"]
        jumlah["total"] = sum(jumlah.values())
        return {"kejadian_id": kejadian_id, "jumlah": jumlah}

    return app
