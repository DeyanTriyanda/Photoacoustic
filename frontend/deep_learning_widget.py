"""
Widget UI Deep Learning.

Data input:
  - Import Citra: dari citra grayscale hasil scan (hanya aktif setelah scan selesai)
  - Folder: muat PNG/JPG dari file explorer

Model default: assets/Real-ESRGAN-x2plus.onnx (auto-load).
Tidak ada preprocessing manual -- ukuran dibaca dari citra input;
keluaran disamakan ke ukuran input (bukan upscale tampilan).
"""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from backend import deep_learning as dl
from frontend.theme import PANEL_BG


class DeepLearningWidget(ttk.Frame):
    def __init__(self, master, spatial_map=None, **kwargs):
        super().__init__(master, **kwargs)
        self.spatial_map = spatial_map
        self._data = None
        self._model = None
        self._hasil_img = None
        self._scan_ready = False
        self._build_ui()
        self._muat_model_default()
        if self.spatial_map is not None:
            self.spatial_map.on_scan_image_ready = self._on_scan_image_ready

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, **pad)

        kiri = ttk.Frame(container)
        kiri.pack(side="left", fill="y", anchor="n")

        kanan = ttk.LabelFrame(container, text="Pratinjau Citra")
        kanan.pack(side="left", fill="both", expand=True, padx=(8, 0))

        # --- 1. Data Input ---
        frame_data = ttk.LabelFrame(kiri, text="1. Data Input")
        frame_data.pack(fill="x", pady=(0, 6))

        self.btn_import = ttk.Button(
            frame_data, text="Import Citra",
            command=self._import_citra_scan, state="disabled",
        )
        self.btn_import.pack(fill="x", padx=6, pady=(6, 2))

        self.btn_folder = ttk.Button(
            frame_data, text="Folder",
            command=self._muat_dari_folder,
        )
        self.btn_folder.pack(fill="x", padx=6, pady=2)

        self.lbl_data = ttk.Label(
            frame_data,
            text="Belum ada data.\nImport Citra aktif setelah scan raster selesai.",
            wraplength=220,
            font=("Segoe UI", 8), foreground="#555555", justify="left",
        )
        self.lbl_data.pack(fill="x", padx=6, pady=(2, 6))

        # --- 2. Model (auto dari assets) ---
        frame_model = ttk.LabelFrame(kiri, text="2. Model")
        frame_model.pack(fill="x", pady=(0, 6))

        self.lbl_model = ttk.Label(
            frame_model, text="Memuat model default...", wraplength=220,
            font=("Segoe UI", 8), foreground="#555555", justify="left",
        )
        self.lbl_model.pack(fill="x", padx=6, pady=6)

        # --- 3. Inferensi ---
        frame_infer = ttk.LabelFrame(kiri, text="3. Inferensi")
        frame_infer.pack(fill="x")

        self.btn_infer = ttk.Button(
            frame_infer, text="Jalankan Inferensi", command=self._jalankan_inferensi,
        )
        self.btn_infer.pack(fill="x", padx=6, pady=(6, 2))

        self.lbl_hasil = ttk.Label(
            frame_infer, text="Hasil: -", wraplength=220,
            font=("Segoe UI", 9, "bold"), justify="left",
        )
        self.lbl_hasil.pack(fill="x", padx=6, pady=(2, 2))

        self.btn_save_hasil = ttk.Button(
            frame_infer, text="Simpan Hasil (PNG)",
            command=self._simpan_hasil, state="disabled",
        )
        self.btn_save_hasil.pack(fill="x", padx=6, pady=(2, 6))

        self.fig = Figure(figsize=(8, 4.2), dpi=100, constrained_layout=True)
        self.fig.patch.set_facecolor(PANEL_BG)
        self.ax_in = self.fig.add_subplot(121)
        self.ax_out = self.fig.add_subplot(122)
        self._reset_axes()

        self.canvas = FigureCanvasTkAgg(self.fig, master=kanan)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)

    def _reset_axes(self):
        for ax, judul in ((self.ax_in, "Citra Input"), (self.ax_out, "Hasil Model")):
            ax.clear()
            ax.set_facecolor(PANEL_BG)
            ax.set_title(judul)
            ax.set_xticks([])
            ax.set_yticks([])

    def _muat_model_default(self):
        path = dl.path_model_default()
        if not os.path.isfile(path):
            self.lbl_model.config(
                text=(
                    f"Model tidak ditemukan:\n{os.path.basename(path)}\n"
                    "Simpan file di folder assets/."
                ),
                foreground="#a00",
            )
            self._model = None
            return
        try:
            self._model = dl.ModelDL(path)
            self.lbl_model.config(
                text=f"Model: {self._model.nama_file}\n(ukuran ikut citra input)",
                foreground="#006600",
            )
        except Exception as exc:
            self._model = None
            self.lbl_model.config(text=f"Gagal memuat model:\n{exc}", foreground="#a00")

    def _on_scan_image_ready(self, ready):
        """Dipanggil SpatialMapWidget saat citra grayscale selesai / di-reset."""
        self.set_scan_ready(bool(ready))

    def set_scan_ready(self, ready):
        self._scan_ready = bool(ready)
        if self.btn_import is not None:
            self.btn_import.config(state="normal" if self._scan_ready else "disabled")
        if ready:
            self.lbl_data.config(
                text="Citra grayscale siap diimpor.\nKlik Import Citra.",
                foreground="#006600",
            )
        elif self._data is None:
            self.lbl_data.config(
                text="Belum ada data.\nImport Citra aktif setelah scan raster selesai.",
                foreground="#555555",
            )

    def _set_data(self, data01, sumber):
        self._data = np.asarray(data01, dtype=np.float32)
        self._hasil_img = None
        self.btn_save_hasil.config(state="disabled")
        h, w = dl.ukuran_citra(self._data)
        self.lbl_data.config(
            text=f"Sumber: {sumber}\nUkuran input: {w} x {h} px",
            foreground="#006600",
        )
        self._reset_axes()
        self.ax_in.imshow(self._data, cmap="gray", vmin=0.0, vmax=1.0)
        self.ax_in.set_title(f"Citra Input ({w}x{h})")
        self.canvas.draw_idle()

    def _import_citra_scan(self):
        if not self._scan_ready:
            messagebox.showwarning(
                "Scan belum selesai",
                "Import Citra hanya tersedia setelah raster scan selesai "
                "dan citra grayscale (hasil akhir) lengkap.",
            )
            return
        if self.spatial_map is None or self.spatial_map.gray_matrix is None:
            messagebox.showwarning(
                "Belum ada citra",
                "Citra grayscale hasil scan belum tersedia.",
            )
            return
        if not self.spatial_map.is_grayscale_complete():
            messagebox.showwarning(
                "Citra belum lengkap",
                "Masih ada titik yang belum terekam. Tunggu scan selesai.",
            )
            return
        self._set_data(
            dl.dari_gray_matrix(self.spatial_map.gray_matrix),
            "citra grayscale hasil scan",
        )

    def _muat_dari_folder(self):
        path = filedialog.askopenfilename(
            filetypes=[("Citra", "*.png *.jpg *.jpeg *.bmp"), ("Semua file", "*.*")],
            title="Pilih Citra (PNG/JPG)",
        )
        if not path:
            return
        try:
            self._set_data(dl.muat_citra(path), os.path.basename(path))
        except Exception as exc:
            messagebox.showerror("Gagal memuat citra", f"Terjadi kesalahan:\n{exc}")

    def _jalankan_inferensi(self):
        if self._data is None:
            messagebox.showwarning(
                "Belum ada data",
                "Import Citra (setelah scan selesai) atau pilih file lewat Folder.",
            )
            return
        if self._model is None:
            self._muat_model_default()
            if self._model is None:
                messagebox.showwarning(
                    "Model belum ada",
                    "Letakkan Real-ESRGAN-x2plus.onnx di folder assets/.",
                )
                return

        # Ukuran otomatis dari citra input -- tanpa resize preprocessing.
        x = np.asarray(self._data, dtype=np.float32)
        h_in, w_in = dl.ukuran_citra(x)

        self.btn_infer.config(state="disabled")
        self.lbl_hasil.config(
            text=f"Hasil: menjalankan inferensi ({w_in}x{h_in})..."
        )

        def _worker():
            try:
                mentah = self._model.jalankan(x)
                jenis, nilai = dl.interpretasi_keluaran(mentah)
                if jenis == "image":
                    nilai = dl.samakan_ukuran(nilai, h_in, w_in)
                hasil = (jenis, nilai)
            except Exception as exc:
                self.after(0, lambda: self._selesai_inferensi(None, exc))
                return
            self.after(0, lambda: self._selesai_inferensi(hasil, None))

        threading.Thread(target=_worker, daemon=True).start()

    def _selesai_inferensi(self, hasil, error):
        self.btn_infer.config(state="normal")
        if error is not None:
            self.lbl_hasil.config(text="Hasil: -")
            if isinstance(error, ImportError):
                messagebox.showerror("Framework belum terinstall", str(error))
            else:
                messagebox.showerror("Inferensi gagal", f"Terjadi kesalahan:\n{error}")
            return

        jenis, nilai = hasil

        if jenis == "image":
            self._hasil_img = nilai
            self.ax_out.clear()
            self.ax_out.set_facecolor(PANEL_BG)
            h, w = nilai.shape[0], nilai.shape[1]
            self.ax_out.set_title(f"Hasil Model ({w}x{h})")
            self.ax_out.set_xticks([])
            self.ax_out.set_yticks([])
            if nilai.ndim == 3:
                self.ax_out.imshow(nilai)
            else:
                self.ax_out.imshow(nilai, cmap="gray", vmin=0.0, vmax=1.0)
            self.canvas.draw_idle()
            self.lbl_hasil.config(text=f"Hasil: citra {w}x{h} px (sama dengan input).")
            self.btn_save_hasil.config(state="normal")
            return

        self._hasil_img = None
        self.btn_save_hasil.config(state="disabled")
        ringkas = ", ".join(f"{v:.4f}" for v in nilai[:8])
        if nilai.size > 8:
            ringkas += ", ..."
        teks = f"Hasil: [{ringkas}]"
        if nilai.size > 1:
            teks += f"\nKelas argmax: {int(np.argmax(nilai))}"
        self.lbl_hasil.config(text=teks)

    def _simpan_hasil(self):
        if self._hasil_img is None:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png", filetypes=[("PNG image", "*.png")],
            title="Simpan Hasil Model (PNG)", initialfile="hasil_model.png",
        )
        if not path:
            return
        try:
            dl.simpan_citra_hasil(path, self._hasil_img)
            messagebox.showinfo("Tersimpan", f"Hasil model tersimpan:\n{path}")
        except Exception as exc:
            messagebox.showerror("Gagal menyimpan", f"Terjadi kesalahan:\n{exc}")
