"""API Sipakarhutla + penyajian SPA React."""

import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, Response as RawResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import scenes, store
from .model import AMBANG_KEYAKINAN, KELAS, MODEL_NAMA, klasifikasi_patch, model

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend" / "dist"
DATA_DIR = Path(os.environ.get("SIPAKARHUTLA_DATA", str(Path(__file__).resolve().parent / "data")))
RINGKASAN = DATA_DIR / "ringkasan_indo.json"
COOKIE = "siparhutla_sesi"
UMUR_SESI = timedelta(days=7)

MODEL_INFO = {
    "nama": MODEL_NAMA,
    "ambang": AMBANG_KEYAKINAN,
    "akurasi": 0.841,
    "macro_f1": 0.709,
    "recall_sedang": 0.626,
    "auc_tinggi": 0.974,
    "catatan": "Skor resmi dari uji leave-one-event-out di enam kejadian Kalimantan. "
    "Label berasal dari dNBR (satelit), bukan pengamatan lapangan.",
}
try:
    _ringkasan = json.loads(RINGKASAN.read_text(encoding="utf-8"))
    _cnn = next(r for r in _ringkasan["tabel_model"] if r["model"].startswith("CNN dari nol"))
    MODEL_INFO.update(
        akurasi=_cnn["akurasi"],
        macro_f1=_cnn["macro_F1"],
        recall_sedang=_cnn["recall_Sedang"],
        auc_tinggi=_cnn["AUC_Tinggi"],
    )
    _amb = next(r for r in _ringkasan["ambang"] if abs(r["ambang"] - AMBANG_KEYAKINAN) < 1e-6)
    MODEL_INFO["porsi_diputuskan"] = _amb["persen_diputuskan_model"]
    MODEL_INFO["akurasi_diputuskan"] = _amb["akurasi_diputuskan"]
except (OSError, ValueError, KeyError, StopIteration):
    pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init_db()
    model()
    yield


app = FastAPI(title="Sipakarhutla API", lifespan=lifespan)

_thumb_cache: dict[str, bytes] = {}


# ---------- auth ----------

class LoginBody(BaseModel):
    username: str
    password: str


def user_dari(request: Request):
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    with store.koneksi() as db:
        row = db.execute(
            "SELECT u.id, u.username, u.nama, u.role, s.dibuat FROM sessions s"
            " JOIN users u ON u.id = s.user_id WHERE s.token = ?",
            (token,),
        ).fetchone()
    if not row:
        return None
    try:
        if datetime.fromisoformat(row["dibuat"]) + UMUR_SESI < datetime.now():
            return None
    except ValueError:
        return None
    return dict(row)


def wajib_user(request: Request):
    user = user_dari(request)
    if not user:
        raise HTTPException(401, "Sesi berakhir. Silakan masuk kembali.")
    return user


def wajib_ahli(request: Request):
    user = wajib_user(request)
    if user["role"] != "ahli":
        raise HTTPException(403, "Hanya akun ahli yang dapat memverifikasi klasifikasi.")
    return user


@app.post("/api/auth/login")
def login(body: LoginBody, response: Response):
    with store.koneksi() as db:
        row = db.execute("SELECT * FROM users WHERE username = ?", (body.username.strip(),)).fetchone()
        if not row or not store.cocok_password(body.password, row["password_hash"]):
            raise HTTPException(401, "Nama pengguna atau kata sandi salah.")
        token = store.buat_sesi(db, row["id"])
    response.set_cookie(
        COOKIE, token, max_age=int(UMUR_SESI.total_seconds()), httponly=True, samesite="lax"
    )
    return {"id": row["id"], "username": row["username"], "nama": row["nama"], "role": row["role"]}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE)
    if token:
        with store.koneksi() as db:
            store.hapus_sesi(db, token)
    response.delete_cookie(COOKIE)
    return {"ok": True}


@app.get("/api/me")
def me(request: Request):
    user = user_dari(request)
    if not user:
        raise HTTPException(401, "Belum masuk.")
    return user


# ---------- data ----------

STATUS_INSIDEN = ("Siaga", "Waspada", "Pantau")


def _status(tinggi, sedang):
    if tinggi:
        return "Siaga"
    if sedang:
        return "Waspada"
    return "Pantau"


def _insiden_rows(db, where="", params=()):
    rows = db.execute(
        "SELECT i.*, COUNT(p.id) AS titik,"
        " COALESCE(SUM(CASE WHEN c.kelas = 'Tinggi' THEN 1 ELSE 0 END), 0) AS tinggi,"
        " COALESCE(SUM(CASE WHEN c.kelas = 'Sedang' THEN 1 ELSE 0 END), 0) AS sedang,"
        " COALESCE(SUM(CASE WHEN c.kelas = 'Rendah' THEN 1 ELSE 0 END), 0) AS rendah"
        " FROM incidents i"
        " LEFT JOIN points p ON p.insiden_id = i.id"
        " LEFT JOIN classifications c ON c.point_id = p.id"
        f" {where} GROUP BY i.id ORDER BY i.kode",
        params,
    ).fetchall()
    hasil = []
    for r in rows:
        item = dict(r)
        item["status"] = _status(r["tinggi"], r["sedang"])
        item["lat"] = round(r["lat"], 5)
        item["lon"] = round(r["lon"], 5)
        hasil.append(item)
    return hasil


@app.get("/api/dashboard")
def dashboard(request: Request):
    user = wajib_user(request)
    with store.koneksi() as db:
        insiden = _insiden_rows(db)
        total_titik = db.execute("SELECT COUNT(*) FROM points").fetchone()[0]
        menunggu = db.execute(
            "SELECT COUNT(*) FROM classifications WHERE status = 'menunggu_ahli'"
        ).fetchone()[0]
        terverifikasi = db.execute(
            "SELECT COUNT(*) FROM classifications WHERE status = 'terverifikasi'"
        ).fetchone()[0]
        distribusi = [
            {"kelas": k, "jumlah": db.execute(
                "SELECT COUNT(*) FROM classifications WHERE kelas = ?", (k,)
            ).fetchone()[0]}
            for k in KELAS
        ]
        per_insiden = db.execute(
            "SELECT i.kode, c.kelas, COUNT(*) AS jumlah FROM classifications c"
            " JOIN points p ON p.id = c.point_id JOIN incidents i ON i.id = p.insiden_id"
            " GROUP BY i.kode, c.kelas"
        ).fetchall()
        terbaru = db.execute(
            "SELECT p.id, p.kode, p.nama, p.lat, p.lon, i.kode AS insiden, c.kelas, c.keyakinan, c.status"
            " FROM points p JOIN incidents i ON i.id = p.insiden_id"
            " JOIN classifications c ON c.point_id = p.id"
            " ORDER BY p.id DESC LIMIT 6"
        ).fetchall()
    sebaran = {}
    for r in per_insiden:
        sebaran.setdefault(r["kode"], {"kode": r["kode"], **{k: 0 for k in KELAS}})
        sebaran[r["kode"]][r["kelas"]] = r["jumlah"]
    return {
        "pengguna": user,
        "statistik": {
            "kejadian": len(insiden),
            "titik": total_titik,
            "menunggu": menunggu,
            "terverifikasi": terverifikasi,
            "tinggi": next((d["jumlah"] for d in distribusi if d["kelas"] == "Tinggi"), 0),
        },
        "insiden": insiden,
        "distribusi": distribusi,
        "sebaran": list(sebaran.values()),
        "terbaru": [dict(r) for r in terbaru],
        "model": MODEL_INFO,
    }


@app.get("/api/insiden")
def daftar_insiden(request: Request, q: str = "", status: str = ""):
    wajib_user(request)
    with store.koneksi() as db:
        rows = _insiden_rows(db)
    if q:
        kata = q.lower()
        rows = [
            r for r in rows
            if kata in r["kode"].lower() or kata in r["nama"].lower() or kata in r["provinsi"].lower()
        ]
    if status:
        rows = [r for r in rows if r["status"].lower() == status.lower()]
    return rows


@app.get("/api/insiden/{insiden_id}")
def detail_insiden(insiden_id: int, request: Request):
    wajib_user(request)
    with store.koneksi() as db:
        insiden = db.execute("SELECT * FROM incidents WHERE id = ?", (insiden_id,)).fetchone()
        if not insiden:
            raise HTTPException(404, "Kejadian tidak ditemukan.")
        titik = db.execute(
            "SELECT p.*, c.id AS klasifikasi_id, c.kelas, c.keyakinan, c.probabilitas, c.status,"
            " c.label_referensi, c.dnbr, c.modis, c.model"
            " FROM points p JOIN classifications c ON c.point_id = p.id"
            " WHERE p.insiden_id = ? ORDER BY p.kode",
            (insiden_id,),
        ).fetchall()
    data = dict(insiden)
    data["status"] = _status(
        sum(1 for t in titik if t["kelas"] == "Tinggi"),
        sum(1 for t in titik if t["kelas"] == "Sedang"),
    )
    data["titik"] = []
    for t in titik:
        item = dict(t)
        item["probabilitas"] = json.loads(t["probabilitas"])
        data["titik"].append(item)
    data["distribusi"] = [
        {"kelas": k, "jumlah": sum(1 for t in titik if t["kelas"] == k)} for k in KELAS
    ]
    data["menunggu"] = sum(1 for t in titik if t["status"] == "menunggu_ahli")
    data["scene_info"] = scenes.SCENES[data["scene"]].meta()
    return data


def _titik_rows(db, where, params):
    rows = db.execute(
        "SELECT p.id, p.kode, p.nama, p.lat, p.lon, p.scene, p.dibuat,"
        " i.id AS insiden_id, i.kode AS insiden,"
        " c.id AS klasifikasi_id, c.kelas, c.keyakinan, c.status, c.label_referensi, c.dnbr"
        " FROM points p JOIN incidents i ON i.id = p.insiden_id"
        " JOIN classifications c ON c.point_id = p.id"
        f" {where} ORDER BY p.kode",
        params,
    ).fetchall()
    return [
        {
            **dict(r),
            "lat": round(r["lat"], 5),
            "lon": round(r["lon"], 5),
            "keyakinan": round(r["keyakinan"], 4),
        }
        for r in rows
    ]


@app.get("/api/titik")
def daftar_titik(request: Request, insiden_id: int | None = None, kelas: str = "", status: str = ""):
    wajib_user(request)
    with store.koneksi() as db:
        rows = _titik_rows(db, "", ())
    if insiden_id:
        rows = [r for r in rows if r["insiden_id"] == insiden_id]
    if kelas:
        rows = [r for r in rows if r["kelas"].lower() == kelas.lower()]
    if status:
        rows = [r for r in rows if r["status"] == status]
    return rows


@app.get("/api/titik/{point_id}")
def detail_titik(point_id: int, request: Request):
    wajib_user(request)
    with store.koneksi() as db:
        row = db.execute(
            "SELECT p.*, i.kode AS insiden, i.id AS insiden_id, i.nama AS insiden_nama,"
            " i.provinsi, i.tahun,"
            " c.id AS klasifikasi_id, c.kelas, c.probabilitas, c.keyakinan, c.status,"
            " c.label_referensi, c.dnbr, c.modis, c.model, c.dibuat AS diklasifikasi"
            " FROM points p JOIN incidents i ON i.id = p.insiden_id"
            " JOIN classifications c ON c.point_id = p.id WHERE p.id = ?",
            (point_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Titik tidak ditemukan.")
        verifikasi = db.execute(
            "SELECT v.*, u.nama AS ahli FROM verifications v JOIN users u ON u.id = v.user_id"
            " WHERE v.classification_id = ? ORDER BY v.id DESC",
            (row["klasifikasi_id"],),
        ).fetchall()
    data = dict(row)
    data["probabilitas"] = json.loads(row["probabilitas"])
    data["lat"] = round(row["lat"], 5)
    data["lon"] = round(row["lon"], 5)
    data["verifikasi"] = [dict(v) for v in verifikasi]
    data["scene_info"] = scenes.SCENES[data["scene"]].meta()
    return data


class TitikBaru(BaseModel):
    nama: str = Field(min_length=3, max_length=120)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    insiden_id: int | None = None
    catatan: str = Field(default="", max_length=500)


@app.post("/api/titik")
def tambah_titik(body: TitikBaru, request: Request):
    user = wajib_user(request)
    with store.koneksi() as db:
        if body.insiden_id:
            insiden = db.execute("SELECT * FROM incidents WHERE id = ?", (body.insiden_id,)).fetchone()
            if not insiden:
                raise HTTPException(404, "Kejadian tidak ditemukan.")
            scene = scenes.SCENES[insiden["scene"]]
            posisi = scenes.baris_kolom(scene, body.lat, body.lon)
            if posisi is None:
                raise HTTPException(
                    400,
                    f"Koordinat berada di luar area citra {scene.kode}. "
                    f"Batas: {scene.lat_min:.4f}–{scene.lat_max:.4f} L, "
                    f"{scene.lon_min:.4f}–{scene.lon_max:.4f} B.",
                )
        else:
            scene, posisi = scenes.cari_scene(body.lat, body.lon)
            if scene is None:
                raise HTTPException(
                    400,
                    "Koordinat berada di luar enam area citra yang tersedia "
                    "(Kalimantan, 2019/2023).",
                )
        try:
            titik = scenes.ekstrak(scene, *posisi)
        except (scenes.TitikDiLuar, scenes.KualitasRendah) as exc:
            raise HTTPException(400, str(exc)) from exc
        hasil = klasifikasi_patch([titik["patch"]])[0]
        jumlah = db.execute("SELECT COUNT(*) FROM points").fetchone()[0]
        kode = f"T-{jumlah + 1:03d}"
        insiden_id = body.insiden_id or db.execute(
            "SELECT id FROM incidents WHERE scene = ?", (scene.kode,)
        ).fetchone()["id"]
        point_id = db.execute(
            "INSERT INTO points (insiden_id, kode, nama, lat, lon, scene, catatan, dibuat)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (
                insiden_id,
                kode,
                body.nama.strip(),
                body.lat,
                body.lon,
                scene.kode,
                body.catatan.strip() or f"Ditambahkan oleh {user['nama']}.",
                store.sekarang(),
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
                store.sekarang(),
            ),
        ).lastrowid
    return {
        "id": point_id,
        "kode": kode,
        "klasifikasi_id": klasifikasi_id,
        "kelas": hasil["kelas"],
        "keyakinan": hasil["keyakinan"],
        "status": status,
        "scene": scene.kode,
    }


@app.get("/api/verifikasi")
def daftar_verifikasi(request: Request):
    user = wajib_user(request)
    with store.koneksi() as db:
        rows = db.execute(
            "SELECT c.id AS klasifikasi_id, c.kelas, c.keyakinan, c.probabilitas, c.status,"
            " c.label_referensi, c.dnbr, c.modis, c.dibuat,"
            " p.id AS point_id, p.kode, p.nama, p.lat, p.lon, i.kode AS insiden,"
            " v.kelas_final, v.catatan AS catatan_verifikasi, v.keputusan, u.nama AS ahli,"
            " v.dibuat AS diverifikasi"
            " FROM classifications c JOIN points p ON p.id = c.point_id"
            " JOIN incidents i ON i.id = p.insiden_id"
            " LEFT JOIN verifications v ON v.id = ("
            "   SELECT id FROM verifications WHERE classification_id = c.id ORDER BY id DESC LIMIT 1)"
            " LEFT JOIN users u ON u.id = v.user_id"
            " ORDER BY CASE WHEN c.status = 'menunggu_ahli' THEN 0 ELSE 1 END, c.keyakinan ASC"
        ).fetchall()
    hasil = []
    for r in rows:
        item = dict(r)
        item["probabilitas"] = json.loads(r["probabilitas"])
        item["lat"] = round(r["lat"], 5)
        item["lon"] = round(r["lon"], 5)
        hasil.append(item)
    return {
        "pengguna": user,
        "menunggu": sum(1 for r in hasil if r["status"] == "menunggu_ahli"),
        "daftar": hasil,
    }


class VerifikasiBody(BaseModel):
    klasifikasi_id: int
    kelas_final: str
    catatan: str = Field(default="", max_length=500)


@app.post("/api/verifikasi")
def simpan_verifikasi(body: VerifikasiBody, request: Request):
    user = wajib_ahli(request)
    if body.kelas_final not in KELAS:
        raise HTTPException(400, "Kelas final harus Rendah, Sedang, atau Tinggi.")
    with store.koneksi() as db:
        row = db.execute("SELECT * FROM classifications WHERE id = ?", (body.klasifikasi_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Klasifikasi tidak ditemukan.")
        keputusan = "dikonfirmasi" if row["kelas"] == body.kelas_final else "dikoreksi"
        db.execute(
            "INSERT INTO verifications (classification_id, user_id, kelas_final, catatan, keputusan, dibuat)"
            " VALUES (?,?,?,?,?,?)",
            (body.klasifikasi_id, user["id"], body.kelas_final, body.catatan.strip(), keputusan, store.sekarang()),
        )
        db.execute("UPDATE classifications SET status = 'terverifikasi' WHERE id = ?", (body.klasifikasi_id,))
    return {"ok": True, "keputusan": keputusan, "kelas_final": body.kelas_final}


@app.get("/api/scene-areas")
def scene_areas(request: Request):
    wajib_user(request)
    with store.koneksi() as db:
        contoh = {
            r["scene"]: dict(r)
            for r in db.execute(
                "SELECT scene, lat, lon, kode FROM points WHERE id IN"
                " (SELECT MIN(id) FROM points GROUP BY scene)"
            )
        }
    hasil = []
    for scene in scenes.SCENES.values():
        contoh_titik = contoh.get(scene.kode)
        hasil.append(
            {
                **scene.meta(),
                "contoh": (
                    {"lat": round(contoh_titik["lat"], 5), "lon": round(contoh_titik["lon"], 5),
                     "kode": contoh_titik["kode"]}
                    if contoh_titik
                    else None
                ),
            }
        )
    return hasil


# ---------- citra ----------

@app.get("/api/insiden/{insiden_id}/thumbnail")
def thumbnail(insiden_id: int, request: Request):
    wajib_user(request)
    with store.koneksi() as db:
        row = db.execute("SELECT scene FROM incidents WHERE id = ?", (insiden_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Kejadian tidak ditemukan.")
    kode = row["scene"]
    if kode not in _thumb_cache:
        _thumb_cache[kode] = scenes.thumbnail_png(scenes.SCENES[kode])
    return RawResponse(_thumb_cache[kode], media_type="image/png", headers={"Cache-Control": "max-age=86400"})


@app.get("/api/titik/{point_id}/patch.png")
def patch(point_id: int, request: Request):
    wajib_user(request)
    with store.koneksi() as db:
        row = db.execute("SELECT scene, lat, lon FROM points WHERE id = ?", (point_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Titik tidak ditemukan.")
    scene = scenes.SCENES[row["scene"]]
    posisi = scenes.baris_kolom(scene, row["lat"], row["lon"])
    if posisi is None:
        raise HTTPException(404, "Koordinat titik tidak valid.")
    try:
        titik = scenes.ekstrak(scene, *posisi)
    except (scenes.TitikDiLuar, scenes.KualitasRendah) as exc:
        raise HTTPException(404, str(exc)) from exc
    return RawResponse(
        scenes.patch_png(titik["rgb10"]), media_type="image/png", headers={"Cache-Control": "max-age=86400"}
    )


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


# ---------- SPA ----------

if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/{path:path}")
def spa(path: str):
    if path.startswith("api/"):
        raise HTTPException(404, "Endpoint tidak ditemukan.")
    if not DIST.exists():
        return JSONResponse(
            {"detail": "Frontend belum dibangun. Jalankan `npm run build` di folder frontend."},
            status_code=503,
        )
    berkas = (DIST / path).resolve()
    if path and berkas.is_file() and DIST.resolve() in berkas.parents:
        return FileResponse(berkas)
    return FileResponse(DIST / "index.html")
