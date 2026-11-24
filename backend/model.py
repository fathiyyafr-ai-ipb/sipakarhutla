"""Inferensi CNN Sipakarhutla tanpa PyTorch.

Bobot checkpoint `model_indo.pt` sudah dikonversi ke `model_indo.npz`
(karena DLL PyTorch diblokir Application Control di mesin ini).
Arsitektur: Conv-BN-ReLU -> Conv-BN-ReLU -> MaxPool -> Conv-BN-ReLU ->
global average pool -> Linear. Input (N, 3, 11, 11), nilai RGB/255*0.3.
"""

import os
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

KELAS = ("Rendah", "Sedang", "Tinggi")
AMBANG_KEYAKINAN = 0.60
MODEL_NAMA = "CNN Sipakarhutla (model_indo)"

DATA_DIR = Path(os.environ.get("SIPAKARHUTLA_DATA", str(Path(__file__).resolve().parent / "data")))
_ARTIFACT = DATA_DIR / "model_indo.npz"


class ModelTidakAda(RuntimeError):
    pass


class ModelKeparahan:
    def __init__(self, path: Path | None = None):
        if path is None:
            data_dir = Path(os.environ.get("SIPAKARHUTLA_DATA", str(Path(__file__).resolve().parent / "data")))
            path = data_dir / "model_indo.npz"
        if not path.exists():
            raise ModelTidakAda(f"Bobot model tidak ditemukan: {path}")
        with np.load(path) as z:
            self.p = {k: z[k] for k in z.files}

    def _conv(self, x, w, b):
        xp = np.pad(x, ((0, 0), (0, 0), (1, 1), (1, 1)))
        win = sliding_window_view(xp, (3, 3), axis=(2, 3))
        y = np.einsum("nchwkl,ockl->nohw", win, w, optimize=True)
        return y + b[None, :, None, None]

    def _bn(self, x, prefix):
        p = self.p
        return (
            (x - p[prefix + ".running_mean"][None, :, None, None])
            / np.sqrt(p[prefix + ".running_var"][None, :, None, None] + 1e-5)
            * p[prefix + ".weight"][None, :, None, None]
            + p[prefix + ".bias"][None, :, None, None]
        )

    def prediksi(self, patches):
        """patches: (N, 11, 11, 3) RGB 0..0.3. Mengembalikan probabilitas (N, 3)."""
        x = np.asarray(patches, dtype=np.float32)
        if x.ndim != 4 or x.shape[1:] != (11, 11, 3):
            raise ValueError(f"Bentuk patch tidak valid: {x.shape}")
        x = np.clip(x, 0, 1).transpose(0, 3, 1, 2)
        p = self.p
        x = (x - p["mu"]) / p["sd"]

        x = np.maximum(self._bn(self._conv(x, p["f.0.0.weight"], p["f.0.0.bias"]), "f.0.1"), 0)
        x = np.maximum(self._bn(self._conv(x, p["f.1.0.weight"], p["f.1.0.bias"]), "f.1.1"), 0)
        x = np.maximum(
            np.maximum(x[:, :, 0:10:2, 0:10:2], x[:, :, 1:11:2, 0:10:2]),
            np.maximum(x[:, :, 0:10:2, 1:11:2], x[:, :, 1:11:2, 1:11:2]),
        )
        x = np.maximum(self._bn(self._conv(x, p["f.3.0.weight"], p["f.3.0.bias"]), "f.3.1"), 0)
        x = x.mean(axis=(2, 3))
        logits = x @ p["c.weight"].T + p["c.bias"]
        logits -= logits.max(axis=1, keepdims=True)
        e = np.exp(logits)
        return e / e.sum(axis=1, keepdims=True)


_model = None


def model():
    global _model
    if _model is None:
        _model = ModelKeparahan()
    return _model


def klasifikasi_patch(patches):
    """Kembalikan list dict kelas, keyakinan, probabilitas."""
    if len(patches) == 0:
        return []
    probs = model().prediksi(patches)
    hasil = []
    for row in probs:
        idx = int(row.argmax())
        hasil.append(
            {
                "kelas": KELAS[idx],
                "keyakinan": round(float(row[idx]), 4),
                "probabilitas": {KELAS[i]: round(float(row[i]), 4) for i in range(3)},
            }
        )
    return hasil
