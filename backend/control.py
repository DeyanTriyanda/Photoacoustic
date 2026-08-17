"""Komunikasi serial Arduino."""

import sys

if sys.platform == "win32":
    from backend._native_fallback import SerialControllerNative
else:
    from backend._native import SerialControllerNative


def _enrich_ports(ports):
    try:
        import serial.tools.list_ports
    except Exception:
        return [(d, lab) for d, lab in ports]

    by_device = {}
    for p in serial.tools.list_ports.comports():
        deskripsi = p.description if p.description and p.description != "n/a" else ""
        label = f"{p.device} - {deskripsi}" if deskripsi else p.device
        by_device[p.device] = label

    hasil = []
    seen = set()
    for device, label in ports:
        hasil.append((device, by_device.get(device, label)))
        seen.add(device)
    for device, label in by_device.items():
        if device not in seen:
            hasil.append((device, label))
    return hasil


class SerialController:
    def __init__(self, on_message=None, on_status_change=None):
        self._native = SerialControllerNative()
        self.on_message = on_message
        self.on_status_change = on_status_change
        if on_message is not None:
            self._native.set_on_message(on_message)
        if on_status_change is not None:
            self._native.set_on_status_change(on_status_change)

    @staticmethod
    def list_ports():
        return _enrich_ports(list(SerialControllerNative.list_ports()))

    def connect(self, port, baudrate=9600, timeout=1):
        return self._native.connect(str(port), int(baudrate), float(timeout))

    def disconnect(self):
        self._native.disconnect()

    def is_connected(self):
        return bool(self._native.is_connected())

    def send(self, command):
        return self._native.send(str(command))

    def set_x(self, cm):
        return self._native.set_x(float(cm))

    def set_y(self, cm):
        return self._native.set_y(float(cm))

    def start_scan(self):
        return self._native.start_scan()

    def stop_scan(self):
        return self._native.stop_scan()

    def jog_kanan(self):
        return self._native.jog_kanan()

    def jog_kiri(self):
        return self._native.jog_kiri()

    def jog_maju(self):
        return self._native.jog_maju()

    def jog_mundur(self):
        return self._native.jog_mundur()
