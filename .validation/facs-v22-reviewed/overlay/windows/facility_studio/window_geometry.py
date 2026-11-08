"""One main-window geometry policy for both views of the same Tk root.

Tk geometry sizes are CLIENT pixels. Do not subtract decorations from the current
window, reapply display scaling, or rewrite its geometry when changing views.
No window placement is persisted in engineering projects or user preferences.
"""
import sys


def _windows_monitor(root):
    """Return the outer HWND and its monitor's work rectangle in native units.

    Use the outer HWND rather than Tk's client child. Failure (old Windows, no
    native handle yet, or a non-Windows Tk) leaves the existing fallback intact.
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
            return user32, hwnd, (rect.left, rect.top, rect.right, rect.bottom)
    except (AttributeError, OSError, ValueError):
        pass
    return None


def _windows_work_area(root):
    """Return the current monitor's work-area size, including secondary monitors."""
    monitor = _windows_monitor(root)
    if monitor is not None:
        _, _, (left, top, right, bottom) = monitor
        return right - left, bottom - top
    return None


def _place_initial_windows_window(root):
    """Keep a freshly mapped normal window inside its native monitor work area.

    GetWindowRect includes the resize frame, so containing it also contains the
    visible frame and client. All coordinates use the same Win32 DPI context;
    do not combine DWM's physical pixels with possibly virtualized coordinates,
    apply Theme.scale again, or interpret negative coordinates as Tk offsets.
    This moves only: startup sizing remains the shared client-size policy.
    """
    if root.state() != "normal" or root.attributes("-fullscreen"):
        return
    monitor = _windows_monitor(root)
    if monitor is None:
        return
    user32, hwnd, (left, top, right, bottom) = monitor
    try:
        import ctypes
        from ctypes import wintypes

        user32.IsZoomed.argtypes = [wintypes.HWND]
        user32.IsZoomed.restype = wintypes.BOOL
        user32.IsIconic.argtypes = [wintypes.HWND]
        user32.IsIconic.restype = wintypes.BOOL
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.GetWindowRect.restype = wintypes.BOOL
        user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.SetWindowPos.restype = wintypes.BOOL
        if user32.IsZoomed(hwnd) or user32.IsIconic(hwnd):
            return
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return
        width, height = rect.right - rect.left, rect.bottom - rect.top
        if not (0 < width <= right - left and 0 < height <= bottom - top):
            return  # Never resize an existing/user-owned window to force a fit.
        x = min(max(rect.left, left), right - width)
        y = min(max(rect.top, top), bottom - height)
        if (x, y) != (rect.left, rect.top):
            # SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE; preserve state/focus.
            user32.SetWindowPos(hwnd, None, x, y, 0, 0, 0x0015)
    except (AttributeError, OSError, ValueError):
        pass


def _bind_initial_windows_placement(root):
    """Consume exactly the first root Map, never a later user move or remap.

    Windows chooses a cascade origin before applying the requested client size.
    At Map, the real outer frame exists at that size. Correct it synchronously,
    before user interaction; an idle/timer retry could move a user-owned window.
    Already mapped roots and non-Windows hosts retain their existing behavior.
    """
    if sys.platform != "win32" or root.winfo_ismapped():
        return
    pending = True

    def first_map(event):
        nonlocal pending
        if event.widget is not root or not pending:
            return
        pending = False
        root.unbind("<Map>", binding)
        _place_initial_windows_window(root)

    binding = root.bind("<Map>", first_map, add="+")


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
    # No x/y or state here: Windows' first Map alone bounds a cascade overflow.
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
    _bind_initial_windows_placement(root)


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
