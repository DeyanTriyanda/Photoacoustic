"""Wrapper komunikasi serial dengan Arduino (scanning fotoakustik)."""

import threading
import time

import serial
import serial.tools.list_ports


class SerialController:
    def __init__(self, on_message=None, on_status_change=None):
        self.ser = None
        self.read_thread = None
        self.running = False
        self.on_message = on_message
        self.on_status_change = on_status_change

    @staticmethod
    def list_ports():
        hasil = []
        for p in serial.tools.list_ports.comports():
            deskripsi = p.description if p.description and p.description != "n/a" else ""
            label = f"{p.device} - {deskripsi}" if deskripsi else p.device
            hasil.append((p.device, label))
        return hasil

    def connect(self, port, baudrate=9600, timeout=1):
        try:
            self.ser = serial.Serial(port, baudrate, timeout=timeout)
            time.sleep(2)
            self.running = True
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()
            if self.on_status_change:
                self.on_status_change(True)
            return True, f"Terhubung ke {port} @ {baudrate} baud"
        except Exception as e:
            self.ser = None
            return False, str(e)

    def disconnect(self):
        self.running = False
        if self.read_thread is not None:
            self.read_thread.join(timeout=1)
        if self.ser is not None and self.ser.is_open:
            self.ser.close()
        self.ser = None
        if self.on_status_change:
            self.on_status_change(False)

    def is_connected(self):
        return self.ser is not None and self.ser.is_open

    def send(self, command):
        if not self.is_connected():
            return False, "Belum terhubung ke Arduino"
        try:
            self.ser.write((command.strip() + "\n").encode("utf-8"))
            return True, f"Terkirim: {command}"
        except Exception as e:
            return False, str(e)

    def set_x(self, cm):
        return self.send(f"x={cm}")

    def set_y(self, cm):
        return self.send(f"y={cm}")

    def start_scan(self):
        return self.send("start")

    def stop_scan(self):
        return self.send("stop")

    def jog_kanan(self):
        return self.send("kanan")

    def jog_kiri(self):
        return self.send("kiri")

    def jog_maju(self):
        return self.send("maju")

    def jog_mundur(self):
        return self.send("mundur")

    def set_laser_freq(self, hz):
        """Kirim f=<Hz> ke Arduino 1; diteruskan ke Arduino laser via SoftSerial."""
        try:
            nilai = float(hz)
        except (TypeError, ValueError):
            return False, "Frekuensi laser tidak valid"
        if nilai < 0.1 or nilai > 50000.0:
            return False, "Frekuensi laser di luar rentang (0.1 .. 50000 Hz)"
        if float(nilai).is_integer():
            teks = str(int(nilai))
        else:
            teks = f"{nilai:.2f}"
        return self.send(f"f={teks}")

    def _read_loop(self):
        while self.running and self.ser is not None and self.ser.is_open:
            try:
                raw = self.ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if line and self.on_message:
                    self.on_message(line)
            except Exception as e:
                if self.on_message:
                    self.on_message(f"[ERROR BACA SERIAL] {e}")
                break
