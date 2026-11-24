"""Membandingkan backend teman (NumPy, tanpa torch) dengan referensi kita (torch + rasterio).

Jalankan setelah path data di backend/model.py dan backend/scenes.py sudah benar:

  python bandingkan_backend.py --backend backend --legacy archive/sipakarhutla_backend_legacy \
         --pt jalur/ke/model_indo.pt --data jalur/folder/berisi/K00x_data.tif

Kebutuhan pustaka (satu lingkungan): torch numpy rasterio tifffile utm pillow
"""
import argparse
import os
import sys

import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--backend", required=True, help="folder berisi model.py dan scenes.py milik teman")
ap.add_argument("--legacy", required=True, help="folder sipakarhutla_backend kita (berisi inferensi.py dan tests/)")
ap.add_argument("--pt", required=True, help="model_indo.pt hasil Notebook 3")
ap.add_argument("--data", required=True, help="folder berisi K00x_..._data.tif")
ap.add_argument("--n", type=int, default=150, help="jumlah titik acak per scene")
a = ap.parse_args()

for p in (a.backend, a.legacy, os.path.join(a.legacy, "tests")):
    sys.path.insert(0, os.path.abspath(p))

import rasterio                                   # noqa: E402
import torch                                      # noqa: E402
from rasterio.warp import transform               # noqa: E402

import model as friend_model                      # noqa: E402  (milik teman)
import scenes as friend_scenes                    # noqa: E402  (milik teman)
import ref_notebook as ref                        # noqa: E402  (salinan logika Notebook 3)
from inferensi import Penduga                     # noqa: E402  (versi torch kita)

LULUS, PERHATIAN = "[LULUS]    ", "[PERHATIAN]"
rng = np.random.RandomState(0)


def lapor(ok, teks):
    print((LULUS if ok else PERHATIAN), teks)


print("=" * 70, "\nA. Bobot .npz vs model_indo.pt\n" + "=" * 70)
M = torch.load(a.pt, map_location="cpu", weights_only=False)
fm = friend_model.ModelKeparahan()
selisih, hilang = 0.0, []
for k, v in M["state_dict"].items():
    if not v.dtype.is_floating_point:
        continue
    if k not in fm.p:
        hilang.append(k)
        continue
    selisih = max(selisih, float(np.abs(fm.p[k] - v.numpy()).max()))
for k in ("mu", "sd"):
    selisih = max(selisih, float(np.abs(np.asarray(fm.p[k]).reshape(-1) - np.asarray(M[k]).reshape(-1)).max()))
lapor(not hilang and selisih < 1e-6, f"selisih bobot maks = {selisih:.2e}; kunci hilang: {hilang or 'tidak ada'}")

print("=" * 70, "\nB. Hitungan maju NumPy vs torch (patch acak)\n" + "=" * 70)
pend = Penduga(a.pt, a.data)
x = rng.uniform(0.0, 0.30, (1000, 11, 11, 3)).astype(np.float32)
p_teman = fm.prediksi(x)
p_torch = np.stack([pend.peluang_patch(x[i].transpose(2, 0, 1))[0] for i in range(len(x))])
lapor(np.abs(p_teman - p_torch).max() < 1e-3 and (p_teman.argmax(1) == p_torch.argmax(1)).all(),
      f"selisih peluang maks = {np.abs(p_teman - p_torch).max():.2e}; kelas sama = "
      f"{(p_teman.argmax(1) == p_torch.argmax(1)).mean():.1%}")

print("=" * 70, "\nC. Pemotongan patch: identik dengan patch Notebook 3?\n" + "=" * 70)
for kode, scene in friend_scenes.SCENES.items():
    r30, l30, ok30, penuh = ref.baca(scene.path)
    pos = [(i, j) for i, j, _ in ref.daftar_patch(r30, l30, ok30) if penuh[i:i+11, j:j+11].all()]
    pilih = [pos[k] for k in rng.choice(len(pos), min(60, len(pos)), replace=False)]
    maks, gagal = 0.0, 0
    for i, j in pilih:
        d = friend_scenes.ekstrak(scene, 3 * (i + 5) + 1, 3 * (j + 5) + 1)
        maks = max(maks, float(np.abs(d["patch"] - r30[:, i:i+11, j:j+11].transpose(1, 2, 0)).max()))
    lapor(maks < 1e-5, f"{kode} zona {scene.zona}{'U' if scene.utara else 'S'}: {len(pilih)} patch, selisih maks = {maks:.2e}")

print("=" * 70, "\nD. Dari koordinat sampai kelas: teman vs kita (titik acak)\n" + "=" * 70)
tot = {"n": 0, "ketemu": 0, "tolak": 0, "sama": 0, "geser": 0.0, "dp": 0.0, "idx_beda": 0}
for kode, scene in friend_scenes.SCENES.items():
    with rasterio.open(scene.path) as src:
        H, W = src.height, src.width
        for _ in range(a.n):
            r, c = int(rng.randint(40, H - 40)), int(rng.randint(40, W - 40))
            xx, yy = src.xy(r, c)
            lon, lat = transform(src.crs, "EPSG:4326", [xx], [yy])
            lat, lon = lat[0], lon[0]
            tot["n"] += 1
            sc, pos = friend_scenes.cari_scene(lat, lon)
            if sc is None or sc.kode != kode:
                tot["tolak"] += 1
                continue
            tot["geser"] = max(tot["geser"], abs(pos[0] - r), abs(pos[1] - c))
            tot["idx_beda"] += int(abs(pos[0] - r) > 0 or abs(pos[1] - c) > 0)
            try:
                d = friend_scenes.ekstrak(sc, *pos)
            except (friend_scenes.TitikDiLuar, friend_scenes.KualitasRendah):
                continue
            h = pend.prediksi(kode, lat, lon)
            if h["peluang"] is None:
                continue
            tot["ketemu"] += 1
            hasil = friend_model.klasifikasi_patch(d["patch"][None])[0]
            tot["sama"] += int(hasil["kelas"] == h["kelas_model"])
            tot["dp"] = max(tot["dp"], abs(hasil["keyakinan"] - h["keyakinan"]))
lapor(tot["tolak"] == 0, f"titik acak yang gagal dicari scene-nya oleh teman: {tot['tolak']} dari {tot['n']}")
lapor(tot["geser"] <= 1, f"selisih baris/kolom piksel (utm vs rasterio): maks {tot['geser']:.0f} piksel, "
                         f"{tot['idx_beda']} titik berbeda")
lapor(tot["sama"] / max(tot["ketemu"], 1) > 0.9,
      f"kelas sama pada {tot['sama']}/{tot['ketemu']} titik ({tot['sama'] / max(tot['ketemu'], 1):.1%}); "
      f"selisih keyakinan maks {tot['dp']:.3f}")
print("   (Beda kecil wajar: teman memotong patch pada grid 30 m yang selaras dengan data latih, "
      "kita memusatkannya pada piksel titik, bergeser maks 1 piksel = 10 m.)")

print("=" * 70, "\nE. Titik di sepanjang batas zona UTM (114 derajat BT)\n" + "=" * 70)
for kode in ("K003", "K005"):
    scene = friend_scenes.SCENES.get(kode)
    if scene is None:
        continue
    with rasterio.open(scene.path) as src:
        kolom = list(range(0, 8)) if kode == "K003" else list(range(src.width - 8, src.width))
        ditolak = 0
        for c in kolom:
            xx, yy = src.xy(src.height // 2, c)
            lon, lat = transform(src.crs, "EPSG:4326", [xx], [yy])
            sc, _ = friend_scenes.cari_scene(lat[0], lon[0])
            ditolak += int(sc is None)
    lapor(ditolak == 0, f"{kode}: {ditolak} dari {len(kolom)} piksel tepi batas zona ditolak oleh cari_scene (zona {scene.zona})")
print("   Titik ditolak di sini berarti dianggap 'di luar area', padahal masih di dalam raster (hanya ~40 m dari tepi).")
