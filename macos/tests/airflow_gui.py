"""Actual Tk widgets for the separate OA inputs; requires a native display."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tkinter as tk
from tkinter import messagebox, ttk as native_ttk
from facility_studio import api, i18n
from facility_studio.desktop import DesktopApp
from facility_studio.schema import FIELDS

errors = []
messagebox.showerror = lambda *args, **kwargs: errors.append(str(args))
messagebox.showinfo = lambda *args, **kwargs: None
messagebox.askyesno = lambda *args, **kwargs: False
messagebox.askyesnocancel = lambda *args, **kwargs: False
root = tk.Tk()
root.withdraw()
try:
    app = DesktopApp(root)
    p = api.default_project()
    p["inputs"].update(sys_type="MAU+FFU+DCC (全外氣/無塵室)",
                       en_L_A="100", en_W_A="83", en_H_A="3", en_ach_A="80",
                       oa_capacity_cmh="58000", en_manual_oa="0",
                       ffu_flow_basis="回風循環（外氣另加）")
    app.apply_project(p)
    app.recalculate()
    app.view_mode.set("基本模式")
    app.show_page(1)
    root.update()
    assert app.result["counts"]["FFU"] == 2050
    for key in ("en_manual_oa", "oa_capacity_cmh", "oa_future_cmh",
                "oa_reserve_pct", "ffu_flow_basis", "ffu_oa_route"):
        assert key in app.widgets
        assert str(app.widgets[key].cget("state")) != "disabled", key
        assert app.form_rows[key].winfo_manager() == "grid", key
    app.variables["en_manual_oa"].set("40000")
    app.recalculate()
    root.update()
    assert abs(app.result["oa_room_cmh"] - 40000) < 1e-6
    assert app.variables["oa_capacity_cmh"].get() == "58000"
    assert app.result["counts"]["FFU"] == 2050
    app.variables["sys_type"].set("AHU (OA+RA 混合)")
    app.recalculate()
    root.update()
    for key in ("oa_capacity_cmh", "ffu_flow_basis", "ffu_oa_route"):
        assert str(app.widgets[key].cget("state")) == "disabled", key
    assert str(app.widgets["en_manual_oa"].cget("state")) == "normal"
    app.variables["sys_type"].set("MAU+FFU+DCC (全外氣/無塵室)")
    app.recalculate()
    root.update()
    assert app.result["counts"]["FFU"] == 2050
    assert app.variables["oa_capacity_cmh"].get() == "58000"
    i18n.set_language("en", persist=False)
    root.update()
    assert "Total supply" in str(native_ttk.Combobox.cget(app.widgets["ffu_flow_basis"], "values"))
    i18n.set_language("zh-Hant", persist=False)
    root.update()
    assert app.snapshot()["inputs"]["oa_capacity_cmh"] == "58000"
    assert not errors, errors
    print("Native Tk OA fields, FFU calculation, interlocks and language switching passed.")
finally:
    root.destroy()
