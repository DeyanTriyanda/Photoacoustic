"""
UI utama Photoacoustic Imaging (Tkinter).

Susunan kolom kiri:
  1. Koneksi Serial (Arduino + Device Mic)
  2. Rentang Frekuensi FFT
  3. Sampling Points
  4. Position Adjustment

Samplerate audio tetap 96000 Hz (tanpa UI).
"""

import os
import queue
import re
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from backend.config import (
    BREAK_TIME_MS,
    DEFAULT_BAUDRATE,
    DEFAULT_FREQ_TOLERANCE_HZ,
    POINT_DISTANCE_CM,
    ROW_DISTANCE_CM,
    SCAN_STEP_DELAY_US,
    STEP_PER_CM_X,
    TARGET_FREQ_HZ,
)
from backend.control import SerialController
from backend.scan_timing import (
    format_jam_menit,
    hitung_estimasi_durasi_s,
    hitung_jumlah_baris,
    hitung_titik_per_baris,
)
from frontend.fft_widget import FFTWidget
from frontend.spatial_map_widget import SpatialMapWidget
from frontend.tooltip import ScrolledCombobox

KATA_KUNCI_SCAN_SELESAI = "selesai"
POLA_SYNC_BARIS = re.compile(r"scanning baris ke-(\d+)")


class ScanControlApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Photoacoustic Imaging")

        dir_frontend = os.path.dirname(os.path.abspath(__file__))
        dir_proyek = os.path.dirname(dir_frontend)
        logo_path = os.path.join(dir_proyek, "assets", "logoPAI.png")
        try:
            if os.path.exists(logo_path):
                logo_img = tk.PhotoImage(file=logo_path)
                self.iconphoto(False, logo_img)
            else:
                print(f"[INFO] Logo tidak ditemukan di path: {logo_path}")
        except Exception as e:
            print(f"[WARNING] Gagal memuat logo: {e}")

        self.msg_queue = queue.Queue()
        self.sedang_scanning = False
        self._last_scan_xy = (0.0, 0.0)
        self._scan_start_time = None
        self._port_map = {}
        self.dl_widget = None

        self.controller = SerialController(
            on_message=self._enqueue_message,
            on_status_change=self._enqueue_status,
        )

        self._build_ui()
        self._refresh_ports()
        self.after(50, self._poll_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.resizable(True, True)
        self.update_idletasks()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        screen_h = self.winfo_screenheight()
        h_final = min(h, screen_h - 100)
        self.geometry(f"{w}x{h_final}")
        self.minsize(600, 400)

    def _on_close(self):
        self.spatial_map.stop_capture()
        self.fft_widget.shutdown()
        try:
            if self.controller.is_connected():
                self.controller.disconnect()
        except Exception:
            pass
        self.destroy()

    def _build_ui(self):
        pad = {"padx": 8, "pady": 3}

        frame_left = ttk.Frame(self)
        frame_left.pack(side="left", fill="y", anchor="n")
        frame_right = ttk.Frame(self)
        frame_right.pack(side="left", fill="both", expand=True)

        # --- 1. Koneksi Serial (Arduino + Mic Device) ---
        frame_conn = ttk.LabelFrame(frame_left, text="Koneksi Serial (Arduino Stepper)")
        frame_conn.pack(fill="x", **pad)

        ttk.Label(frame_conn, text="Port:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.cmb_port = ScrolledCombobox(frame_conn, width=22, list_height=8)
        self.cmb_port.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        frame_conn.columnconfigure(1, weight=1)

        ttk.Button(frame_conn, text="Refresh", command=self._refresh_ports, width=8).grid(
            row=0, column=2, padx=5, pady=5
        )
        self.btn_connect = ttk.Button(
            frame_conn, text="Connect", command=self._toggle_connect, width=12
        )
        self.btn_connect.grid(row=0, column=3, padx=5, pady=5)

        self.lbl_status = ttk.Label(
            frame_conn, text="\u25CF Belum terhubung", foreground="red"
        )
        self.lbl_status.grid(row=1, column=0, columnspan=4, padx=5, pady=(0, 5), sticky="w")

        # --- Notebook kanan dulu (FFTWidget dibuat dulu agar kontrol mic
        #     bisa di-mount ke frame_conn memakai instance yang sama) ---
        self.notebook = ttk.Notebook(frame_right)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=6)

        tab_fft = ttk.Frame(self.notebook)
        tab_spatial = ttk.Frame(self.notebook)
        tab_dl = ttk.Frame(self.notebook)
        self.notebook.add(tab_fft, text="FFT Fotoakustik")
        self.notebook.add(tab_spatial, text="Citra 2D Fotoakustik")
        self.notebook.add(tab_dl, text="Deep Learning")

        self.fft_widget = FFTWidget(tab_fft, show_controls=False)
        self.fft_widget.pack(fill="both", expand=True, padx=4, pady=4)

        # Device mic masuk ke frame Koneksi Serial (bukan frame Audio Input terpisah)
        self.fft_widget.mount_mic_controls(frame_conn, start_row=2)
        self.fft_widget._refresh_devices()

        # --- 2. Rentang Frekuensi FFT ---
        self.fft_widget.mount_freq_panel(frame_left, pad=pad)

        # --- 3. Sampling Points (X/Y + Start Scan + progres) ---
        frame_hitung = ttk.LabelFrame(frame_left, text="Sampling Points")
        frame_hitung.pack(fill="x", **pad)
        frame_hitung.columnconfigure(0, weight=1)

        baris_xy = ttk.Frame(frame_hitung)
        baris_xy.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=(6, 4))

        ttk.Label(baris_xy, text="X:").pack(side="left")
        self.entry_x = ttk.Entry(baris_xy, width=5)
        self.entry_x.pack(side="left", padx=(2, 2))
        ttk.Label(baris_xy, text="cm").pack(side="left", padx=(0, 6))

        ttk.Label(baris_xy, text="Y:").pack(side="left")
        self.entry_y = ttk.Entry(baris_xy, width=5)
        self.entry_y.pack(side="left", padx=(2, 2))
        ttk.Label(baris_xy, text="cm").pack(side="left", padx=(0, 6))

        self.entry_x.bind("<KeyRelease>", lambda e: self._update_hitungan())
        self.entry_y.bind("<KeyRelease>", lambda e: self._update_hitungan())

        self.btn_set_area = tk.Button(
            baris_xy, text="Set Area", command=self._kirim_xy,
            bg="#ffc107", fg="black", activebackground="#e0a800",
            activeforeground="black", font=("Segoe UI", 8, "bold"),
            width=8, padx=2, pady=1, relief="raised", bd=1, cursor="hand2",
        )
        self.btn_set_area.pack(side="left", padx=(0, 3))

        self.btn_scan = tk.Button(
            baris_xy, text="\u25B6 Start", command=self._toggle_scan,
            bg="#28a745", fg="white", activebackground="#218838",
            activeforeground="white", font=("Segoe UI", 8, "bold"),
            width=8, padx=2, pady=1, relief="raised", bd=1, cursor="hand2",
        )
        self.btn_scan.pack(side="left")

        self.lbl_titik_x = ttk.Label(
            frame_hitung, text="X points selesai: 0 / -", font=("Segoe UI", 9)
        )
        self.lbl_titik_x.grid(row=1, column=0, padx=8, pady=3, sticky="w")
        self.lbl_icon_x = ttk.Label(frame_hitung, text="\u26AA", font=("Segoe UI", 10))
        self.lbl_icon_x.grid(row=1, column=1, padx=8, pady=3, sticky="e")

        self.lbl_baris_y = ttk.Label(
            frame_hitung, text="Y points selesai: 0 / -", font=("Segoe UI", 9)
        )
        self.lbl_baris_y.grid(row=2, column=0, padx=8, pady=3, sticky="w")
        self.lbl_icon_y = ttk.Label(frame_hitung, text="\u26AA", font=("Segoe UI", 10))
        self.lbl_icon_y.grid(row=2, column=1, padx=8, pady=3, sticky="e")

        self.lbl_total = ttk.Label(
            frame_hitung, text="Total points selesai: 0 / -", font=("Segoe UI", 9, "bold")
        )
        self.lbl_total.grid(row=3, column=0, padx=8, pady=(2, 6), sticky="w")
        self.lbl_icon_total = ttk.Label(frame_hitung, text="\u26AA", font=("Segoe UI", 10))
        self.lbl_icon_total.grid(row=3, column=1, padx=8, pady=(2, 6), sticky="e")

        self.lbl_waktu_target = ttk.Label(
            frame_hitung, text="Waktu target: -", font=("Segoe UI", 9)
        )
        self.lbl_waktu_target.grid(
            row=4, column=0, columnspan=2, padx=8, pady=(2, 2), sticky="w"
        )
        self.lbl_waktu_tempuh = ttk.Label(
            frame_hitung, text="Waktu tempuh: -", font=("Segoe UI", 9)
        )
        self.lbl_waktu_tempuh.grid(
            row=5, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="w"
        )

        # --- 5. Position Adjustment (paling bawah) ---
        frame_jog = ttk.LabelFrame(frame_left, text="Position Adjustment")
        frame_jog.pack(fill="x", **pad)
        for i in range(3):
            frame_jog.columnconfigure(i, weight=1)

        self.btn_maju = ttk.Button(frame_jog, text="\u25B2 Y+", width=7)
        self.btn_maju.grid(row=0, column=1, padx=2, pady=2)
        self.btn_kiri = ttk.Button(frame_jog, text="\u25C0 X-", width=7)
        self.btn_kiri.grid(row=1, column=0, padx=2, pady=2)
        self.btn_kanan = ttk.Button(frame_jog, text="X+ \u25B6", width=7)
        self.btn_kanan.grid(row=1, column=2, padx=2, pady=2)
        self.btn_mundur = ttk.Button(frame_jog, text="\u25BC Y-", width=7)
        self.btn_mundur.grid(row=2, column=1, padx=2, pady=2)

        self._pasang_tombol_jog(self.btn_maju, self.controller.jog_maju)
        self._pasang_tombol_jog(self.btn_kiri, self.controller.jog_kiri)
        self._pasang_tombol_jog(self.btn_kanan, self.controller.jog_kanan)
        self._pasang_tombol_jog(self.btn_mundur, self.controller.jog_mundur)

        # --- Tab Citra 2D + Deep Learning ---
        self.spatial_map = SpatialMapWidget(
            tab_spatial,
            audio_capture=self.fft_widget.audio,
            scan_params={
                "point_distance_cm": POINT_DISTANCE_CM,
                "row_distance_cm": ROW_DISTANCE_CM,
                "scan_step_delay_us": SCAN_STEP_DELAY_US,
                "step_per_cm_x": STEP_PER_CM_X,
                "break_time_ms": BREAK_TIME_MS,
                "target_freq_hz": TARGET_FREQ_HZ,
                "freq_tolerance_hz": DEFAULT_FREQ_TOLERANCE_HZ,
            },
        )
        self.spatial_map.pack(fill="both", expand=True, padx=4, pady=4)
        self._pasang_tab_deep_learning(tab_dl)

    def _pasang_tab_deep_learning(self, tab_dl):
        try:
            from frontend.deep_learning_widget import DeepLearningWidget
            self.dl_widget = DeepLearningWidget(tab_dl, spatial_map=self.spatial_map)
            self.dl_widget.pack(fill="both", expand=True, padx=4, pady=4)
        except Exception as exc:
            import traceback
            print("[ERROR] Gagal memuat tab Deep Learning:")
            print(traceback.format_exc())
            ttk.Label(
                tab_dl,
                text=(
                    "Tab Deep Learning gagal dimuat.\n\n"
                    f"Error: {exc}\n\n"
                    "Coba: pip install -r requirements.txt\n"
                    "(butuh Pillow, matplotlib, numpy, onnxruntime)"
                ),
                foreground="#a00",
                justify="left",
                wraplength=480,
            ).pack(anchor="nw", padx=16, pady=16)
            self.dl_widget = None

    def _update_waktu_tempuh(self):
        if not self.sedang_scanning or self._scan_start_time is None:
            return
        elapsed_s = time.monotonic() - self._scan_start_time
        self.lbl_waktu_tempuh.config(
            text=f"Waktu tempuh: {format_jam_menit(elapsed_s)}"
        )
        self.after(1000, self._update_waktu_tempuh)

    def _lock_inputs(self):
        self.entry_x.config(state="disabled")
        self.entry_y.config(state="disabled")

    def _unlock_inputs(self):
        self.entry_x.config(state="normal")
        self.entry_y.config(state="normal")

    def _on_spatial_progress(self, col, row, n_done, n_total):
        x, y = self._get_xy()
        if x is None:
            return
        titik_x = hitung_titik_per_baris(x)
        baris_y = hitung_jumlah_baris(y)
        self.after(
            0,
            lambda: self._update_progress_ui(
                col + 1, titik_x, row + 1, baris_y, n_done, n_total
            ),
        )

    def _update_progress_ui(self, curr_x, titik_x, curr_y, baris_y, n_done, n_total):
        self.lbl_titik_x.config(text=f"X points selesai: {curr_x} / {titik_x}")
        self.lbl_icon_x.config(text="\u2705" if curr_x == titik_x else "\u26AA")

        self.lbl_baris_y.config(text=f"Y points selesai: {curr_y} / {baris_y}")
        selesai_baris = curr_y == baris_y and curr_x == titik_x
        self.lbl_icon_y.config(text="\u2705" if selesai_baris else "\u26AA")

        self.lbl_total.config(text=f"Total points selesai: {n_done} / {n_total}")
        self.lbl_icon_total.config(text="\u2705" if n_done == n_total else "\u26AA")

    def _on_spatial_finish(self, matrix):
        self.after(0, self._update_finish_ui)

    def _update_finish_ui(self):
        x, y = self._get_xy()
        if x is not None:
            titik_x = hitung_titik_per_baris(x)
            baris_y = hitung_jumlah_baris(y)
            total = titik_x * baris_y
            self.lbl_titik_x.config(text=f"X points selesai: {titik_x} / {titik_x}")
            self.lbl_icon_x.config(text="\u2705")
            self.lbl_baris_y.config(text=f"Y points selesai: {baris_y} / {baris_y}")
            self.lbl_icon_y.config(text="\u2705")
            self.lbl_total.config(text=f"Total points selesai: {total} / {total}")
            self.lbl_icon_total.config(text="\u2705")

        if self.sedang_scanning:
            self._log(
                "[INFO] Perekaman data selesai -- motor masih menyelesaikan "
                "sisa scan dan akan berhenti otomatis (tunggu pesan "
                "'Scanning selesai.' dari firmware)."
            )

    def _refresh_ports(self):
        ports = SerialController.list_ports()
        self._port_map = {label: device for device, label in ports}
        labels = list(self._port_map.keys())
        self.cmb_port["values"] = labels
        if labels:
            self.cmb_port.current(0)
        else:
            self.cmb_port.set("")

    def _toggle_connect(self):
        if self.controller.is_connected():
            self.controller.disconnect()
            self._log("Terputus dari Arduino.")
            self._set_scan_status(False)
            return

        port_label = self.cmb_port.get()
        if not port_label:
            messagebox.showwarning("Port kosong", "Pilih port serial terlebih dahulu.")
            return
        port = self._port_map.get(port_label, port_label)
        self.btn_connect.config(state="disabled", text="Menghubungkan...")
        threading.Thread(target=self._connect_worker, args=(port,), daemon=True).start()

    def _connect_worker(self, port):
        ok, msg = self.controller.connect(port, DEFAULT_BAUDRATE)
        self.msg_queue.put(("connect_result", (ok, msg)))

    def _enqueue_status(self, connected):
        self.msg_queue.put(("status", connected))

    def _enqueue_message(self, line):
        self.msg_queue.put(("log", line))

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "status":
                    self._set_status_ui(payload)
                elif kind == "log":
                    self._log(payload)
                    payload_lower = payload.lower()
                    if self.sedang_scanning:
                        m = POLA_SYNC_BARIS.search(payload_lower)
                        if m:
                            self.spatial_map.resync_row(int(m.group(1)))
                        if KATA_KUNCI_SCAN_SELESAI in payload_lower:
                            self._set_scan_status(False)
                elif kind == "scan_status":
                    self._set_scan_status(payload)
                elif kind == "connect_result":
                    ok, msg = payload
                    self._log(msg)
                    if not ok:
                        self.btn_connect.config(state="normal", text="Connect")
                        messagebox.showerror("Gagal terhubung", msg)
                    else:
                        self.btn_connect.config(state="normal")
        except queue.Empty:
            pass
        self.after(50, self._poll_queue)

    def _set_status_ui(self, connected):
        if connected:
            self.lbl_status.config(text="\u25CF Terhubung", foreground="green")
            self.btn_connect.config(text="Disconnect")
        else:
            self.lbl_status.config(text="\u25CF Belum terhubung", foreground="red")
            self.btn_connect.config(text="Connect")

    def _set_scan_status(self, aktif):
        self.sedang_scanning = aktif
        state_jog = "disabled" if aktif else "normal"
        self.fft_widget.set_device_lock(aktif)

        if aktif:
            self._scan_start_time = time.monotonic()
            self.lbl_waktu_tempuh.config(text="Waktu tempuh: 0 jam 0 menit")
            self.after(1000, self._update_waktu_tempuh)
            self.btn_scan.config(
                text="\u25A0 Stop", bg="#dc3545", fg="white",
                activebackground="#c82333", activeforeground="white",
            )
            self._lock_inputs()
        else:
            self.btn_scan.config(
                text="\u25B6 Start", bg="#28a745", fg="white",
                activebackground="#218838", activeforeground="white",
            )
            self.spatial_map.stop_capture()
            self.fft_widget.stop_audio()
            self._unlock_inputs()

        for tombol in (self.btn_maju, self.btn_mundur, self.btn_kiri, self.btn_kanan):
            tombol.config(state=state_jog)

    def _toggle_scan(self):
        if self.sedang_scanning:
            self._stop_scan()
        else:
            self._start_scan()

    def _get_xy(self):
        try:
            x = float(self.entry_x.get().replace(",", "."))
            y = float(self.entry_y.get().replace(",", "."))
            if x <= 0 or y <= 0:
                raise ValueError
            return x, y
        except ValueError:
            return None, None

    def _update_hitungan(self):
        x, y = self._get_xy()
        if x is None:
            self.lbl_titik_x.config(text="X points selesai: 0 / -")
            self.lbl_icon_x.config(text="\u26AA")
            self.lbl_baris_y.config(text="Y points selesai: 0 / -")
            self.lbl_icon_y.config(text="\u26AA")
            self.lbl_total.config(text="Total points selesai: 0 / -")
            self.lbl_icon_total.config(text="\u26AA")
            self.lbl_waktu_target.config(text="Waktu target: -")
            if not self.sedang_scanning:
                self.lbl_waktu_tempuh.config(text="Waktu tempuh: -")
            return

        titik_x = hitung_titik_per_baris(x)
        baris_y = hitung_jumlah_baris(y)
        total = titik_x * baris_y

        self.lbl_titik_x.config(text=f"X points selesai: 0 / {titik_x}")
        self.lbl_icon_x.config(text="\u26AA")
        self.lbl_baris_y.config(text=f"Y points selesai: 0 / {baris_y}")
        self.lbl_icon_y.config(text="\u26AA")
        self.lbl_total.config(text=f"Total points selesai: 0 / {total}")
        self.lbl_icon_total.config(text="\u26AA")

        durasi_s = hitung_estimasi_durasi_s(x, y)
        self.lbl_waktu_target.config(
            text=f"Waktu target: {format_jam_menit(durasi_s, bulatkan_ke_atas=True)}"
        )
        if not self.sedang_scanning:
            self.lbl_waktu_tempuh.config(text="Waktu tempuh: -")

    def _kirim_xy(self):
        x, y = self._get_xy()
        if x is None:
            messagebox.showwarning(
                "Input tidak valid", "Isi nilai X dan Y dengan angka > 0."
            )
            return
        if not self.controller.is_connected():
            messagebox.showwarning(
                "Belum terhubung", "Hubungkan ke Arduino terlebih dahulu."
            )
            return
        if self.sedang_scanning:
            messagebox.showwarning(
                "Scanning sedang berlangsung",
                "Tidak bisa mengubah nilai X/Y saat raster scan sedang berproses.\n\n"
                "Tekan STOP terlebih dahulu jika ingin mengubah parameter scan.",
            )
            return

        self._update_hitungan()
        self._lock_inputs()
        threading.Thread(target=self._kirim_xy_worker, args=(x, y), daemon=True).start()

    def _kirim_xy_worker(self, x, y):
        ok, msg = self.controller.set_x(x)
        self.msg_queue.put(("log", msg if ok else f"Gagal kirim X: {msg}"))
        ok, msg = self.controller.set_y(y)
        self.msg_queue.put(("log", msg if ok else f"Gagal kirim Y: {msg}"))

    def _start_scan(self):
        if not self.controller.is_connected():
            messagebox.showwarning(
                "Belum terhubung", "Hubungkan ke Arduino terlebih dahulu."
            )
            return
        x, y = self._get_xy()
        if x is None:
            messagebox.showwarning(
                "Input tidak valid",
                "Isi nilai X dan Y dengan angka > 0 sebelum start.",
            )
            return

        audio_ok, audio_msg = self.fft_widget.ensure_audio_started()
        if not audio_ok:
            messagebox.showwarning(
                "Audio Belum Siap",
                f"Gagal memulai audio secara otomatis:\n{audio_msg}",
            )
            return

        self._last_scan_xy = (x, y)
        self._set_scan_status(True)
        threading.Thread(target=self._start_scan_worker, args=(x, y), daemon=True).start()

    def _start_scan_worker(self, x, y):
        self.controller.set_x(x)
        self.controller.set_y(y)
        ok, msg = self.controller.start_scan()
        self.msg_queue.put(("log", msg if ok else f"Gagal memulai scan: {msg}"))
        if ok:
            self.after(0, self._mulai_capture_di_main_thread, x, y)
        else:
            self.msg_queue.put(("scan_status", False))

    def _mulai_capture_di_main_thread(self, x, y):
        ok, msg = self.spatial_map.start_capture(
            x, y,
            on_progress_cb=self._on_spatial_progress,
            on_finished_cb=self._on_spatial_finish,
        )
        self._log(msg)
        if not ok:
            messagebox.showerror("Perekaman citra gagal dimulai", msg)

    def _stop_scan(self):
        if not self.controller.is_connected():
            messagebox.showwarning(
                "Belum terhubung", "Hubungkan ke Arduino terlebih dahulu."
            )
            return
        self._set_scan_status(False)
        threading.Thread(target=self._stop_scan_worker, daemon=True).start()

    def _stop_scan_worker(self):
        ok, msg = self.controller.stop_scan()
        self.msg_queue.put(("log", msg if ok else f"Gagal mengirim stop: {msg}"))

    def _pasang_tombol_jog(self, tombol, fungsi_kirim):
        tombol.bind("<ButtonPress-1>", lambda e: self._jog_mulai(fungsi_kirim))
        tombol.bind("<ButtonRelease-1>", lambda e: self._jog_berhenti())

    def _jog_mulai(self, fungsi_kirim):
        if not self.controller.is_connected():
            messagebox.showwarning(
                "Belum terhubung", "Hubungkan ke Arduino terlebih dahulu."
            )
            return
        if self.sedang_scanning:
            messagebox.showwarning(
                "Scanning sedang berlangsung",
                "Kontrol manual (jog) dikunci karena raster scan sedang berproses.",
            )
            return
        threading.Thread(
            target=self._jog_mulai_worker, args=(fungsi_kirim,), daemon=True
        ).start()

    def _jog_mulai_worker(self, fungsi_kirim):
        ok, msg = fungsi_kirim()
        self.msg_queue.put(
            ("log", msg if ok else f"Gagal mengirim perintah jog: {msg}")
        )

    def _jog_berhenti(self):
        if not self.controller.is_connected() or self.sedang_scanning:
            return
        threading.Thread(target=self._stop_scan_worker, daemon=True).start()

    def _log(self, text):
        print(f"[SERIAL LOG]: {text}")


def run():
    app = ScanControlApp()
    app.mainloop()


if __name__ == "__main__":
    run()
