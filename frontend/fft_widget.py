"""
Widget FFT: waveform, spektrum, puncak -- rolling buffer AudioCapture.

Panel Audio Input bisa dipasang di parent eksternal (kolom kiri ui_control).
Rentang FFT di latar belakang: FFT_MIN_HZ .. FFT_MAX_HZ (tanpa UI).
"""

import tkinter as tk
from tkinter import messagebox, ttk

import matplotlib.ticker as ticker
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from backend.audio_capture import AudioCapture
from backend.config import FFT_MAX_HZ, FFT_MIN_HZ

UPDATE_INTERVAL_MS = 50
DEFAULT_SAMPLERATE = 48000


class FFTWidget(ttk.Frame):
    def __init__(self, master, show_controls=True, **kwargs):
        super().__init__(master, **kwargs)

        self.audio = AudioCapture(on_error=self._on_audio_error)
        self._running_ui_update = False
        self._device_map = {}
        self._confirmed_device_label = None

        self.cmb_device = None
        self.cmb_samplerate = None
        self.btn_refresh = None
        self.btn_connect_mic = None
        self.lbl_status = None

        if show_controls:
            self.mount_device_panel(self)

        self._build_plots()
        if show_controls:
            self._refresh_devices()

    def mount_device_panel(self, parent, pad=None):
        pad = pad or {"padx": 8, "pady": 3}
        frame_dev = ttk.LabelFrame(parent, text="Audio Input (Soundcard)")
        frame_dev.pack(fill="x", **pad)

        ttk.Label(frame_dev, text="Device:").grid(row=0, column=0, padx=4, pady=4, sticky="w")
        self.cmb_device = ttk.Combobox(frame_dev, width=14, state="readonly")
        self.cmb_device.grid(row=0, column=1, padx=4, pady=4, sticky="w")

        self.btn_refresh = ttk.Button(
            frame_dev, text="Refresh", command=self._refresh_devices, width=7
        )
        self.btn_refresh.grid(row=0, column=2, padx=2, pady=4)

        self.btn_connect_mic = ttk.Button(
            frame_dev, text="Connect Mic", command=self._connect_microphone, width=11,
        )
        self.btn_connect_mic.grid(row=0, column=3, padx=2, pady=4)

        ttk.Label(frame_dev, text="Samplerate:").grid(row=1, column=0, padx=4, pady=4, sticky="w")
        self.cmb_samplerate = ttk.Combobox(
            frame_dev, width=10, state="readonly",
            values=["44100", "48000", "96000"],
        )
        self.cmb_samplerate.set(str(DEFAULT_SAMPLERATE))
        self.cmb_samplerate.grid(row=1, column=1, padx=4, pady=4, sticky="w")

        self.lbl_status = ttk.Label(frame_dev, text="\u25CF Belum aktif", foreground="red")
        self.lbl_status.grid(row=1, column=2, columnspan=2, padx=4, pady=4, sticky="w")
        return frame_dev

    def _build_plots(self):
        pad = {"padx": 8, "pady": 4}
        frame_plot = ttk.Frame(self)
        frame_plot.pack(fill="both", expand=True, **pad)

        self.fig = Figure(figsize=(7, 5.5), dpi=100, constrained_layout=True)
        self.ax_wave = self.fig.add_subplot(211)
        self.ax_fft = self.fig.add_subplot(212)

        self.ax_wave.set_title("1. Waveform (Domain Waktu)")
        self.ax_wave.set_xlabel("Waktu (s)")
        self.ax_wave.set_ylabel("Amplitudo")
        self.ax_wave.set_xlim(0.0, 1.0)
        self.ax_wave.set_ylim(-1.05, 1.05)
        (self.line_wave,) = self.ax_wave.plot([], [], linewidth=0.8)

        self.ax_fft.set_title("2. FFT (Domain Frekuensi)")
        self.ax_fft.set_xlabel("Frekuensi (Hz)")
        self.ax_fft.set_ylabel("Amplitudo")
        self.ax_fft.set_xlim(FFT_MIN_HZ, FFT_MAX_HZ)
        self.ax_fft.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.3f"))
        (self.line_fft,) = self.ax_fft.plot([], [], linewidth=0.8)
        (self.marker_peak,) = self.ax_fft.plot([], [], "ro", markersize=6)

        self.canvas = FigureCanvasTkAgg(self.fig, master=frame_plot)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        frame_out = ttk.LabelFrame(self, text="3. Nilai Hasil (Output)")
        frame_out.pack(fill="x", **pad)

        self.lbl_peak_freq = ttk.Label(
            frame_out, text="Frekuensi Puncak: - Hz", font=("Segoe UI", 12, "bold")
        )
        self.lbl_peak_freq.pack(side="left", padx=20, pady=8)

        self.lbl_peak_amp = ttk.Label(
            frame_out, text="Amplitudo Puncak: -", font=("Segoe UI", 12, "bold")
        )
        self.lbl_peak_amp.pack(side="left", padx=20, pady=8)

    def _refresh_devices(self):
        if self.cmb_device is None:
            return
        devices = AudioCapture.list_input_devices(force_rescan=not self.audio.is_running())
        self._device_map = {label: idx for idx, label in devices}
        labels = list(self._device_map.keys())
        self.cmb_device["values"] = labels
        if labels:
            preferred = next(
                (l for l in labels if "umc" in l.lower() or "usb" in l.lower()),
                labels[0],
            )
            self.cmb_device.set(preferred)
        else:
            self.cmb_device.set("")

        if (self._confirmed_device_label
                and self._confirmed_device_label not in self._device_map):
            self._confirmed_device_label = None
            if self.lbl_status is not None:
                self.lbl_status.config(text="\u25CF Belum aktif", foreground="red")

    def set_device_lock(self, locked):
        if self.cmb_device is None:
            return
        if locked:
            self.cmb_device.config(state="disabled")
            self.cmb_samplerate.config(state="disabled")
            self.btn_refresh.config(state="disabled")
            self.btn_connect_mic.config(state="disabled")
        else:
            self.cmb_device.config(state="readonly")
            self.cmb_samplerate.config(state="readonly")
            self.btn_refresh.config(state="normal")
            self.btn_connect_mic.config(state="normal")

    def _connect_microphone(self):
        label = self.cmb_device.get() if self.cmb_device is not None else ""
        if not label or label not in self._device_map:
            self._confirmed_device_label = None
            if self.lbl_status is not None:
                self.lbl_status.config(text="\u25CF Belum aktif", foreground="red")
            messagebox.showwarning(
                "Mic belum dipilih",
                "Pilih device mic dari dropdown terlebih dahulu, lalu klik "
                "'Connect Mic'.",
            )
            return
        self._confirmed_device_label = label
        if self.lbl_status is not None:
            self.lbl_status.config(text="\u25CF Aktif", foreground="green")

    def is_mic_connected(self):
        return self._confirmed_device_label is not None

    def ensure_audio_started(self):
        if self.audio.is_running():
            return True, "Audio sudah aktif."

        label = self._confirmed_device_label
        if not label:
            return False, (
                "Mic belum terhubung. Pilih device di panel Audio Input lalu klik "
                "'Connect Mic' terlebih dahulu."
            )
        if label not in self._device_map:
            self._confirmed_device_label = None
            if self.lbl_status is not None:
                self.lbl_status.config(text="\u25CF Belum aktif", foreground="red")
            return False, (
                f"Mic '{label}' tidak lagi terdeteksi (tercabut?). "
                "Klik Refresh lalu Connect Mic ulang."
            )

        device_index = self._device_map[label]
        try:
            samplerate = int(self.cmb_samplerate.get()) if self.cmb_samplerate else DEFAULT_SAMPLERATE
        except ValueError:
            samplerate = DEFAULT_SAMPLERATE

        ok, msg = self.audio.start(device_index, samplerate=samplerate, channels=1)
        if not ok:
            return False, msg

        if self.lbl_status is not None:
            self.lbl_status.config(text="\u25CF Aktif", foreground="green")
        if not self._running_ui_update:
            self._running_ui_update = True
            self._update_plot()
        return True, "Audio berhasil diaktifkan."

    def stop_audio(self):
        if self.audio.is_running():
            self.audio.stop()
        self._running_ui_update = False
        if not self._confirmed_device_label and self.lbl_status is not None:
            self.lbl_status.config(text="\u25CF Belum aktif", foreground="red")

    def _on_audio_error(self, msg):
        print(f"[AUDIO WARNING] {msg}")

    def _get_freq_range(self):
        return FFT_MIN_HZ, FFT_MAX_HZ

    def _update_plot(self):
        if not self._running_ui_update or not self.audio.is_running():
            self._running_ui_update = False
            return

        wave = self.audio.get_waveform()
        if len(wave) > 0:
            t = np.arange(len(wave)) / self.audio.samplerate
            self.line_wave.set_data(t, wave)

        fmin, fmax = self._get_freq_range()
        freqs, mag = self.audio.get_fft(min_freq=fmin, max_freq=fmax)

        if len(freqs) > 0:
            self.line_fft.set_data(freqs, mag)
            y_max = float(np.max(mag)) if len(mag) else 0.01
            self.ax_fft.set_ylim(0.0, max(y_max * 1.15, 0.01))

            peak_freq, peak_amp = self.audio.get_peak(min_freq=fmin, max_freq=fmax)
            self.lbl_peak_freq.config(text=f"Frekuensi Puncak: {peak_freq:.1f} Hz")
            self.lbl_peak_amp.config(text=f"Amplitudo Puncak: {peak_amp:.6f}")
            self.marker_peak.set_data([peak_freq], [peak_amp])

        self.canvas.draw_idle()
        self.after(UPDATE_INTERVAL_MS, self._update_plot)

    def get_current_peak(self, min_freq=None, max_freq=None):
        if min_freq is None or max_freq is None:
            min_freq, max_freq = self._get_freq_range()
        return self.audio.get_peak(min_freq=min_freq, max_freq=max_freq)

    def shutdown(self):
        self._running_ui_update = False
        self.audio.stop()
