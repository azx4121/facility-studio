"""Desktop conventions shared by the simple and complete workbenches."""

import math
import os
from pathlib import Path
import sys


def app_data_root(platform=None, home=None, environ=None):
    platform = sys.platform if platform is None else platform
    home = Path.home() if home is None else Path(home)
    environ = os.environ if environ is None else environ
    # Explicit LOCALAPPDATA is retained for Windows and isolated test sessions.
    if environ.get("LOCALAPPDATA"):
        return Path(environ["LOCALAPPDATA"]) / "Facility_Studio_V5_5"
    if platform == "darwin":
        return home / "Library" / "Application Support" / "Facility_Studio_V5_5"
    return home / ".local" / "share" / "Facility_Studio_V5_5"


def preferred_ui_font(families, platform=None):
    platform = sys.platform if platform is None else platform
    names = ["Microsoft JhengHei", "Noto Sans CJK TC", "Noto Sans CJK JP"]
    if platform == "darwin":
        names = ["PingFang TC", "Heiti TC", *names]
    else:
        names.extend(["PingFang TC", "Segoe UI", "DejaVu Sans"])
    return next((name for name in names if name in families), "TkDefaultFont")


def scroll_units(event, platform=None):
    """Convert Tk wheel events to steps; a quiet trackpad event never scrolls."""
    platform = sys.platform if platform is None else platform
    number = getattr(event, "num", 0)
    if number in (4, 5):
        return -3 if number == 4 else 3
    try:
        delta = float(getattr(event, "delta", 0))
    except (ValueError, TypeError):
        return 0
    if not math.isfinite(delta) or delta == 0:
        return 0
    magnitude = abs(delta) if platform == "darwin" else abs(delta) / 120.0
    steps = min(12, max(1, math.ceil(magnitude)))
    return -steps if delta > 0 else steps


def bind_mac_shortcuts(window, **callbacks):
    if sys.platform != "darwin":
        return
    sequences = {
        "save": "<Command-s>",
        "open": "<Command-o>",
        "calculate": "<Command-Return>",
    }
    for key, callback in callbacks.items():

        def run(event, action=callback):
            action()
            return "break"

        window.bind(sequences[key], run, add="+")


def install_mac_quit(window, callback):
    """Route the application menu's Quit through the unsaved-project check."""
    if sys.platform == "darwin" and window is window._root():
        window.createcommand("tk::mac::Quit", callback)
