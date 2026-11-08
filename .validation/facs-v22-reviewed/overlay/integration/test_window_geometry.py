"""Main-window sizing regressions. Run each source tree in a separate process.

FACILITY_TEST_PLATFORM=windows|macos selects source, not the host OS.
FACILITY_REQUIRE_DISPLAY=1 turns missing Tk displays into failures for native QA.
All GUI user data, preferences and recovery files live in pytest's temp directory.
"""
import ast
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / os.environ.get("FACILITY_TEST_PLATFORM", "windows")
sys.path.insert(0, str(SOURCE))
from facility_studio import window_geometry as geometry
from facility_studio.platform_support import normalize_tk_scaling

NATIVE_WORK_AREA = geometry._windows_work_area


class Window:
    def __init__(self, screen=(1920, 1080), dpi=96):
        self.screen = screen
        self.dpi = dpi
        self.minimum = (1, 1)
        self.geometry_calls = []
        self.geometry_value = "1x1+0+0"
        self.state_value = "normal"
        self.tk = self
        self.display_scale = None
        self.bindings = {}
        self.pending = []

    def winfo_exists(self):
        return True

    def winfo_ismapped(self):
        return False

    def bind(self, event, callback, add):
        assert add == "+"
        self.bindings[event] = callback

    def after_idle(self, callback):
        self.pending.append(callback)
        return "pending"

    def eval(self, command):
        if command.startswith("info exists"):
            return int(self.display_scale is not None)
        if command.startswith("set ::facility_display_scale "):
            self.display_scale = float(command.split()[-1])
        return self.display_scale

    def call(self, *args):
        assert args[:2] == ("tk", "scaling")
        self.dpi = 72 * args[2]

    def winfo_fpixels(self, dimension):
        assert dimension == "1i"
        return self.dpi

    def winfo_screenwidth(self):
        return self.screen[0]

    def winfo_screenheight(self):
        return self.screen[1]

    def minsize(self, *size):
        if size:
            self.minimum = size
        return self.minimum

    def geometry(self, value=None):
        if value is not None:
            self.geometry_calls.append(value)
            self.geometry_value = value
        return self.geometry_value


@pytest.fixture(autouse=True)
def no_native_handle_in_fake_tests(monkeypatch):
    # Pure tests need no HWND; native cases explicitly undo this patch.
    monkeypatch.setattr(geometry, "_windows_work_area", lambda root: None)


def test_selected_source():
    assert Path(geometry.__file__).resolve().is_relative_to(SOURCE)


@pytest.mark.parametrize("screen", [(3840, 2160), (1920, 1080), (1366, 768), (960, 600)])
@pytest.mark.parametrize("dpi", [72, 96, 120, 144, 192])
def test_dpi_startup_is_bounded_and_twenty_mode_changes_do_not_shrink(screen, dpi):
    root = Window(screen, dpi)
    scale = normalize_tk_scaling(root)
    geometry.initialize_main_window(root, scale)
    initial = root.geometry()
    width, height = map(int, initial.split("x"))
    assert 1 <= width <= screen[0] - round(60 * scale)
    assert 1 <= height <= screen[1] - round(100 * scale)
    assert root.minimum[0] <= width and root.minimum[1] <= height
    for _ in range(20):
        assert normalize_tk_scaling(root) == scale
        geometry.initialize_main_window(root, scale)
        geometry.set_main_window_minimum(root, round(900 * scale), 810, "simple")
        geometry.set_main_window_minimum(root, round(900 * scale), 750, "workbench")
    assert root.geometry_calls == [initial]


@pytest.mark.parametrize("state", ["normal", "zoomed", "iconic", "fullscreen"])
@pytest.mark.parametrize("position", ["+100+120", "-1600+80", "+40-1200"])
def test_manual_size_negative_monitor_position_and_state_are_untouched(state, position):
    root = Window()
    geometry.initialize_main_window(root, 1)
    root.geometry(f"1575x920{position}")
    root.state_value = state
    previous = list(root.geometry_calls)
    for _ in range(20):
        geometry.initialize_main_window(root, 2)  # no second scaling/reposition
        geometry.set_main_window_minimum(root, 900, 760, "simple")
        geometry.set_main_window_minimum(root, 900, 690, "workbench")
    assert root.geometry_calls == previous
    assert root.state_value == state


def test_shared_minimum_is_stable_and_uses_current_monitor_work_area(monkeypatch):
    root = Window((3840, 2160))
    monkeypatch.setattr(geometry, "_windows_work_area", lambda root: (1280, 720))
    geometry.initialize_main_window(root, 1.5)
    assert root.geometry() == "1190x570"
    assert geometry.set_main_window_minimum(root, 1350, 900, "simple") == (1190, 570)
    assert geometry.set_main_window_minimum(root, 880, 560, "workbench") == (1190, 570)
    assert root.geometry_calls == ["1190x570"]


def test_small_screen_never_gets_an_oversized_minimum():
    root = Window((800, 600))
    geometry.initialize_main_window(root, 2)
    assert root.geometry() == "680x400"
    assert geometry.set_main_window_minimum(root, 1800, 2400, "simple") == (680, 400)


def test_restarts_do_not_inherit_an_already_normalized_dpi_or_client_size():
    results = []
    for _ in range(20):
        root = Window((2560, 1440), dpi=144)
        scale = normalize_tk_scaling(root)
        geometry.initialize_main_window(root, scale)
        results.append((root.geometry(), scale))
        root.geometry("900x600-1500+20")
    assert len(set(results)) == 1
    assert results[0] == ("2160x1245", 1.5)


def method_calls(filename, class_name, method_name):
    tree = ast.parse((SOURCE / "facility_studio" / filename).read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == method_name)
    return [node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
            for node in ast.walk(method) if isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Attribute, ast.Name))]


@pytest.mark.parametrize("filename, class_name, method", [
    ("simple_desktop.py", "SimpleToolsApp", "__init__"),
    ("desktop.py", "DesktopApp", "_build_window"),
])
def test_both_entry_paths_use_one_initializer(filename, class_name, method):
    calls = method_calls(filename, class_name, method)
    assert calls.count("initialize_main_window") == 1
    assert "geometry" not in calls
    assert "minsize" not in calls


def test_sidebar_measurement_does_not_write_a_transient_client_size():
    calls = method_calls("simple_desktop.py", "SimpleToolsApp", "fit_window_to_sidebar")
    assert "set_main_window_minimum" in calls
    assert "geometry" not in calls
    assert "winfo_width" not in calls


@pytest.fixture
def native_root(tmp_path, monkeypatch):
    import tkinter as tk
    from facility_studio import i18n
    monkeypatch.undo()  # Exercise the real Windows monitor query on native hosts.
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("FACILITY_STUDIO_PREFERENCES", str(tmp_path / "preferences.json"))
    i18n.set_language("zh-Hant", persist=False)
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        if os.environ.get("FACILITY_REQUIRE_DISPLAY") == "1":
            pytest.fail(f"Native GUI requires a display: {exc}")
        pytest.skip(f"No display; not native GUI acceptance: {exc}")
    errors = []
    root.report_callback_exception = lambda kind, value, tb: errors.append(str(value))
    yield root
    for token in root.tk.splitlist(root.tk.call("after", "info")):
        root.tk.call("after", "cancel", token)
    root.destroy()
    i18n.set_language("zh-Hant", persist=False)
    assert not errors


def pump(root, seconds=0.1):
    # Let the WM and deferred toolbar wrapping/min-height jobs both settle.
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        root.update_idletasks()
        root.update()
        time.sleep(0.005)


@pytest.mark.parametrize("entry", ["simple", "workbench"])
def test_real_tk_repeated_switches_preserve_geometry_and_data(native_root, entry):
    from facility_studio.desktop import DesktopApp
    from facility_studio.simple_desktop import SimpleToolsApp
    root = native_root
    if entry == "simple":
        simple = SimpleToolsApp(root)
        pump(root)
        width, height = geometry.client_size_limit(root, root._facility_main_window_scale)
        root.geometry(f"{width}x{height}+24+24")
        pump(root)
        before_first_switch = root.geometry()
        workbench = simple.open_workbench()
    else:
        workbench = DesktopApp(root)
        pump(root)
        width, height = geometry.client_size_limit(root, root._facility_main_window_scale)
        root.geometry(f"{width}x{height}+24+24")
        pump(root)
        before_first_switch = root.geometry()
        simple = workbench.show_simple_tools()
    pump(root)
    assert root.geometry() == before_first_switch
    simple.show_simple_tools()
    pump(root)
    workbench_before = workbench.session_snapshot()
    simple_before = simple.active_page().data()
    # Both modes are laid out; use a deliberate user resize after shared minima.
    width, height = geometry.client_size_limit(root, root._facility_main_window_scale)
    root.geometry(f"{min(width, max(root.winfo_width(), 1400))}x{min(height, max(root.winfo_height(), 950))}+24+24")
    pump(root)
    expected = (root.geometry(), root.state(), float(root.tk.call("tk", "scaling")))
    for _ in range(12):
        simple.open_workbench()
        pump(root)
        assert (root.geometry(), root.state(), float(root.tk.call("tk", "scaling"))) == expected
        simple.show_simple_tools()
        pump(root)
        assert (root.geometry(), root.state(), float(root.tk.call("tk", "scaling"))) == expected
    assert workbench.session_snapshot() == workbench_before
    assert simple.active_page().data() == simple_before


@pytest.mark.parametrize("state", ["zoomed", "fullscreen"])
def test_real_tk_maximized_or_fullscreen_switch_keeps_state(native_root, state):
    import tkinter as tk
    from facility_studio.simple_desktop import SimpleToolsApp
    root = native_root
    simple = SimpleToolsApp(root)
    pump(root)

    def unsupported_fullscreen():
        if root.tk.call("tk", "windowingsystem") != "x11" or not shutil.which("xprop"):
            return None
        result = subprocess.run(["xprop", "-root", "_NET_SUPPORTED"],
                                capture_output=True, text=True, check=False)
        if result.returncode == 0 and ("not found" in result.stdout or
                ("_NET_SUPPORTED" in result.stdout and
                 "_NET_WM_STATE_FULLSCREEN" not in result.stdout)):
            return result.stdout.strip()
        return None

    try:
        if state == "fullscreen":
            root.attributes("-fullscreen", True)
        else:
            root.state("zoomed")
    except tk.TclError as exc:
        if state == "fullscreen":
            evidence = unsupported_fullscreen()
            if evidence is None:
                raise
            pytest.skip(f"X11 window manager does not advertise fullscreen: {evidence}")
        pytest.skip(f"Window manager has no {state} support: {exc}")
    pump(root, seconds=1.5)  # Allow native fullscreen/maximize animation.
    if state == "fullscreen" and not root.attributes("-fullscreen"):
        # A window manager may silently ignore the request. Skip only when
        # X11 provides affirmative evidence that fullscreen is unsupported.
        evidence = unsupported_fullscreen()
        if evidence is not None:
            pytest.skip("X11 window manager does not advertise fullscreen: " + evidence)
        pytest.fail("Fullscreen request did not activate; support could not be ruled out")
    for _ in range(3):
        simple.open_workbench()
        pump(root)
        simple.show_simple_tools()
        pump(root)
        assert root.attributes("-fullscreen") if state == "fullscreen" else root.state() == "zoomed"


def test_windows_query_uses_outer_window_and_secondary_work_area(monkeypatch):
    import ctypes
    from types import SimpleNamespace

    class Function:
        def __init__(self, callback):
            self.callback = callback

        def __call__(self, *args):
            return self.callback(*args)

    calls = []
    def monitor(hwnd, flags):
        calls.append((hwnd, flags))
        return 222

    def info(handle, pointer):
        assert handle == 222
        rect = pointer._obj.rcWork
        rect.left, rect.top, rect.right, rect.bottom = -1920, -1200, 0, -120
        return 1

    user32 = SimpleNamespace(
        GetAncestor=Function(lambda hwnd, flags: 111),
        MonitorFromWindow=Function(monitor), GetMonitorInfoW=Function(info),
    )
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **kw: user32, raising=False)
    monkeypatch.setattr(geometry.sys, "platform", "win32")
    root = Window((3840, 2160))
    root.winfo_id = lambda: 777
    assert NATIVE_WORK_AREA(root) == (1920, 1080)
    assert calls == [(111, 2)]
    assert root.geometry_calls == []


def test_moving_simple_view_to_smaller_monitor_refreshes_minimum_without_switch(monkeypatch):
    from types import SimpleNamespace
    root = Window((3840, 2160))
    area = [(3840, 2120)]
    monkeypatch.setattr(geometry, "_windows_work_area", lambda root: area[0])
    geometry.initialize_main_window(root, 2)
    geometry.set_main_window_minimum(root, 1800, 1500, "simple")
    assert root.minsize() == (1800, 1500)
    original = list(root.geometry_calls)
    area[0] = (1280, 720)
    callback = root.bindings["<Configure>"]
    callback(SimpleNamespace(widget=object()))  # child layout is not a move
    assert not root.pending
    callback(SimpleNamespace(widget=root))
    geometry.set_main_window_minimum(root, 1800, 1500, "simple")
    # A synchronous layout setter must not lose the already queued idle job.
    for _ in range(20):
        callback(SimpleNamespace(widget=root))
    assert len(root.pending) == 1  # coalesce the native move/resize events
    root.pending.pop()()
    assert root.minsize() == (1160, 520)
    assert root.geometry_calls == original
    area[0] = (3840, 2120)
    callback(SimpleNamespace(widget=root))
    root.pending.pop()()
    assert root.minsize() == (1800, 1500)
    assert root.geometry_calls == original
