"""
Widget UI Deep Learning -- logika di backend/deep_learning.py.
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
        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, **pad)

        kiri = ttk.Frame(container)
        kiri.pack(side="left", fill="y", anchor="n")

        kanan = ttk.LabelFrame(container, text="Pratinjau Citra Input")
        kanan.pack(side="left", fill="both", expand=True, padx=(8, 0))

        frame_data = ttk.LabelFrame(kiri, text="1. Data Input")
        frame_data.pack(fill="x", pady=(0, 6))

        if self.spatial_map is not None:
            ttk.Button(
                frame_data, text="Ambil dari Hasil Scan",
                command=self._ambil_dari_scan,
            ).pack(fill="x", padx=6, pady=(6, 2))

        ttk.Button(frame_data, text="Muat CSV...", command=self._muat_csv).pack(
            fill="x", padx=6, pady=2
        )
        ttk.Button(
            frame_data, text="Muat Citra (PNG/JPG)...", command=self._muat_citra,
        ).pack(fill="x", padx=6, pady=2)

        self.lbl_data = ttk.Label(
            frame_data, text="Belum ada data.", wraplength=220,
            font=("Segoe UI", 8), foreground="#555555", justify="left",
        )
        self.lbl_data.pack(fill="x", padx=6, pady=(2, 6))

        frame_prep = ttk.LabelFrame(kiri, text="2. Preprocessing")
        frame_prep.pack(fill="x", pady=(0, 6))

        baris_n = ttk.Frame(frame_prep)
        baris_n.pack(fill="x", padx=6, pady=(6, 2))
        ttk.Label(baris_n, text="Ukuran input model (NxN):").pack(side="left")
        self.entry_n = ttk.Entry(baris_n, width=6)
        self.entry_n.insert(0, str(dl.DEFAULT_INPUT_SIZE))
        self.entry_n.pack(side="left", padx=(4, 0))

        self.var_resize = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            frame_prep, text="Resize ke NxN (matikan utk Real-ESRGAN)",
            variable=self.var_resize,
        ).pack(fill="x", padx=6, pady=(0, 2))

        ttk.Label(
            frame_prep,
            text="Citra dinormalisasi ke 0..1. Model ONNX ber-ukuran\n"
                 "input tetap akan di-resize otomatis oleh backend.",
            font=("Segoe UI", 8), foreground="#555555", justify="left",
        ).pack(fill="x", padx=6, pady=(0, 6))

        frame_model = ttk.LabelFrame(kiri, text="3. Model Terlatih")
        frame_model.pack(fill="x", pady=(0, 6))

        ttk.Button(
            frame_model, text="Muat Model (.h5/.keras/.pt/.onnx)...",
            command=self._muat_model,
        ).pack(fill="x", padx=6, pady=(6, 2))

        self.lbl_model = ttk.Label(
            frame_model, text="Belum ada model.", wraplength=220,
            font=("Segoe UI", 8), foreground="#555555", justify="left",
        )
        self.lbl_model.pack(fill="x", padx=6, pady=(2, 6))

        frame_infer = ttk.LabelFrame(kiri, text="4. Inferensi")
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

    def _set_data(self, data01, sumber):
        self._data = np.asarray(data01, dtype=np.float32)
        self._hasil_img = None
        self.btn_save_hasil.config(state="disabled")
        self.lbl_data.config(
            text=f"Sumber: {sumber}\nUkuran: {self._data.shape[1]}x{self._data.shape[0]} px",
            foreground="#006600",
        )
        self._reset_axes()
        self.ax_in.imshow(self._data, cmap="gray", vmin=0.0, vmax=1.0)
        self.canvas.draw_idle()

    def _ambil_dari_scan(self):
        if self.spatial_map is None or self.spatial_map.gray_matrix is None:
            messagebox.showwarning(
                "Belum ada hasil scan",
                "Belum ada citra hasil scan. Jalankan scan dulu di tab "
                "Citra 2D Fotoakustik.",
            )
            return
        self._set_data(
            dl.dari_gray_matrix(self.spatial_map.gray_matrix),
            "hasil scan terakhir",
        )

    def _muat_csv(self):
        path = filedialog.askopenfilename(
            filetypes=[("CSV file", "*.csv"), ("Semua file", "*.*")],
            title="Muat CSV (amplitudo / matrix grayscale)",
        )
        if not path:
            return
        try:
            self._set_data(dl.muat_csv(path), os.path.basename(path))
        except Exception as exc:
            messagebox.showerror("Gagal memuat CSV", f"Terjadi kesalahan:\n{exc}")

    def _muat_citra(self):
        path = filedialog.askopenfilename(
            filetypes=[("Citra", "*.png *.jpg *.jpeg *.bmp"), ("Semua file", "*.*")],
            title="Muat Citra",
        )
        if not path:
            return
        try:
            self._set_data(dl.muat_citra(path), os.path.basename(path))
        except Exception as exc:
            messagebox.showerror("Gagal memuat citra", f"Terjadi kesalahan:\n{exc}")

    def _get_input_size(self):
        try:
            return int(self.entry_n.get())
        except (ValueError, tk.TclError):
            return dl.DEFAULT_INPUT_SIZE

    def _muat_model(self):
        path = filedialog.askopenfilename(
            filetypes=[
                ("Model DL", "*.h5 *.keras *.pt *.pth *.onnx"),
                ("Semua file", "*.*"),
            ],
            title="Muat Model Terlatih",
        )
        if not path:
            return
        try:
            self._model = dl.ModelDL(path)
        except ValueError as exc:
            messagebox.showerror("Model tidak didukung", str(exc))
            return
        self.lbl_model.config(
            text=f"Model: {self._model.nama_file}\n(di-load saat inferensi pertama)",
            foreground="#006600",
        )

    def _jalankan_inferensi(self):
        if self._data is None:
            messagebox.showwarning(
                "Belum ada data",
                "Muat data dulu (dari hasil scan / CSV / citra).",
            )
            return
        if self._model is None:
            messagebox.showwarning(
                "Belum ada model",
                "Muat file model terlatih dulu (.h5/.keras/.pt/.onnx).\n\n"
                "Contoh: file realesrgan .onnx untuk super-resolution, "
                "atau model klasifikasi hasil pelatihan Anda.",
            )
            return

        if self.var_resize.get():
            x = dl.siapkan_input(self._data, self._get_input_size())
        else:
            x = np.asarray(self._data, dtype=np.float32)

        self.btn_infer.config(state="disabled")
        self.lbl_hasil.config(text="Hasil: menjalankan inferensi...")

        def _worker():
            try:
                hasil = self._model.jalankan(x)
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

        jenis, nilai = dl.interpretasi_keluaran(hasil)

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
            self.lbl_hasil.config(text=f"Hasil: citra {w}x{h} px.")
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
