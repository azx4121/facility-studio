"""Windows first-map placement, separate from the immutable frozen capture gate.

Headless Win32 doubles exercise the actual production API path and its ABI;
these are regression/negative controls, not native GUI evidence. Native cases
inspect untouched real launches without relocating or resizing them for capture.
"""
import ctypes
import importlib.util
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "windows" / "facility_studio" / "window_geometry.py"
SPEC = importlib.util.spec_from_file_location("windows_startup_geometry", SOURCE)
geometry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(geometry)


class Function:
    def __init__(self, callback):
        self.callback = callback

    def __call__(self, *args):
        return self.callback(*args)


class Window:
    def __init__(self, *, mapped=False, state="normal", fullscreen=False):
        self.mapped = mapped
        self.state_value = state
        self.fullscreen = fullscreen
        self.bindings = {}
        self.unbound = []
        self.minimum = (1, 1)
        self.geometry_calls = []
        self.pending = []

    def winfo_id(self):
        return 777

    def winfo_ismapped(self):
        return self.mapped

    def winfo_exists(self):
        return True

    def winfo_screenwidth(self):
        return 1920

    def winfo_screenheight(self):
        return 1080

    def state(self):
        return self.state_value

    def attributes(self, name):
        assert name == "-fullscreen"
        return self.fullscreen

    def bind(self, event, callback, add):
        assert add == "+"
        token = f"binding-{len(self.bindings)}"
        self.bindings[event] = (token, callback)
        return token

    def unbind(self, event, token):
        assert self.bindings[event][0] == token
        self.unbound.append((event, token))
        del self.bindings[event]

    def geometry(self, value):
        self.geometry_calls.append(value)

    def minsize(self, *size):
        if size:
            self.minimum = size
        return self.minimum

    def after_idle(self, callback):
        self.pending.append(callback)
        return "minimum-job"


class Win32:
    # Deliberately beyond 32 bits: HWNDs must not be truncated by ctypes.
    outer = 0x123456789
    monitor = 0x23456789A

    def __init__(self, *, rect=(234, 211, 1690, 1100), work=(0, 0, 1920, 1040)):
        self.rect, self.work = rect, work
        self.moves, self.monitor_calls = [], []
        self.info_ok = self.rect_ok = self.move_ok = True
        self.zoomed = self.iconic = False
        self.GetAncestor = Function(self.ancestor)
        self.MonitorFromWindow = Function(self.monitor_from_window)
        self.GetMonitorInfoW = Function(self.monitor_info)
        self.GetWindowRect = Function(self.window_rect)
        self.IsZoomed = Function(lambda hwnd: self.zoomed)
        self.IsIconic = Function(lambda hwnd: self.iconic)
        self.SetWindowPos = Function(self.move)

    def ancestor(self, hwnd, flags):
        assert (hwnd, flags) == (777, 2)
        return self.outer

    def monitor_from_window(self, hwnd, flags):
        assert (hwnd, flags) == (self.outer, 2)
        self.monitor_calls.append((hwnd, flags))
        return self.monitor

    def monitor_info(self, monitor, pointer):
        assert monitor == self.monitor
        info = pointer._obj
        assert info.cbSize == ctypes.sizeof(info)
        info.rcWork.left, info.rcWork.top, info.rcWork.right, info.rcWork.bottom = self.work
        return self.info_ok

    def window_rect(self, hwnd, pointer):
        assert hwnd == self.outer
        rect = pointer._obj
        rect.left, rect.top, rect.right, rect.bottom = self.rect
        return self.rect_ok

    def move(self, hwnd, after, x, y, width, height, flags):
        self.moves.append((hwnd, after, x, y, width, height, flags))
        if self.move_ok:
            left, top, right, bottom = self.rect
            self.rect = x, y, x + right - left, y + bottom - top
        return self.move_ok


@pytest.fixture
def win32(monkeypatch):
    api = Win32()
    monkeypatch.setattr(geometry, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: api, raising=False)
    return api


@pytest.mark.parametrize("rect,work,expected", [
    # Exact failed final EXE: outer 1456x889, client 1440x830, work height 1040.
    ((234, 211, 1690, 1100), (0, 0, 1920, 1040), (234, 151)),
    ((900, 500, 2356, 1389), (0, 0, 1920, 1040), (464, 151)),
    ((10, 0, 1466, 889), (80, 40, 1920, 1040), (80, 40)),
    ((-1800, -1000, -344, -111), (-1920, -1200, 0, -160), (-1800, -1049)),
    ((-2000, -1300, -544, -411), (-1920, -1200, 0, -160), (-1920, -1200)),
    ((3000, 211, 4456, 1100), (1920, 0, 3840, 1040), (2384, 151)),
    # A scaled native rectangle is already in the right units, not scaled again.
    ((900, 500, 3084, 1833), (0, 0, 2880, 1560), (696, 227)),
])
def test_actual_outer_frame_is_clamped_in_native_work_area(win32, rect, work, expected):
    from ctypes import wintypes
    win32.rect, win32.work = rect, work
    root = Window()
    root._facility_main_window_scale = 3.0  # Must not rescale native coordinates.
    geometry._place_initial_windows_window(root)
    assert win32.moves == [(win32.outer, None, *expected, 0, 0, 0x0015)]
    assert win32.GetAncestor.restype is wintypes.HWND
    assert win32.MonitorFromWindow.restype is wintypes.HANDLE
    assert win32.GetWindowRect.argtypes == [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    assert win32.SetWindowPos.argtypes[:2] == [wintypes.HWND, wintypes.HWND]
    assert win32.monitor_calls == [(win32.outer, 2)]
    left, top, right, bottom = win32.rect
    assert work[0] <= left < right <= work[2]
    assert work[1] <= top < bottom <= work[3]
    assert (right - left, bottom - top) == (rect[2] - rect[0], rect[3] - rect[1])
    assert root.geometry_calls == []
    assert root.state() == "normal" and not root.fullscreen


@pytest.mark.parametrize("rect,work", [
    ((234, 120, 1690, 1009), (0, 0, 1920, 1040)),
    ((0, 0, 1920, 1040), (0, 0, 1920, 1040)),
    ((-1850, -1150, -394, -261), (-1920, -1200, 0, -160)),
    ((2000, 50, 3456, 939), (1920, 0, 3840, 1040)),
])
def test_fitting_positions_including_negative_monitors_are_untouched(win32, rect, work):
    win32.rect, win32.work = rect, work
    geometry._place_initial_windows_window(Window())
    assert win32.moves == [] and win32.rect == rect


@pytest.mark.parametrize("state,fullscreen,native_state", [
    ("zoomed", False, None), ("iconic", False, None),
    ("withdrawn", False, None), ("normal", True, None),
    ("normal", False, "zoomed"), ("normal", False, "iconic"),
])
def test_non_normal_or_fullscreen_state_is_never_changed(win32, state, fullscreen, native_state):
    if native_state:
        setattr(win32, native_state, True)
    root = Window(state=state, fullscreen=fullscreen)
    geometry._place_initial_windows_window(root)
    assert win32.moves == []
    assert (root.state(), root.fullscreen) == (state, fullscreen)
    assert root.geometry_calls == []


@pytest.mark.parametrize("failure", ["info", "rect", "missing_api", "load", "move"])
def test_native_api_failure_is_bounded_without_geometry_fallback(win32, monkeypatch, failure):
    if failure == "info":
        win32.info_ok = False
    elif failure == "rect":
        win32.rect_ok = False
    elif failure == "missing_api":
        del win32.SetWindowPos
    elif failure == "load":
        def unavailable(*args, **kwargs):
            raise OSError("No native handle/API")
        monkeypatch.setattr(ctypes, "WinDLL", unavailable)
    else:
        win32.move_ok = False
    root = Window()
    geometry._place_initial_windows_window(root)
    assert len(win32.moves) == (1 if failure == "move" else 0)
    assert win32.rect == (234, 211, 1690, 1100)
    assert root.geometry_calls == [] and root.pending == []


@pytest.mark.parametrize("rect", [
    (234, 211, 234, 1100), (234, 211, 1690, 211),
    (0, 0, 1921, 1040), (0, 0, 1920, 1041),
])
def test_invalid_or_oversized_outer_frame_is_not_resized(win32, rect):
    win32.rect = rect
    geometry._place_initial_windows_window(Window())
    assert win32.moves == [] and win32.rect == rect


def test_initializer_places_only_first_root_map_not_later_moves_or_switches(win32):
    root = Window()
    geometry.initialize_main_window(root, 1)
    assert win32.moves == [] and root.pending == []
    token, first_map = root.bindings["<Map>"]
    configure = root.bindings["<Configure>"][1]
    first_map(SimpleNamespace(widget=object()))
    assert win32.moves == [] and root.unbound == []
    first_map(SimpleNamespace(widget=root))
    assert win32.moves == [(win32.outer, None, 234, 151, 0, 0, 0x0015)]
    assert root.unbound == [("<Map>", token)] and "<Map>" not in root.bindings
    assert root.pending == []  # No delayed startup correction can move the user.
    # Deliberate later user move off-screen: minima may refresh, never placement.
    manual = (-2100, -1300, -644, -411)
    win32.rect = manual
    for _ in range(20):
        geometry.initialize_main_window(root, 2)
        geometry.set_main_window_minimum(root, 900, 760, "simple")
        geometry.set_main_window_minimum(root, 900, 690, "workbench")
        configure(SimpleNamespace(widget=root))
        first_map(SimpleNamespace(widget=root))  # A stale/repeated event is inert.
    assert len(root.pending) == 1
    root.pending.pop()()
    assert len(win32.moves) == 1 and win32.rect == manual
    assert root.geometry_calls == ["1440x830"]


def test_already_mapped_root_does_not_arm_placement(win32):
    root = Window(mapped=True)
    geometry.initialize_main_window(root, 1)
    assert "<Map>" not in root.bindings and win32.moves == []


@pytest.mark.parametrize("state,fullscreen", [("zoomed", False), ("iconic", False), ("normal", True)])
def test_skipped_first_map_is_consumed_not_retried_on_restore(win32, state, fullscreen):
    root = Window(state=state, fullscreen=fullscreen)
    geometry.initialize_main_window(root, 1)
    first_map = root.bindings["<Map>"][1]
    first_map(SimpleNamespace(widget=root))
    root.state_value, root.fullscreen = "normal", False
    first_map(SimpleNamespace(widget=root))
    assert win32.moves == [] and "<Map>" not in root.bindings and root.pending == []


@pytest.mark.parametrize("platform", ["darwin", "linux"])
def test_other_hosts_never_bind_or_query_native_placement(monkeypatch, platform):
    monkeypatch.setattr(geometry, "sys", SimpleNamespace(platform=platform))
    monkeypatch.setattr(geometry, "_place_initial_windows_window", lambda root: pytest.fail("Non-Windows placement"))
    root = Window()
    geometry.initialize_main_window(root, 1)
    assert "<Map>" not in root.bindings and root.geometry_calls == ["1440x830"]


@pytest.mark.skipif(sys.platform != "win32" or os.environ.get("FACILITY_TEST_PLATFORM", "windows") != "windows",
                    reason="Requires the Windows source on a real Windows desktop")
@pytest.mark.parametrize("language", ["zh-Hant", "en"])
@pytest.mark.parametrize("entry", ["simple", "workbench"])
@pytest.mark.parametrize("launch", range(4))
def test_native_untouched_launch_contains_outer_visible_frame_and_client(
        tmp_path, monkeypatch, entry, launch, language):
    """Observe real default-cascade launches; the test never adjusts placement."""
    import tkinter as tk
    from ctypes import wintypes

    monkeypatch.syspath_prepend(str(ROOT / "windows"))
    from facility_studio import i18n
    from facility_studio.industrial_theme import enable_high_dpi
    from facility_studio.desktop import DesktopApp
    from facility_studio.simple_desktop import SimpleToolsApp

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("FACILITY_STUDIO_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("FACILITY_STUDIO_PREFERENCES", str(tmp_path / "preferences.json"))
    i18n.set_language(language, persist=False)
    enable_high_dpi()
    # No missing-display skip on Windows: this is required native evidence.
    root = tk.Tk()
    errors = []
    initial_client = []
    root.bind("<Map>", lambda event: initial_client.append((root.winfo_width(), root.winfo_height()))
              if event.widget is root else None, add="+")
    root.report_callback_exception = lambda kind, value, trace: errors.append(str(value))
    try:
        (SimpleToolsApp if entry == "simple" else DesktopApp)(root)
        end = time.monotonic() + 0.4
        while time.monotonic() < end:
            root.update_idletasks()
            root.update()
            time.sleep(0.005)
        assert root.winfo_viewable() and root.state() == "normal"
        assert not errors
        # Independent native readout, not the production placement helper.
        class MonitorInfo(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
        api = ctypes.WinDLL("user32", use_last_error=True)
        api.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        api.GetAncestor.restype = wintypes.HWND
        api.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        api.MonitorFromWindow.restype = wintypes.HANDLE
        api.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
        api.GetMonitorInfoW.restype = wintypes.BOOL
        api.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        api.GetWindowRect.restype = wintypes.BOOL
        api.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        api.GetClientRect.restype = wintypes.BOOL
        api.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        api.ClientToScreen.restype = wintypes.BOOL
        hwnd = api.GetAncestor(root.winfo_id(), 2)
        assert hwnd
        monitor = api.MonitorFromWindow(hwnd, 2)
        info = MonitorInfo(cbSize=ctypes.sizeof(MonitorInfo))
        assert api.GetMonitorInfoW(monitor, ctypes.byref(info))
        work = (info.rcWork.left, info.rcWork.top, info.rcWork.right, info.rcWork.bottom)
        outer, client, visible = wintypes.RECT(), wintypes.RECT(), wintypes.RECT()
        origin = wintypes.POINT()
        assert api.GetWindowRect(hwnd, ctypes.byref(outer))
        assert api.GetClientRect(hwnd, ctypes.byref(client))
        assert api.ClientToScreen(hwnd, ctypes.byref(origin))
        dwm = ctypes.WinDLL("dwmapi", use_last_error=True)
        dwm.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        dwm.DwmGetWindowAttribute.restype = ctypes.c_long
        assert dwm.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(visible), ctypes.sizeof(visible)) == 0
        rects = {
            "outer": (outer.left, outer.top, outer.right, outer.bottom),
            "visible": (visible.left, visible.top, visible.right, visible.bottom),
            "client": (origin.x, origin.y, origin.x + client.right, origin.y + client.bottom),
        }
        for kind, (left, top, right, bottom) in rects.items():
            assert work[0] <= left < right <= work[2] and work[1] <= top < bottom <= work[3], (
                entry, language, launch, kind, rects, work, initial_client)
    finally:
        for token in root.tk.splitlist(root.tk.call("after", "info")):
            root.tk.call("after", "cancel", token)
        root.destroy()
        i18n.set_language("zh-Hant", persist=False)
