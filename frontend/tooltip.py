"""Tooltip hover untuk menampilkan teks lengkap (mis. nama device/port)."""

import tkinter as tk


class HoverTooltip:
    """Popup keterangan lengkap saat kursor diam di atas widget."""

    def __init__(self, widget, text_fn, delay_ms=350):
        """
        text_fn: callable () -> str, atau callable(event) -> str
        """
        self.widget = widget
        self.text_fn = text_fn
        self.delay_ms = delay_ms
        self._after_id = None
        self._tip = None
        self._bound = []
        self.bind_widget(widget)

    def bind_widget(self, widget):
        if widget is None:
            return
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
        widget.bind("<Motion>", self._on_motion, add="+")
        self._bound.append(widget)

    def _resolve_text(self, event=None):
        try:
            text = self.text_fn(event) if event is not None else self.text_fn()
        except TypeError:
            try:
                text = self.text_fn()
            except Exception:
                text = ""
        except Exception:
            text = ""
        return (text or "").strip()

    def _schedule(self, event=None):
        self._hide()
        text = self._resolve_text(event)
        if not text:
            return
        self._pending_text = text
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _on_motion(self, event=None):
        text = self._resolve_text(event)
        if not text:
            self._hide()
            return
        if getattr(self, "_pending_text", None) != text:
            self._pending_text = text
            if self._tip is not None:
                self._hide()
                self._after_id = self.widget.after(120, self._show)
            elif self._after_id is None:
                self._after_id = self.widget.after(self.delay_ms, self._show)

    def _show(self):
        self._after_id = None
        text = getattr(self, "_pending_text", None) or self._resolve_text()
        if not text:
            return
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None

        x = self.widget.winfo_pointerx() + 14
        y = self.widget.winfo_pointery() + 18
        self._tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        try:
            tw.attributes("-topmost", True)
        except tk.TclError:
            pass
        lbl = tk.Label(
            tw,
            text=text,
            justify="left",
            background="#ffffe0",
            foreground="#1a1a1a",
            relief="solid",
            borderwidth=1,
            font=("Segoe UI", 9),
            padx=8,
            pady=5,
            wraplength=480,
        )
        lbl.pack()

    def _hide(self, _event=None):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None
