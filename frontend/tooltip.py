"""Tooltip hover + combobox dengan scrollbar (vertikal & horizontal)."""

import tkinter as tk
from tkinter import ttk


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
        # Perbarui teks pending jika kursor pindah antar item listbox
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


class ScrolledCombobox(ttk.Frame):
    """
    Pengganti ttk.Combobox untuk label panjang:
      - Entry readonly + scrollbar horizontal
      - Dropdown list + scrollbar vertikal & horizontal
      - Tooltip teks lengkap saat hover (entry + item di list)
    API mirip Combobox: get/set/current, ['values'], config(state=...)
    """

    def __init__(self, master, width=22, list_height=8, **kwargs):
        super().__init__(master, **kwargs)
        self._values = []
        self._state = "readonly"
        self._list_height = list_height
        self._popup = None
        self._root_bind_id = None
        self._listbox = None

        self._var = tk.StringVar()
        self.entry = tk.Entry(
            self,
            textvariable=self._var,
            width=width,
            state="readonly",
            readonlybackground="white",
            relief="solid",
            borderwidth=1,
        )
        self._hbar = ttk.Scrollbar(self, orient="horizontal", command=self.entry.xview)
        self.entry.configure(xscrollcommand=self._hbar.set)

        self._btn = ttk.Button(self, text="\u25BC", width=2, command=self._toggle_popup)

        self.entry.grid(row=0, column=0, sticky="ew")
        self._btn.grid(row=0, column=1, sticky="ns", padx=(2, 0))
        self._hbar.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.columnconfigure(0, weight=1)

        self.entry.bind("<Button-1>", self._on_entry_click)
        self._tip = HoverTooltip(self.entry, text_fn=self._tooltip_text)
        self._tip.bind_widget(self)

    def _tooltip_text(self, event=None):
        """Teks lengkap nilai terpilih / item listbox di bawah kursor."""
        if event is not None and self._listbox is not None:
            try:
                if str(event.widget) == str(self._listbox):
                    idx = self._listbox.nearest(event.y)
                    if 0 <= idx < self._listbox.size():
                        return self._listbox.get(idx)
            except Exception:
                pass
        return self.get()

    def _on_entry_click(self, _event=None):
        if self._state == "disabled":
            return "break"
        self._toggle_popup()
        return "break"

    def get(self):
        return self._var.get()

    def set(self, value):
        self._var.set(value if value is not None else "")
        self.entry.xview_moveto(0)

    def current(self, index=None):
        if index is None:
            try:
                return self._values.index(self.get())
            except ValueError:
                return -1
        if 0 <= index < len(self._values):
            self.set(self._values[index])

    def __setitem__(self, key, value):
        if key == "values":
            self._values = list(value)
        else:
            raise KeyError(key)

    def __getitem__(self, key):
        if key == "values":
            return tuple(self._values)
        raise KeyError(key)

    def config(self, **kwargs):
        return self.configure(**kwargs)

    def configure(self, **kwargs):
        if "values" in kwargs:
            self._values = list(kwargs.pop("values"))
        if "state" in kwargs:
            state = kwargs.pop("state")
            self._state = state
            if state == "disabled":
                self.entry.config(state="disabled")
                self._btn.config(state="disabled")
                self._close_popup()
            else:
                # readonly / normal -> entry tetap readonly (pilih dari list)
                self.entry.config(state="readonly", readonlybackground="white")
                self._btn.config(state="normal")
        if kwargs:
            super().configure(**kwargs)

    def _toggle_popup(self):
        if self._state == "disabled":
            return
        if self._popup is not None and self._popup.winfo_exists():
            self._close_popup()
            return
        self._open_popup()

    def _close_popup(self):
        self._listbox = None
        if self._root_bind_id is not None:
            try:
                self.winfo_toplevel().unbind("<Button-1>", self._root_bind_id)
            except Exception:
                pass
            self._root_bind_id = None
        if self._popup is not None:
            try:
                self._popup.destroy()
            except Exception:
                pass
            self._popup = None

    def _open_popup(self):
        self._close_popup()
        self.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        width = max(self.winfo_width(), 320)

        pop = tk.Toplevel(self)
        pop.wm_overrideredirect(True)
        pop.wm_geometry(f"{width}x220+{x}+{y}")
        try:
            pop.attributes("-topmost", True)
        except tk.TclError:
            pass
        self._popup = pop

        wrap = ttk.Frame(pop, padding=2)
        wrap.pack(fill="both", expand=True)

        vbar = ttk.Scrollbar(wrap, orient="vertical")
        hbar = ttk.Scrollbar(wrap, orient="horizontal")
        lb = tk.Listbox(
            wrap,
            height=self._list_height,
            exportselection=False,
            font=("Segoe UI", 9),
            yscrollcommand=vbar.set,
            xscrollcommand=hbar.set,
            activestyle="dotbox",
        )
        vbar.config(command=lb.yview)
        hbar.config(command=lb.xview)

        lb.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        for item in self._values:
            lb.insert("end", item)

        cur = self.get()
        if cur in self._values:
            idx = self._values.index(cur)
            lb.selection_set(idx)
            lb.see(idx)

        self._listbox = lb
        self._tip.bind_widget(lb)

        def _choose(_event=None):
            sel = lb.curselection()
            if not sel:
                return
            self.set(lb.get(sel[0]))
            self._close_popup()
            self.event_generate("<<ComboboxSelected>>")

        lb.bind("<Double-Button-1>", _choose)
        lb.bind("<Return>", _choose)
        lb.bind("<ButtonRelease-1>", _choose)

        pop.bind("<Escape>", lambda e: self._close_popup())
        self._root_bind_id = self.winfo_toplevel().bind(
            "<Button-1>", self._on_root_click, add="+"
        )
        lb.focus_set()

    def _on_root_click(self, event):
        if self._popup is None:
            return
        w = event.widget
        try:
            if str(w).startswith(str(self._popup)):
                return
            if w in (self.entry, self._btn):
                return
        except Exception:
            pass
        self._close_popup()
