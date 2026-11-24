# Sipakarhutla Backend (tahap 1–2: modul inferensi + API)

Isi paket:
- `inferensi.py` — memuat model, memotong patch 330 m dari koordinat, menjalankan CNN, memutuskan otomatis / menunggu ahli.
- `api.py` — API FastAPI + SQLite (titik, antrean ahli, verifikasi, ringkasan dashboard).
- `tests/` — 28 uji otomatis (pytest).

## 1. Persiapan (sekali saja)
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
Jika `pip install rasterio` gagal di Windows, pakai `conda install -c conda-forge rasterio`.

Letakkan di folder `data/`: `model_indo.pt` dan keenam `K00x_..._data.tif` (lihat `data/LETAKKAN_DI_SINI.txt`).
Untuk folder lain: `export SIPAKARHUTLA_DATA=/jalur/folder` (Windows: `set SIPAKARHUTLA_DATA=...`).

## 2. Jalankan uji otomatis
```bash
pytest -v -s
```
Hasil yang diharapkan: `28 passed`. Baris latensi akan tercetak (median per titik).
Jika `model_indo.pt` tidak ada, uji akan di-*skip*, bukan gagal.

Yang diuji:
| Berkas | Isi |
|---|---|
| `test_inferensi.py` | model termuat & mode eval; peluang berjumlah 1; patch dari koordinat **identik** dengan patch di Notebook 3; prediksi backend = prediksi model langsung; aturan ambang 0,60; titik di luar area; koordinat tidak valid; piksel kosong → `citra_tidak_cukup`; tepi raster; latensi |
| `test_api.py` | bentuk JSON; 404/422; alur ahli (konfirmasi & koreksi); ringkasan dashboard; PNG pratinjau; CORS |

Catatan penting: `test_smoke_akurasi_tidak_rusak` memakai data yang sudah dilihat model saat latih, jadi **bukan** evaluasi performa. Angka performa sebenarnya tetap dari LOEO di Notebook 3.

## 3. Jalankan server
```bash
uvicorn api:create_app --factory --reload
```
Buka http://127.0.0.1:8000/docs — semua endpoint bisa dicoba dari browser.

Contoh curl:
```bash
curl localhost:8000/kejadian
curl -X POST localhost:8000/titik -H "Content-Type: application/json" \
     -d '{"kejadian_id":"K003","lat":-2.7757,"lon":114.0665}'
curl localhost:8000/antrean-ahli
curl -X POST localhost:8000/titik/T-xxxxxxxx/verifikasi -H "Content-Type: application/json" \
     -d '{"kelas":"Tinggi","catatan":"cek lapangan"}'
curl localhost:8000/kejadian/K003/ringkasan
```

## 4. Endpoint
| Metode | Jalur | Fungsi |
|---|---|---|
| GET | `/kesehatan` | cek server & model |
| GET | `/kejadian` | daftar kejadian + kotak area (untuk peta frontend) |
| POST | `/titik` | koordinat → taksiran (201). 404 kejadian tak dikenal; 422 di luar area / koordinat salah |
| GET | `/titik`, `/titik/{id}` | daftar / detail (filter `kejadian_id`, `status`) |
| GET | `/titik/{id}/pratinjau.png` | potongan citra 330 m |
| GET | `/antrean-ahli` | titik berstatus `menunggu_ahli` |
| POST | `/titik/{id}/verifikasi` | ahli menetapkan kelas final |
| GET | `/kejadian/{id}/ringkasan` | jumlah per kelas untuk grafik dashboard |

Makna `status`: `otomatis` (keyakinan ≥ 0,60), `menunggu_ahli` (keyakinan rendah **atau** citra tidak cukup), `terverifikasi` (sudah ditetapkan ahli).
Field `kelas` kosong (`null`) sampai status `otomatis`/`terverifikasi`; saran model selalu ada di `kelas_model` (kecuali citra tidak cukup) supaya ahli punya titik awal.

## 5. Batasan prototipe (jangan dilupakan)
- Raster uji berisi band label/dNBR. Di produksi cukup citra RGB pascakebakaran; validitas piksel di backend hanya dari RGB > 0, jadi tidak memakai label.
- Daftar kejadian dibaca dengan memindai folder. Di produksi ganti dengan tabel kejadian di basis data.
- CORS `*` hanya untuk pengembangan; isi `SIPAKARHUTLA_CORS` dengan alamat frontend.
- SQLite cukup untuk demo; ganti PostgreSQL bila banyak pengguna.
- Keyakinan model pada area yang ikut dilatih akan terlihat sangat tinggi (mis. 0,99). Itu bukan bukti akurasi; pengujian yang jujur memakai kejadian baru yang belum pernah dilatih.
- Hasil adalah taksiran dari citra satelit, bukan pengukuran lapangan.
