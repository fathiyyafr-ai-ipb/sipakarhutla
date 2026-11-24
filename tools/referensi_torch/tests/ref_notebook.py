"""Salinan logika pembuatan patch dari Notebook 3 (pembanding)."""

import numpy as np
import tifffile
import utm

P = 11


def blok(a, H3, W3):
    n = a.ndim
    return a.reshape(a.shape[:-2] + (H3 // 3, 3, W3 // 3, 3)).transpose(
        tuple(range(n - 2)) + (n - 2, n, n - 1, n + 1)).reshape(a.shape[:-2] + (H3 // 3, W3 // 3, 9))


def turunkan_30m(refl, K, valid):
    H3, W3 = K.shape
    v = blok(valid.astype(np.float32), H3, W3)
    r30 = blok(refl * valid, H3, W3).sum(-1) / np.maximum(v.sum(-1), 1)
    cnt = np.stack([(blok(np.where(valid, K, 0).astype(np.float32), H3, W3).astype(int) == c).sum(-1)
                    for c in (1, 2, 3)], -1)
    return r30, cnt.argmax(-1), v.mean(-1) >= 0.67


def baca(path):
    with tifffile.TiffFile(path) as tf:
        a = tf.pages[0].asarray().transpose(2, 0, 1)
    H, W = a.shape[1:]
    H3, W3 = H // 3 * 3, W // 3 * 3
    a = a[:, :H3, :W3]
    K = a[3].astype(int)
    valid = (K > 0) & (a[:3].sum(0) > 0)
    r30, l30, ok30 = turunkan_30m(a[:3].astype(np.float32) / 255 * 0.3, K, valid)
    penuh = blok(valid.astype(np.float32), H3, W3).mean(-1) == 1.0
    return r30, l30, ok30, penuh


def daftar_patch(r30, l30, ok30, langkah=11):
    h, w = ok30.shape
    hasil = []
    for i in range(0, h - P + 1, langkah):
        for j in range(0, w - P + 1, langkah):
            m = ok30[i:i + P, j:j + P]
            if m.mean() < 0.8:
                continue
            c = np.bincount(l30[i:i + P, j:j + P][m], minlength=3)
            lb = int(c.argmax())
            if c[lb] / m.sum() < 0.5:
                continue
            hasil.append((i, j, lb))
    return hasil


def pusat_lonlat(path, i, j):
    with tifffile.TiffFile(path) as tf:
        page = tf.pages[0]
        scale = page.tags["ModelPixelScaleTag"].value
        tie = page.tags["ModelTiepointTag"].value
        geo = page.tags["GeoKeyDirectoryTag"].value
        x0, y0 = float(tie[3]), float(tie[4])
        pixel = float(scale[0])
        epsg = 0
        for k in range(4, len(geo), 4):
            if geo[k] == 3072:
                epsg = int(geo[k + 3])
        zona = epsg % 100
        utara = 32600 <= epsg < 32700
    r, c = 3 * (i + P // 2) + 1, 3 * (j + P // 2) + 1
    easting = x0 + c * pixel
    northing = y0 - r * pixel
    lat, lon = utm.to_latlon(easting, northing, zona, northern=utara)
    return lat, lon