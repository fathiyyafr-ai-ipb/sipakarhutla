# PROMPT — Sipakarhutla: Dashboard Web Pemantauan Karhutla

## Tujuan
Bangun dashboard web full-stack untuk memantau kejadian karhutla di Kalimantan dan
mengklasifikasikan tingkat keparahannya (Rendah / Sedang / Tinggi) menggunakan
model CNN yang sudah dilatih pada data Indonesia. Model hanya memberi **estimasi**;
hasil dengan keyakinan < 0,60 masuk antrean verifikasi ahli. Label referensi berasal
dari dNBR satelit, bukan pengamatan lapangan — tampilkan disclaimer ini di UI.

## Stack
- Frontend: React 19 + TypeScript + Vite, React Router, Recharts, Lucide.
- Backend: FastAPI (Python 3.12), SQLite.
- Inference: NumPy murni (DLL PyTorch diblokir Application Control).
- Citra: `tifffile` + `imagecodecs` (rasterio diblokir). Konversi koordinat UTM↔WGS84
  dengan paket `utm`.
- Satu aplikasi FastAPI yang menyajikan API + SPA hasil build; Vite proxy `/api`
  saat pengembangan.

## Model & data nyata (jangan mengarang nilai)
- Gunakan `sipakarhutla_ml/model_indo.pt` (6 kejadian Kalimantan K002–K007; akurasi 0,841;
  macro-F1 0,709; recall Sedang 0,626; AUC Tinggi 0,974), bukan model AS.
- Konversi checkpoint `.pt` ke `model_indo.npz` dengan unpickler kustom (format PyTorch zip).
- Input: patch RGB 11×11 pada grid 30 m, nilai `/255 * 0,3`, normalisasi dengan `mu`/`sd`
  dari checkpoint.
- Citra 10 m → rata-rata blok 3×3 (piksel valid ≥ 80%) untuk membentuk 11×11.
- Arsitektur: Conv(3→32)+BN+ReLU, Conv(32→64)+BN+ReLU, MaxPool, Conv(64→96)+BN+ReLU,
  global average pool, Linear(96→3).
- Ambang keyakinan 0,60. Di bawahnya status "Menunggu Ahli".
- Band TIFF: 0–2 RGB, 3 kelas dNBR (1=Rendah, 2=Sedang, 3=Tinggi), 4 dNBR×1000,
  5 MODIS terbakar. Georeferensi dari tag TIFF (`ModelPixelScaleTag`, `ModelTiepointTag`,
  `GeoKeyDirectoryTag`, `GeoAsciiParamsTag`). Zona: K002/3/4/6 = 50S, K005/7 = 49S.
- K001 Jabiren Raya (berkabut) dipakai untuk state penolakan kualitas, bukan prediksi.

## Halaman
1. Login — akun `petugas` / `petugas123` dan `ahli` / `ahli123` (HttpOnly cookie session).
2. Dashboard — statistik, donut distribusi kelas, batang per area, kartu kejadian, titik
   terbaru, panel kualitas model.
3. Daftar kejadian — pencarian + filter status.
4. Detail kejadian — citra RGB, ringkasan kelas, daftar titik.
5. Daftar titik observasi — filter area/kelas/status.
6. Tambah titik — koordinat + validasi area citra + klasifikasi otomatis.
7. Hasil klasifikasi — patch, kelas, keyakinan, probabilitas, metadata, riwayat verifikasi.
8. Verifikasi ahli — antrean, panel tinjauan, konfirmasi/koreksi.

## Aturan implementasi
- Prediksi harus nyata dari model; jangan membuat skor palsu. Titik demo berasal dari
  patch berlabel dNBR pada citra asli dan diberi label "data demo".
- Tampilkan AI sebagai estimasi yang perlu diverifikasi.
- Jangan wajibkan unggah foto jika backend mengekstrak patch dari citra kejadian.
- Validasi di batas kepercayaan: koordinat di luar area citra, patch < 80% valid, atau
  citra terlalu gelap → tolak dengan pesan jelas.
- Peran `ahli` wajib untuk POST verifikasi; `petugas` hanya baca/tambah.
- Responsif, state loading/error/empty/success, label Indonesia.
- Identitas visual: SaaS lingkungan — hijau hutan, krem, aksen amber; tipografi
  Fraunces (display) + Plus Jakarta Sans (body).

## Output yang diharapkan
- `backend/` (main.py, model.py, scenes.py, store.py) + `backend/requirements.txt`.
- `frontend/` (Vite React TS) dengan halaman di atas dan `frontend/dist` hasil build.
- `PROMPT.md` ini.
- `model_indo.npz` di `sipakarhutla_ml/`.
- Instruksi run: install deps, `uvicorn backend.main:app --reload`, `npm run dev` / build.
