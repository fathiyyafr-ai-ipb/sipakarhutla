"""Uji API (tahap 2): memakai TestClient, tanpa menjalankan server dan tanpa frontend."""
import numpy as np
import pytest
from fastapi.testclient import TestClient

import ref_notebook as ref
from api import create_app
from conftest import MODEL
from inferensi import NAMA_KELAS, Penduga

KEJ = "K003"


@pytest.fixture(scope="module")
def lokasi(penduga):
    r30, l30, ok30, penuh = ref.baca(penduga.kejadian[KEJ]["path"])
    pos = [(i, j, lb) for i, j, lb in ref.daftar_patch(r30, l30, ok30) if penuh[i:i+11, j:j+11].all()]
    return [ref.pusat_lonlat(penduga.kejadian[KEJ]["path"], i, j) for i, j, _ in pos[::max(1, len(pos) // 30)]]


@pytest.fixture()
def klien(penduga, tmp_path):
    return TestClient(create_app(penduga, str(tmp_path / "uji.db")))


@pytest.fixture()
def klien_ahli(penduga, tmp_path):
    """Ambang mustahil (1.01) -> semua titik masuk antrean ahli."""
    p = Penduga(MODEL, None, ambang=1.01)
    p.kejadian = penduga.kejadian
    return TestClient(create_app(p, str(tmp_path / "uji_ahli.db")))


def test_kesehatan_dan_daftar_kejadian(klien):
    r = klien.get("/kesehatan"); assert r.status_code == 200 and r.json()["model_dimuat"] is True
    kej = klien.get("/kejadian").json()
    assert any(k["id"] == KEJ for k in kej) and set(kej[0]["kotak"]) == {"lon_min", "lat_min", "lon_maks", "lat_maks"}


def test_tambah_titik_bentuk_jawaban(klien, lokasi):
    lat, lon = lokasi[0]
    r = klien.post("/titik", json={"kejadian_id": KEJ, "lat": lat, "lon": lon})
    assert r.status_code == 201
    j = r.json()
    for kunci in ("titik_id", "kejadian_id", "koordinat", "status", "kelas", "kelas_model", "keyakinan",
                  "peluang", "ambang", "pratinjau_citra", "catatan", "dibuat_pada"):
        assert kunci in j, f"kunci '{kunci}' hilang dari jawaban"
    assert j["status"] in ("otomatis", "menunggu_ahli") and j["ambang"] == 0.6
    assert abs(sum(j["peluang"].values()) - 1) < 1e-2
    assert klien.get(f"/titik/{j['titik_id']}").json()["titik_id"] == j["titik_id"]


def test_kesalahan_input(klien, lokasi):
    lat, lon = lokasi[0]
    r = klien.post("/titik", json={"kejadian_id": KEJ, "lat": 10.0, "lon": 100.0})
    assert r.status_code == 422 and r.json()["detail"]["kode"] == "di_luar_area"
    r = klien.post("/titik", json={"kejadian_id": "K999", "lat": lat, "lon": lon})
    assert r.status_code == 404 and r.json()["detail"]["kode"] == "kejadian_tidak_dikenal"
    assert klien.post("/titik", json={"kejadian_id": KEJ, "lat": 95, "lon": lon}).status_code == 422
    assert klien.post("/titik", json={"kejadian_id": KEJ, "lat": "abc", "lon": lon}).status_code == 422
    assert klien.post("/titik", json={"kejadian_id": KEJ}).status_code == 422
    assert klien.get("/titik/T-tidakada").status_code == 404
    assert klien.get("/kejadian/K999/ringkasan").status_code == 404


def test_alur_ahli_dan_dashboard(klien_ahli, lokasi):
    ids = []
    for lat, lon in lokasi[:6]:
        r = klien_ahli.post("/titik", json={"kejadian_id": KEJ, "lat": lat, "lon": lon}); assert r.status_code == 201
        assert r.json()["status"] == "menunggu_ahli" and r.json()["kelas"] is None
        ids.append(r.json()["titik_id"])
    assert len(klien_ahli.get("/antrean-ahli", params={"kejadian_id": KEJ}).json()) == 6
    assert klien_ahli.get(f"/kejadian/{KEJ}/ringkasan").json()["jumlah"]["menunggu_ahli"] == 6

    # ahli: satu titik dikonfirmasi sesuai saran model, satu dikoreksi
    t0 = klien_ahli.get(f"/titik/{ids[0]}").json()
    r0 = klien_ahli.post(f"/titik/{ids[0]}/verifikasi", json={"kelas": t0["kelas_model"]}).json()
    assert r0["status"] == "terverifikasi" and r0["kelas"] == t0["kelas_model"] and r0["dikoreksi_ahli"] is False
    t1 = klien_ahli.get(f"/titik/{ids[1]}").json()
    lain = next(k for k in NAMA_KELAS if k != t1["kelas_model"])
    r1 = klien_ahli.post(f"/titik/{ids[1]}/verifikasi", json={"kelas": lain, "catatan": "koreksi lapangan"}).json()
    assert r1["kelas"] == lain and r1["dikoreksi_ahli"] is True and r1["catatan_ahli"] == "koreksi lapangan"

    assert klien_ahli.post(f"/titik/{ids[2]}/verifikasi", json={"kelas": "Sangat tinggi"}).status_code == 422
    assert klien_ahli.post("/titik/T-tidakada/verifikasi", json={"kelas": "Rendah"}).status_code == 404

    j = klien_ahli.get(f"/kejadian/{KEJ}/ringkasan").json()["jumlah"]
    assert j["menunggu_ahli"] == 4 and j["total"] == 6 and sum(j[k] for k in NAMA_KELAS) == 2
    assert len(klien_ahli.get("/antrean-ahli", params={"kejadian_id": KEJ}).json()) == 4


def test_ringkasan_titik_otomatis(klien, lokasi):
    n_oto = 0
    for lat, lon in lokasi[:10]:
        if klien.post("/titik", json={"kejadian_id": KEJ, "lat": lat, "lon": lon}).json()["status"] == "otomatis":
            n_oto += 1
    j = klien.get(f"/kejadian/{KEJ}/ringkasan").json()["jumlah"]
    assert j["total"] == 10 and sum(j[k] for k in NAMA_KELAS) == n_oto and j["menunggu_ahli"] == 10 - n_oto
    assert klien.get("/kejadian").json()[0]["jumlah_titik"] >= 0


def test_pratinjau_png(klien, lokasi):
    lat, lon = lokasi[0]
    tid = klien.post("/titik", json={"kejadian_id": KEJ, "lat": lat, "lon": lon}).json()["titik_id"]
    r = klien.get(f"/titik/{tid}/pratinjau.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content[:4] == b"\x89PNG"


def test_cors_untuk_frontend(klien):
    r = klien.options("/titik", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert r.status_code == 200 and "access-control-allow-origin" in r.headers
