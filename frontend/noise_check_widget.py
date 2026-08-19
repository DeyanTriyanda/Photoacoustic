"""
Tab Cek Noise Plat: spektrum mic saat laser mengenai tatakan/plat.

Tujuan: melihat frekuensi noise mana saja yang muncul (biasanya < frekuensi
modulasi sampel) agar bisa memisahkan plat vs objek.
"""

import os
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
        get_modulasi_hz: callable → float|None frekuensi Set Modulasi.
        """
        super().__init__(master, **kwargs)
        self.audio = audio_capture
        self.get_modulasi_hz = get_modulasi_hz
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
                "Arahkan laser ke plat (tanpa sampel) → Set Modulasi → "
                "pastikan mic aktif → klik Ambil Spektrum Noise."
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
            kontrol, text="Simpan Puncak (CSV)",
            command=self._simpan_csv, state="disabled",
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

        # Plot
        frame_plot = ttk.LabelFrame(isi, text="Spektrum FFT (noise plat)")
        frame_plot.pack(side="left", fill="both", expand=True)

        self.fig = Figure(figsize=(6.5, 4.2), dpi=100, constrained_layout=True)
        self.fig.patch.set_facecolor(PANEL_BG)
        self.ax = self.fig.add_subplot(111)
        self._reset_plot()
        self.canvas = FigureCanvasTkAgg(self.fig, master=frame_plot)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)

        # Daftar puncak
        frame_list = ttk.LabelFrame(isi, text="Frekuensi terdeteksi")
        frame_list.pack(side="left", fill="y", padx=(8, 0))

        kolom = ("rank", "freq", "amp", "label")
        self.tree = ttk.Treeview(
            frame_list, columns=kolom, show="headings", height=18
        )
        self.tree.heading("rank", text="#")
        self.tree.heading("freq", text="Hz")
        self.tree.heading("amp", text="Amp")
        self.tree.heading("label", text="Label")
        self.tree.column("rank", width=36, anchor="center")
        self.tree.column("freq", width=80, anchor="e")
        self.tree.column("amp", width=80, anchor="e")
        self.tree.column("label", width=80, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)

        self.lbl_ringkas = ttk.Label(
            frame_list,
            text="Label: plat = di bawah Set Modulasi; modulasi = dekat frekuensi set.",
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
                puncak = na.temukan_puncak_spektrum(
                    freqs, mag,
                    min_freq_hz=MIN_FREQ_HZ,
                    max_freq_hz=MAX_FREQ_HZ,
                    n_puncak=n_puncak,
                )
                fmod = None
                if self.get_modulasi_hz is not None:
                    try:
                        fmod = float(self.get_modulasi_hz())
                    except Exception:
                        fmod = None
                puncak = na.beri_label_puncak(puncak, frekuensi_modulasi_hz=fmod)
                hasil = (freqs, mag, puncak, fmod)
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
        freqs, mag, puncak, fmod = hasil
        self._freqs, self._mag, self._puncak = freqs, mag, puncak
        self._busy = False
        self.btn_ambil.config(state="normal")
        self.btn_simpan.config(state="normal")
        self.lbl_status.config(
            text=f"Status: {len(puncak)} puncak | avg {N_AVG}x FFT",
            foreground="#060",
        )

        self.ax.clear()
        self.ax.set_facecolor(PANEL_BG)
        judul = "Spektrum noise saat laser → plat"
        if fmod:
            judul += f" (Set Modulasi {fmod:g} Hz)"
        self.ax.set_title(judul)
        self.ax.set_xlabel("Frekuensi (Hz)")
        self.ax.set_ylabel("Amplitudo")
        self.ax.plot(freqs, mag, color="#1a5fb4", linewidth=0.9)
        if fmod and fmod > 0:
            self.ax.axvline(
                fmod, color="#e01b24", linestyle="--", linewidth=1.0,
                label=f"Set Modulasi {fmod:g} Hz",
            )
            self.ax.axvspan(MIN_FREQ_HZ, fmod, color="#888", alpha=0.12, label="Zona plat (< set)")
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
        if fmod:
            self.ax.legend(loc="upper right", fontsize=8)
        self.canvas.draw_idle()

        for item in self.tree.get_children():
            self.tree.delete(item)
        for p in puncak:
            self.tree.insert(
                "",
                "end",
                values=(
                    p.rank,
                    f"{p.freq_hz:.1f}",
                    f"{p.amplitude:.4g}",
                    p.label or "-",
                ),
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
