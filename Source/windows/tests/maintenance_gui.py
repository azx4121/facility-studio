"""Actual Tk checks for repaired quick-tool error location and mode switching."""

import json
import math
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
from tkinter import messagebox

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from facility_studio.desktop import DesktopApp
from facility_studio.tools_view import QuickToolsWindow

checks, errors = [], []
messagebox.showerror = lambda *args, **kwargs: errors.append(str(args))


def check(name, condition):
    checks.append(dict(name=name, passed=bool(condition)))
    assert condition, name


with tempfile.TemporaryDirectory(prefix="facility_maintenance_gui_") as directory:
    os.environ["LOCALAPPDATA"] = directory
    root = tk.Tk()
    root.report_callback_exception = lambda *args: errors.append(str(args))
    app = DesktopApp(root)
    quick = QuickToolsWindow(root, app)
    try:
        quick.tool.set("濕空氣計算")
        quick.build()
        quick.calculate()
        root.update()
        check("default_valid", quick.result is not None)
        quick.values["pressure"].set("50")
        quick.calculate()
        check("invalid_pressure_blocks_result", quick.result is None)
        check("pressure_label_explains_range", "60～120" in quick.field_labels["pressure"].cget("text"))
        check("pressure_error_identifies_field", "大氣壓" in quick.text.get("1.0", "end"))
        check("pressure_field_marked", quick.widgets["pressure"].cget("style") == "Invalid.TEntry")
        quick.values["pressure"].set("101.325")
        quick.values["first"].set("-50")
        quick.values["second"].set("10")
        quick.calculate()
        original = quick.result
        check("low_temperature_valid", original is not None and original["dewpoint_c"] < -60)
        check("corrected_style_clears", quick.widgets["pressure"].cget("style") == "TEntry")
        quick.values["mode"].set("乾球＋露點")
        quick.calculate()
        check("dewpoint_switch_stays_valid", quick.result is not None)
        check("dewpoint_switch_preserves_humidity", math.isclose(quick.result["w"], original["w"], rel_tol=1e-8))
        quick.values["first"].set("22")
        quick.values["second"].set("22")
        quick.calculate()
        check("saturated_dewpoint_valid", quick.result is not None and math.isclose(quick.result["rh"], 100))
        quick.values["first"].set("bad")
        quick.calculate()
        check("bad_temperature_blocks_result", quick.result is None)
        check("temperature_error_identifies_field", "乾球" in quick.text.get("1.0", "end"))
        check("temperature_field_marked", quick.widgets["first"].cget("style") == "Invalid.TEntry")
        check("no_unhandled_callbacks", not errors)
    finally:
        quick.close(force=True)
        root.destroy()

(ROOT / "evidence/Maintenance_GUI_Checks.json").write_text(
    json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"{len(checks)} maintenance real Tk interaction checks passed")
