"""Windows startup screenshots of an identity-verified, bounded EXE process.

No UI function or calculation is inferred from screenshots. A preexisting
matching process window, unresponsive window, failed foreground activation,
blank capture, early exit, or inability to close cleanly fails the capture.
The existing launcher owns the kill-on-close job and its timeout throughout.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time


class MonitorInfo(ctypes.Structure):
    _fields_ = [("cbSize", w.DWORD), ("rcMonitor", w.RECT), ("rcWork", w.RECT), ("dwFlags", w.DWORD)]


def rect_inside(inner, outer):
    return (inner[0] >= outer[0] and inner[1] >= outer[1]
            and inner[2] <= outer[2] and inner[3] <= outer[3])


def _require(condition, message):
    if not condition:
        raise RuntimeError(message)


class NativeWindows:
    def __init__(self):
        _require(sys.platform == "win32", "Startup capture needs native Windows")
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.callback_type = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
        definitions = [
            (self.user, "EnumWindows", [self.callback_type, w.LPARAM], w.BOOL),
            (self.user, "IsWindowVisible", [w.HWND], w.BOOL),
            (self.user, "IsWindow", [w.HWND], w.BOOL),
            (self.user, "GetWindowThreadProcessId", [w.HWND, ctypes.POINTER(w.DWORD)], w.DWORD),
            (self.user, "GetWindowTextLengthW", [w.HWND], ctypes.c_int),
            (self.user, "GetWindowTextW", [w.HWND, w.LPWSTR, ctypes.c_int], ctypes.c_int),
            (self.user, "GetClassNameW", [w.HWND, w.LPWSTR, ctypes.c_int], ctypes.c_int),
            (self.user, "GetWindowRect", [w.HWND, ctypes.POINTER(w.RECT)], w.BOOL),
            (self.user, "GetSystemMetrics", [ctypes.c_int], ctypes.c_int),
            (self.user, "MonitorFromWindow", [w.HWND, w.DWORD], w.HANDLE),
            (self.user, "GetMonitorInfoW", [w.HANDLE, ctypes.POINTER(MonitorInfo)], w.BOOL),
            (self.user, "SetForegroundWindow", [w.HWND], w.BOOL),
            (self.user, "GetForegroundWindow", [], w.HWND),
            (self.user, "PostMessageW", [w.HWND, w.UINT, w.WPARAM, w.LPARAM], w.BOOL),
            (self.user, "SendMessageTimeoutW", [w.HWND, w.UINT, w.WPARAM, w.LPARAM, w.UINT, w.UINT,
                                                 ctypes.POINTER(ctypes.c_size_t)], ctypes.c_ssize_t),
            (self.kernel, "OpenProcess", [w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            (self.kernel, "QueryFullProcessImageNameW", [w.HANDLE, w.DWORD, w.LPWSTR,
                                                          ctypes.POINTER(w.DWORD)], w.BOOL),
            (self.kernel, "CloseHandle", [w.HANDLE], w.BOOL),
        ]
        for library, name, args, result in definitions:
            function = getattr(library, name)
            function.argtypes = args
            function.restype = result
        # Screenshot coordinates and native RECT must use the same DPI space.
        self.user.SetProcessDPIAware.argtypes = []
        self.user.SetProcessDPIAware.restype = w.BOOL
        self.user.SetProcessDPIAware()
        self.user.IsProcessDPIAware.argtypes = []
        self.user.IsProcessDPIAware.restype = w.BOOL
        _require(self.user.IsProcessDPIAware(), "Cannot establish DPI-aware capture coordinates")

    def display_bounds(self, window):
        monitor = self.user.MonitorFromWindow(window["hwnd"], 2)  # nearest monitor
        info = MonitorInfo()
        info.cbSize = ctypes.sizeof(info)
        _require(monitor and self.user.GetMonitorInfoW(monitor, ctypes.byref(info)), "Monitor geometry unavailable")
        rectangle = lambda r: [r.left, r.top, r.right, r.bottom]
        left, top, width, height = [self.user.GetSystemMetrics(index) for index in (76, 77, 78, 79)]
        return {"coordinate_space": "DPI-aware native screen pixels",
                "primary_display": [0, 0, self.user.GetSystemMetrics(0), self.user.GetSystemMetrics(1)],
                "virtual_display": [left, top, left + width, top + height],
                "nearest_monitor": rectangle(info.rcMonitor),
                "nearest_work_area": rectangle(info.rcWork),
                "entire_window_inside_monitor": rect_inside(window["rect"], rectangle(info.rcMonitor)),
                "entire_window_inside_work_area": rect_inside(window["rect"], rectangle(info.rcWork))}

    @staticmethod
    def normalized(path):
        return os.path.normcase(os.path.abspath(path))

    def image_path(self, pid):
        process = self.kernel.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not process:
            return None
        try:
            length = w.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(length.value)
            if not self.kernel.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(length)):
                return None
            return buffer.value
        finally:
            self.kernel.CloseHandle(process)

    def windows(self, executable):
        found = []
        errors = []
        expected = self.normalized(executable)

        @self.callback_type
        def callback(hwnd, unused):
            try:
                if not self.user.IsWindowVisible(hwnd):
                    return True
                pid = w.DWORD()
                self.user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                actual = self.image_path(pid.value)
                if not actual or self.normalized(actual) != expected:
                    return True
                length = self.user.GetWindowTextLengthW(hwnd)
                title = ctypes.create_unicode_buffer(max(length + 1, 2))
                self.user.GetWindowTextW(hwnd, title, len(title))
                window_class = ctypes.create_unicode_buffer(256)
                self.user.GetClassNameW(hwnd, window_class, len(window_class))
                rect = w.RECT()
                _require(self.user.GetWindowRect(hwnd, ctypes.byref(rect)), "GetWindowRect failed")
                found.append({"hwnd": int(hwnd), "pid": pid.value, "process_image": actual,
                              "title": title.value, "class": window_class.value,
                              "rect": [rect.left, rect.top, rect.right, rect.bottom]})
            except Exception as error:
                errors.append(error)
                return False
            return True

        success = self.user.EnumWindows(callback, 0)
        if errors:
            raise errors[0]
        _require(success, "EnumWindows failed")
        return found

    def verify(self, window, executable):
        hwnd = window["hwnd"]
        _require(self.user.IsWindow(hwnd) and self.user.IsWindowVisible(hwnd), "Window disappeared")
        pid = w.DWORD()
        self.user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        actual = self.image_path(pid.value)
        _require(pid.value == window["pid"] and actual
                 and self.normalized(actual) == self.normalized(executable), "Window process identity changed")
        response = ctypes.c_size_t()
        _require(self.user.SendMessageTimeoutW(hwnd, 0, 0, 0, 2, 3000, ctypes.byref(response)),
                 "Native application window is unresponsive")  # WM_NULL / SMTO_ABORTIFHUNG

    def close(self, window, executable):
        self.verify(window, executable)
        _require(self.user.PostMessageW(window["hwnd"], 0x0010, 0, 0), "WM_CLOSE could not be posted")


def capture_startup(executable, output, language, full, run_bounded, offline_environment, timeout=180):
    from PIL import ImageGrab, ImageStat

    executable = Path(executable).resolve()
    case = Path(output) / (language + ("-full-startup" if full else "-simple-startup"))
    case.mkdir(exist_ok=False)
    data = case / "app-data"
    data.mkdir()
    native = NativeWindows()
    _require(not native.windows(executable), "Matching EXE windows already exist before launch")
    command = [str(executable), "--language", language] + (["--full"] if full else [])
    state = {}
    done = threading.Event()
    record = {"passed": False, "scope": "Visible native startup only; no form interaction is proven",
              "language_argument": language, "mode_argument": "full" if full else "simple",
              "command": command, "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
              "window": None, "closed_cleanly": False}
    metadata = case / "Startup_Capture.json"

    def persist():
        metadata.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    def launch():
        try:
            state["process"] = run_bounded(command, case / "process.log", offline_environment(data), timeout=timeout)
        except BaseException as error:
            state["error"] = repr(error)
        finally:
            done.set()

    persist()
    worker = threading.Thread(target=launch, name="bounded-facs-startup", daemon=True)
    worker.start()
    start = time.monotonic()
    window = None
    try:
        # Leave timeout budget for clean close and the proven launcher cleanup.
        deadline = start + max(10, timeout - 20)
        stable_since = None
        previous = None
        while time.monotonic() < deadline:
            _require(not done.is_set(), "EXE exited before a stable startup window: " + str(state))
            windows = native.windows(executable)
            mains = [item for item in windows if item["class"] == "TkTopLevel"
                     and item["title"] and item["rect"][2] - item["rect"][0] >= 400
                     and item["rect"][3] - item["rect"][1] >= 300]
            if len(mains) == 1:
                current = mains[0]
                key = current["hwnd"], tuple(current["rect"]), current["title"]
                if key != previous:
                    stable_since = time.monotonic()
                    previous = key
                elif time.monotonic() - stable_since >= 3:
                    window = current
                    break
            else:
                stable_since = previous = None
            time.sleep(.2)
        _require(window is not None, "No unique stable native Tk application window before deadline")
        native.verify(window, executable)
        bounds = native.display_bounds(window)
        record.update(window=window, display_bounds=bounds)
        persist()
        _require(bounds["entire_window_inside_monitor"] and bounds["entire_window_inside_work_area"],
                 "Application window is clipped by the display or work area; whole-window capture refused")
        if native.user.GetForegroundWindow() != window["hwnd"]:
            _require(native.user.SetForegroundWindow(window["hwnd"]), "Cannot activate target window for screenshot")
        time.sleep(.7)
        _require(native.user.GetForegroundWindow() == window["hwnd"], "Target window is not in foreground")
        native.verify(window, executable)
        latest = [item for item in native.windows(executable) if item["hwnd"] == window["hwnd"]]
        _require(len(latest) == 1 and latest[0]["rect"] == window["rect"], "Window moved before capture")
        screenshot = ImageGrab.grab(bbox=tuple(window["rect"]), all_screens=True)
        _require(screenshot.size == (window["rect"][2] - window["rect"][0],
                                     window["rect"][3] - window["rect"][1]), "Screenshot geometry mismatch")
        statistics = ImageStat.Stat(screenshot.convert("RGB"))
        _require(max(statistics.stddev) > 5, "Blank or nearly uniform screenshot")
        target = case / "startup.png"
        screenshot.save(target, "PNG")
        native.verify(window, executable)
        _require(native.user.GetForegroundWindow() == window["hwnd"], "Foreground changed during capture")
        record.update(window=window, screenshot=str(target), screenshot_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                      screenshot_size=list(screenshot.size), pixel_stddev=statistics.stddev,
                      human_visual_review="pending")
        persist()
        native.close(window, executable)
        _require(done.wait(min(20, max(1, timeout - (time.monotonic() - start)))), "EXE did not close promptly")
        _require("error" not in state, "Bounded EXE launch failed: " + str(state))
        _require(state["process"]["exit_code"] == 0, "EXE close returned failure")
        _require(not native.windows(executable), "Application window survived bounded launch")
        record.update(passed=True, closed_cleanly=True, process=state["process"])
        return record
    except Exception as error:
        record["error"] = str(error)
        raise
    finally:
        if not done.is_set():
            # Close only a currently identity-verified window from this unique copy.
            for remaining in native.windows(executable):
                try:
                    native.close(remaining, executable)
                except RuntimeError:
                    pass
            remaining_budget = max(1, timeout - (time.monotonic() - start)) + 45
            if not done.wait(remaining_budget):
                record["cleanup_error"] = "Bounded launcher did not finish within its cleanup budget"
                record["passed"] = False
        record["launcher_finished"] = done.is_set()
        if "error" in state:
            record["launcher_error"] = state["error"]
        persist()
