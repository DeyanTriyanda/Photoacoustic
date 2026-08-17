"""
Deep learning untuk citra fotoakustik -- tanpa GUI.

Framework (TF/PyTorch/ONNX) di-import lazy saat inferensi pertama.
"""

import csv
import os

import numpy as np
from PIL import Image

DEFAULT_INPUT_SIZE = 64


def _normalisasi_01(data):
    data = np.asarray(data, dtype=np.float32)
    dmin, dmax = float(data.min()), float(data.max())
    if dmax <= dmin:
        return np.zeros_like(data)
    return (data - dmin) / (dmax - dmin)


def muat_csv(path):
    """CSV aplikasi (header posisi cm) -> float32 0..1, baris 0 di atas."""
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    data = np.array([
        [float(c) if c.strip() else 0.0 for c in r[1:]]
        for r in rows[1:]
    ], dtype=np.float32)
    if data.size == 0:
        raise ValueError("CSV kosong / format tidak dikenali.")
    return np.flipud(_normalisasi_01(data)).copy()


def muat_citra(path):
    """PNG/JPG grayscale -> float32 0..1."""
    img = Image.open(path).convert("L")
    return np.asarray(img, dtype=np.float32) / 255.0


def dari_gray_matrix(gray_matrix):
    """gray_matrix uint8 (baris 0 = baris scan pertama) -> 0..1 citra standar."""
    gray = np.asarray(gray_matrix, dtype=np.float32) / 255.0
    return np.flipud(gray).copy()


def siapkan_input(data01, n=DEFAULT_INPUT_SIZE):
    """Resize 2D 0..1 ke (n, n) float32."""
    n = max(int(n), 8)
    img = Image.fromarray(
        (np.asarray(data01, dtype=np.float32) * 255.0).astype(np.uint8), mode="L"
    )
    img = img.resize((n, n), Image.BILINEAR)
    return np.asarray(img, dtype=np.float32) / 255.0


def _susun_tensor_onnx(x, bentuk_input):
    """Susun tensor ONNX dari grayscale x (H,W) 0..1 sesuai shape model."""
    x = np.asarray(x, dtype=np.float32)
    dims = []
    for d in bentuk_input:
        dims.append(int(d) if isinstance(d, (int, np.integer)) else -1)

    if len(dims) != 4:
        return x[np.newaxis, :, :, np.newaxis]

    channel_first = dims[1] in (1, 3)
    if channel_first:
        ch, h_wajib, w_wajib = dims[1], dims[2], dims[3]
    else:
        ch = dims[3] if dims[3] in (1, 3) else 1
        h_wajib, w_wajib = dims[1], dims[2]

    if h_wajib > 0 and w_wajib > 0 and (x.shape[0] != h_wajib or x.shape[1] != w_wajib):
        img = Image.fromarray((x * 255.0).astype(np.uint8), mode="L")
        img = img.resize((w_wajib, h_wajib), Image.BILINEAR)
        x = np.asarray(img, dtype=np.float32) / 255.0

    if channel_first:
        tensor = x[np.newaxis, np.newaxis, :, :]
        if ch == 3:
            tensor = np.repeat(tensor, 3, axis=1)
    else:
        tensor = x[np.newaxis, :, :, np.newaxis]
        if ch == 3:
            tensor = np.repeat(tensor, 3, axis=3)
    return tensor.astype(np.float32)


def interpretasi_keluaran(hasil):
    """Return ("image", arr) atau ("vector", flat)."""
    h = np.asarray(hasil)
    h = np.squeeze(h)

    if h.ndim == 3:
        if h.shape[0] in (1, 3):
            img = np.transpose(h, (1, 2, 0))
        elif h.shape[2] in (1, 3):
            img = h
        else:
            return "vector", h.flatten()
        img = np.clip(img.astype(np.float32), 0.0, 1.0)
        if img.shape[2] == 1:
            img = img[:, :, 0]
        return "image", img

    if h.ndim == 2 and min(h.shape) > 4:
        return "image", np.clip(h.astype(np.float32), 0.0, 1.0)

    return "vector", h.flatten()


def simpan_citra_hasil(path, img):
    arr = np.clip(np.asarray(img, dtype=np.float32), 0.0, 1.0)
    arr8 = (arr * 255.0).astype(np.uint8)
    mode = "RGB" if arr8.ndim == 3 else "L"
    Image.fromarray(arr8, mode=mode).save(path)


class ModelDL:
    """Pembungkus model .h5/.keras/.pt/.pth/.onnx -- framework lazy-load."""

    EKSTENSI_DIDUKUNG = (".h5", ".keras", ".pt", ".pth", ".onnx")

    def __init__(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext not in self.EKSTENSI_DIDUKUNG:
            raise ValueError(
                f"Ekstensi model tidak dikenali: {ext} "
                f"(didukung: {', '.join(self.EKSTENSI_DIDUKUNG)})"
            )
        self.path = path
        self.ext = ext
        self._model = None

    @property
    def nama_file(self):
        return os.path.basename(self.path)

    def jalankan(self, x):
        x = np.asarray(x, dtype=np.float32)
        if self.ext in (".h5", ".keras"):
            return self._infer_keras(x)
        if self.ext in (".pt", ".pth"):
            return self._infer_torch(x)
        return self._infer_onnx(x)

    def _infer_keras(self, x):
        try:
            import tensorflow as tf
            keras = tf.keras
        except ImportError:
            raise ImportError(
                "TensorFlow/Keras tidak ditemukan (pip install tensorflow)."
            )
        if self._model is None:
            self._model = keras.models.load_model(self.path)
        tensor = x[np.newaxis, :, :, np.newaxis]
        return np.asarray(self._model.predict(tensor, verbose=0))

    def _infer_torch(self, x):
        try:
            import torch
        except ImportError:
            raise ImportError("PyTorch tidak ditemukan (pip install torch).")
        if self._model is None:
            self._model = torch.jit.load(self.path, map_location="cpu")
            self._model.eval()
        tensor = torch.from_numpy(x[np.newaxis, np.newaxis, :, :])
        with torch.no_grad():
            keluaran = self._model(tensor)
        return keluaran.numpy()

    def _infer_onnx(self, x):
        try:
            import onnxruntime as ort
        except ImportError:
            raise ImportError(
                "ONNX Runtime tidak ditemukan (pip install onnxruntime)."
            )
        if self._model is None:
            self._model = ort.InferenceSession(self.path)
        inp = self._model.get_inputs()[0]
        tensor = _susun_tensor_onnx(x, inp.shape)
        keluaran = self._model.run(None, {inp.name: tensor})
        return np.asarray(keluaran[0])
