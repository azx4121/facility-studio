"""macOS must show the same text size as Windows (1 pt = 1.33 px), not 1 pt = 1 px.

The mapping is checked on a real Tk root: a 72 dpi interpreter (what macOS reports) is normalised to 96 dpi, and
a 10 pt font then measures the same as on a 96 dpi interpreter. Windows and Linux are left alone.
This proves the scaling rule, not how macOS draws its fonts.
"""

import sys
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from facility_studio.platform_support import normalize_tk_scaling  # noqa: E402


def line_height(root):
    return tkfont.Font(root=root, family="TkDefaultFont", size=10).metrics("linespace")


def main():
    failures = []
    reference = tk.Tk()
    reference.withdraw()
    reference.tk.call("tk", "scaling", 96.0 / 72.0)
    expected = line_height(reference)
    reference.destroy()

    root = tk.Tk()
    root.withdraw()
    root.tk.call("tk", "scaling", 1.0)  # what macOS reports: 72 dpi
    if round(root.winfo_fpixels("1i")) != 72:
        failures.append("test setup: could not emulate a 72 dpi interpreter")
    small = line_height(root)
    if normalize_tk_scaling(root, platform="darwin") is not True:
        failures.append("darwin was not normalised")
    if round(root.winfo_fpixels("1i")) != 96:
        failures.append(f"darwin dpi after normalising is {root.winfo_fpixels('1i')}, expected 96")
    after = line_height(root)
    if after != expected:
        failures.append(f"10 pt line height {after} px, Windows mapping gives {expected} px")
    if not after > small:
        failures.append(f"text did not grow: {small} -> {after}")

    root.tk.call("tk", "scaling", 2.0)
    before = float(root.tk.call("tk", "scaling"))  # Tk rounds the request to a whole pixel size
    for platform in ("win32", "linux"):
        if normalize_tk_scaling(root, platform=platform):
            failures.append(f"{platform} must not be touched")
    if float(root.tk.call("tk", "scaling")) != before:
        failures.append("scaling on a non-macOS platform changed")
    root.destroy()

    print(f"line height 10 pt: 72 dpi {small} px -> normalised {after} px (Windows mapping {expected} px)")
    if failures:
        print("FAILED:", *failures, sep="\n  ")
        return 1
    print("UI SCALING CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
