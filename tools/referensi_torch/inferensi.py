"""Modul inferensi Sipakarhutla (versi yang bisa jalan di lingkungan ini).

Alur satu titik:
    koordinat (lat, lon) + kejadian
      -> cek berada di dalam kotak citra kejadian
      -> potong jendela 330 x 330 m (33 x 33 piksel 10 m) dari citra RGB tersimpan
      -> turunkan ke 11 x 11 piksel (30 m): rata-rata blok 3 x 3, hanya piksel valid
      -> normalisasi (mu, sd dari saat latihan) -> CNN -> 3 peluang
      -> keputusan: keyakinan >= ambang -> "otomatis", selain itu "menunggu_ahli"

Implementasi memakai tifffile + utm + NumPy (PyTorch/rasterio diblokir Application Control).
Antarmuka kelas Penduga dipertahankan agar api.py dan pengujian tetap jalan.
"""

from __future__ import annotations

import glob
import io
import math
import os
import pickle
import zipfile
from typing import Optional

import numpy as np
import tifffile
import utm
from numpy.lib.stride_tricks import sliding_window_view
from PIL import Image

NAMA_KELAS = ["Rendah", "Sedang", "Tinggi"]
AMBANG_BAWAAN = 0.60
UKURAN_PATCH = 11
SKALA = 3
JENDELA = UKURAN_PATCH * SKALA
MIN_VALID_SEL = 0.67
MIN_VALID_PATCH = 0.80
FAKTOR_REFLEKTANSI = 3000 / 10000 / 255
CATATAN = "Taksiran dari citra satelit, bukan pengukuran lapangan"


class GalatInferensi(Exception):
    kode = "galat"


class KoordinatTidakValid(GalatInferensi):
    kode = "koordinat_tidak_valid"


class KejadianTidakDikenal(GalatInferensi):
    kode = "kejadian_tidak_dikenal"


class DiLuarArea(GalatInferensi):
    kode = "di_luar_area"


def putuskan(peluang, ambang: float = AMBANG_BAWAAN):
    idx = int(np.argmax(peluang))
    if float(peluang[idx]) >= ambang:
        return "otomatis", None, idx
    return "menunggu_ahli", "keyakinan_rendah", idx


def turunkan_ke_sel(dn: np.ndarray):
    refl = dn.astype(np.float32) * FAKTOR_REFLEKTANSI
    valid = (dn.sum(0) > 0).astype(np.float32)
    n = UKURAN_PATCH
    v = valid.reshape(n, SKALA, n, SKALA)
    jml_valid = v.sum((1, 3))
    r = (refl * valid).reshape(3, n, SKALA, n, SKALA).sum((2, 4))
    patch = r / np.maximum(jml_valid, 1)
    sel_valid = jml_valid / (SKALA * SKALA) >= MIN_VALID_SEL
    return patch.astype(np.float32), float(sel_valid.mean())


# ---------- pembacaan TIFF ----------
def _meta(path):
    with tifffile.TiffFile(path) as tf:
        page = tf.pages[0]
        arr = page.asarray()
        if arr.ndim == 3 and arr.shape[0] in (3, 4, 5, 6) and arr.shape[2] not in (3, 4, 5, 6):
            arr = np.transpose(arr, (1, 2, 0))
        h, w = arr.shape[0], arr.shape[1]
        scale = page.tags["ModelPixelScaleTag"].value
        tie = page.tags["ModelTiepointTag"].value
        geo = page.tags["GeoKeyDirectoryTag"].value
        x0, y0 = float(tie[3]), float(tie[4])
        pixel = float(scale[0])
        epsg = 0
        for i in range(4, len(geo), 4):
            if geo[i] == 3072:
                epsg = int(geo[i + 3])
        zona = epsg % 100
        utara = 32600 <= epsg < 32700
    return h, w, x0, y0, pixel, zona, utara


def _rgb(path):
    with tifffile.TiffFile(path) as tf:
        arr = tf.pages[0].asarray()
    if arr.ndim == 3 and arr.shape[0] in (3, 4, 5, 6) and arr.shape[2] not in (3, 4, 5, 6):
        arr = np.transpose(arr, (1, 2, 0))
    return arr[..., :3]


# ---------- model (numpy) ----------
class _NetSentinel:
    training = False


DTYPES = {"FloatStorage": np.float32, "DoubleStorage": np.float64, "LongStorage": np.int64,
          "IntStorage": np.int32, "ShortStorage": np.int16, "ByteStorage": np.uint8, "BoolStorage": np.bool_}


def _muat_model(path):
    if path.endswith(".npz") and os.path.exists(path):
        z = np.load(path)
        return {k: z[k] for k in z.files}
    with zipfile.ZipFile(path) as z:
        obj = _unpickle2(z, "model_indo/")
        out = {}
        for k, v in obj["state_dict"].items():
            kind, storage, offset, size, stride = v
            raw = z.read("model_indo/data/%s" % storage.key)
            arr = np.frombuffer(raw, dtype=storage.dtype, count=storage.numel)
            arr = arr[offset:]
            item = np.lib.stride_tricks.as_strided(arr, shape=size, strides=tuple(s * arr.itemsize for s in stride))
            out[k] = np.array(item, copy=True)
        out["mu"] = np.asarray(obj["mu"], dtype=np.float32)
        out["sd"] = np.asarray(obj["sd"], dtype=np.float32)
        out["classes"] = np.asarray(obj.get("kelas", NAMA_KELAS))
        return out


class _StorageRef:
    def __init__(self, key, dtype, numel):
        self.key, self.dtype, self.numel = key, dtype, numel


def _unpickle(z, prefix):
    import io

    class U(pickle.Unpickler):
        def find_class(self, module, name):
            if module == "torch" and name in DTYPES:
                return name
            if module == "torch._utils" and name == "_rebuild_tensor_v2":
                return lambda storage, offset, size, stride, *a: ("tensor", storage, offset, size, stride)
            if module == "torch._utils" and name == "_rebuild_parameter":
                return lambda data, *a: data
            if module == "collections" and name == "OrderedDict":
                import collections
                return collections.OrderedDict
            return super().find_class(module, name)

        def persistent_load(self, pid):
            if isinstance(pid, tuple) and pid[0] == "storage":
                typ, key, loc, numel = pid[1], pid[2], pid[3], pid[4]
                return _StorageRef(key, DTYPES.get(typ if isinstance(typ, str) else typ.__name__, np.float32), int(numel))
            return ("unknown", pid)

    data = z.read(prefix + "data.pkl")
    up = U(io.BytesIO(data))
    # map storage class names to dtypes via find_class returning str token; persistent_load uses DTYPES
    # torch storage class name -> dtype handled by find_class returning the string name? Need find_class return dtype class
    return up.load()


# patch find_class for torch storage to return a class-like with __name__
_orig_find = None


def _fix_find_class():
    # Re-define U.find_class properly: torch storage names must map to a class whose __name__ is in DTYPES
    pass


# We'll instead monkeypatch at runtime below by overriding _unpickle with a corrected version.
def _unpickle2(z, prefix):
    import io

    class _Cls:
        def __init__(self, name):
            self.__name__ = name

    class U(pickle.Unpickler):
        def find_class(self, module, name):
            if module == "torch" and name in DTYPES:
                return _Cls(name)
            if module == "torch._utils" and name == "_rebuild_tensor_v2":
                return lambda storage, offset, size, stride, *a: ("tensor", storage, offset, size, stride)
            if module == "torch._utils" and name == "_rebuild_parameter":
                return lambda data, *a: data
            if module == "collections" and name == "OrderedDict":
                import collections
                return collections.OrderedDict
            return super().find_class(module, name)

        def persistent_load(self, pid):
            if isinstance(pid, tuple) and pid[0] == "storage":
                typ, key, loc, numel = pid[1], pid[2], pid[3], pid[4]
                name = typ.__name__ if hasattr(typ, "__name__") else str(typ)
                return _StorageRef(key, DTYPES.get(name, np.float32), int(numel))
            return ("unknown", pid)

    data = z.read(prefix + "data.pkl")
    return U(io.BytesIO(data)).load()


# replace
_unpickle = _unpickle2


def _conv(x, w, b):
    xp = np.pad(x, ((0, 0), (0, 0), (1, 1), (1, 1)))
    win = sliding_window_view(xp, (3, 3), axis=(2, 3))
    y = np.einsum("nchwkl,ockl->nohw", win, w, optimize=True)
    return y + b[None, :, None, None]


def _bn(x, p, prefix_w, prefix_bn):
    return (
        (x - p[prefix_bn + ".running_mean"][None, :, None, None])
        / np.sqrt(p[prefix_bn + ".running_var"][None, :, None, None] + 1e-5)
        * p[prefix_w + ".weight"][None, :, None, None]
        + p[prefix_w + ".bias"][None, :, None, None]
    ) if False else None


class Penduga:
    def __init__(self, path_model: str, folder_data: Optional[str] = None, ambang: float = AMBANG_BAWAAN):
        self.p = _muat_model(path_model)
        self.mu = np.asarray(self.p["mu"], dtype=np.float32).reshape(1, 3, 1, 1)
        self.sd = np.asarray(self.p["sd"], dtype=np.float32).reshape(1, 3, 1, 1)
        self.nama_kelas = list(self.p.get("classes", NAMA_KELAS))
        if isinstance(self.nama_kelas, np.ndarray):
            self.nama_kelas = [str(x) for x in self.nama_kelas.tolist()]
        self.ambang = float(ambang)
        self.net = _NetSentinel()
        self.kejadian: dict = {}
        if folder_data:
            self.muat_folder(folder_data)

    def muat_folder(self, folder):
        for f in sorted(glob.glob(os.path.join(folder, "K*_data.tif"))):
            nama = os.path.basename(f)[: -len("_data.tif")]
            self.tambah_kejadian(nama.split("_")[0], f, nama=nama)

    def tambah_kejadian(self, kejadian_id, path_raster, nama=None):
        h, w, x0, y0, pixel, zona, utara = _meta(path_raster)
        # bounds in lat/lon
        lat_a, lon_a = utm.to_latlon(x0, y0, zona, northern=utara)
        lat_b, lon_b = utm.to_latlon(x0 + w * pixel, y0 - h * pixel, zona, northern=utara)
        self.kejadian[kejadian_id] = {
            "id": kejadian_id, "nama": nama or kejadian_id, "path": path_raster,
            "kotak": {"lon_min": min(lon_a, lon_b), "lat_min": min(lat_a, lat_b),
                      "lon_maks": max(lon_a, lon_b), "lat_maks": max(lat_a, lat_b)},
            "_meta": (h, w, x0, y0, pixel, zona, utara),
        }

    def _ambil(self, kejadian_id):
        try:
            return self.kejadian[kejadian_id]
        except KeyError:
            raise KejadianTidakDikenal(f"Kejadian '{kejadian_id}' tidak dikenal") from None

    @staticmethod
    def _cek_koordinat(lat, lon):
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            raise KoordinatTidakValid("Koordinat harus berupa angka") from None
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise KoordinatTidakValid("Lintang harus -90..90 dan bujur -180..180")
        return lat, lon

    def jendela(self, kejadian_id, lat, lon):
        lat, lon = self._cek_koordinat(lat, lon)
        kej = self._ambil(kejadian_id)
        h, w, x0, y0, pixel, zona, utara = kej["_meta"]
        easting, northing, z, huruf = utm.from_latlon(lat, lon)
        ut = huruf >= "N"
        if z != zona or ut != utara:
            raise DiLuarArea("Titik berada di luar area kejadian")
        col = (easting - x0) / pixel
        row = (y0 - northing) / pixel
        if not (0 <= row < h and 0 <= col < w):
            raise DiLuarArea("Titik berada di luar area kejadian")
        baris, kolom = int(round(row)), int(round(col))
        r0, c0 = baris - JENDELA // 2, kolom - JENDELA // 2
        ra, ca = max(r0, 0), max(c0, 0)
        rb, cb = min(r0 + JENDELA, h), min(c0 + JENDELA, w)
        # read rgb
        rgb = _rgb(kej["path"])  # (H,W,3)
        data = rgb[ra:rb, ca:cb].transpose(2, 0, 1).copy()  # (3, hh, ww)
        out = np.zeros((3, JENDELA, JENDELA), dtype=np.uint8)
        out[:, ra - r0: ra - r0 + data.shape[1], ca - c0: ca - c0 + data.shape[2]] = data
        return np.clip(out, 0, 255)

    def ambil_patch(self, kejadian_id, lat, lon):
        return turunkan_ke_sel(self.jendela(kejadian_id, lat, lon))

    def peluang_patch(self, patch):
        x = patch[None] if patch.ndim == 3 else patch  # (N,3,11,11)
        x = (np.clip(x, 0, 1) - self.mu) / self.sd
        p = self.p

        def conv(inp, w, b):
            xp = np.pad(inp, ((0, 0), (0, 0), (1, 1), (1, 1)))
            win = sliding_window_view(xp, (3, 3), axis=(2, 3))
            y = np.einsum("nchwkl,ockl->nohw", win, w, optimize=True)
            return y + b[None, :, None, None]

        def bn(inp, prefix):
            return ((inp - p[prefix + ".running_mean"][None, :, None, None])
                    / np.sqrt(p[prefix + ".running_var"][None, :, None, None] + 1e-5)
                    * p[prefix + ".weight"][None, :, None, None]
                    + p[prefix + ".bias"][None, :, None, None])

        x = np.maximum(bn(conv(x, p["f.0.0.weight"], p["f.0.0.bias"]), "f.0.1"), 0)
        x = np.maximum(bn(conv(x, p["f.1.0.weight"], p["f.1.0.bias"]), "f.1.1"), 0)
        x = np.maximum(np.maximum(x[:, :, 0:10:2, 0:10:2], x[:, :, 1:11:2, 0:10:2]),
                       np.maximum(x[:, :, 0:10:2, 1:11:2], x[:, :, 1:11:2, 1:11:2]))
        x = np.maximum(bn(conv(x, p["f.3.0.weight"], p["f.3.0.bias"]), "f.3.1"), 0)
        x = x.mean(axis=(2, 3))
        logits = x @ p["c.weight"].T + p["c.bias"]
        logits -= logits.max(axis=1, keepdims=True)
        e = np.exp(logits)
        return (e / e.sum(axis=1, keepdims=True)).astype(np.float32)

    def prediksi(self, kejadian_id, lat, lon, ambang=None):
        ambang = self.ambang if ambang is None else float(ambang)
        lat, lon = self._cek_koordinat(lat, lon)
        patch, frac = self.ambil_patch(kejadian_id, lat, lon)
        dasar = {"kejadian_id": kejadian_id, "koordinat": {"lat": lat, "lon": lon},
                 "ambang": ambang, "piksel_valid": round(frac, 4), "catatan": CATATAN}
        if frac < MIN_VALID_PATCH:
            return {**dasar, "status": "menunggu_ahli", "alasan": "citra_tidak_cukup",
                    "kelas": None, "kelas_model": None, "keyakinan": None, "peluang": None}
        p = self.peluang_patch(patch)[0]
        status, alasan, idx = putuskan(p, ambang)
        kelas_model = self.nama_kelas[idx]
        return {**dasar, "status": status, "alasan": alasan,
                "kelas": kelas_model if status == "otomatis" else None,
                "kelas_model": kelas_model, "keyakinan": round(float(p[idx]), 4),
                "peluang": {n: round(float(v), 4) for n, v in zip(self.nama_kelas, p)}}

    def pratinjau_png(self, kejadian_id, lat, lon, perbesar=8):
        dn = self.jendela(kejadian_id, lat, lon).astype(np.float32)
        img = np.clip(dn / 255 * 2.0, 0, 1)
        arr = (img.transpose(1, 2, 0) * 255).astype(np.uint8)
        im = Image.fromarray(arr).resize((JENDELA * perbesar, JENDELA * perbesar), Image.NEAREST)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        return buf.getvalue()
