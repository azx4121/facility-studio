"""Temporary, advertised-mode-only Win32 display setup for native GUI checks.

No registry persistence, guessed modes, virtual desktop claims, or skipped gates.
The child command runs only after Win32 AND Tk verify the requested desktop.
"""
from __future__ import annotations

import argparse
import ctypes as C
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback


class POINTL(C.Structure):
    _fields_ = [("x", C.c_int32), ("y", C.c_int32)]


class DISPLAY(C.Structure):
    _fields_ = [("position", POINTL), ("orientation", C.c_uint32),
                ("fixed_output", C.c_uint32)]


class MODE_UNION(C.Union):
    _fields_ = [("display", DISPLAY), ("printer", C.c_byte * 16)]


class DEVMODEW(C.Structure):
    # Fixed-width types preserve the documented 220-byte ABI even in unit tests
    # running on Unix, where c_long/wchar_t have different sizes from Windows.
    _fields_ = [("dmDeviceName", C.c_uint16 * 32),
                ("dmSpecVersion", C.c_uint16), ("dmDriverVersion", C.c_uint16),
                ("dmSize", C.c_uint16), ("dmDriverExtra", C.c_uint16),
                ("dmFields", C.c_uint32), ("mode_union", MODE_UNION),
                ("dmColor", C.c_int16), ("dmDuplex", C.c_int16),
                ("dmYResolution", C.c_int16), ("dmTTOption", C.c_int16),
                ("dmCollate", C.c_int16), ("dmFormName", C.c_uint16 * 32),
                ("dmLogPixels", C.c_uint16), ("dmBitsPerPel", C.c_uint32),
                ("dmPelsWidth", C.c_uint32), ("dmPelsHeight", C.c_uint32),
                ("dmDisplayFlags", C.c_uint32), ("dmDisplayFrequency", C.c_uint32),
                ("dmICMMethod", C.c_uint32), ("dmICMIntent", C.c_uint32),
                ("dmMediaType", C.c_uint32), ("dmDitherType", C.c_uint32),
                ("dmReserved1", C.c_uint32), ("dmReserved2", C.c_uint32),
                ("dmPanningWidth", C.c_uint32), ("dmPanningHeight", C.c_uint32)]


class RECT(C.Structure):
    _fields_ = [(name, C.c_int32) for name in ("left", "top", "right", "bottom")]


def describe(mode):
    return dict(width=mode.dmPelsWidth, height=mode.dmPelsHeight,
                bits=mode.dmBitsPerPel, frequency=mode.dmDisplayFrequency,
                fields=mode.dmFields)


def choose_mode(modes, width, height, exact=False):
    eligible = [m for m in modes if m.dmBitsPerPel >= 24 and
                ((m.dmPelsWidth, m.dmPelsHeight) == (width, height) if exact else
                 (m.dmPelsWidth >= width and m.dmPelsHeight >= height))]
    if not eligible:
        raise RuntimeError(f"No advertised display mode satisfies {width}x{height}, exact={exact}")
    return min(eligible, key=lambda m: (m.dmPelsWidth * m.dmPelsHeight,
                                       abs(m.dmDisplayFrequency - 60), -m.dmBitsPerPel))


class NativeDisplay:
    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError("Native Windows required; no emulation accepted")
        assert C.sizeof(DEVMODEW) == 220
        self.api = C.WinDLL("user32", use_last_error=True)
        self.api.EnumDisplaySettingsExW.argtypes = [C.c_wchar_p, C.c_uint32,
                                                   C.POINTER(DEVMODEW), C.c_uint32]
        self.api.EnumDisplaySettingsExW.restype = C.c_int
        self.api.ChangeDisplaySettingsExW.argtypes = [C.c_wchar_p, C.POINTER(DEVMODEW),
                                                      C.c_void_p, C.c_uint32, C.c_void_p]
        self.api.ChangeDisplaySettingsExW.restype = C.c_int32
        self.api.GetSystemMetrics.argtypes = [C.c_int]
        self.api.GetSystemMetrics.restype = C.c_int
        self.api.SystemParametersInfoW.argtypes = [C.c_uint32, C.c_uint32,
                                                  C.c_void_p, C.c_uint32]
        self.api.SystemParametersInfoW.restype = C.c_int
        self.api.GetAncestor.argtypes = [C.c_void_p, C.c_uint32]
        self.api.GetAncestor.restype = C.c_void_p
        self.api.GetWindowRect.argtypes = [C.c_void_p, C.POINTER(RECT)]
        self.api.GetWindowRect.restype = C.c_int

    def mode(self, index):
        mode = DEVMODEW()
        mode.dmSize = C.sizeof(mode)
        return mode if self.api.EnumDisplaySettingsExW(None, index, C.byref(mode), 0) else None

    def modes(self):
        result = []
        for index in range(4096):
            mode = self.mode(index)
            if mode is None:
                return result
            result.append(mode)
        raise RuntimeError("Display enumeration did not terminate")

    def change(self, mode, test=False):
        # CDS_TEST=2. Flags=0 is a temporary session change, not CDS_UPDATEREGISTRY.
        return self.api.ChangeDisplaySettingsExW(None, C.byref(mode), None, 2 if test else 0, None)

    def metrics(self):
        rect = RECT()
        if not self.api.SystemParametersInfoW(0x0030, 0, C.byref(rect), 0):
            raise C.WinError(C.get_last_error())
        return dict(screen=[self.api.GetSystemMetrics(0), self.api.GetSystemMetrics(1)],
                    work_area=[rect.left, rect.top, rect.right, rect.bottom],
                    current_mode=describe(self.mode(0xFFFFFFFF)))

    def verify_tk(self, width, height, exact, client):
        import tkinter as tk
        root = tk.Tk()
        try:
            root.geometry(f"{client[0]}x{client[1]}+20+20")
            for _ in range(20):
                root.update()
                time.sleep(.02)
            screen = (root.winfo_screenwidth(), root.winfo_screenheight())
            realized = (root.winfo_width(), root.winfo_height())
            rect = RECT()
            hwnd = self.api.GetAncestor(root.winfo_id(), 2)
            if not hwnd or not self.api.GetWindowRect(hwnd, C.byref(rect)):
                raise C.WinError(C.get_last_error())
            info = dict(windowing=root.tk.call("tk", "windowingsystem"),
                        tcl=root.tk.call("info", "patchlevel"),
                        tk=root.tk.call("package", "present", "Tk"),
                        screen=screen, requested_client=client, realized_client=realized,
                        outer_rect=[rect.left, rect.top, rect.right, rect.bottom])
            assert info["windowing"] == "win32", info
            assert (screen == (width, height) if exact else
                    screen[0] >= width and screen[1] >= height), info
            assert realized == tuple(client), info
            work = self.metrics()["work_area"]
            assert work[0] <= rect.left < rect.right <= work[2], (info, work)
            assert work[1] <= rect.top < rect.bottom <= work[3], (info, work)
            return info
        finally:
            root.destroy()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--exact", action="store_true")
    parser.add_argument("--client", default="1480x1000")
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    receipt = dict(native_windows=sys.platform == "win32", requested=[args.width, args.height],
                   exact=args.exact, command=command, passed=False,
                   frozen_binary_tested=False, formal_feed_accepted=False)
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    display = original = None
    restore_needed = False
    exit_code = 1
    try:
        display = NativeDisplay()
        original = display.mode(0xFFFFFFFF)
        assert original is not None, "Cannot save current display mode"
        receipt["before"] = display.metrics()
        modes = display.modes()
        receipt["advertised_modes"] = [describe(mode) for mode in modes]
        chosen = choose_mode(modes, args.width, args.height, args.exact)
        receipt["selected"] = describe(chosen)
        receipt["test_return"] = display.change(chosen, test=True)
        assert receipt["test_return"] == 0, "CDS_TEST rejected selected mode"
        # Set this before applying: an uncertain failure still attempts restoration.
        restore_needed = True
        receipt["apply_return"] = display.change(chosen)
        assert receipt["apply_return"] == 0, "Display change failed or requires restart"
        time.sleep(.5)
        receipt["after"] = display.metrics()
        actual = receipt["after"]["screen"]
        assert (actual == [args.width, args.height] if args.exact else
                actual[0] >= args.width and actual[1] >= args.height), receipt["after"]
        client = tuple(map(int, args.client.split("x")))
        assert len(client) == 2 and min(client) > 0
        receipt["tk"] = display.verify_tk(args.width, args.height, args.exact, client)
        # Persist the setup evidence before the potentially long-running command.
        args.evidence.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        exit_code = subprocess.run(command, check=False).returncode if command else 0
        receipt["command_exit_code"] = exit_code
    except Exception:
        receipt["error"] = traceback.format_exc()
        exit_code = 1
    finally:
        if display is not None and original is not None and restore_needed:
            try:
                receipt["restore_return"] = display.change(original)
                time.sleep(.5)
                receipt["restored"] = display.metrics()
                assert receipt["restore_return"] == 0
                assert receipt["restored"]["current_mode"] == describe(original)
                assert receipt["restored"]["screen"] == receipt["before"]["screen"]
            except Exception:
                receipt["restore_error"] = traceback.format_exc()
                exit_code = 1
        receipt["passed"] = exit_code == 0
        args.evidence.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
