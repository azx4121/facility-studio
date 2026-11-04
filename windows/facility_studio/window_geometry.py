"""One main-window geometry policy for both views of the same Tk root.

Tk geometry sizes are CLIENT pixels. Do not subtract decorations from the current
window, reapply display scaling, or rewrite its geometry when changing views.
No window placement is persisted in engineering projects or user preferences.
"""
import sys


def _windows_work_area(root):
    """Return the current monitor's work-area size, including secondary monitors.

    Use the outer HWND rather than Tk's client child. Failure (old Windows, no
    native handle yet, or a non-Windows Tk) falls back to Tk's screen dimensions.
    Coordinates are deliberately not used to relocate the user's window.
    """
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class MonitorInfo(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.MonitorFromWindow.restype = wintypes.HANDLE
        user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
        user32.GetMonitorInfoW.restype = wintypes.BOOL
        hwnd = user32.GetAncestor(root.winfo_id(), 2) or root.winfo_id()
        monitor = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
        info = MonitorInfo(cbSize=ctypes.sizeof(MonitorInfo))
        if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            rect = info.rcWork
            return rect.right - rect.left, rect.bottom - rect.top
    except (AttributeError, OSError, ValueError):
        pass
    return None


def client_size_limit(root, scale):
    """Conservative client-area limits, always derived from the screen, not self.

    Leave room for window decorations and desktop chrome. Tk's screen fallback
    is also used on macOS; the window manager chooses initial placement. We do
    not clamp x/y to zero, which would move valid left/upper-screen windows.
    """
    area = _windows_work_area(root)
    if area is None:
        area = (root.winfo_screenwidth(), root.winfo_screenheight())
    return max(1, area[0] - round(60 * scale)), max(1, area[1] - round(100 * scale))


def initialize_main_window(root, scale):
    """Set the common startup size exactly once for this root, in either mode."""
    if getattr(root, "_facility_main_window_initialized", False):
        return
    root._facility_main_window_scale = scale
    width_limit, height_limit = client_size_limit(root, scale)
    width, height = min(round(1440 * scale), width_limit), min(round(830 * scale), height_limit)
    # No x/y or state: leave placement, maximization and full-screen to the WM.
    root.geometry(f"{width}x{height}")
    root._facility_main_window_initialized = True
    set_main_window_minimum(root, round(900 * scale), round(600 * scale), "base")

    def refresh_after_move():
        root._facility_minimum_job = None
        _refresh_main_window_minimum(root)

    def moved_or_resized(event):
        if event.widget is root and getattr(root, "_facility_minimum_job", None) is None:
            root._facility_minimum_job = root.after_idle(refresh_after_move)

    # Moving the simple view to a smaller monitor must refresh limits even when
    # no mode switch or workbench layout callback occurs.
    root.bind("<Configure>", moved_or_resized, add="+")


def _refresh_main_window_minimum(root):
    if not root.winfo_exists():
        return
    requirements = root._facility_main_window_minima
    limit = client_size_limit(root, getattr(root, "_facility_main_window_scale", 1.0))
    size = tuple(min(limit[i], max(value[i] for value in requirements.values())) for i in (0, 1))
    if tuple(root.minsize()) != size:
        root.minsize(*size)
    return size


def set_main_window_minimum(root, width, height, owner):
    """Share view minima, bounded by the current display, without writing geometry.

    Keeping each view's latest requirement prevents a hidden view from resetting
    the other view's minimum. WM minsize can grow a too-small window, but never
    shrinks a user-resized one or restores a maximized window to normal state.
    """
    requirements = getattr(root, "_facility_main_window_minima", {})
    requirements[owner] = (width, height)
    root._facility_main_window_minima = requirements
    return _refresh_main_window_minimum(root)
