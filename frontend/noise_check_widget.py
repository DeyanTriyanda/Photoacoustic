"""
Tab Cek Noise Plat: spektrum mic saat laser mengenai tatakan/plat.

Murni analisis frekuensi dari FFT — TIDAK memakai nilai Set Modulasi.
Tujuan: melihat frekuensi noise mana saja yang muncul di plat.
"""

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from backend import noise_analysis as na
from frontend.theme import PANEL_BG

FFT_N = 8192
N_AVG = 8
MAX_FREQ_HZ = 20000.0
MIN_FREQ_HZ = 20.0


class NoiseCheckWidget(ttk.Frame):
    def __init__(self, master, audio_capture=None, get_modulasi_hz=None, **kwargs):
        """
        audio_capture: instance AudioCapture bersama (dari FFTWidget).
        get_modulasi_hz: diabaikan (kompatibilitas pemanggilan lama).
        """
        super().__init__(master, **kwargs)
        self.audio = audio_capture
        self._puncak = []
        self._freqs = None
        self._mag = None
        self._busy = False
        self._build_ui()

    def set_audio_capture(self, audio_capture):
        self.audio = audio_capture

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}
        atas = ttk.Frame(self)
        atas.pack(fill="x", **pad)

        ttk.Label(
            atas,
            text=(
                "Arahkan laser ke plat (tanpa sampel) → pastikan mic aktif → "
                "klik Ambil Spektrum Noise. "
                "Hasil = frekuensi murni dari FFT (tidak memakai Set Modulasi)."
            ),
            wraplength=720,
            foreground="#444",
        ).pack(anchor="w")

        kontrol = ttk.Frame(self)
        kontrol.pack(fill="x", **pad)

        self.btn_ambil = ttk.Button(
            kontrol, text="Ambil Spektrum Noise", command=self._ambil_spektrum
        )
        self.btn_ambil.pack(side="left", padx=(0, 6))

        self.btn_simpan = ttk.Button(
            kontrol,
            text="Simpan Puncak (CSV)",
            command=self._simpan_csv,
            state="disabled",
        )
        self.btn_simpan.pack(side="left", padx=(0, 6))

        ttk.Label(kontrol, text="Jumlah puncak:").pack(side="left")
        self.var_n = tk.StringVar(value="15")
        ttk.Entry(kontrol, textvariable=self.var_n, width=5).pack(
            side="left", padx=(2, 8)
        )

        self.lbl_status = ttk.Label(
            kontrol, text="Status: siap", foreground="#555"
        )
        self.lbl_status.pack(side="left", padx=8)

        isi = ttk.Frame(self)
        isi.pack(fill="both", expand=True, **pad)

        frame_plot = ttk.LabelFrame(isi, text="Spektrum FFT (noise plat — murni)")
        frame_plot.pack(side="left", fill="both", expand=True)

        self.fig = Figure(figsize=(6.5, 4.2), dpi=100, constrained_layout=True)
        self.fig.patch.set_facecolor(PANEL_BG)
        self.ax = self.fig.add_subplot(111)
        self._reset_plot()
        self.canvas = FigureCanvasTkAgg(self.fig, master=frame_plot)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)

        frame_list = ttk.LabelFrame(isi, text="Frekuensi terdeteksi (dari spektrum)")
        frame_list.pack(side="left", fill="y", padx=(8, 0))

        kolom = ("rank", "freq", "amp")
        self.tree = ttk.Treeview(
            frame_list, columns=kolom, show="headings", height=18
        )
        self.tree.heading("rank", text="#")
        self.tree.heading("freq", text="Hz")
        self.tree.heading("amp", text="Amp")
        self.tree.column("rank", width=40, anchor="center")
        self.tree.column("freq", width=90, anchor="e")
        self.tree.column("amp", width=90, anchor="e")
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)

        self.lbl_ringkas = ttk.Label(
            frame_list,
            text="Hanya puncak FFT mic. Set Modulasi tidak memengaruhi daftar ini.",
            wraplength=280,
            foreground="#555",
            font=("Segoe UI", 8),
        )
        self.lbl_ringkas.pack(fill="x", padx=6, pady=(0, 6))

    def _reset_plot(self):
        self.ax.clear()
        self.ax.set_facecolor(PANEL_BG)
        self.ax.set_title("Spektrum noise (belum diambil)")
        self.ax.set_xlabel("Frekuensi (Hz)")
        self.ax.set_ylabel("Amplitudo")
        self.ax.set_xlim(MIN_FREQ_HZ, MAX_FREQ_HZ)
        self.ax.grid(True, alpha=0.3)

    def _ambil_spektrum(self):
        if self._busy:
            return
        if self.audio is None or not self.audio.is_running():
            messagebox.showwarning(
                "Mic belum aktif",
                "Aktifkan microphone di panel Koneksi Serial dulu "
                "(sama seperti tab FFT).",
            )
            return
        try:
            n_puncak = max(1, min(50, int(self.var_n.get().strip())))
        except ValueError:
            messagebox.showwarning("Input", "Jumlah puncak harus angka.")
            return

        self._busy = True
        self.btn_ambil.config(state="disabled")
        self.lbl_status.config(text="Status: merekam...", foreground="#a60")

        def worker():
            try:
                mag_sum = None
                freqs = None
                for _ in range(N_AVG):
                    samples = self.audio.capture_samples(FFT_N, timeout=3.0)
                    f, m = self.audio.compute_fft(
                        samples,
                        window="hann",
                        min_freq=MIN_FREQ_HZ,
                        max_freq=MAX_FREQ_HZ,
                    )
                    if len(f) == 0:
                        continue
                    if mag_sum is None:
                        freqs, mag_sum = f, m.astype(np.float64)
                    else:
                        mag_sum += m
                if freqs is None:
                    raise RuntimeError("Gagal mengambil spektrum (data kosong).")
                mag = mag_sum / N_AVG
                # Murni dari spektrum — tanpa Set Modulasi
                puncak = na.temukan_puncak_spektrum(
                    freqs,
                    mag,
                    min_freq_hz=MIN_FREQ_HZ,
                    max_freq_hz=MAX_FREQ_HZ,
                    n_puncak=n_puncak,
                )
                hasil = (freqs, mag, puncak)
                self.after(0, lambda: self._selesai_ok(hasil))
            except Exception as exc:
                self.after(0, lambda: self._selesai_err(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _selesai_err(self, exc):
        self._busy = False
        self.btn_ambil.config(state="normal")
        self.lbl_status.config(text="Status: gagal", foreground="#a00")
        messagebox.showerror("Cek Noise gagal", str(exc))

    def _selesai_ok(self, hasil):
        freqs, mag, puncak = hasil
        self._freqs, self._mag, self._puncak = freqs, mag, puncak
        self._busy = False
        self.btn_ambil.config(state="normal")
        self.btn_simpan.config(state="normal")
        self.lbl_status.config(
            text=f"Status: {len(puncak)} puncak | avg {N_AVG}x FFT (murni)",
            foreground="#060",
        )

        self.ax.clear()
        self.ax.set_facecolor(PANEL_BG)
        self.ax.set_title("Spektrum noise plat (frekuensi murni dari FFT)")
        self.ax.set_xlabel("Frekuensi (Hz)")
        self.ax.set_ylabel("Amplitudo")
        self.ax.plot(freqs, mag, color="#1a5fb4", linewidth=0.9)
        for p in puncak[:10]:
            self.ax.plot(p.freq_hz, p.amplitude, "o", markersize=4, color="#e66100")
            self.ax.annotate(
                f"{p.freq_hz:.0f}",
                (p.freq_hz, p.amplitude),
                textcoords="offset points",
                xytext=(0, 6),
                ha="center",
                fontsize=7,
            )
        self.ax.set_xlim(MIN_FREQ_HZ, MAX_FREQ_HZ)
        self.ax.grid(True, alpha=0.3)
        self.canvas.draw_idle()

        for item in self.tree.get_children():
            self.tree.delete(item)
        for p in puncak:
            self.tree.insert(
                "",
                "end",
                values=(p.rank, f"{p.freq_hz:.1f}", f"{p.amplitude:.4g}"),
            )

    def _simpan_csv(self):
        if not self._puncak:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            title="Simpan daftar puncak noise",
            initialfile="noise_plat_puncak.csv",
        )
        if not path:
            return
        try:
            na.simpan_puncak_csv(path, self._puncak)
            messagebox.showinfo("Tersimpan", f"Disimpan:\n{path}")
        except Exception as exc:
            messagebox.showerror("Gagal menyimpan", str(exc))
