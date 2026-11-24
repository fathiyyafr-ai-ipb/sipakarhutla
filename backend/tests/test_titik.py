"""Tes kode titik, nama wajib, pencegahan duplikat, dan kelas efektif (koreksi ahli)."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend import main, store

# Geseran ~110-330 m dari titik seed: cukup jauh dari ambang duplikat 30 m.
GESERAN_JAUH = [
    (0.001, 0.0), (0.0, 0.001), (-0.001, 0.0), (0.0, -0.001),
    (0.002, 0.002), (-0.002, 0.002), (0.002, -0.002), (-0.002, -0.002),
    (0.003, 0.0), (0.0, 0.003), (-0.003, 0.0), (0.0, -0.003),
]


def _login(client, username, password):
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return client


@pytest.fixture
def client(db_path):
    with TestClient(main.app) as c:
        yield _login(c, "petugas", "petugas123")


def _insiden(client, kode):
    return next(i for i in client.get("/api/insiden").json() if i["kode"] == kode)


def _titik(client, kode):
    return next(t for t in client.get("/api/titik").json() if t["kode"] == kode)


def _tambah_dekat(client, kode_acuan, insiden_id, nama="Desa Uji Coba", lewati=()):
    """Tambah titik ~100-300 m dari titik acuan; coba beberapa posisi sampai lolos."""
    acuan = _titik(client, kode_acuan)
    for dlat, dlon in GESERAN_JAUH:
        if (dlat, dlon) in lewati:
            continue
        res = client.post(
            "/api/titik",
            json={
                "nama": nama,
                "lat": acuan["lat"] + dlat,
                "lon": acuan["lon"] + dlon,
                "insiden_id": insiden_id,
            },
        )
        if res.status_code == 200:
            return res, (dlat, dlon)
        assert res.status_code in (400, 409), res.text
    pytest.fail(f"Tidak ada posisi valid di sekitar {kode_acuan}")


# ---------- kode ----------

def test_kode_berurutan_per_kejadian(client):
    k002 = _insiden(client, "K002")
    k003 = _insiden(client, "K003")

    res1, g1 = _tambah_dekat(client, "K002-01", k002["id"])
    assert res1.json()["kode"] == "K002-07"
    res2, _ = _tambah_dekat(client, "K002-01", k002["id"], lewati={g1})
    assert res2.json()["kode"] == "K002-08"

    # Urutan kejadian lain tidak terpengaruh.
    res3, _ = _tambah_dekat(client, "K003-01", k003["id"])
    assert res3.json()["kode"] == "K003-07"


def test_kode_otomatis_tanpa_insiden_id_mengikuti_area(client):
    """Tanpa insiden_id, kejadian dicari dari koordinat dan kode tetap per kejadian."""
    res, _ = _tambah_dekat(client, "K004-01", None)
    assert res.json()["kode"] == "K004-07"


def test_kode_tidak_bentrok_setelah_titik_dihapus(client, db_path):
    db = sqlite3.connect(db_path)
    pid = db.execute("SELECT id FROM points WHERE kode = 'K002-03'").fetchone()[0]
    db.execute("DELETE FROM classifications WHERE point_id = ?", (pid,))
    db.execute("DELETE FROM points WHERE id = ?", (pid,))
    db.commit()
    db.close()

    # COUNT akan menghasilkan K002-06 (bentrok); angka terbesar + 1 menghasilkan K002-07.
    res, _ = _tambah_dekat(client, "K002-01", _insiden(client, "K002")["id"])
    assert res.status_code == 200
    assert res.json()["kode"] == "K002-07"


def test_kode_tanpa_kejadian_memakai_awalan_t(db_path):
    with store.koneksi() as db:
        assert store.kode_berikutnya(db, None, None) == "T-01"


def test_simpan_titik_mengulang_bila_kode_bentrok(db_path, monkeypatch):
    asli = store.kode_berikutnya
    panggilan = []

    def palsu(db, insiden_id, kode_insiden):
        panggilan.append(1)
        # Dua percobaan pertama memakai kode yang sudah ada (simulasi balapan).
        return "K002-01" if len(panggilan) < 3 else asli(db, insiden_id, kode_insiden)

    monkeypatch.setattr(store, "kode_berikutnya", palsu)
    hasil = {"kelas": "Rendah", "probabilitas": {"Rendah": 1, "Sedang": 0, "Tinggi": 0}, "keyakinan": 0.9}
    titik = {"label_index": 0, "dnbr": 0.1, "modis": False}
    with store.koneksi() as db:
        insiden = db.execute("SELECT id, kode FROM incidents WHERE kode = 'K002'").fetchone()
        _, kode, _, _ = store.simpan_titik(
            db, insiden_id=insiden["id"], kode_insiden=insiden["kode"], nama="Desa Uji",
            lat=0.0, lon=0.0, scene="K002", catatan="", hasil=hasil, titik=titik,
        )
    assert kode == "K002-07"
    assert len(panggilan) == 3

    # Bentrok terus -> menyerah setelah MAKS_PERCOBAAN_KODE kali.
    panggilan.clear()
    monkeypatch.setattr(store, "kode_berikutnya", lambda *a: panggilan.append(1) or "K002-01")
    with store.koneksi() as db, pytest.raises(sqlite3.IntegrityError):
        store.simpan_titik(
            db, insiden_id=insiden["id"], kode_insiden="K002", nama="Desa Uji",
            lat=0.0, lon=0.0, scene="K002", catatan="", hasil=hasil, titik=titik,
        )
    assert len(panggilan) == store.MAKS_PERCOBAAN_KODE


# ---------- duplikat ----------

def test_titik_duplikat_ditolak_409_tanpa_inferensi(client, monkeypatch):
    def jangan_dipanggil(*a, **k):
        raise AssertionError("inferensi tidak boleh berjalan untuk titik duplikat")

    monkeypatch.setattr(main, "klasifikasi_patch", jangan_dipanggil)
    monkeypatch.setattr(main.scenes, "ekstrak", jangan_dipanggil)

    acuan = _titik(client, "K002-01")
    res = client.post(
        "/api/titik",
        json={
            "nama": "Desa Dobel",
            "lat": acuan["lat"] + 0.00003,  # ~3,3 m
            "lon": acuan["lon"],
            "insiden_id": _insiden(client, "K002")["id"],
        },
    )
    assert res.status_code == 409
    body = res.json()
    assert set(body["detail"]) == {"kode", "titik_ada", "jarak_m"}
    assert body["detail"]["kode"] == "titik_duplikat"
    assert body["detail"]["titik_ada"] == "K002-01"
    assert 0 < body["detail"]["jarak_m"] < store.JARAK_DUPLIKAT_M


def test_titik_lebih_dari_30_m_diterima_200(client):
    res, _ = _tambah_dekat(client, "K002-01", _insiden(client, "K002")["id"])
    assert res.status_code == 200


def test_cari_titik_dekat_batas_jarak(db_path):
    with store.koneksi() as db:
        acuan = db.execute("SELECT lat, lon FROM points WHERE kode = 'K002-01'").fetchone()
        # ~22 m -> duplikat; ~44 m -> bukan (titik seed lain jauh lebih dari 30 m).
        dekat = store.cari_titik_dekat(db, acuan["lat"] + 0.0002, acuan["lon"])
        jauh = store.cari_titik_dekat(db, acuan["lat"] + 0.0004, acuan["lon"])
    assert dekat["kode"] == "K002-01" and 20 < dekat["jarak_m"] < 25
    assert jauh is None


# ---------- nama ----------

@pytest.mark.parametrize("nama", ["", "ab", "     ", "  a  b  "[:4]])
def test_nama_terlalu_pendek_422(client, nama):
    res = client.post("/api/titik", json={"nama": nama, "lat": -3.16, "lon": 114.84})
    assert res.status_code == 422


def test_nama_wajib_ada_422(client):
    res = client.post("/api/titik", json={"lat": -3.16, "lon": 114.84})
    assert res.status_code == 422


def test_nama_121_karakter_422(client):
    res = client.post("/api/titik", json={"nama": "a" * 121, "lat": -3.16, "lon": 114.84})
    assert res.status_code == 422


def test_nama_dipangkas_saat_disimpan(client):
    res, _ = _tambah_dekat(client, "K002-01", _insiden(client, "K002")["id"], nama=" Desa Sungai Tuan ")
    assert res.json()["nama"] == "Desa Sungai Tuan"
    detail = client.get(f"/api/titik/{res.json()['id']}").json()
    assert detail["nama"] == "Desa Sungai Tuan"


def test_nama_spasi_ganda_dirapikan(client):
    res, _ = _tambah_dekat(
        client, "K002-01", _insiden(client, "K002")["id"], nama="Desa  Sungai   Tuan,  Kec. Karang Intan"
    )
    assert res.json()["nama"] == "Desa Sungai Tuan, Kec. Karang Intan"


def test_kode_dari_pengguna_diabaikan(client):
    acuan = _titik(client, "K002-01")
    for dlat, dlon in GESERAN_JAUH:
        res = client.post(
            "/api/titik",
            json={"nama": "Desa Uji", "kode": "X-99", "lat": acuan["lat"] + dlat,
                  "lon": acuan["lon"] + dlon, "insiden_id": _insiden(client, "K002")["id"]},
        )
        if res.status_code == 200:
            assert res.json()["kode"] == "K002-07"
            return
    pytest.fail("Tidak ada posisi valid")


def test_semua_titik_seed_punya_nama(client):
    titik = client.get("/api/titik").json()
    assert len(titik) == 36
    for t in titik:
        assert t["nama"].strip(), t["kode"]
    # File nama_titik_contoh.json masih kosong -> cadangan dipakai.
    contoh = store._muat_nama_contoh()
    k = _titik(client, "K002-01")
    assert k["nama"] == (contoh.get("K002-01") or "Titik contoh K002-01")


def test_nama_titik_contoh_mencakup_semua_kode_seed(client):
    kode_seed = {t["kode"] for t in client.get("/api/titik").json()}
    assert set(store._muat_nama_contoh()) == kode_seed


# ---------- kelas efektif ----------

def _hitung(dashboard, kelas):
    return next(d["jumlah"] for d in dashboard["distribusi"] if d["kelas"] == kelas)


def test_koreksi_ahli_ikut_terhitung(client, db_path):
    rendah = next(t for t in client.get("/api/titik").json() if t["kelas_model"] == "Rendah")
    assert rendah["dikoreksi"] is False and rendah["kelas"] == "Rendah"
    sebelum = client.get("/api/dashboard").json()
    insiden_sebelum = _insiden(client, rendah["insiden"])

    _login(client, "ahli", "ahli123")
    res = client.post(
        "/api/verifikasi",
        json={"klasifikasi_id": rendah["klasifikasi_id"], "kelas_final": "Tinggi", "catatan": "uji"},
    )
    assert res.status_code == 200 and res.json()["keputusan"] == "dikoreksi"

    sesudah = client.get("/api/dashboard").json()
    assert _hitung(sesudah, "Tinggi") == _hitung(sebelum, "Tinggi") + 1
    assert _hitung(sesudah, "Rendah") == _hitung(sebelum, "Rendah") - 1
    assert sesudah["statistik"]["tinggi"] == sebelum["statistik"]["tinggi"] + 1

    # Sebaran per kejadian dan ringkasan kejadian ikut berubah.
    def sebaran(d):
        return next(s for s in d["sebaran"] if s["kode"] == rendah["insiden"])

    assert sebaran(sesudah)["Tinggi"] == sebaran(sebelum)["Tinggi"] + 1
    insiden_sesudah = _insiden(client, rendah["insiden"])
    assert insiden_sesudah["tinggi"] == insiden_sebelum["tinggi"] + 1
    assert insiden_sesudah["rendah"] == insiden_sebelum["rendah"] - 1
    assert insiden_sesudah["status"] == "Siaga"

    # Daftar titik, detail titik, dan detail kejadian.
    t = _titik(client, rendah["kode"])
    assert t["kelas"] == "Tinggi" and t["kelas_model"] == "Rendah" and t["dikoreksi"] is True
    detail = client.get(f"/api/titik/{rendah['id']}").json()
    assert detail["kelas"] == "Tinggi" and detail["kelas_model"] == "Rendah" and detail["dikoreksi"] is True
    di_insiden = next(
        x for x in client.get(f"/api/insiden/{rendah['insiden_id']}").json()["titik"]
        if x["kode"] == rendah["kode"]
    )
    assert di_insiden["kelas"] == "Tinggi" and di_insiden["dikoreksi"] is True

    # Filter kelas memakai kelas efektif.
    assert rendah["kode"] in {x["kode"] for x in client.get("/api/titik?kelas=Tinggi").json()}

    # classifications.kelas tidak ditimpa.
    db = sqlite3.connect(db_path)
    kelas_db = db.execute(
        "SELECT kelas FROM classifications WHERE id = ?", (rendah["klasifikasi_id"],)
    ).fetchone()[0]
    db.close()
    assert kelas_db == "Rendah"


def test_konfirmasi_ahli_bukan_koreksi(client):
    t = client.get("/api/titik").json()[0]
    _login(client, "ahli", "ahli123")
    client.post("/api/verifikasi", json={"klasifikasi_id": t["klasifikasi_id"], "kelas_final": t["kelas_model"]})
    sesudah = _titik(client, t["kode"])
    assert sesudah["dikoreksi"] is False and sesudah["kelas"] == t["kelas_model"]
