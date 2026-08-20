"""
Widget hasil raster scan: Frame 1 amplitudo raw, Frame 2 matrix 0-255,
Frame 3 citra grayscale.
"""

import csv
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from PIL import Image

from backend.config import DEFAULT_FREQ_TOLERANCE_HZ, USE_LOCKIN_HILBERT_DAS
from backend.spatial_mapping import amplitude_matrix_to_grayscale
from backend.spatial_scan_recorder import SpatialScanRecorder
from frontend.theme import PANEL_BG

try:
    from matplotlib import colormaps as _mpl_colormaps

    def _gray_cmap():
        return _mpl_colormaps["gray"].copy()
except ImportError:
    from matplotlib import cm as _mpl_cm

    def _gray_cmap():
        return _mpl_cm.get_cmap("gray").copy()

GRID_CELL_WIDTH = 48
GRID_CELL_HEIGHT = 48
GRID_HEADER_BG = "#e8e8e8"
GRID_EMPTY_BG = "#ffffff"
GRID_EMPTY_FG = "#bbbbbb"


class SpatialMapWidget(ttk.Frame):
    def __init__(self, master, audio_capture, scan_params, **kwargs):
        super().__init__(master, **kwargs)
        self.audio_capture = audio_capture
        self.scan_params = scan_params
        self.recorder = None

        self._detected_target_hz = None
        self._on_progress_cb = None
        self._on_finished_cb = None
        # Callback(bool) ke DeepLearningWidget: True saat grayscale lengkap.
        self.on_scan_image_ready = None
        self._scan_complete = False

        self.n_baris = 0
        self.n_kolom = 0
        self._captured_mask = None
        self._amplitude_matrix = None
        self._corrected_matrix = None
        self.gray_matrix = None
        self._amp_min = None
        self._amp_max = None

        self._amp_rect_ids = {}
        self._amp_text_ids = {}
        self._val_rect_ids = {}
        self._val_text_ids = {}

        self._im = None
        self._full_extent = None
        self._zoom_step_factor = 1.3

        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        frame_top = ttk.Frame(self)
        frame_top.pack(fill="x", **pad)
        self.lbl_progress = ttk.Label(frame_top, text="Belum ada data scan.")
        self.lbl_progress.pack(side="left")

        frame_stats = ttk.Frame(self)
        frame_stats.pack(fill="x", **pad)
        self.lbl_stats = ttk.Label(frame_stats, text="", font=("Segoe UI", 9))
        self.lbl_stats.pack(side="left")

        paned_h = ttk.PanedWindow(self, orient="horizontal")
        paned_h.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        paned_kiri = ttk.PanedWindow(paned_h, orient="vertical")
        frame1 = ttk.LabelFrame(paned_kiri, text="1. Amplitudo per Titik (nilai fisik)")
        frame2 = ttk.LabelFrame(paned_kiri, text="2. Matrix Grayscale (0-255)")
        frame3 = ttk.LabelFrame(paned_h, text="3. Citra Grayscale (Hasil Akhir)")

        paned_kiri.add(frame1, weight=1)
        paned_kiri.add(frame2, weight=1)
        paned_h.add(paned_kiri, weight=1)
        paned_h.add(frame3, weight=1)

        style = ttk.Style()
        style.configure("Kecil.TButton", font=("Segoe UI", 8), padding=(4, 1))

        self.btn_save_amp_csv = ttk.Button(
            frame1, text="Simpan CSV", style="Kecil.TButton", width=11,
            command=self._on_save_amp_csv,
        )
        self.btn_save_amp_csv.pack(side="top", anchor="e", padx=4, pady=(2, 0))

        self.btn_save_gray_csv = ttk.Button(
            frame2, text="Simpan CSV", style="Kecil.TButton", width=11,
            command=self._on_save_gray_csv,
        )
        self.btn_save_gray_csv.pack(side="top", anchor="e", padx=4, pady=(2, 0))

        self.canvas_amp = self._build_scrollable_grid_canvas(frame1)
        self.canvas_val = self._build_scrollable_grid_canvas(frame2)
        self._build_image_panel(frame3)

    def _build_scrollable_grid_canvas(self, parent):
        container = ttk.Frame(parent)
        container.pack(fill="both", expand=True, padx=4, pady=4)

        vbar = ttk.Scrollbar(container, orient="vertical")
        hbar = ttk.Scrollbar(container, orient="horizontal")
        canvas = tk.Canvas(
            container, bg=PANEL_BG, highlightthickness=1, highlightbackground="#ccc",
            yscrollcommand=vbar.set, xscrollcommand=hbar.set,
        )
        vbar.config(command=canvas.yview)
        hbar.config(command=canvas.xview)

        canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        return canvas

    def _build_image_panel(self, parent):
        self.fig = Figure(figsize=(5, 5), dpi=100, constrained_layout=True)
        self.fig.patch.set_facecolor(PANEL_BG)
        self.ax = self.fig.add_subplot(111)
        self._reset_axes()

        self.canvas_img = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas_img.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=(4, 0))

        frame_zoom = ttk.Frame(parent)
        frame_zoom.pack(fill="x", padx=4, pady=2)
        ttk.Button(frame_zoom, text="\u2212 Zoom Out", command=self._zoom_out).pack(side="left", padx=2)
        ttk.Button(frame_zoom, text="+ Zoom In", command=self._zoom_in).pack(side="left", padx=2)
        ttk.Button(frame_zoom, text="Reset Zoom", command=self._reset_zoom).pack(side="left", padx=2)

        self.btn_save_png = ttk.Button(
            frame_zoom, text="Simpan Citra (PNG)", command=self._on_save_png
        )
        self.btn_save_png.pack(side="right", padx=2)
        self.canvas_img.mpl_connect("scroll_event", self._on_scroll_zoom)

    def _reset_axes(self):
        self.ax.clear()
        self.ax.set_facecolor(PANEL_BG)
        judul = "Citra Grayscale (Hasil Akhir)"
        if self._detected_target_hz is not None:
            judul += f" - Target {self._detected_target_hz:.1f} Hz"
        self.ax.set_title(judul)
        self.ax.set_xlabel("X (cm)")
        self.ax.set_ylabel("Y (cm)")
        self._im = None

    def _build_empty_grids(self, n_baris, n_kolom):
        point_distance_cm = self.scan_params.get("point_distance_cm", 1.0)
        row_distance_cm = self.scan_params.get("row_distance_cm", 1.0)

        self._amp_rect_ids.clear()
        self._amp_text_ids.clear()
        self._val_rect_ids.clear()
        self._val_text_ids.clear()

        for canvas in (self.canvas_amp, self.canvas_val):
            canvas.delete("all")

        total_w = (n_kolom + 1) * GRID_CELL_WIDTH
        total_h = (n_baris + 1) * GRID_CELL_HEIGHT
        for canvas in (self.canvas_amp, self.canvas_val):
            canvas.configure(scrollregion=(0, 0, total_w, total_h))

        for canvas in (self.canvas_amp, self.canvas_val):
            canvas.create_rectangle(
                0, 0, GRID_CELL_WIDTH, GRID_CELL_HEIGHT,
                fill=GRID_HEADER_BG, outline="#aaaaaa",
            )
            canvas.create_text(
                GRID_CELL_WIDTH / 2, GRID_CELL_HEIGHT / 2, text="Y\\X",
                font=("Segoe UI", 8, "bold"),
            )
            for col in range(n_kolom):
                x0 = (col + 1) * GRID_CELL_WIDTH
                x_cm = col * point_distance_cm
                canvas.create_rectangle(
                    x0, 0, x0 + GRID_CELL_WIDTH, GRID_CELL_HEIGHT,
                    fill=GRID_HEADER_BG, outline="#aaaaaa",
                )
                canvas.create_text(
                    x0 + GRID_CELL_WIDTH / 2, GRID_CELL_HEIGHT / 2,
                    text=f"{x_cm:.2f}", font=("Segoe UI", 8, "bold"),
                )
            for row in range(n_baris):
                display_row = (n_baris - 1 - row)
                y0 = (display_row + 1) * GRID_CELL_HEIGHT
                y_cm = row * row_distance_cm
                canvas.create_rectangle(
                    0, y0, GRID_CELL_WIDTH, y0 + GRID_CELL_HEIGHT,
                    fill=GRID_HEADER_BG, outline="#aaaaaa",
                )
                canvas.create_text(
                    GRID_CELL_WIDTH / 2, y0 + GRID_CELL_HEIGHT / 2,
                    text=f"{y_cm:.2f}", font=("Segoe UI", 8, "bold"),
                )

        for row in range(n_baris):
            display_row = (n_baris - 1 - row)
            y0 = (display_row + 1) * GRID_CELL_HEIGHT
            for col in range(n_kolom):
                x0 = (col + 1) * GRID_CELL_WIDTH

                self._amp_rect_ids[(row, col)] = self.canvas_amp.create_rectangle(
                    x0, y0, x0 + GRID_CELL_WIDTH, y0 + GRID_CELL_HEIGHT,
                    fill=GRID_EMPTY_BG, outline="#dddddd",
                )
                self._amp_text_ids[(row, col)] = self.canvas_amp.create_text(
                    x0 + GRID_CELL_WIDTH / 2, y0 + GRID_CELL_HEIGHT / 2,
                    text="-", font=("Consolas", 8), fill=GRID_EMPTY_FG,
                )
                self._val_rect_ids[(row, col)] = self.canvas_val.create_rectangle(
                    x0, y0, x0 + GRID_CELL_WIDTH, y0 + GRID_CELL_HEIGHT,
                    fill=GRID_EMPTY_BG, outline="#dddddd",
                )
                self._val_text_ids[(row, col)] = self.canvas_val.create_text(
                    x0 + GRID_CELL_WIDTH / 2, y0 + GRID_CELL_HEIGHT / 2,
                    text="-", font=("Consolas", 8, "bold"), fill=GRID_EMPTY_FG,
                )

    def start_capture(self, x_cm, y_cm, on_progress_cb=None, on_finished_cb=None):
        if self.recorder is not None:
            self.recorder.stop_recording()

        self._on_progress_cb = on_progress_cb
        self._on_finished_cb = on_finished_cb
        self._scan_complete = False
        self._notify_scan_ready(False)

        target_freq = self.scan_params.get("target_freq_hz")

        self.recorder = SpatialScanRecorder(
            audio_capture=self.audio_capture,
            point_distance_cm=self.scan_params["point_distance_cm"],
            row_distance_cm=self.scan_params["row_distance_cm"],
            scan_step_delay_us=self.scan_params["scan_step_delay_us"],
            step_per_cm_x=self.scan_params["step_per_cm_x"],
            break_time_ms=self.scan_params["break_time_ms"],
            target_freq_hz=target_freq,
            freq_tolerance_hz=self.scan_params.get(
                "freq_tolerance_hz", DEFAULT_FREQ_TOLERANCE_HZ
            ),
        )

        self.recorder.on_point_captured = self._on_point_captured
        self.recorder.on_finished = self._on_finished
        self.recorder.on_error = self._on_recorder_error
        self.recorder.on_target_detected = self._on_target_detected
        self.recorder.on_timing_warning = (
            lambda msg: print(f"[SpatialMapWidget] TIMING WARNING: {msg}")
        )

        self.n_baris = round(y_cm / self.scan_params["row_distance_cm"]) + 1
        self.n_kolom = round(x_cm / self.scan_params["point_distance_cm"]) + 1
        self._captured_mask = np.zeros((self.n_baris, self.n_kolom), dtype=bool)
        self._amplitude_matrix = None
        self._corrected_matrix = None
        self.gray_matrix = None
        self._amp_min = None
        self._amp_max = None
        self._detected_target_hz = float(target_freq) if target_freq else None

        self._build_empty_grids(self.n_baris, self.n_kolom)
        self._reset_axes()
        self.canvas_img.draw_idle()

        self.recorder.start_recording(x_cm, y_cm)

        self.lbl_progress.config(text="Merekam... 0 titik selesai")
        if USE_LOCKIN_HILBERT_DAS and target_freq:
            self.lbl_stats.config(
                text=(
                    f"Lock-In+Hilbert @ {target_freq:.0f} Hz → DAS "
                    f"(synthetic aperture)"
                )
            )
            return True, (
                f"Perekaman citra Lock-In+Hilbert+DAS @ {target_freq:.0f} Hz."
            )
        if target_freq:
            tol = self.scan_params.get("freq_tolerance_hz", DEFAULT_FREQ_TOLERANCE_HZ)
            self.lbl_stats.config(
                text=(
                    f"Objek: {target_freq:.0f} Hz \u00B1 {tol:.0f} Hz  |  "
                    f"Background hitam: < {target_freq:.0f} Hz (plat)"
                )
            )
            return True, (
                f"Perekaman citra: objek {target_freq:.0f} Hz, "
                f"background hitam < {target_freq:.0f} Hz."
            )
        self.lbl_stats.config(
            text="Frekuensi target akan terdeteksi otomatis di titik pertama."
        )
        return True, "Perekaman citra dimulai (frekuensi target dideteksi otomatis)."

    def stop_capture(self):
        if self.recorder is not None:
            self.recorder.stop_recording()

    def resync_row(self, baris_ke):
        if self.recorder is not None and self.recorder.is_recording():
            self.recorder.resync_row(baris_ke)

    def _on_recorder_error(self, msg):
        print(f"[SpatialMapWidget] ERROR perekaman: {msg}")
        self.after(0, lambda: self.lbl_progress.config(
            text="ERROR perekaman -- lihat konsol untuk detail."
        ))

    def _on_target_detected(self, freq_hz, amplitude):
        print(
            f"[SpatialMapWidget] Frekuensi target otomatis: {freq_hz:.1f} Hz "
            f"(amplitudo {amplitude:.6g})"
        )
        self._detected_target_hz = float(freq_hz)

    def _on_point_captured(self, col, row, value_raw, value_corrected,
                           n_done, n_total):
        self.after(0, lambda: self._update_point_ui(
            col, row, value_raw, value_corrected, n_done, n_total
        ))

    def _update_point_ui(self, col, row, value_raw, value_corrected,
                         n_done, n_total):
        if self.recorder is None or self.recorder.matrix is None:
            return
        if not (0 <= row < self.n_baris and 0 <= col < self.n_kolom):
            return

        self._amplitude_matrix = self.recorder.matrix_raw
        self._corrected_matrix = self.recorder.matrix
        self._captured_mask[row, col] = True

        self.canvas_amp.itemconfig(
            self._amp_text_ids[(row, col)], text=f"{value_raw:.3g}", fill="#000000"
        )
        self.canvas_amp.itemconfig(self._amp_rect_ids[(row, col)], fill="#fff7d6")

        self.gray_matrix, self._amp_min, self._amp_max = amplitude_matrix_to_grayscale(
            self._corrected_matrix, captured_mask=self._captured_mask
        )
        self._redraw_value_grid()
        self._redraw_image()

        self.lbl_progress.config(text=f"Merekam... {n_done}/{n_total} titik selesai")
        self.lbl_stats.config(
            text=(
                f"Objek (terkoreksi) min={self._amp_min:.6g}, max={self._amp_max:.6g}  |  "
                f"Amp tinggi=terang, amp rendah=gelap  |  "
                f"Titik selesai: {n_done}/{n_total}"
            )
        )

        if self._on_progress_cb is not None:
            self._on_progress_cb(col, row, n_done, n_total)

    def _redraw_value_grid(self):
        rows, cols = np.where(self._captured_mask)
        for row, col in zip(rows, cols):
            v = int(self.gray_matrix[row, col])
            text_color = "#ffffff" if v < 128 else "#000000"
            bg_color = f"#{v:02x}{v:02x}{v:02x}"
            self.canvas_val.itemconfig(
                self._val_text_ids[(row, col)], text=str(v), fill=text_color
            )
            self.canvas_val.itemconfig(self._val_rect_ids[(row, col)], fill=bg_color)

    def _redraw_image(self):
        n_baris, n_kolom = self.gray_matrix.shape
        point_distance_cm = self.scan_params.get("point_distance_cm", 1.0)
        row_distance_cm = self.scan_params.get("row_distance_cm", 1.0)

        extent = [
            0.0, (n_kolom - 1) * point_distance_cm if n_kolom > 1 else point_distance_cm,
            0.0, (n_baris - 1) * row_distance_cm if n_baris > 1 else row_distance_cm,
        ]

        display_matrix = np.ma.masked_where(~self._captured_mask, self.gray_matrix)

        if self._im is None:
            self._reset_axes()
            cmap = _gray_cmap()
            cmap.set_bad(color="#e0e0e0")
            self._im = self.ax.imshow(
                display_matrix, origin="lower", aspect="equal", extent=extent,
                cmap=cmap, vmin=0, vmax=255,
            )
            self.ax.set_xlim(extent[0], extent[1])
            self.ax.set_ylim(extent[2], extent[3])
        else:
            self._im.set_data(display_matrix)
            self._im.set_extent(extent)

        self._full_extent = extent
        self.canvas_img.draw_idle()

    def is_grayscale_complete(self):
        """True jika semua titik raster sudah terekam jadi citra grayscale."""
        return bool(self._scan_complete and self.gray_matrix is not None)

    def _notify_scan_ready(self, ready):
        if self.on_scan_image_ready is not None:
            try:
                self.on_scan_image_ready(bool(ready))
            except Exception:
                pass

    def _on_finished(self, matrix):
        self.after(0, lambda: self._finish_ui(matrix))

    def _finish_ui(self, matrix):
        if matrix is not None:
            self._corrected_matrix = np.asarray(matrix, dtype=np.float64)
            if self._captured_mask is None or self._captured_mask.shape != matrix.shape:
                self._captured_mask = np.ones(matrix.shape, dtype=bool)
            else:
                self._captured_mask[:, :] = True
            self.gray_matrix, self._amp_min, self._amp_max = amplitude_matrix_to_grayscale(
                self._corrected_matrix, captured_mask=self._captured_mask
            )
            self._redraw_value_grid()
            self._redraw_image()
            mode = "DAS" if USE_LOCKIN_HILBERT_DAS else "FFT"
            self.lbl_stats.config(
                text=(
                    f"Citra akhir ({mode}) min={self._amp_min:.6g}, "
                    f"max={self._amp_max:.6g}"
                )
            )

        self._scan_complete = (
            self._captured_mask is not None
            and self._captured_mask.size > 0
            and bool(self._captured_mask.all())
        )
        self._notify_scan_ready(self._scan_complete)
        self.lbl_progress.config(
            text="Semua titik terekam. Motor berhenti otomatis saat firmware selesai."
        )
        if self._on_finished_cb is not None:
            self._on_finished_cb(matrix)

    def _tulis_matrix_csv(self, path, matrix, format_nilai):
        point_distance_cm = self.scan_params.get("point_distance_cm", 1.0)
        row_distance_cm = self.scan_params.get("row_distance_cm", 1.0)
        n_baris, n_kolom = matrix.shape

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["Y\\X (cm)"]
                + [f"{col * point_distance_cm:.2f}" for col in range(n_kolom)]
            )
            for row in range(n_baris):
                nilai_baris = []
                for col in range(n_kolom):
                    if (self._captured_mask is not None
                            and not self._captured_mask[row, col]):
                        nilai_baris.append("")
                    else:
                        nilai_baris.append(format_nilai(matrix[row, col]))
                writer.writerow([f"{row * row_distance_cm:.2f}"] + nilai_baris)

    def _on_save_amp_csv(self):
        if self._amplitude_matrix is None:
            messagebox.showwarning(
                "Belum ada data",
                "Belum ada data amplitudo untuk disimpan -- jalankan scan dulu.",
            )
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV file", "*.csv")],
            title="Simpan Amplitudo per Titik (CSV)",
            initialfile="amplitudo_per_titik.csv",
        )
        if not path:
            return
        try:
            self._tulis_matrix_csv(
                path, np.asarray(self._amplitude_matrix),
                format_nilai=lambda v: f"{float(v):.6g}",
            )
            messagebox.showinfo("Tersimpan", f"Amplitudo per titik berhasil disimpan:\n{path}")
        except Exception as exc:
            messagebox.showerror("Gagal menyimpan", f"Terjadi kesalahan:\n{exc}")

    def _on_save_gray_csv(self):
        if self.gray_matrix is None:
            messagebox.showwarning(
                "Belum ada data",
                "Belum ada matrix grayscale untuk disimpan -- jalankan scan dulu.",
            )
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV file", "*.csv")],
            title="Simpan Matrix Grayscale 0-255 (CSV)",
            initialfile="matrix_grayscale.csv",
        )
        if not path:
            return
        try:
            self._tulis_matrix_csv(
                path, np.asarray(self.gray_matrix),
                format_nilai=lambda v: str(int(v)),
            )
            messagebox.showinfo("Tersimpan", f"Matrix grayscale berhasil disimpan:\n{path}")
        except Exception as exc:
            messagebox.showerror("Gagal menyimpan", f"Terjadi kesalahan:\n{exc}")

    def _on_save_png(self):
        if self.gray_matrix is None:
            messagebox.showwarning(
                "Belum ada citra", "Belum ada data scan untuk disimpan sebagai citra."
            )
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png", filetypes=[("PNG image", "*.png")],
            title="Simpan Citra Fotoakustik (Grayscale)",
        )
        if not path:
            return
        try:
            img = Image.fromarray(np.flipud(self.gray_matrix), mode="L")
            img.save(path)
            messagebox.showinfo("Tersimpan", f"Citra grayscale berhasil disimpan:\n{path}")
        except Exception as exc:
            messagebox.showerror("Gagal menyimpan", f"Terjadi kesalahan:\n{exc}")

    def _apply_zoom(self, scale_factor, center_xy=None):
        if self._im is None:
            return
        cur_xlim = self.ax.get_xlim()
        cur_ylim = self.ax.get_ylim()
        cur_xrange = cur_xlim[1] - cur_xlim[0]
        cur_yrange = cur_ylim[1] - cur_ylim[0]

        if center_xy is None:
            xcenter = (cur_xlim[0] + cur_xlim[1]) / 2.0
            ycenter = (cur_ylim[0] + cur_ylim[1]) / 2.0
        else:
            xcenter, ycenter = center_xy

        relx = (xcenter - cur_xlim[0]) / cur_xrange if cur_xrange != 0 else 0.5
        rely = (ycenter - cur_ylim[0]) / cur_yrange if cur_yrange != 0 else 0.5

        new_xrange = max(cur_xrange * scale_factor, 1e-6)
        new_yrange = max(cur_yrange * scale_factor, 1e-6)

        self.ax.set_xlim(xcenter - new_xrange * relx, xcenter + new_xrange * (1 - relx))
        self.ax.set_ylim(ycenter - new_yrange * rely, ycenter + new_yrange * (1 - rely))
        self.canvas_img.draw_idle()

    def _zoom_in(self):
        self._apply_zoom(1.0 / self._zoom_step_factor)

    def _zoom_out(self):
        self._apply_zoom(self._zoom_step_factor)

    def _reset_zoom(self):
        if self._im is None or self._full_extent is None:
            return
        left, right, bottom, top = self._full_extent
        self.ax.set_xlim(left, right)
        self.ax.set_ylim(bottom, top)
        self.canvas_img.draw_idle()

    def _on_scroll_zoom(self, event):
        if self._im is None or event.inaxes != self.ax:
            return
        if event.xdata is None or event.ydata is None:
            return
        if event.button == "up":
            scale_factor = 1.0 / self._zoom_step_factor
        elif event.button == "down":
            scale_factor = self._zoom_step_factor
        else:
            return
        self._apply_zoom(scale_factor, center_xy=(event.xdata, event.ydata))
