"""SQLite: skema, akun demo, dan penyemaian titik dari citra asli."""

import hashlib
import json
import os
import random
import sqlite3
import secrets
import time
from pathlib import Path

import numpy as np
import utm

from . import scenes
from .model import AMBANG_KEYAKINAN, KELAS, MODEL_NAMA, klasifikasi_patch

import os
from pathlib import Path

DB_PATH = Path(
    os.environ.get(
        "SIPAKARHUTLA_DB",
        "/tmp/sipakarhutla.db"
        if os.environ.get("VERCEL")
        else str(Path(__file__).resolve().parent / "data" / "sipakarhutla.db"),
    )
)

SKEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  nama TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('petugas','ahli')),
  password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  dibuat TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS incidents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kode TEXT UNIQUE NOT NULL,
  nama TEXT NOT NULL,
  tahun INTEGER NOT NULL,
  provinsi TEXT NOT NULL,
  lat REAL NOT NULL,
  lon REAL NOT NULL,
  cakupan_ha REAL NOT NULL,
  scene TEXT NOT NULL,
  ringkasan TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS points (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  insiden_id INTEGER NOT NULL REFERENCES incidents(id),
  kode TEXT UNIQUE NOT NULL,
  nama TEXT NOT NULL,
  lat REAL NOT NULL,
  lon REAL NOT NULL,
  scene TEXT NOT NULL,
  catatan TEXT NOT NULL,
  dibuat TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS classifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  point_id INTEGER UNIQUE NOT NULL REFERENCES points(id),
  kelas TEXT NOT NULL,
  probabilitas TEXT NOT NULL,
  keyakinan REAL NOT NULL,
  status TEXT NOT NULL,
  label_referensi TEXT NOT NULL,
  dnbr REAL NOT NULL,
  modis INTEGER NOT NULL,
  model TEXT NOT NULL,
  dibuat TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS verifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  classification_id INTEGER NOT NULL REFERENCES classifications(id),
  user_id INTEGER NOT NULL REFERENCES users(id),
  kelas_final TEXT NOT NULL,
  catatan TEXT NOT NULL,
  keputusan TEXT NOT NULL,
  dibuat TEXT NOT NULL
);
"""


def koneksi():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


def sekarang():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def hash_password(password: str, salt: bytes | None = None):
    salt = salt or os.urandom(16)
    kunci = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return f"{salt.hex()}${kunci.hex()}"


def cocok_password(password: str, tersimpan: str):
    salt_hex, _ = tersimpan.split("$", 1)
    return secrets.compare_digest(hash_password(password, bytes.fromhex(salt_hex)), tersimpan)


_initialized = False


def ensure_initialized():
    global _initialized
    if not _initialized:
        _initialized = True
        try:
            init_db()
        except Exception:
            _initialized = False
            raise


def init_db():
    with koneksi() as db:
        db.executescript(SKEMA)
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            db.executemany(
                "INSERT INTO users (username, nama, role, password_hash) VALUES (?,?,?,?)",
                [
                    ("petugas", "Rani Petugas Lapangan", "petugas", hash_password("petugas123")),
                    ("ahli", "Dr. Bima Ahli Karhutla", "ahli", hash_password("ahli123")),
                ],
            )
            _seed(db)


def _kandidat(scene, rng, per_kelas=4, maks_percobaan=4000):
    data = scenes.muat(scene)
    k = data.kelas
    rgb = data.rgb
    hasil = {0: [], 1: [], 2: []}
    dipakai = set()
    percobaan = 0
    while percobaan < maks_percobaan and any(len(v) < per_kelas for v in hasil.values()):
        percobaan += 1
        baris = rng.randrange(24, scene.tinggi - 24)
        kolom = rng.randrange(24, scene.lebar - 24)
        if (baris // 6, kolom // 6) in dipakai:
            continue
        if k[baris, kolom] not in (1, 2, 3):
            continue
        win_k = k[baris - 15 : baris + 16, kolom - 15 : kolom + 16]
        win_rgb = rgb[baris - 15 : baris + 16, kolom - 15 : kolom + 16]
        valid = (win_k > 0) & (win_rgb.sum(axis=-1) > 0)
        if valid.mean() < scenes.MIN_VALID:
            continue
        suara = np.bincount(win_k[valid], minlength=4)
        label = int(np.argmax(suara[1:]))
        if suara[1:].sum() == 0 or suara[label + 1] / valid.sum() < 0.5:
            continue
        if len(hasil[label]) >= per_kelas:
            continue
        try:
            titik = scenes.ekstrak(scene, baris, kolom)
        except (scenes.TitikDiLuar, scenes.KualitasRendah):
            continue
        dipakai.add((baris // 6, kolom // 6))
        hasil[titik["label_index"]].append(titik)
    return [(t["label_index"], t) for daftar in hasil.values() for t in daftar]


def _seed(db):
    rng = random.Random(20231123)
    for scene in scenes.SCENES.values():
        kandidat = _kandidat(scene, rng)
        if not kandidat:
            continue
        prediksi = klasifikasi_patch([t["patch"] for _, t in kandidat])

        pilihan = []
        for label in (0, 1, 2):
            kelompok = [
                (i, t) for i, (lb, t) in enumerate(kandidat) if lb == label
            ]
            if not kelompok:
                continue
            urut = sorted(kelompok, key=lambda it: prediksi[it[0]]["keyakinan"])
            pilihan.append(urut[0])
            if len(urut) > 2:
                pilihan.append(urut[-1])
        if not pilihan:
            continue

        pusat_lat, pusat_lon = utm.to_latlon(
            scene.x0 + scene.lebar * scene.pixel / 2,
            scene.y0 - scene.tinggi * scene.pixel / 2,
            scene.zona,
            northern=scene.utara,
        )
        insiden_id = db.execute(
            "INSERT INTO incidents (kode, nama, tahun, provinsi, lat, lon, cakupan_ha, scene, ringkasan)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (
                scene.kode,
                f"Area {scene.kode}",
                scene.tahun,
                "Kalimantan",
                round(pusat_lat, 6),
                round(pusat_lon, 6),
                scene.cakupan_ha,
                scene.kode,
                "Area contoh dari dataset Sipakarhutla. Prediksi dihitung model CNN pada citra Sentinel-2 asli; "
                "titik dipilih dari patch berlabel dNBR untuk keperluan demo.",
            ),
        ).lastrowid

        for urutan, (idx, titik) in enumerate(pilihan, start=1):
            hasil = prediksi[idx]
            lat, lon = utm.to_latlon(
                scene.x0 + (titik["kolom"] + 0.5) * scene.pixel,
                scene.y0 - (titik["baris"] + 0.5) * scene.pixel,
                scene.zona,
                northern=scene.utara,
            )
            kode = f"{scene.kode}-{urutan:02d}"
            point_id = db.execute(
                "INSERT INTO points (insiden_id, kode, nama, lat, lon, scene, catatan, dibuat)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    insiden_id,
                    kode,
                    f"Titik {kode}",
                    round(lat, 6),
                    round(lon, 6),
                    scene.kode,
                    "Titik contoh pada citra "
                    f"{scene.kode}; label referensi dNBR: {KELAS[titik['label_index']]}.",
                    sekarang(),
                ),
            ).lastrowid
            status = "menunggu_ahli" if hasil["keyakinan"] < AMBANG_KEYAKINAN else "terverifikasi_model"
            db.execute(
                "INSERT INTO classifications (point_id, kelas, probabilitas, keyakinan, status,"
                " label_referensi, dnbr, modis, model, dibuat)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    point_id,
                    hasil["kelas"],
                    json.dumps(hasil["probabilitas"]),
                    hasil["keyakinan"],
                    status,
                    KELAS[titik["label_index"]],
                    titik["dnbr"],
                    1 if titik["modis"] else 0,
                    MODEL_NAMA,
                    sekarang(),
                ),
            )


def buat_sesi(db, user_id):
    token = secrets.token_urlsafe(32)
    db.execute("INSERT INTO sessions (token, user_id, dibuat) VALUES (?,?,?)", (token, user_id, sekarang()))
    return token


def hapus_sesi(db, token):
    db.execute("DELETE FROM sessions WHERE token = ?", (token,))
