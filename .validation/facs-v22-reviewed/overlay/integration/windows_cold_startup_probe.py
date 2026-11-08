"""Read-only native trace around the real entry.py/CLI in a fresh process.

Does not import view modules, initialize geometry, update Tk, reposition, resize,
withdraw, crop, or replace the application's mainloop. Only observation and
bounded test-process shutdown are added. Not a replacement for frozen capture.
"""
import argparse
import ctypes
from ctypes import wintypes
import json
import hashlib
import os
from pathlib import Path
import runpy
import sys
import time
import tkinter as tk


def native_snapshot(root):
    api = ctypes.WinDLL("user32", use_last_error=True)
    definitions = {
        "GetAncestor": ([wintypes.HWND, wintypes.UINT], wintypes.HWND),
        "GetMenu": ([wintypes.HWND], wintypes.HMENU),
        "GetWindowRect": ([wintypes.HWND, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
        "GetClientRect": ([wintypes.HWND, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
        "ClientToScreen": ([wintypes.HWND, ctypes.POINTER(wintypes.POINT)], wintypes.BOOL),
        "GetWindowLongW": ([wintypes.HWND, ctypes.c_int], wintypes.LONG),
        "GetDpiForWindow": ([wintypes.HWND], wintypes.UINT),
        "GetWindowDpiAwarenessContext": ([wintypes.HWND], wintypes.HANDLE),
        "MonitorFromWindow": ([wintypes.HWND, wintypes.DWORD], wintypes.HANDLE),
    }
    for name, (args, result) in definitions.items():
        fn = getattr(api, name)
        fn.argtypes, fn.restype = args, result
    hwnd = api.GetAncestor(root.winfo_id(), 2)
    if not hwnd:
        raise RuntimeError("No outer HWND")
    outer, client, visible = wintypes.RECT(), wintypes.RECT(), wintypes.RECT()
    origin = wintypes.POINT()
    if not (api.GetWindowRect(hwnd, ctypes.byref(outer))
            and api.GetClientRect(hwnd, ctypes.byref(client))
            and api.ClientToScreen(hwnd, ctypes.byref(origin))):
        raise RuntimeError("Native rectangle query failed")
    class MonitorInfo(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
    api.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
    api.GetMonitorInfoW.restype = wintypes.BOOL
    info = MonitorInfo(cbSize=ctypes.sizeof(MonitorInfo))
    if not api.GetMonitorInfoW(api.MonitorFromWindow(hwnd, 2), ctypes.byref(info)):
        raise RuntimeError("Monitor query failed")
    style = api.GetWindowLongW(hwnd, -16) & 0xffffffff
    extended = api.GetWindowLongW(hwnd, -20) & 0xffffffff
    dpi = api.GetDpiForWindow(hwnd)
    projection = wintypes.RECT(client.left, client.top, client.right, client.bottom)
    adjust = api.AdjustWindowRectExForDpi
    adjust.argtypes = [ctypes.POINTER(wintypes.RECT), wintypes.DWORD, wintypes.BOOL,
                       wintypes.DWORD, wintypes.UINT]
    adjust.restype = wintypes.BOOL
    adjusted = adjust(ctypes.byref(projection), style, True, extended, dpi)
    dwm = ctypes.WinDLL("dwmapi", use_last_error=True)
    dwm.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    dwm.DwmGetWindowAttribute.restype = ctypes.c_long
    hr = dwm.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(visible), ctypes.sizeof(visible))
    rect = lambda r: [r.left, r.top, r.right, r.bottom]
    return {"hwnd": int(hwnd), "menu": int(api.GetMenu(hwnd) or 0),
            "outer": rect(outer), "client_size": [client.right-client.left, client.bottom-client.top],
            "client": [origin.x, origin.y, origin.x+client.right, origin.y+client.bottom],
            "visible": rect(visible) if hr == 0 else None, "dwm_hresult": hr,
            "work": rect(info.rcWork), "title": root.title(), "state": root.state(), "style": style, "extended_style": extended,
            "dpi": dpi, "dpi_context": int(api.GetWindowDpiAwarenessContext(hwnd) or 0),
            "menu_projection_success": bool(adjusted),
            "menu_projection_size": [projection.right-projection.left, projection.bottom-projection.top]
            if adjusted else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--language", choices=["zh-Hant", "en"], required=True)
    parser.add_argument("--mode", choices=["simple", "workbench"], required=True)
    args = parser.parse_args()
    if sys.platform != "win32":
        raise RuntimeError("Requires real Windows; no synthetic native pass")
    root_path = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root_path / "windows"))
    os.environ["FACILITY_STUDIO_FUSION_DATA"] = str(args.data)
    os.environ["FACILITY_TEST_BLOCK_NETWORK"] = "1"
    os.environ["LOCALAPPDATA"] = str(args.data / "localappdata")
    report = {"mode": args.mode, "language": args.language, "events": [], "errors": [],
              "probe_moves_or_resizes_window": False, "passed": False}
    report["source_sha256"] = {str(path.relative_to(root_path)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [root_path / "integration/entry.py", root_path / "windows/facility_studio/cli.py",
                     root_path / "windows/facility_studio/window_geometry.py",
                     root_path / "windows/facility_studio/simple_desktop.py",
                     root_path / "windows/facility_studio/desktop.py"]}
    roots = []
    original_init = tk.Tk.__init__
    started = time.monotonic()
    def observe(label, extra=None):
        item = {"event": label, "elapsed": time.monotonic()-started, **(extra or {})}
        try:
            item["native"] = native_snapshot(roots[0])
        except Exception as exc:
            item["error"] = repr(exc)
        report["events"].append(item)
        return item
    def initialized(self, *pos, **kw):
        original_init(self, *pos, **kw)
        if roots:
            return
        roots.append(self)
        report["views_imported_when_tk_created"] = {
            name: name in sys.modules for name in
            ("facility_studio.simple_desktop", "facility_studio.desktop")}
        self.bind("<Map>", lambda event: observe("first_map") if event.widget is self else None, add="+")
        self.report_callback_exception = lambda kind, value, trace: report["errors"].append(repr(value))
        samples = []
        def settled():
            item = observe("settled_sample")
            samples.append(item)
            # Require six identical samples over >=0.5 seconds in the actual mainloop.
            recent = samples[-6:]
            comparable = lambda row: row.get("native")
            stable = len(recent) == 6 and all(comparable(row) == comparable(recent[0]) for row in recent)
            if stable or len(samples) >= 100:
                report["stable"] = stable
                report["settled"] = item.get("native")
                self.destroy()  # Test cleanup only; no placement/state alteration.
            else:
                self.after(100, settled)
        self.after(1000, settled)
    def profiler(frame, event, arg):
        if not roots or event not in ("call", "return"):
            return
        if not frame.f_code.co_filename.replace("\\", "/").endswith("/window_geometry.py"):
            return
        if frame.f_code.co_name not in ("_place_initial_windows_window", "_windows_startup_frame_size"):
            return
        extra = {"function": frame.f_code.co_name}
        if frame.f_code.co_name == "_windows_startup_frame_size":
            extra["measured_size"] = [frame.f_locals.get("width"), frame.f_locals.get("height")]
            if event == "return":
                extra["returned_size"] = arg
        observe(event, extra)
    tk.Tk.__init__ = initialized
    sys.setprofile(profiler)
    exit_code = 2
    try:
        sys.argv = [str(root_path / "integration/entry.py"), "--language", args.language]
        if args.mode == "workbench":
            sys.argv.append("--full")
        try:
            runpy.run_path(sys.argv[0], run_name="__main__")
        except SystemExit as exc:
            exit_code = exc.code or 0
    except Exception as exc:
        report["errors"].append(repr(exc))
    finally:
        sys.setprofile(None)
        tk.Tk.__init__ = original_init
        report["entry_exit"] = exit_code
        s = report.get("settled")
        if s:
            left, top, right, bottom = s["work"]
            report["containment"] = {name: bool(s[name] and left <= s[name][0] < s[name][2] <= right
                and top <= s[name][1] < s[name][3] <= bottom) for name in ("outer", "visible", "client")}
            report["passed"] = bool(exit_code == 0 and report.get("stable")
                and not report["errors"] and not any("error" in event for event in report["events"])
                and s["menu"] and all(report["containment"].values())
                and not any(report["views_imported_when_tk_created"].values()))
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
