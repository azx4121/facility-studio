"""Mac portability decisions and real Tk regressions; not a Mac execution claim."""

import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "macos"))
from facility_studio.platform_support import (
    app_data_root,
    preferred_ui_font,
    scroll_units,
)
from bootstrap import bundle_paths

checks = []


def check(name, value):
    checks.append({"name": name, "passed": bool(value)})
    assert value, name


home = Path("/Users/Test User 測試")
check(
    "Mac data belongs in Application Support",
    app_data_root("darwin", home, {})
    == home / "Library/Application Support/Facility_Studio_V5_5",
)
check(
    "Windows user data preserved",
    app_data_root("win32", home, {"LOCALAPPDATA": "C:/Local"})
    == Path("C:/Local/Facility_Studio_V5_5"),
)
check(
    "Linux data location preserved",
    app_data_root("linux", home, {}) == home / ".local/share/Facility_Studio_V5_5",
)
check(
    "Isolated recovery test directory honored",
    app_data_root("darwin", home, {"LOCALAPPDATA": "/tmp/recovery"})
    == Path("/tmp/recovery/Facility_Studio_V5_5"),
)
check(
    "Mac Chinese font selected",
    preferred_ui_font({"PingFang TC", "Segoe UI"}, "darwin") == "PingFang TC",
)
check(
    "Mac Chinese fallback selected",
    preferred_ui_font({"Heiti TC", "Segoe UI"}, "darwin") == "Heiti TC",
)
check(
    "Windows font preserved",
    preferred_ui_font({"Microsoft JhengHei", "PingFang TC"}, "win32")
    == "Microsoft JhengHei",
)
check(
    "No installed font gives Tk default",
    preferred_ui_font(set(), "darwin") == "TkDefaultFont",
)
for index, (platform, delta, number, expected) in enumerate(
    [
        ("darwin", 0, 0, 0),
        ("darwin", 1, 0, -1),
        ("darwin", -1, 0, 1),
        ("darwin", 3, 0, -3),
        ("darwin", -4, 0, 4),
        ("darwin", 0.1, 0, -1),
        ("darwin", -0.1, 0, 1),
        ("darwin", 100, 0, -12),
        ("darwin", float("nan"), 0, 0),
        ("darwin", float("inf"), 0, 0),
        ("win32", 120, 0, -1),
        ("win32", -240, 0, 2),
        ("win32", 0, 0, 0),
        ("linux", 0, 4, -3),
        ("linux", 0, 5, 3),
        ("linux", -120, 0, 1),
    ]
):
    check(
        f"Wheel condition {index + 1}",
        scroll_units(SimpleNamespace(delta=delta, num=number), platform) == expected,
    )
with tempfile.TemporaryDirectory(prefix="Mac Bundle 測試 ") as directory:
    resources = Path(directory) / "測試 App.app/Contents/Resources"
    (resources / "app/facility_studio").mkdir(parents=True)
    (resources / "app/facility_studio/cli.py").write_text("", encoding="utf-8")
    for architecture in ("arm64", "x86_64"):
        (resources / "python-packages" / architecture).mkdir(parents=True)
        source, packages, framework = bundle_paths(resources, architecture)
        check(
            f"Select matching wheels for {architecture}", packages.name == architecture
        )
        check(
            f"Paths remain relative for {architecture}",
            source.is_relative_to(resources)
            and framework.is_relative_to(resources.parent),
        )
    try:
        bundle_paths(resources, "i386")
        rejected = False
    except RuntimeError:
        rejected = True
    check("Unsupported CPU rejected", rejected)
    (resources / "app/facility_studio/cli.py").unlink()
    try:
        bundle_paths(resources, "arm64")
        rejected = False
    except RuntimeError:
        rejected = True
    check("Partial app extraction detected", rejected)

# Real Tk widgets, with only the portability decision simulated.
import tkinter as tk
from tkinter import ttk
from facility_studio.simple_desktop import SimpleToolsApp
from facility_studio.platform_support import bind_mac_shortcuts

root = tk.Tk()
app = SimpleToolsApp(root)
root.update()
page = app.active_page()
page.canvas.yview_moveto(0.2)
root.update()
position = page.canvas.yview()
app.wheel(SimpleNamespace(widget=page.canvas, delta=0, num=0))
check("Zero delta leaves real page stationary", page.canvas.yview() == position)
with patch("facility_studio.platform_support.sys.platform", "darwin"):
    bind_mac_shortcuts(root, calculate=lambda: None)
    check("Mac calculate shortcut registered", bool(root.bind("<Command-Return>")))
    app.wheel(SimpleNamespace(widget=page.canvas, delta=-1, num=0))
check(
    "Mac small trackpad event scrolls real page", page.canvas.yview()[0] >= position[0]
)
combo = next(
    widget for widget in page.widgets.values() if isinstance(widget, ttk.Combobox)
)
position = page.canvas.yview()
app.wheel(SimpleNamespace(widget=combo, delta=-1, num=0))
check(
    "Combo wheel does not scroll its containing form", page.canvas.yview() == position
)
workbench = app.open_workbench()
workbench.root.withdraw()
root.update()
check("Full workbench still calculates", workbench.result is not None)
with patch("facility_studio.platform_support.sys.platform", "darwin"):
    bind_mac_shortcuts(
        workbench.root,
        save=workbench.save,
        open=workbench.load,
        calculate=lambda: workbench.recalculate(True),
    )
check("Full Mac save shortcut", bool(workbench.root.bind("<Command-s>")))
check("Full Mac open shortcut", bool(workbench.root.bind("<Command-o>")))
app.close()
(ROOT / "evidence/Mac_Portability_Checks.json").write_text(
    json.dumps(
        {
            "environment": "Linux real Tk/Xvfb; macOS decisions simulated",
            "checks": checks,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
print(
    f"{len(checks)} Mac portability and real Tk checks passed; Mac hardware execution not performed"
)
