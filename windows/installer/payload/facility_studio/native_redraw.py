"""Refresh the complete Windows client after Tk moves or resizes controls.

Windows hosted desktops can retain GDI pixels from earlier child positions.
A debounced native repaint clears them without changing layout or model state.
"""

import sys
import tkinter as tk


class NativeRedraw:
    def __init__(self, window):
        import ctypes
        from ctypes import wintypes

        self.window = window
        self.pending = None
        self.repaint_window = ctypes.windll.user32.RedrawWindow
        self.repaint_window.argtypes = (
            wintypes.HWND, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT
        )
        self.repaint_window.restype = wintypes.BOOL
        window.bind("<Configure>", self.schedule, add="+")
        window.bind("<Map>", self.schedule, add="+")
        window.bind("<Destroy>", self.release, add="+")

    def schedule(self, event=None):
        if event is not None and event.widget.winfo_toplevel() is not self.window:
            return
        if self.pending is not None:
            self.window.after_cancel(self.pending)
        self.pending = self.window.after(50, self.repaint)

    def repaint(self):
        self.pending = None
        if not self.window.winfo_exists() or not self.window.winfo_ismapped():
            return False
        # INVALIDATE | ERASE | ALLCHILDREN | UPDATENOW | ERASENOW.
        return bool(self.repaint_window(self.window.winfo_id(), None, None, 0x0385))

    def release(self, event):
        if event.widget is self.window and self.pending is not None:
            try:
                self.window.after_cancel(self.pending)
            except tk.TclError:
                pass
            self.pending = None


def install_native_redraw(window):
    if sys.platform != "win32" or hasattr(window, "_native_redraw"):
        return
    window._native_redraw = NativeRedraw(window)
