#!/usr/bin/env python3
"""
Program terpisah: cek frekuensi plat vs sample (fotoakustik).

Mic menyala + laser termodulasi (perintah f= ke Arduino 1 → Arduino laser).
Tidak menggantikan main.py (aplikasi scanning).

Jalankan dari root repo:
  python cek_frekuensi_pa.py
  # atau
  python3 cek_frekuensi_pa.py
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from backend.audio_capture import AudioCapture
from backend.config import AUDIO_SAMPLERATE, DEFAULT_BAUDRATE, TARGET_FREQ_HZ
from backend.control import SerialController

FFT_N = 8192
N_AVG = 8
FFT_MIN_HZ = 100.0
FFT_MAX_HZ = 20000.0
UI_MS = 80


class CekFrekuensiApp(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=8)
        self.pack(fill="both", expand=True)

        self.audio = AudioCapture(on_error=self._on_audio_error)
        self.controller = SerialController(
            on_message=self._on_serial_msg,
            on_status_change=self._on_serial_status,
        )
        self.msg_q: queue.Queue = queue.Queue()
        self._device_map = {}
        self._port_map = {}
        self._mic_ok = False
        self._mod_hz = float(TARGET_FREQ_HZ)
        self._freq_plat = None
        self._amp_plat = None
        self._freq_sample = None
        self._amp_sample = None
        self._busy = False

        self._build_ui()
        self._refresh_ports()
        self._refresh_mics()
        self.after(UI_MS, self._tick)

    # --- UI ---
    def _build_ui(self):
        self.master.title("Cek Frekuensi Plat & Sample (Fotoakustik)")
        self.master.minsize(720, 520)

        kiri = ttk.Frame(self)
        kiri.pack(side="left", fill="y", padx=(0, 8))
        kanan = ttk.Frame(self)
        kanan.pack(side="left", fill="both", expand=True)

        # Arduino / laser
        fr_ard = ttk.LabelFrame(kiri, text="Arduino 1 (laser modulasi)", padding=6)
        fr_ard.pack(fill="x", pady=(0, 6))
        ttk.Label(fr_ard, text="Port:").grid(row=0, column=0, sticky="w")
        self.cmb_port = ttk.Combobox(fr_ard, state="readonly", width=22)
        self.cmb_port.grid(row=0, column=1, padx=4, pady=2, sticky="ew")
        ttk.Button(fr_ard, text="Refresh", width=8, command=self._refresh_ports).grid(
            row=0, column=2, padx=2
        )
        self.btn_ard = ttk.Button(fr_ard, text="Connect", command=self._toggle_arduino)
        self.btn_ard.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(4, 2))
        self.lbl_ard = ttk.Label(fr_ard, text="● Belum terhubung", foreground="red")
        self.lbl_ard.grid(row=2, column=0, columnspan=3, sticky="w")

        ttk.Label(fr_ard, text="Modulasi (Hz):").grid(row=3, column=0, sticky="w", pady=(6, 0))
        self.ent_freq = ttk.Entry(fr_ard, width=12)
        self.ent_freq.insert(0, str(int(TARGET_FREQ_HZ)))
        self.ent_freq.grid(row=3, column=1, sticky="ew", pady=(6, 0), padx=4)
        ttk.Button(fr_ard, text="Set Modulasi", command=self._set_modulasi).grid(
            row=3, column=2, pady=(6, 0)
        )
        ttk.Label(
            fr_ard,
            text="Laser tetap termodulasi saat cek.",
            foreground="#555",
            wraplength=240,
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(4, 0))

        # Mic
        fr_mic = ttk.LabelFrame(kiri, text="Microphone", padding=6)
        fr_mic.pack(fill="x", pady=(0, 6))
        ttk.Label(fr_mic, text="Device:").grid(row=0, column=0, sticky="w")
        self.cmb_mic = ttk.Combobox(fr_mic, state="readonly", width=22)
        self.cmb_mic.grid(row=0, column=1, padx=4, pady=2, sticky="ew")
        ttk.Button(fr_mic, text="Refresh", width=8, command=self._refresh_mics).grid(
            row=0, column=2, padx=2
        )
        self.btn_mic = ttk.Button(fr_mic, text="Connect Mic", command=self._connect_mic)
        self.btn_mic.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(4, 2))
        self.lbl_mic = ttk.Label(fr_mic, text="● Mic belum aktif", foreground="red")
        self.lbl_mic.grid(row=2, column=0, columnspan=3, sticky="w")

        # Tombol cek
        fr_cek = ttk.LabelFrame(kiri, text="Pengukuran", padding=6)
        fr_cek.pack(fill="x", pady=(0, 6))
        self.btn_plat = ttk.Button(
            fr_cek,
            text="Cek Frekuensi Plat",
            command=lambda: self._mulai_cek("plat"),
        )
        self.btn_plat.pack(fill="x", pady=3)
        self.btn_sample = ttk.Button(
            fr_cek,
            text="Cek Frekuensi Sample",
            command=lambda: self._mulai_cek("sample"),
        )
        self.btn_sample.pack(fill="x", pady=3)
        ttk.Label(
            fr_cek,
            text=(
                "1) Arahkan ke plat saja → Cek Frekuensi Plat\n"
                "2) Letakkan sample → Cek Frekuensi Sample\n"
                "Mic & laser modulasi harus sudah aktif."
            ),
            foreground="#555",
            justify="left",
            wraplength=260,
        ).pack(anchor="w", pady=(4, 0))

        # Hasil
        fr_hasil = ttk.LabelFrame(kiri, text="Hasil", padding=6)
        fr_hasil.pack(fill="x", pady=(0, 6))
        self.lbl_plat = ttk.Label(fr_hasil, text="Plat   : —")
        self.lbl_plat.pack(anchor="w")
        self.lbl_sample = ttk.Label(fr_hasil, text="Sample : —")
        self.lbl_sample.pack(anchor="w")
        self.lbl_beda = ttk.Label(fr_hasil, text="Selisih: —")
        self.lbl_beda.pack(anchor="w")
        self.lbl_live = ttk.Label(fr_hasil, text="Live peak: —", foreground="#333")
        self.lbl_live.pack(anchor="w", pady=(6, 0))

        # Log
        fr_log = ttk.LabelFrame(kiri, text="Log", padding=4)
        fr_log.pack(fill="both", expand=True)
        self.txt_log = tk.Text(fr_log, height=8, width=34, wrap="word", state="disabled")
        self.txt_log.pack(fill="both", expand=True)

        # Plot FFT
        self.fig = Figure(figsize=(5.5, 4.2), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_xlabel("Frekuensi (Hz)")
        self.ax.set_ylabel("Amplitudo")
        self.ax.set_xlim(FFT_MIN_HZ, FFT_MAX_HZ)
        self.ax.grid(True, alpha=0.3)
        (self.line_fft,) = self.ax.plot([], [], color="#1f77b4", lw=1.0)
        self.vline_mod = self.ax.axvline(self._mod_hz, color="#c44", ls="--", lw=1.0, label="modulasi")
        self.vline_plat = self.ax.axvline(np.nan, color="#2ca02c", ls=":", lw=1.2, label="plat")
        self.vline_sample = self.ax.axvline(np.nan, color="#ff7f0e", ls=":", lw=1.2, label="sample")
        self.ax.legend(loc="upper right", fontsize=8)
        self.canvas = FigureCanvasTkAgg(self.fig, master=kanan)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.fig.tight_layout()

    # --- Helpers ---
    def _log(self, teks: str):
        self.txt_log.config(state="normal")
        self.txt_log.insert("end", teks.rstrip() + "\n")
        self.txt_log.see("end")
        self.txt_log.config(state="disabled")

    def _on_audio_error(self, msg):
        self.msg_q.put(("log", f"[audio] {msg}"))

    def _on_serial_msg(self, line):
        self.msg_q.put(("log", f"[arduino] {line}"))

    def _on_serial_status(self, connected):
        self.msg_q.put(("ard_status", bool(connected)))

    def _refresh_ports(self):
        ports = SerialController.list_ports()
        labels = [lab for _, lab in ports]
        self._port_map = {lab: dev for dev, lab in ports}
        self.cmb_port["values"] = labels
        if labels and not self.cmb_port.get():
            self.cmb_port.current(0)

    def _refresh_mics(self):
        devices = AudioCapture.list_input_devices(force_rescan=True)
        self._device_map = {lab: idx for idx, lab in devices}
        self.cmb_mic["values"] = list(self._device_map.keys())
        if devices and not self.cmb_mic.get():
            self.cmb_mic.current(0)

    def _toggle_arduino(self):
        if self.controller.is_connected():
            self.controller.disconnect()
            self.lbl_ard.config(text="● Belum terhubung", foreground="red")
            self.btn_ard.config(text="Connect")
            self._log("Arduino diputus.")
            return
        label = self.cmb_port.get()
        if not label or label not in self._port_map:
            messagebox.showwarning("Port", "Pilih port Arduino 1 dulu.")
            return
        port = self._port_map[label]
        self.btn_ard.config(state="disabled")

        def worker():
            ok, msg = self.controller.connect(port, baudrate=DEFAULT_BAUDRATE)
            self.msg_q.put(("connect_ard", (ok, msg)))

        threading.Thread(target=worker, daemon=True).start()

    def _connect_mic(self):
        if self.audio.is_running():
            self.audio.stop()
            self._mic_ok = False
            self.lbl_mic.config(text="● Mic belum aktif", foreground="red")
            self.btn_mic.config(text="Connect Mic")
            self._log("Mic dimatikan.")
            return
        label = self.cmb_mic.get()
        if not label or label not in self._device_map:
            messagebox.showwarning("Mic", "Pilih device mic dulu.")
            return
        idx = self._device_map[label]
        ok, msg = self.audio.start(
            device_index=idx,
            samplerate=AUDIO_SAMPLERATE,
            buffer_seconds=1.0,
        )
        self._log(msg)
        if ok:
            self._mic_ok = True
            self.lbl_mic.config(text="● Mic aktif", foreground="green")
            self.btn_mic.config(text="Disconnect Mic")
        else:
            messagebox.showerror("Mic", msg)

    def _set_modulasi(self):
        raw = self.ent_freq.get().strip().replace(",", ".")
        try:
            hz = float(raw)
        except ValueError:
            messagebox.showwarning("Modulasi", "Isi frekuensi dengan angka.")
            return
        if hz <= 0 or hz > FFT_MAX_HZ:
            messagebox.showwarning(
                "Modulasi", f"Frekuensi harus > 0 dan ≤ {int(FFT_MAX_HZ)} Hz."
            )
            return
        self._mod_hz = hz
        self.vline_mod.set_xdata([hz, hz])
        self.canvas.draw_idle()
        if not self.controller.is_connected():
            self._log(
                f"Modulasi {hz:g} Hz disimpan di UI. "
                "Hubungkan Arduino agar laser ikut."
            )
            return
        ok, msg = self.controller.set_laser_freq(hz)
        self._log(msg if ok else f"Gagal set modulasi: {msg}")

    def _siap_ukur(self):
        if not self.audio.is_running():
            messagebox.showwarning(
                "Mic", "Nyalakan mic dulu (Connect Mic)."
            )
            return False
        if not self.controller.is_connected():
            if not messagebox.askyesno(
                "Laser",
                "Arduino belum terhubung — laser mungkin tidak termodulasi.\n"
                "Lanjut ukur mic saja?",
            ):
                return False
        return True

    def _mulai_cek(self, mode: str):
        if self._busy:
            return
        if not self._siap_ukur():
            return
        self._busy = True
        self.btn_plat.config(state="disabled")
        self.btn_sample.config(state="disabled")
        self._log(f"Mengukur frekuensi {mode} ...")

        def worker():
            try:
                freq, amp, freqs, mag = self._ukur_puncak()
                self.msg_q.put(("hasil", (mode, freq, amp, freqs, mag)))
            except Exception as e:
                self.msg_q.put(("hasil_err", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _ukur_puncak(self):
        """Rata-rata beberapa FFT; cari puncak di jendela sekitar modulasi (±2 kHz,
        dibatasi FFT_MIN..FFT_MAX). Juga laporkan puncak global di rentang penuh
        jika lebih kuat jauh dari modulasi (info noise)."""
        acc = None
        freqs_ref = None
        for _ in range(N_AVG):
            samples = self.audio.capture_samples(FFT_N, timeout=3.0)
            freqs, mag = self.audio.compute_fft(
                samples, min_freq=FFT_MIN_HZ, max_freq=FFT_MAX_HZ
            )
            if freqs_ref is None:
                freqs_ref = freqs
                acc = mag.astype(np.float64)
            else:
                n = min(len(acc), len(mag))
                acc[:n] += mag[:n]
        mag_avg = (acc / float(N_AVG)).astype(np.float64)
        freqs = freqs_ref

        # Jendela pencarian: sekitar frekuensi modulasi
        half = 2000.0
        f0 = max(FFT_MIN_HZ, self._mod_hz - half)
        f1 = min(FFT_MAX_HZ, self._mod_hz + half)
        mask = (freqs >= f0) & (freqs <= f1)
        if not np.any(mask):
            mask = np.ones(len(freqs), dtype=bool)
        idx_local = int(np.argmax(mag_avg[mask]))
        # map ke indeks global
        idxs = np.flatnonzero(mask)
        idx = int(idxs[idx_local])
        return float(freqs[idx]), float(mag_avg[idx]), freqs, mag_avg

    def _update_hasil_labels(self):
        if self._freq_plat is None:
            self.lbl_plat.config(text="Plat   : —")
        else:
            self.lbl_plat.config(
                text=f"Plat   : {self._freq_plat:.1f} Hz  (amp {self._amp_plat:.4g})"
            )
        if self._freq_sample is None:
            self.lbl_sample.config(text="Sample : —")
        else:
            self.lbl_sample.config(
                text=f"Sample : {self._freq_sample:.1f} Hz  (amp {self._amp_sample:.4g})"
            )
        if self._freq_plat is not None and self._freq_sample is not None:
            df = self._freq_sample - self._freq_plat
            self.lbl_beda.config(text=f"Selisih sample−plat: {df:+.1f} Hz")
        else:
            self.lbl_beda.config(text="Selisih: —")

    def _tick(self):
        try:
            while True:
                kind, payload = self.msg_q.get_nowait()
                if kind == "log":
                    self._log(payload)
                elif kind == "ard_status":
                    if payload:
                        self.lbl_ard.config(text="● Terhubung", foreground="green")
                        self.btn_ard.config(text="Disconnect", state="normal")
                    else:
                        self.lbl_ard.config(text="● Belum terhubung", foreground="red")
                        self.btn_ard.config(text="Connect", state="normal")
                elif kind == "connect_ard":
                    ok, msg = payload
                    self._log(msg)
                    self.btn_ard.config(state="normal")
                    if ok:
                        self.lbl_ard.config(text="● Terhubung", foreground="green")
                        self.btn_ard.config(text="Disconnect")
                        # Kirim ulang modulasi agar laser nyala
                        self._set_modulasi()
                    else:
                        messagebox.showerror("Arduino", msg)
                elif kind == "hasil":
                    mode, freq, amp, freqs, mag = payload
                    self._busy = False
                    self.btn_plat.config(state="normal")
                    self.btn_sample.config(state="normal")
                    if mode == "plat":
                        self._freq_plat = freq
                        self._amp_plat = amp
                        self.vline_plat.set_xdata([freq, freq])
                        self._log(f"Plat → {freq:.1f} Hz (amp {amp:.4g})")
                    else:
                        self._freq_sample = freq
                        self._amp_sample = amp
                        self.vline_sample.set_xdata([freq, freq])
                        self._log(f"Sample → {freq:.1f} Hz (amp {amp:.4g})")
                    self._update_hasil_labels()
                    self.line_fft.set_data(freqs, mag)
                    if len(mag):
                        self.ax.set_ylim(0, max(float(np.max(mag)) * 1.15, 1e-9))
                    self.canvas.draw_idle()
                elif kind == "hasil_err":
                    self._busy = False
                    self.btn_plat.config(state="normal")
                    self.btn_sample.config(state="normal")
                    self._log(f"Gagal ukur: {payload}")
                    messagebox.showerror("Pengukuran", payload)
        except queue.Empty:
            pass

        # Live peak (ringan) jika mic aktif dan tidak sedang ukur
        if self.audio.is_running() and not self._busy:
            try:
                f, a = self.audio.get_peak(min_freq=FFT_MIN_HZ, max_freq=FFT_MAX_HZ)
                self.lbl_live.config(text=f"Live peak: {f:.1f} Hz (amp {a:.4g})")
                freqs, mag = self.audio.get_fft(
                    min_freq=FFT_MIN_HZ, max_freq=FFT_MAX_HZ
                )
                if len(freqs):
                    self.line_fft.set_data(freqs, mag)
                    self.ax.set_ylim(0, max(float(np.max(mag)) * 1.15, 1e-9))
                    self.canvas.draw_idle()
            except Exception:
                pass

        self.after(UI_MS, self._tick)

    def shutdown(self):
        try:
            if self.audio.is_running():
                self.audio.stop()
        except Exception:
            pass
        try:
            if self.controller.is_connected():
                self.controller.disconnect()
        except Exception:
            pass


def main():
    root = tk.Tk()
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    app = CekFrekuensiApp(root)

    def on_close():
        app.shutdown()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
