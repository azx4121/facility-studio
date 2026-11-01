"""Windows and macOS must draw text at the same size (the macOS mapping: 1 pt = 1 px at 100 % display scaling).

Real Tk roots emulate what each platform reports: 72 dpi (macOS), 96 dpi (Windows at 100 %) and 144 dpi (Windows at
150 %). After normalising, 72 and 96 dpi give identical 10 pt text, 144 dpi gives 1.5 times that, the returned scale is
dpi/96 (never below 1) and a second call changes nothing. This proves the scaling rule, not how each OS draws fonts.
"""

import sys
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from facility_studio.platform_support import normalize_tk_scaling  # noqa: E402


def emulate(dpi):
    root = tk.Tk()
    root.withdraw()
    root.tk.call("tk", "scaling", dpi / 72.0)
    reported = root.winfo_fpixels("1i")
    scale = normalize_tk_scaling(root)
    again = normalize_tk_scaling(root)
    height = tkfont.Font(root=root, family="TkDefaultFont", size=10).metrics("linespace")
    pixels = root.winfo_fpixels("10p")
    root.destroy()
    return round(reported), scale, again, height, pixels


def main():
    failures = []
    mac = emulate(72)
    win100 = emulate(96)
    win150 = emulate(144)
    for name, (reported, scale, again, height, pixels), expected_scale in (
        ("72 dpi (macOS)", mac, 1.0),
        ("96 dpi (Windows 100 %)", win100, 1.0),
        ("144 dpi (Windows 150 %)", win150, 1.5),
    ):
        print(f"{name}: reported {reported} dpi, scale {scale:.3f}, 10 pt text {height} px line, 10 pt = {pixels:.1f} px")
        if abs(scale - expected_scale) > 0.01:
            failures.append(f"{name}: scale {scale}, expected {expected_scale}")
        if again != scale:
            failures.append(f"{name}: second call changed the scale to {again}")
    if mac[3] != win100[3] or abs(mac[4] - win100[4]) > 1e-6:
        failures.append(f"macOS and Windows 100 % differ: {mac[3:]} vs {win100[3:]}")
    if abs(win150[4] / win100[4] - 1.5) > 0.02:
        failures.append("150 % display did not draw 1.5 times larger text")
    if failures:
        print("FAILED:", *failures, sep="\n  ")
        return 1
    print("UI SCALING CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
