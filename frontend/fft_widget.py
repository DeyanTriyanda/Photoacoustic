"""
Widget FFT: waveform, spektrum, puncak -- rolling buffer AudioCapture.

Kontrol mic (Device) dipasang ke frame Koneksi Serial di ui_control.
Satu isian Frekuensi Modulasi Laser mengatur:
  - frekuensi target citra (via callback ke ui_control)
  - perintah f= ke Arduino laser (via callback)
Plot FFT selalu 0 .. 20000 Hz (tidak mengikuti nilai modulasi sebagai min).
Max FFT tetap 20000 Hz di latar.
Skala Log (dB) ada di tab FFT Fotoakustik. Samplerate tetap 192000 Hz.
"""

import tkinter as tk
from tkinter import messagebox, ttk

import matplotlib.ticker as ticker
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from backend.audio_capture import AudioCapture
from backend.config import AUDIO_SAMPLERATE, TARGET_FREQ_HZ
from frontend.tooltip import HoverTooltip

UPDATE_INTERVAL_MS = 50
# Nilai awal di kotak UI (saran); baru aktif setelah Set Modulasi.
INITIAL_MOD_FREQ_HZ = TARGET_FREQ_HZ
# Alias lama (kompatibilitas)
INITIAL_MIN_FREQ_HZ = INITIAL_MOD_FREQ_HZ
# Max FFT tetap di latar (bukan diedit di UI).
FFT_MIN_FREQ_HZ = 0.0
FFT_MAX_FREQ_HZ = 20000.0

# Alias kompatibilitas
DEFAULT_MIN_FREQ = FFT_MIN_FREQ_HZ
DEFAULT_MAX_FREQ = FFT_MAX_FREQ_HZ


class FFTWidget(ttk.Frame):
    def __init__(self, master, show_controls=True, on_frekuensi_ditetapkan=None, **kwargs):
        """
        show_controls=False: jangan bangun panel device/frekuensi di sini
        (akan dipasang lewat mount_device_panel / mount_freq_panel).
        on_frekuensi_ditetapkan(hz): setelah Set Modulasi / Enter sukses —
        ui_control menerapkan target citra + kirim ke Arduino.
        """
        super().__init__(master, **kwargs)

        self.audio = AudioCapture(on_error=self._on_audio_error)
        self.on_frekuensi_ditetapkan = on_frekuensi_ditetapkan
        self._running_ui_update = False
        self._device_map = {}
        self._confirmed_device_label = None

        self._last_fmin = None
        self._last_fmax = None
        self._last_logscale = None

        self.cmb_device = None
        self.btn_refresh = None
        self.btn_connect_mic = None
        self.lbl_status = None  # status mic
        self.entry_min_freq = None
        self.btn_set_freq = None
        self.lbl_freq_hint = None
        # Belum diterapkan sampai Set Modulasi; plot awal pakai saran TARGET.
        self._applied_fmin = float(INITIAL_MOD_FREQ_HZ)
        self._freq_ditetapkan = False
        self.var_logscale = tk.BooleanVar(value=False)

        if show_controls:
            # Standalone: buat frame kecil untuk mic (tanpa samplerate UI)
            frame = ttk.LabelFrame(self, text="Microphone")
            frame.pack(fill="x", padx=8, pady=3)
            self.mount_mic_controls(frame, start_row=0)
            self.mount_freq_panel(self)

        self._build_plots()
        if show_controls:
            self._refresh_devices()

    def mount_mic_controls(self, parent, start_row=0):
        """Pasang Device / Refresh / Connect Mic ke frame induk (mis. Koneksi Serial)."""
        row = start_row
        ttk.Label(parent, text="Device:").grid(row=row, column=0, padx=5, pady=5, sticky="w")
        self.cmb_device = ttk.Combobox(parent, state="readonly", width=22)
        self.cmb_device.grid(row=row, column=1, padx=5, pady=5, sticky="ew")
        parent.columnconfigure(1, weight=1)
        HoverTooltip(self.cmb_device, text_fn=self.cmb_device.get)

        self.btn_refresh = ttk.Button(
            parent, text="Refresh", command=self._refresh_devices, width=8
        )
        self.btn_refresh.grid(row=row, column=2, padx=5, pady=5)

        self.btn_connect_mic = ttk.Button(
            parent, text="Connect Mic", command=self._connect_microphone, width=12,
        )
        self.btn_connect_mic.grid(row=row, column=3, padx=5, pady=5)

        self.lbl_status = ttk.Label(parent, text="\u25CF Mic belum aktif", foreground="red")
        self.lbl_status.grid(row=row + 1, column=0, columnspan=4, padx=5, pady=(0, 5), sticky="w")
        return row + 2

    def mount_device_panel(self, parent, pad=None):
        """Kompatibilitas: pasang kontrol mic ke parent tanpa frame Audio Input."""
        return self.mount_mic_controls(parent, start_row=0)

    def mount_freq_panel(self, parent, pad=None):
        """Isian frekuensi modulasi → laser + target citra (bukan min plot FFT)."""
        pad = pad or {"padx": 8, "pady": 3}
        frame_range = ttk.LabelFrame(parent, text="Frekuensi Modulasi Laser (Hz)")
        frame_range.pack(fill="x", **pad)
        frame_range.columnconfigure(0, weight=1)

        self.entry_min_freq = ttk.Entry(frame_range, width=12)
        self.entry_min_freq.insert(
            0, str(int(INITIAL_MOD_FREQ_HZ) if float(INITIAL_MOD_FREQ_HZ).is_integer()
                   else INITIAL_MOD_FREQ_HZ)
        )
        self.entry_min_freq.grid(row=0, column=0, padx=(8, 4), pady=(6, 2), sticky="ew")
        self.entry_min_freq.bind("<Return>", lambda e: self._set_frekuensi())
        # FocusOut ditunda: kalau langsung restore, klik Set akan
        # mengembalikan angka lama (mis. 17000) sebelum tombol terbaca.
        self.entry_min_freq.bind("<FocusOut>", self._on_freq_focus_out)

        self.btn_set_freq = ttk.Button(
            frame_range, text="Set Modulasi", command=self._set_frekuensi, width=14
        )
        self.btn_set_freq.grid(row=0, column=1, padx=(0, 8), pady=(6, 2), sticky="e")

        self.lbl_freq_hint = ttk.Label(
            frame_range,
            text=(
                "Set Modulasi: laser + target citra. "
                "Plot FFT tetap 0–20000 Hz; puncak muncul di frekuensi set."
            ),
            foreground="#555",
            wraplength=280,
        )
        self.lbl_freq_hint.grid(
            row=1, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="w"
        )
        return frame_range

    def get_fft_min_hz(self):
        """Min plot FFT selalu 0 Hz (tidak mengikuti Set Modulasi)."""
        return float(FFT_MIN_FREQ_HZ)

    def get_modulasi_hz(self):
        """Nilai frekuensi modulasi yang sudah di-Set (boleh sampai 20000)."""
        return float(self._applied_fmin)

    def get_fft_max_hz(self):
        """Max frekuensi FFT (tetap di latar)."""
        return float(FFT_MAX_FREQ_HZ)

    def is_frekuensi_ditetapkan(self):
        """True jika pengguna sudah menekan Set Modulasi / Enter dengan nilai valid."""
        return bool(self._freq_ditetapkan)

    def _on_freq_focus_out(self, _event=None):
        # after_idle: biarkan klik Set Modulasi jalan dulu tanpa overwrite entry
        self.after_idle(self._maybe_restore_freq_entry)

    def _maybe_restore_freq_entry(self):
        try:
            fokus = self.focus_get()
        except tk.TclError:
            fokus = None
        if self.btn_set_freq is not None and fokus == self.btn_set_freq:
            return
        self._restore_freq_entry()

    def _set_frekuensi(self, silent=False):
        """Terapkan nilai modulasi dari UI (fleksibel: >0 dan ≤ 20000 Hz)."""
        if self.btn_set_freq is not None:
            try:
                if str(self.btn_set_freq.cget("state")) == "disabled":
                    return
            except tk.TclError:
                pass
        raw = ""
        if self.entry_min_freq is not None:
            raw = self.entry_min_freq.get().strip().replace(",", ".")
        try:
            nilai = float(raw)
        except ValueError:
            if not silent:
                messagebox.showwarning(
                    "Peringatan Frekuensi",
                    "Isi frekuensi modulasi dengan angka.\n"
                    "Nilai valid: lebih dari 0 dan maksimal 20000 Hz.",
                )
            self._restore_freq_entry()
            return
        if nilai <= 0:
            if not silent:
                messagebox.showwarning(
                    "Peringatan Frekuensi",
                    "Frekuensi tidak boleh 0 atau negatif.\n"
                    "Set Modulasi dibatalkan.",
                )
            self._restore_freq_entry()
            return
        if nilai > FFT_MAX_FREQ_HZ:
            if not silent:
                messagebox.showwarning(
                    "Peringatan Frekuensi",
                    f"Frekuensi tidak boleh lebih dari {int(FFT_MAX_FREQ_HZ)} Hz.\n"
                    "Set Modulasi dibatalkan.",
                )
            self._restore_freq_entry()
            return
        self._applied_fmin = nilai
        self._freq_ditetapkan = True
        self._restore_freq_entry()
        if getattr(self, "vline_modulasi", None) is not None:
            self.vline_modulasi.set_xdata([nilai, nilai])
            try:
                self.canvas.draw_idle()
            except Exception:
                pass
        if self.on_frekuensi_ditetapkan is not None:
            try:
                self.on_frekuensi_ditetapkan(nilai)
            except Exception:
                pass

    def _restore_freq_entry(self):
        """Tampilkan kembali nilai frekuensi yang terakhir berhasil di-set."""
        if self.entry_min_freq is None:
            return
        fmin = self._applied_fmin
        teks = str(int(fmin) if float(fmin).is_integer() else fmin)
        self.entry_min_freq.delete(0, tk.END)
        self.entry_min_freq.insert(0, teks)

    def _build_plots(self):
        pad = {"padx": 8, "pady": 4}

        frame_opts = ttk.Frame(self)
        frame_opts.pack(fill="x", padx=8, pady=(4, 0))
        ttk.Checkbutton(
            frame_opts, text="Skala Log (dB)", variable=self.var_logscale
        ).pack(side="left")

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
        self.ax_fft.set_xlim(FFT_MIN_FREQ_HZ, FFT_MAX_FREQ_HZ)
        (self.line_fft,) = self.ax_fft.plot([], [], linewidth=0.8)
        (self.marker_peak,) = self.ax_fft.plot([], [], "ro", markersize=6)
        self.vline_modulasi = self.ax_fft.axvline(
            self._applied_fmin,
            color="#c44",
            ls="--",
            lw=1.0,
            alpha=0.8,
            label="Set Modulasi",
        )

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
                self.lbl_status.config(text="\u25CF Mic belum aktif", foreground="red")

    def set_device_lock(self, locked):
        if self.cmb_device is None:
            return
        if locked:
            self.cmb_device.config(state="disabled")
            self.btn_refresh.config(state="disabled")
            self.btn_connect_mic.config(state="disabled")
        else:
            self.cmb_device.config(state="readonly")
            self.btn_refresh.config(state="normal")
            self.btn_connect_mic.config(state="normal")

    def set_freq_lock(self, locked):
        """Kunci rentang frekuensi saat scan; buka lagi saat stop/selesai."""
        if self.entry_min_freq is not None:
            self.entry_min_freq.config(state="disabled" if locked else "normal")
        if self.btn_set_freq is not None:
            self.btn_set_freq.config(state="disabled" if locked else "normal")

    def _connect_microphone(self):
        label = self.cmb_device.get() if self.cmb_device is not None else ""
        if not label or label not in self._device_map:
            self._confirmed_device_label = None
            if self.lbl_status is not None:
                self.lbl_status.config(text="\u25CF Mic belum aktif", foreground="red")
            messagebox.showwarning(
                "Mic belum dipilih",
                "Pilih device mic dari dropdown terlebih dahulu, lalu klik "
                "'Connect Mic'.",
            )
            return

        self._confirmed_device_label = label
        if self.lbl_status is not None:
            self.lbl_status.config(text="\u25CF Mic aktif", foreground="green")

    def is_mic_connected(self):
        return self._confirmed_device_label is not None

    def ensure_audio_started(self):
        if self.audio.is_running():
            return True, "Audio sudah aktif."

        label = self._confirmed_device_label
        if not label:
            return False, (
                "Mic belum terhubung. Pilih Device di panel Koneksi Serial lalu klik "
                "'Connect Mic' terlebih dahulu."
            )
        if label not in self._device_map:
            self._confirmed_device_label = None
            if self.lbl_status is not None:
                self.lbl_status.config(text="\u25CF Mic belum aktif", foreground="red")
            return False, (
                f"Mic '{label}' tidak lagi terdeteksi (tercabut?). "
                "Klik Refresh lalu Connect Mic ulang."
            )

        device_index = self._device_map[label]
        # Samplerate tetap dari backend.config.AUDIO_SAMPLERATE (192000 Hz).
        ok, msg = self.audio.start(
            device_index, samplerate=AUDIO_SAMPLERATE, channels=1
        )
        if not ok:
            return False, msg

        if self.lbl_status is not None:
            self.lbl_status.config(text="\u25CF Mic aktif", foreground="green")

        if not self._running_ui_update:
            self._running_ui_update = True
            self._update_plot()

        return True, "Audio berhasil diaktifkan."

    def stop_audio(self):
        if self.audio.is_running():
            self.audio.stop()
        self._running_ui_update = False
        if not self._confirmed_device_label and self.lbl_status is not None:
            self.lbl_status.config(text="\u25CF Mic belum aktif", foreground="red")

    def _on_audio_error(self, msg):
        print(f"[AUDIO WARNING] {msg}")

    def _get_freq_range(self):
        """Rentang plot FFT tetap 0 .. 20000 Hz."""
        return float(FFT_MIN_FREQ_HZ), float(FFT_MAX_FREQ_HZ)

    def _update_plot(self):
        if not self._running_ui_update or not self.audio.is_running():
            self._running_ui_update = False
            return

        wave = self.audio.get_waveform()
        if len(wave) > 0:
            t = np.arange(len(wave)) / self.audio.samplerate
            self.line_wave.set_data(t, wave)

        fmin, fmax = self._get_freq_range()
        is_log = self.var_logscale.get()

        if is_log != self._last_logscale or fmin != self._last_fmin or fmax != self._last_fmax:
            self._last_logscale = is_log
            self._last_fmin = fmin
            self._last_fmax = fmax
            self.ax_fft.set_xlim(fmin, fmax)
            if is_log:
                self.ax_fft.set_ylabel("Amplitudo (dB)")
                self.ax_fft.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f"))
            else:
                self.ax_fft.set_ylabel("Amplitudo")
                self.ax_fft.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.3f"))

        freqs, mag = self.audio.get_fft(min_freq=fmin, max_freq=fmax)

        if len(freqs) > 0:
            mag_plot = 20.0 * np.log10(np.maximum(mag, 1e-12)) if is_log else mag
            self.line_fft.set_data(freqs, mag_plot)

            if len(mag_plot) > 0:
                y_min = float(np.min(mag_plot))
                y_max = float(np.max(mag_plot))
                if is_log:
                    margin = (y_max - y_min) * 0.1 if y_max > y_min else 5.0
                    self.ax_fft.set_ylim(y_min - margin, y_max + margin)
                else:
                    self.ax_fft.set_ylim(0.0, max(y_max * 1.15, 0.01))

            peak_freq, peak_amp = self.audio.get_peak(min_freq=fmin, max_freq=fmax)
            self.lbl_peak_freq.config(text=f"Frekuensi Puncak: {peak_freq:.1f} Hz")
            self.lbl_peak_amp.config(text=f"Amplitudo Puncak: {peak_amp:.6f}")

            peak_amp_plot = (
                20.0 * np.log10(max(peak_amp, 1e-12)) if is_log else peak_amp
            )
            self.marker_peak.set_data([peak_freq], [peak_amp_plot])

        self.canvas.draw_idle()
        self.after(UPDATE_INTERVAL_MS, self._update_plot)

    def get_current_peak(self, min_freq=None, max_freq=None):
        if min_freq is None or max_freq is None:
            min_freq, max_freq = self._get_freq_range()
        return self.audio.get_peak(min_freq=min_freq, max_freq=max_freq)

    def shutdown(self):
        self._running_ui_update = False
        self.audio.stop()
