"""Pembacaan citra Sentinel-2 (GeoTIFF) dan ekstraksi patch 11x11.

Band: 0-2 RGB, 3 kelas dNBR (1=Rendah, 2=Sedang, 3=Tinggi),
4 dNBR x1000, 5 MODIS terbakar. Resolusi 10 m, grid model 30 m.
Georeferensi dibaca langsung dari tag TIFF (rasterio tidak tersedia).
"""

import os
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import numpy as np
import tifffile
import utm

DARI_FILE = Path(os.environ.get("SIPAKARHUTLA_DATA", str(Path(__file__).resolve().parent / "data")))

SCENE_FILES = [
    ("K002", "K002_2023_A_data.tif", 2023),
    ("K003", "K003_2023_B_data.tif", 2023),
    ("K004", "K004_2019_A_data.tif", 2019),
    ("K005", "K005_2019_B_data.tif", 2019),
    ("K006", "K006_2019_C_data.tif", 2019),
    ("K007", "K007_2019_D_data.tif", 2019),
]

PATCH_30 = 11
WINDOW_10 = PATCH_30 * 3
MIN_VALID = 0.80
MIN_KECERAHAN = 0.01


class TitikDiLuar(ValueError):
    pass


class KualitasRendah(ValueError):
    pass


@dataclass
class Scene:
    kode: str
    nama: str
    tahun: int
    path: Path
    tinggi: int
    lebar: int
    x0: float
    y0: float
    pixel: float
    zona: int
    utara: bool
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float

    @property
    def cakupan_ha(self):
        return round(self.lebar * self.pixel / 1000 * self.tinggi * self.pixel / 1000 * 100)

    def meta(self):
        return {
            "kode": self.kode,
            "nama": self.nama,
            "tahun": self.tahun,
            "lat_min": round(self.lat_min, 5),
            "lat_max": round(self.lat_max, 5),
            "lon_min": round(self.lon_min, 5),
            "lon_max": round(self.lon_max, 5),
            "cakupan_ha": self.cakupan_ha,
            "zona_utm": f"{self.zona}{'U' if self.utara else 'S'}",
        }


def _baca_meta(kode, nama_file, tahun):
    path = DARI_FILE / nama_file
    with tifffile.TiffFile(path) as tf:
        page = tf.pages[0]
        tinggi, lebar, _ = page.shape
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
        lat_a, lon_a = utm.to_latlon(x0, y0, zona, northern=utara)
        lat_b, lon_b = utm.to_latlon(x0 + lebar * pixel, y0 - tinggi * pixel, zona, northern=utara)
        return Scene(
            kode=kode,
            nama=f"Area {kode}",
            tahun=tahun,
            path=path,
            tinggi=tinggi,
            lebar=lebar,
            x0=x0,
            y0=y0,
            pixel=pixel,
            zona=zona,
            utara=utara,
            lat_min=min(lat_a, lat_b),
            lat_max=max(lat_a, lat_b),
            lon_min=min(lon_a, lon_b),
            lon_max=max(lon_a, lon_b),
        )


SCENES = {kode: _baca_meta(kode, nama, tahun) for kode, nama, tahun in SCENE_FILES}


@dataclass
class SceneData:
    rgb: np.ndarray
    kelas: np.ndarray
    dnbr: np.ndarray
    modis: np.ndarray


_cache: OrderedDict[str, SceneData] = OrderedDict()
_cache_lock = Lock()
MAKS_CACHE = 3


def muat(scene: Scene) -> SceneData:
    with _cache_lock:
        if scene.kode in _cache:
            _cache.move_to_end(scene.kode)
            return _cache[scene.kode]
    with tifffile.TiffFile(scene.path) as tf:
        arr = tf.pages[0].asarray()
    data = SceneData(
        rgb=arr[..., :3].astype(np.uint8),
        kelas=arr[..., 3].astype(np.uint8),
        dnbr=(arr[..., 4].astype(np.float32) / 1000.0),
        modis=arr[..., 5] > 0,
    )
    del arr
    with _cache_lock:
        _cache[scene.kode] = data
        while len(_cache) > MAKS_CACHE:
            _cache.popitem(last=False)
    return data


def baris_kolom(scene: Scene, lat: float, lon: float):
    easting, northing, _zona, huruf = utm.from_latlon(lat, lon, force_zone_number=scene.zona)
    if (huruf >= "N") != scene.utara:
        return None
    kolom = (easting - scene.x0) / scene.pixel
    baris = (scene.y0 - northing) / scene.pixel
    if not (0 <= baris < scene.tinggi and 0 <= kolom < scene.lebar):
        return None
    return int(baris), int(kolom)


def cari_scene(lat: float, lon: float):
    for scene in SCENES.values():
        posisi = baris_kolom(scene, lat, lon)
        if posisi is not None:
            return scene, posisi
    return None, None


def ekstrak(scene: Scene, baris: int, kolom: int):
    data = muat(scene)
    r30, c30 = baris // 3, kolom // 3
    r0, c0 = (r30 - PATCH_30 // 2) * 3, (c30 - PATCH_30 // 2) * 3
    if r0 < 0 or c0 < 0 or r0 + WINDOW_10 > scene.tinggi or c0 + WINDOW_10 > scene.lebar:
        raise TitikDiLuar("Titik terlalu dekat tepi citra; pilih titik yang lebih ke tengah area.")

    win_rgb = data.rgb[r0 : r0 + WINDOW_10, c0 : c0 + WINDOW_10]
    win_kelas = data.kelas[r0 : r0 + WINDOW_10, c0 : c0 + WINDOW_10]
    valid = (win_kelas > 0) & (win_rgb.sum(axis=-1) > 0)
    valid_frac = float(valid.mean())
    if valid_frac < MIN_VALID:
        raise KualitasRendah(
            f"Kualitas citra di sekitar titik rendah ({valid_frac:.0%} piksel valid, minimal 80%)."
        )

    blok = valid.reshape(PATCH_30, 3, PATCH_30, 3)
    hitung = np.maximum(blok.sum(axis=(1, 3)), 1)[..., None]
    jumlah = (win_rgb.astype(np.float32) * valid[..., None]).reshape(PATCH_30, 3, PATCH_30, 3, 3)
    patch = (jumlah.sum(axis=(1, 3)) / hitung / 255.0 * 0.3).astype(np.float32)

    if float(patch.mean()) < MIN_KECERAHAN:
        raise KualitasRendah("Citra di sekitar titik terlalu gelap/kosong untuk dinilai.")

    jumlah_kelas = [int(((win_kelas == c) & valid).sum()) for c in (1, 2, 3)]
    label_idx = int(np.argmax(jumlah_kelas))

    return {
        "patch": patch,
        "rgb10": win_rgb,
        "valid": round(valid_frac, 4),
        "label_index": label_idx,
        "dnbr": round(float(data.dnbr[baris, kolom]), 3),
        "modis": bool(data.modis[baris, kolom]),
        "baris": baris,
        "kolom": kolom,
    }


def thumbnail_png(scene: Scene) -> bytes:
    """Citra RGB scene, diregangkan persentil 2-98, untuk kartu dashboard."""
    from io import BytesIO

    from PIL import Image

    data = muat(scene)
    step = max(1, int(np.ceil(max(scene.tinggi, scene.lebar) / 400)))
    kecil = data.rgb[::step, ::step].astype(np.float32)
    lo = np.percentile(kecil, 2, axis=(0, 1), keepdims=True)
    hi = np.percentile(kecil, 98, axis=(0, 1), keepdims=True)
    gambar = np.clip((kecil - lo) / np.maximum(hi - lo, 1) * 255, 0, 255).astype(np.uint8)
    out = BytesIO()
    Image.fromarray(gambar).save(out, format="PNG", optimize=True)
    return out.getvalue()


def patch_png(rgb10: np.ndarray) -> bytes:
    from io import BytesIO

    from PIL import Image

    gambar = Image.fromarray(rgb10).resize((330, 330), Image.Resampling.NEAREST)
    out = BytesIO()
    gambar.save(out, format="PNG")
    return out.getvalue()
