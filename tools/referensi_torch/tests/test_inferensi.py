"""Uji modul inferensi (tahap 1): tanpa API, tanpa frontend."""
import time

import numpy as np
import pytest
import utm
import tifffile

import ref_notebook as ref
from conftest import MODEL
from inferensi import (AMBANG_BAWAAN, DiLuarArea, KejadianTidakDikenal, KoordinatTidakValid, NAMA_KELAS,
                       Penduga, putuskan, turunkan_ke_sel)

KEJ = "K003"


# ---------------------------------------------------------------- model -----
def test_model_dimuat(penduga):
    assert penduga.nama_kelas == NAMA_KELAS
    assert penduga.mu.shape == (1, 3, 1, 1) and penduga.sd.shape == (1, 3, 1, 1)
    assert not penduga.net.training                     # harus mode evaluasi (BatchNorm & Dropout)


def test_peluang_jumlahnya_satu(penduga):
    x = np.random.RandomState(0).uniform(0.02, 0.12, (5, 3, 11, 11)).astype(np.float32)
    p = penduga.peluang_patch(x)
    assert p.shape == (5, 3)
    assert np.allclose(p.sum(1), 1.0, atol=1e-5)


def test_deterministik(penduga):
    x = np.random.RandomState(1).uniform(0.02, 0.12, (3, 11, 11)).astype(np.float32)
    assert np.allclose(penduga.peluang_patch(x), penduga.peluang_patch(x))


# ------------------------------------------------------------- keputusan ----
def test_aturan_ambang():
    assert putuskan(np.array([0.1, 0.2, 0.7]), 0.6) == ("otomatis", None, 2)
    assert putuskan(np.array([0.1, 0.5, 0.4]), 0.6) == ("menunggu_ahli", "keyakinan_rendah", 1)
    assert putuskan(np.array([0.6, 0.3, 0.1]), 0.6)[0] == "otomatis"      # tepat di ambang -> otomatis
    assert AMBANG_BAWAAN == 0.60


def test_keyakinan_rendah_masuk_antrean_ahli(penduga):
    p = Penduga(MODEL, None, ambang=1.01)   # ambang mustahil
    p.kejadian = penduga.kejadian
    r, c = 1500, 1000
    kej = penduga.kejadian[KEJ]
    h, w, x0, y0, pixel, zona, utara = kej["_meta"]
    easting = x0 + c * pixel
    northing = y0 - r * pixel
    lat, lon = utm.to_latlon(easting, northing, zona, northern=utara)
    h = p.prediksi(KEJ, lat, lon)
    assert h["status"] == "menunggu_ahli" and h["alasan"] == "keyakinan_rendah"
    assert h["kelas"] is None and h["kelas_model"] in NAMA_KELAS     # saran model tetap ada untuk ahli


# ------------------------------------------- kesesuaian dengan notebook -----
@pytest.fixture(scope="module")
def acuan(penduga):
    r30, l30, ok30, penuh = ref.baca(penduga.kejadian[KEJ]["path"])
    pos = [(i, j, lb) for i, j, lb in ref.daftar_patch(r30, l30, ok30)
           if penuh[i:i+11, j:j+11].all()]           # patch yang semua pikselnya valid -> pasti sama
    return r30, pos


def test_patch_backend_sama_dengan_notebook(penduga, acuan):
    """Uji terpenting: potongan dari koordinat harus identik dengan patch latih di notebook."""
    r30, pos = acuan
    rng = np.random.RandomState(0)
    for k in rng.choice(len(pos), 40, replace=False):
        i, j, _ = pos[k]
        lat, lon = ref.pusat_lonlat(penduga.kejadian[KEJ]["path"], i, j)
        patch, frac = penduga.ambil_patch(KEJ, lat, lon)
        assert frac == 1.0
        assert np.allclose(patch, r30[:, i:i+11, j:j+11], atol=1e-5), f"patch ({i},{j}) berbeda dari notebook"


def test_prediksi_backend_sama_dengan_model_langsung(penduga, acuan):
    r30, pos = acuan
    rng = np.random.RandomState(1)
    for k in rng.choice(len(pos), 20, replace=False):
        i, j, _ = pos[k]
        lat, lon = ref.pusat_lonlat(penduga.kejadian[KEJ]["path"], i, j)
        h = penduga.prediksi(KEJ, lat, lon)
        langsung = penduga.peluang_patch(r30[:, i:i+11, j:j+11])[0]
        assert np.allclose([h["peluang"][n] for n in NAMA_KELAS], langsung, atol=1e-3)


def test_smoke_akurasi_tidak_rusak(penduga, acuan):
    """BUKAN evaluasi (model ini sudah melihat data ini saat latih). Hanya memastikan alur tidak merusak hasil."""
    r30, pos = acuan
    rng = np.random.RandomState(2)
    benar = []
    for k in rng.choice(len(pos), 150, replace=False):
        i, j, lb = pos[k]
        lat, lon = ref.pusat_lonlat(penduga.kejadian[KEJ]["path"], i, j)
        benar.append(NAMA_KELAS.index(penduga.prediksi(KEJ, lat, lon)["kelas_model"]) == lb)
    assert np.mean(benar) > 0.75, f"akurasi smoke {np.mean(benar):.2f} terlalu rendah, periksa normalisasi/kanal warna"


# -------------------------------------------------------------- skenario ----
def test_titik_di_dalam_area(penduga, acuan):
    r30, pos = acuan
    i, j, _ = pos[len(pos) // 2]
    lat, lon = ref.pusat_lonlat(penduga.kejadian[KEJ]["path"], i, j)
    h = penduga.prediksi(KEJ, lat, lon)
    assert h["status"] in ("otomatis", "menunggu_ahli")
    assert set(h["peluang"]) == set(NAMA_KELAS)
    assert h["keyakinan"] == max(h["peluang"].values())
    assert (h["kelas"] == h["kelas_model"]) == (h["status"] == "otomatis")
    assert h["piksel_valid"] >= 0.8 and "bukan pengukuran lapangan" in h["catatan"]


def test_titik_di_luar_area(penduga):
    with pytest.raises(DiLuarArea):
        penduga.prediksi(KEJ, 10.0, 100.0)
    k = penduga.kejadian[KEJ]["kotak"]
    with pytest.raises(DiLuarArea):                              # sedikit di luar tepi kotak
        penduga.prediksi(KEJ, k["lat_maks"] + 0.05, (k["lon_min"] + k["lon_maks"]) / 2)


@pytest.mark.parametrize("lat,lon", [(91, 114), (-2.7, 181), (float("nan"), 114), ("abc", 114), (None, 114)])
def test_koordinat_tidak_valid(penduga, lat, lon):
    with pytest.raises(KoordinatTidakValid):
        penduga.prediksi(KEJ, lat, lon)


def test_kejadian_tidak_dikenal(penduga):
    with pytest.raises(KejadianTidakDikenal):
        penduga.prediksi("K999", -2.7, 114.1)


def test_piksel_kosong_menunggu_ahli(penduga, tmp_path):
    """Raster buatan: separuh kiri berisi data, separuh kanan kosong (0) seperti area berkabut yang dibuang."""
    import tifffile
    path = tmp_path / "KX_data.tif"
    data = np.zeros((3, 120, 240), dtype=np.int16)
    data[:, :, :120] = 40
    geo_keys = (1, 1, 0, 7, 1024, 0, 1, 1, 1025, 0, 1, 1, 1026, 34737, 22, 0, 2049, 34737, 7, 22, 2054, 0, 1, 9102, 3072, 0, 1, 32750, 3076, 0, 1, 9001)
    extratags = [
        (33550, "d", 3, (10.0, 10.0, 0.0), False),
        (33922, "d", 6, (0.0, 0.0, 0.0, 500000.0, 9700000.0, 0.0), False),
        (34735, "H", len(geo_keys), geo_keys, False),
        (34737, "s", 0, "WGS 84 / UTM zone 50S|WGS 84|", False),
    ]
    tifffile.imwrite(str(path), np.transpose(data, (1, 2, 0)), photometric="minisblack",
                     planarconfig="contig", extratags=extratags, dtype="int16")
    penduga.tambah_kejadian("KX", str(path))
    def lonlat(r, c):
        kej = penduga.kejadian["KX"]
        h, w, x0, y0, pixel, zona, utara = kej["_meta"]
        easting = x0 + c * pixel
        northing = y0 - r * pixel
        lat, lon = utm.to_latlon(easting, northing, zona, northern=utara)
        return lat, lon
    import utm
    sisi_data = penduga.prediksi("KX", *lonlat(60, 60))
    sisi_kosong = penduga.prediksi("KX", *lonlat(60, 200))
    tepi = penduga.prediksi("KX", *lonlat(60, 118))            # jendela separuh terisi
    assert sisi_data["piksel_valid"] == 1.0 and sisi_data["status"] in ("otomatis", "menunggu_ahli")
    assert sisi_kosong["status"] == "menunggu_ahli" and sisi_kosong["alasan"] == "citra_tidak_cukup"
    assert sisi_kosong["kelas"] is None and sisi_kosong["peluang"] is None
    assert tepi["piksel_valid"] < 0.8 and tepi["alasan"] == "citra_tidak_cukup"
    del penduga.kejadian["KX"]


def test_titik_di_tepi_raster_tidak_crash(penduga):
    """Jendela 330 m yang sebagian keluar raster diisi 0 -> menunggu ahli, bukan galat."""
    k = penduga.kejadian[KEJ]["kotak"]
    h = penduga.prediksi(KEJ, k["lat_maks"] - 0.0003, (k["lon_min"] + k["lon_maks"]) / 2)
    assert h["status"] in ("otomatis", "menunggu_ahli")


def test_turunkan_ke_sel_bentuk():
    dn = np.full((3, 33, 33), 50, dtype=np.int16)
    patch, frac = turunkan_ke_sel(dn)
    assert patch.shape == (3, 11, 11) and frac == 1.0
    assert np.allclose(patch, 50 * 3000 / 10000 / 255)


def test_pratinjau_png(penduga, acuan):
    r30, pos = acuan
    lat, lon = ref.pusat_lonlat(penduga.kejadian[KEJ]["path"], pos[0][0], pos[0][1])
    png = penduga.pratinjau_png(KEJ, lat, lon)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


# --------------------------------------------------------------- latensi ----
def test_latensi_satu_titik(penduga, acuan):
    r30, pos = acuan
    lokasi = [ref.pusat_lonlat(penduga.kejadian[KEJ]["path"], i, j) for i, j, _ in pos[:60]]
    for lat, lon in lokasi[:5]:
        penduga.prediksi(KEJ, lat, lon)                  # pemanasan
    t = []
    for lat, lon in lokasi:
        a = time.perf_counter(); penduga.prediksi(KEJ, lat, lon); t.append(time.perf_counter() - a)
    med, p95 = np.median(t) * 1000, np.percentile(t, 95) * 1000
    print(f"\nLatensi per titik: median {med:.1f} ms, p95 {p95:.1f} ms (n={len(t)})")
    assert med < 200 and p95 < 500
