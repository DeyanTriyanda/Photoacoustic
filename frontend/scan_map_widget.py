"""
Peta 2D estimasi posisi alat (open-loop, tanpa feedback encoder).

Kecepatan diambil dari backend.scan_timing supaya sama dengan firmware
dan SpatialScanRecorder.
"""

import time
import tkinter as tk
from tkinter import ttk

from backend.scan_timing import jog_speed_cm_s, scan_speed_cm_s


class ScanMapWidget(ttk.LabelFrame):
    def __init__(self, parent, point_distance_cm, row_distance_cm,
                 step_per_cm_x, step_per_cm_y,
                 jog_step_delay_us, scan_step_delay_us, break_time_ms,
                 canvas_size=230, **kwargs):
        super().__init__(parent, text="Peta Posisi 2D (Titik Tengah Alat)", **kwargs)

        self.point_distance_cm = point_distance_cm
        self.row_distance_cm = row_distance_cm
        self.canvas_size = canvas_size

        self.jog_speed_cm_s = jog_speed_cm_s(jog_step_delay_us, step_per_cm_x)
        self.scan_speed_cm_s = scan_speed_cm_s(scan_step_delay_us, step_per_cm_x)
        self.break_time_ms = break_time_ms

        self.pos_x = 0.0
        self.pos_y = 0.0
        self.area_x_cm = 1.0
        self.area_y_cm = 1.0

        self._jog_after_id = None
        self._jog_dx = 0.0
        self._jog_dy = 0.0
        self._jog_last_time = None

        self._scan_after_id = None
        self._scan_queue = []

        self._build_ui()
        self._redraw()

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=6, pady=(4, 0))

        self.lbl_pos = ttk.Label(
            top, text="Posisi: X=0.00 cm, Y=0.00 cm", font=("Segoe UI", 8, "bold")
        )
        self.lbl_pos.pack(side="left")

        self.btn_reset = ttk.Button(top, text="Reset", command=self.reset_center)
        self.btn_reset.pack(side="right")

        self.canvas = tk.Canvas(
            self, width=self.canvas_size, height=self.canvas_size,
            bg="white", highlightthickness=1, highlightbackground="#ccc",
        )
        self.canvas.pack(padx=6, pady=4)

        self.lbl_info = ttk.Label(
            self,
            text=(
                "Titik hitam = titik tengah (diset manual di alat).\n"
                "Titik merah = estimasi posisi alat saat ini."
            ),
            foreground="#666",
            justify="left",
            font=("Segoe UI", 7),
        )
        self.lbl_info.pack(anchor="w", padx=6, pady=(0, 4))

    def set_reset_enabled(self, enabled):
        self.btn_reset.config(state="normal" if enabled else "disabled")

    def reset_center(self):
        if self.btn_reset["state"] == "disabled":
            return
        self._cancel_jog_timer()
        self._cancel_scan_timer()
        self.pos_x = 0.0
        self.pos_y = 0.0
        self._redraw()

    def set_area(self, x_cm, y_cm):
        self.area_x_cm = max(x_cm, 0.1)
        self.area_y_cm = max(y_cm, 0.1)
        self._redraw()

    def start_jog(self, dx_sign, dy_sign):
        self._cancel_scan_timer()
        self._jog_dx = dx_sign
        self._jog_dy = dy_sign
        self._jog_last_time = time.monotonic()
        self._jog_tick()

    def stop_jog(self):
        self._cancel_jog_timer()

    def start_scan_animation(self, x_cm, y_cm):
        self.set_reset_enabled(False)
        self._cancel_jog_timer()
        self._cancel_scan_timer()

        jumlah_titik = round(x_cm / self.point_distance_cm) + 1
        jumlah_baris = round(y_cm / self.row_distance_cm) + 1
        if jumlah_titik < 1 or jumlah_baris < 1:
            return

        rencana = []
        for baris in range(1, jumlah_baris + 1):
            arah_x = 1 if baris % 2 == 1 else -1
            rencana.append(("pause", self.break_time_ms))
            for _ in range(jumlah_titik - 1):
                durasi = (self.point_distance_cm / self.scan_speed_cm_s) * 1000
                rencana.append(("move", arah_x * self.point_distance_cm, 0.0, durasi))
                rencana.append(("pause", self.break_time_ms))
            if baris < jumlah_baris:
                durasi = (self.row_distance_cm / self.scan_speed_cm_s) * 1000
                rencana.append(("move", 0.0, -self.row_distance_cm, durasi))

        self._scan_queue = rencana
        self._scan_step()

    def stop_scan_animation(self):
        self._cancel_scan_timer()
        self.set_reset_enabled(True)

    def _jog_tick(self):
        now = time.monotonic()
        dt = now - self._jog_last_time
        self._jog_last_time = now
        self.pos_x += self._jog_dx * self.jog_speed_cm_s * dt
        self.pos_y += self._jog_dy * self.jog_speed_cm_s * dt
        self._redraw()
        self._jog_after_id = self.after(40, self._jog_tick)

    def _cancel_jog_timer(self):
        if self._jog_after_id is not None:
            self.after_cancel(self._jog_after_id)
            self._jog_after_id = None

    def _scan_step(self):
        if not self._scan_queue:
            self.set_reset_enabled(True)
            return

        aksi = self._scan_queue.pop(0)
        if aksi[0] == "pause":
            _, durasi_ms = aksi
            self._scan_after_id = self.after(max(int(durasi_ms), 1), self._scan_step)
        else:
            _, dx, dy, durasi_ms = aksi
            self._animate_move(dx, dy, max(durasi_ms, 1), self._scan_step)

    def _animate_move(self, dx, dy, durasi_ms, on_done):
        langkah = max(int(durasi_ms // 40), 1)
        step_dx = dx / langkah
        step_dy = dy / langkah

        def loop(sisa):
            if sisa <= 0:
                on_done()
                return
            self.pos_x += step_dx
            self.pos_y += step_dy
            self._redraw()
            self._scan_after_id = self.after(40, lambda: loop(sisa - 1))

        loop(langkah)

    def _cancel_scan_timer(self):
        if self._scan_after_id is not None:
            self.after_cancel(self._scan_after_id)
            self._scan_after_id = None
        self._scan_queue = []

    def _redraw(self):
        c = self.canvas
        c.delete("all")
        w = h = self.canvas_size
        cx, cy = w // 2, h // 2

        batas = max(
            self.area_x_cm, self.area_y_cm,
            abs(self.pos_x) * 1.3, abs(self.pos_y) * 1.3, 1.0,
        )
        margin = 25
        skala = (min(w, h) / 2 - margin) / batas

        c.create_line(margin, cy, w - margin, cy, fill="#bbb")
        c.create_line(cx, margin, cx, h - margin, fill="#bbb")
        c.create_text(w - margin + 10, cy - 8, text="X", fill="#888", font=("Segoe UI", 7))
        c.create_text(cx + 8, margin - 10, text="Y", fill="#888", font=("Segoe UI", 7))

        ax = self.area_x_cm * skala
        ay = self.area_y_cm * skala
        c.create_rectangle(cx, cy, cx + ax, cy + ay, dash=(4, 3), outline="#4a90d9")

        c.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill="black", outline="")
        c.create_text(cx, cy - 10, text="Tengah", fill="#555", font=("Segoe UI", 7))

        px = cx + self.pos_x * skala
        py = cy - self.pos_y * skala
        r = 5
        c.create_oval(px - r, py - r, px + r, py + r, fill="red", outline="#a00")

        self.lbl_pos.config(
            text=f"Posisi: X={self.pos_x:+.2f} cm, Y={self.pos_y:+.2f} cm"
        )
