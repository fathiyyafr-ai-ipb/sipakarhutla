"""SQLite: skema, akun demo, dan penyemaian titik dari citra asli."""

import base64
import hashlib
import hmac
import json
import os
import random
import sqlite3
import secrets
import time
from pathlib import Path

import numpy as np
import utm

try:
    from . import scenes
    from .model import AMBANG_KEYAKINAN, KELAS, MODEL_NAMA, klasifikasi_patch
except ImportError:
    import scenes
    from model import AMBANG_KEYAKINAN, KELAS, MODEL_NAMA, klasifikasi_patch

import math
import re

DATA_DIR = Path(__file__).resolve().parent / "data"
NAMA_TITIK_CONTOH = DATA_DIR / "nama_titik_contoh.json"

# Dua titik yang berjarak kurang dari ini (meter) dianggap duplikat.
JARAK_DUPLIKAT_M = 30
# Berapa kali pembuatan kode + INSERT diulang bila bentrok UNIQUE pada points.kode.
MAKS_PERCOBAAN_KODE = 3
# Awalan kode untuk titik yang tidak terkait kejadian mana pun.
AWALAN_TANPA_KEJADIAN = "T"

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
    nama_contoh = _muat_nama_contoh()
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

        for idx, titik in pilihan:
            lat, lon = utm.to_latlon(
                scene.x0 + (titik["kolom"] + 0.5) * scene.pixel,
                scene.y0 - (titik["baris"] + 0.5) * scene.pixel,
                scene.zona,
                northern=scene.utara,
            )
            simpan_titik(
                db,
                insiden_id=insiden_id,
                kode_insiden=scene.kode,
                nama=lambda kode: nama_contoh.get(kode, "").strip() or f"Titik contoh {kode}",
                lat=round(lat, 6),
                lon=round(lon, 6),
                scene=scene.kode,
                catatan="Titik contoh pada citra "
                f"{scene.kode}; label referensi dNBR: {KELAS[titik['label_index']]}.",
                hasil=prediksi[idx],
                titik=titik,
            )


def _muat_nama_contoh():
    """Nama daerah titik seed (kode -> nama), diisi manual. Tanpa geocoding."""
    try:
        data = json.loads(NAMA_TITIK_CONTOH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k): v for k, v in data.items() if isinstance(v, str)}


# ---------- kode titik & duplikat ----------

class TitikDuplikat(Exception):
    def __init__(self, titik_ada: str, jarak_m: float):
        super().__init__(f"Titik berdekatan dengan {titik_ada} ({jarak_m} m).")
        self.titik_ada = titik_ada
        self.jarak_m = jarak_m


def kode_berikutnya(db, insiden_id, kode_insiden):
    """Kode titik berikutnya: '<kode_insiden>-NN', NN = urutan terbesar + 1.

    Memakai angka terbesar (bukan COUNT) supaya tidak bentrok bila ada titik yang
    dihapus. Titik tanpa kejadian memakai awalan 'T' dengan urutan sendiri.
    """
    awalan = kode_insiden if insiden_id is not None and kode_insiden else AWALAN_TANPA_KEJADIAN
    pola = re.compile(rf"^{re.escape(awalan)}-(\d+)$")
    terbesar = 0
    for (kode,) in db.execute(
        "SELECT kode FROM points WHERE kode LIKE ? ESCAPE '\\'",
        (awalan.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "-%",),
    ):
        cocok = pola.match(kode)
        if cocok:
            terbesar = max(terbesar, int(cocok.group(1)))
    return f"{awalan}-{terbesar + 1:02d}"


def jarak_m(lat1, lon1, lat2, lon2):
    """Jarak haversine dalam meter."""
    r = 6_371_008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def cari_titik_dekat(db, lat, lon, batas_m=None):
    """Titik terdekat dalam jarak JARAK_DUPLIKAT_M, atau None.

    Hasil: {"id", "kode", "jarak_m"}.
    """
    batas_m = JARAK_DUPLIKAT_M if batas_m is None else batas_m
    # Saring kasar dengan kotak lintang/bujur, lalu hitung haversine.
    dlat = batas_m / 111_000 * 1.5
    dlon = dlat / max(math.cos(math.radians(lat)), 0.01)
    terdekat = None
    for row in db.execute(
        "SELECT id, kode, lat, lon FROM points"
        " WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?",
        (lat - dlat, lat + dlat, lon - dlon, lon + dlon),
    ):
        d = jarak_m(lat, lon, row["lat"], row["lon"])
        if d < batas_m and (terdekat is None or d < terdekat["jarak_m"]):
            terdekat = {"id": row["id"], "kode": row["kode"], "jarak_m": d}
    if terdekat:
        terdekat["jarak_m"] = round(terdekat["jarak_m"], 1)
    return terdekat


def simpan_titik(
    db, *, insiden_id, kode_insiden, nama, lat, lon, scene, catatan, hasil, titik, cek_duplikat=False
):
    """Buat kode + INSERT titik dan klasifikasinya secara atomik.

    `nama` boleh string atau fungsi kode -> nama. Bila koneksi belum dalam
    transaksi, dipakai BEGIN IMMEDIATE (kunci tulis diambil sebelum kode dihitung);
    bila sudah (mis. saat seed), dipakai SAVEPOINT. IntegrityError pada points.kode
    diulang paling banyak MAKS_PERCOBAAN_KODE kali.

    Hasil: (point_id, kode, klasifikasi_id, status).
    """
    milik_sendiri = not db.in_transaction
    for percobaan in range(1, MAKS_PERCOBAAN_KODE + 1):
        db.execute("BEGIN IMMEDIATE" if milik_sendiri else "SAVEPOINT simpan_titik")
        try:
            if cek_duplikat:
                dekat = cari_titik_dekat(db, lat, lon)
                if dekat:
                    raise TitikDuplikat(dekat["kode"], dekat["jarak_m"])
            kode = kode_berikutnya(db, insiden_id, kode_insiden)
            point_id = db.execute(
                "INSERT INTO points (insiden_id, kode, nama, lat, lon, scene, catatan, dibuat)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    insiden_id,
                    kode,
                    nama(kode) if callable(nama) else nama,
                    lat,
                    lon,
                    scene,
                    catatan,
                    sekarang(),
                ),
            ).lastrowid
            status = "menunggu_ahli" if hasil["keyakinan"] < AMBANG_KEYAKINAN else "terverifikasi_model"
            klasifikasi_id = db.execute(
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
            ).lastrowid
        except BaseException as exc:
            if milik_sendiri:
                db.rollback()
            else:
                db.execute("ROLLBACK TO simpan_titik")
                db.execute("RELEASE simpan_titik")
            bentrok_kode = isinstance(exc, sqlite3.IntegrityError) and "points.kode" in str(exc)
            if bentrok_kode and percobaan < MAKS_PERCOBAAN_KODE:
                continue
            raise
        if milik_sendiri:
            db.commit()
        else:
            db.execute("RELEASE simpan_titik")
        return point_id, kode, klasifikasi_id, status


# ---------- HMAC stateless token (tidak butuh DB) ----------

_SECRET_KEY = os.environ.get("SESSION_SECRET", "sipakarhutla-dev-secret-change-in-prod")
_SESSION_TTL = 7 * 24 * 3600  # 7 hari


def buat_token(user_dict: dict) -> str:
    """Buat signed token dari data user. Tidak menyimpan apapun ke DB."""
    payload = json.dumps({
        "id": user_dict["id"],
        "username": user_dict["username"],
        "nama": user_dict["nama"],
        "role": user_dict["role"],
        "exp": int(time.time()) + _SESSION_TTL,
    }, ensure_ascii=False, separators=(",", ":"))
    b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    tanda = hmac.new(_SECRET_KEY.encode(), b64.encode(), "sha256").hexdigest()
    return f"{b64}.{tanda}"


def verifikasi_token(token: str) -> dict | None:
    """Verifikasi signed token. Tidak ada query ke DB."""
    try:
        b64, tanda = token.rsplit(".", 1)
    except ValueError:
        return None
    expected = hmac.new(_SECRET_KEY.encode(), b64.encode(), "sha256").hexdigest()
    if not secrets.compare_digest(tanda, expected):
        return None
    # padding base64
    pad = 4 - len(b64) % 4
    try:
        payload = json.loads(base64.urlsafe_b64decode(b64 + "=" * pad))
    except Exception:
        return None
    if payload.get("exp", 0) < int(time.time()):
        return None
    return payload


# ---------- fungsi lama (dipertahankan sebagai no-op agar tidak error) ----------

def buat_sesi(db, user_id):
    """Deprecated: gunakan buat_token() sebagai gantinya."""
    return buat_token({"id": user_id, "username": "", "nama": "", "role": "petugas"})


def hapus_sesi(db, token):
    """Deprecated: token HMAC tidak disimpan di DB, tidak perlu dihapus."""
    pass
