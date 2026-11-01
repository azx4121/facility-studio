"""Capture the first-launch window of a delivered Facility Studio app on a native desktop.

    python tools/capture_native_ui.py --platform windows --app Facility_Studio_V5_6_0_Windows_Offline.exe --language en --out win9-en.png
    python tools/capture_native_ui.py --platform macos --app "Facility Studio.app" --language zh-Hant --out mac7-zh.png

The app is started exactly as a user would start it (nothing is patched or driven); only the stored language preference
is pre-set through FACILITY_STUDIO_PREFERENCES, so every platform shows the same page (first tool, default inputs) in the
same language. The window itself is captured, with its frame, so the picture is what opens on that desktop. Needs Pillow on
Windows and pyobjc-framework-Quartz on macOS. Not for Linux.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TITLES = ("Facility Studio", "廠務簡易工具", "廠務工程工作台")


def windows_find():
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buffer, length + 1)
                if any(t in buffer.value for t in TITLES) and "5.6.0" in buffer.value:
                    found.append((hwnd, buffer.value))
        return True

    user32.EnumWindows(callback_type(callback), 0)
    return found[0] if found else None


def windows_capture(handle, out):
    import ctypes
    from ctypes import wintypes
    from PIL import ImageGrab

    user32 = ctypes.windll.user32
    user32.ShowWindow(handle, 9)
    user32.SetForegroundWindow(handle)
    time.sleep(2)
    rect = wintypes.RECT()
    # DwmGetWindowAttribute(DWMWA_EXTENDED_FRAME_BOUNDS) excludes the invisible resize margin.
    try:
        ctypes.windll.dwmapi.DwmGetWindowAttribute(handle, 9, ctypes.byref(rect), ctypes.sizeof(rect))
    except OSError:
        user32.GetWindowRect(handle, ctypes.byref(rect))
    ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom), all_screens=True).save(out)


def mac_find():
    import Quartz

    for window in Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID):
        owner = str(window.get("kCGWindowOwnerName", ""))
        name = str(window.get("kCGWindowName", ""))
        if ("FacilityStudio" in owner or "Facility Studio" in owner or any(t in name for t in TITLES)) and window.get("kCGWindowLayer", 1) == 0:
            bounds = window.get("kCGWindowBounds", {})
            if bounds.get("Width", 0) > 300 and bounds.get("Height", 0) > 300:
                return int(window["kCGWindowNumber"]), name
    return None


def mac_capture(number, out):
    subprocess.run(["/usr/sbin/screencapture", "-x", "-o", "-l", str(number), str(out)], check=True, timeout=60)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("windows", "macos"), required=True)
    parser.add_argument("--app", required=True, help="the .exe, or the .app bundle")
    parser.add_argument("--language", choices=("zh-Hant", "en"), required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout", type=int, default=180, help="seconds to wait for the window")
    args = parser.parse_args()
    if sys.platform != ("win32" if args.platform == "windows" else "darwin"):
        raise SystemExit("run this on the native platform")
    work = Path(tempfile.mkdtemp(prefix="fs-capture-"))
    preferences = work / "preferences.json"
    preferences.write_text(json.dumps({"language": args.language}), encoding="utf-8")
    env = dict(os.environ, FACILITY_STUDIO_PREFERENCES=str(preferences))
    command = [args.app] if args.platform == "windows" else [str(Path(args.app) / "Contents/MacOS/FacilityStudio")]
    if args.platform == "windows":
        import ctypes

        ctypes.windll.user32.SetProcessDPIAware()
    cwd = work / "empty"
    cwd.mkdir()
    process = subprocess.Popen(command, env=env, cwd=cwd)
    try:
        deadline = time.time() + args.timeout
        window = None
        while time.time() < deadline and window is None:
            time.sleep(2)
            window = windows_find() if args.platform == "windows" else mac_find()
        if window is None:
            raise SystemExit("no Facility Studio window appeared within " + str(args.timeout) + " s")
        print("window:", ascii(window), flush=True)
        time.sleep(8)  # first calculation and layout settle
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        (windows_capture if args.platform == "windows" else mac_capture)(window[0], out)
        print("saved", out, out.stat().st_size, "bytes", flush=True)
    finally:
        if args.platform == "windows":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True)
        else:
            process.kill()


if __name__ == "__main__":
    main()
