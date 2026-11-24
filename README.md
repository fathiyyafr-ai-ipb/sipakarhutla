# Sipakarhutla: Dashboard Pemantauan Karhutla

Sipakarhutla adalah dashboard web full-stack untuk memantau kejadian kebakaran hutan dan lahan (karhutla) di Kalimantan serta mengklasifikasikan tingkat keparahannya (**Rendah**, **Sedang**, **Tinggi**) menggunakan model CNN yang dilatih pada data citra satelit Indonesia.

## Struktur Repositori

- `backend/` — Backend aktif (FastAPI, Python 3.12, inferensi CNN berbasis NumPy murni, GeoTIFF via `tifffile`, dan basis data SQLite).
- `frontend/` — Antarmuka web pengguna (React 19, TypeScript, Vite, React Router, Recharts, Lucide).
- `api/` — Handler serverless (`api/index.py`) untuk deployment Vercel.
- `tools/referensi_torch/` — Prototipe awal (PyTorch + rasterio) yang digunakan sebagai referensi pengujian (28 uji pytest).
- `tools/bandingkan_backend.py` — Skrip verifikasi output antara backend aktif dan model PyTorch referensi.
- `riset/` — Notebook pelatihan data Indonesia (`03_latih_uji_data_Indonesia.ipynb`) dan spesifikasi teknis (`PROMPT.md`).

---

## Cara Menjalankan

### 1. Menjalankan Backend
Prasyarat: Python 3.12

```powershell
# Aktifkan virtual environment
.\.venv\Scripts\Activate.ps1

# Pasang dependensi
pip install -r backend\requirements.txt

# Jalankan server FastAPI
uvicorn backend.main:app --reload --port 8000
```
Server backend akan berjalan di `http://127.0.0.1:8000` (dokumentasi API interaktif tersedia di `/docs`).

### 2. Menjalankan Frontend
Prasyarat: Node.js (v18+)

```powershell
cd frontend
npm install
npm run dev
```
Buka browser di `http://localhost:5173`. Request `/api/*` secara otomatis diarahkan ke backend (port 8000) melalui konfigurasi proxy Vite.

---

## Akun Demo
- **Petugas Lapangan**: `petugas` / `petugas123`
- **Ahli Karhutla**: `ahli` / `ahli123`
