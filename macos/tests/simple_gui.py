"""Real Tk checks for independent navigation, defaults, interlocks and resizing."""

from pathlib import Path
import json
import math
import os
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import tkinter as tk
from tkinter import messagebox
from PIL import ImageGrab
from facility_studio.simple_desktop import SimpleToolsApp
from facility_studio.simple_schema import TOOLS

checks, errors = [], []
answer = False
messagebox.showerror = lambda *args, **kwargs: errors.append(str(args))
messagebox.showinfo = lambda *args, **kwargs: None
messagebox.askyesnocancel = lambda *args, **kwargs: answer
messagebox.askyesno = lambda *args, **kwargs: True
messagebox.askokcancel = lambda *args, **kwargs: True


def check(name, condition):
    checks.append({"name": name, "passed": bool(condition)})
    assert condition, name


def set_values(page, **values):
    for key, value in values.items():
        page.variables[key].set(str(value))
    page.calculate()
    root.update()


def screenshot(name):
    root.update()
    time.sleep(.1)
    box = (root.winfo_rootx(), root.winfo_rooty(),
           root.winfo_rootx()+root.winfo_width(), root.winfo_rooty()+root.winfo_height())
    ImageGrab.grab(bbox=box).save(ROOT / "evidence" / name)


with tempfile.TemporaryDirectory(prefix="facility553_gui_") as directory:
    os.environ["LOCALAPPDATA"] = directory
    root = tk.Tk()
    root.report_callback_exception = lambda *args: errors.append(str(args))
    app = SimpleToolsApp(root)
    root.geometry("1120x830+20+20")
    root.update()
    check("01_four_primary_tools", len(app.nav) == 4)
    check("02_no_project_required", app.workbench is None and len(app.pages) == 1)
    power = app.active_page()
    check("03_electrical_three_visible_fields", sum(bool(row.winfo_manager()) for row in power.rows.values()) == 3)
    check("04_defaults_exposed", "PF .85" in power.assumptions.cget("text") and "單程30m" in power.assumptions.cget("text"))
    check("05_default_electrical_calculates", power.result["selected"]["nfb_a"] == 20)
    screenshot("V554_Electrical.png")
    power.variables["power"].set("not a number")
    check("06_stale_values_cleared_immediately", power.result is None and app.export_button.instate(["disabled"]))
    power.calculate(True)
    check("07_inline_field_error", "設備用電功率" in power.status.cget("text") and power.widgets["power"].cget("style") == "Simple.Invalid.TEntry")
    check("08_invalid_copy_blocked", not app.copy_result())
    output = Path(directory) / "invalid.txt"
    check("09_invalid_export_blocked", not app.export_result(output) and not output.exists())

    app.nav["duct"].invoke()
    root.update()
    duct = app.active_page()
    check("10_unrelated_bad_power_ignored", duct.result is not None)
    check("11_duct_two_visible_fields", sum(bool(row.winfo_manager()) for row in duct.rows.values()) == 2)
    check("12_pressure_not_certified", not duct.result["path_checked"] and "未核" in duct.details.cget("text"))
    original = duct.result["flow_cmh"]
    for index in range(4):
        set_values(duct, flow_unit="CFM")
        check("13_flow_equivalence_" + str(index), math.isclose(duct.result["flow_cmh"], original, rel_tol=1e-12))
        set_values(duct, flow_unit="CMH")
    set_values(duct, pressure_unit="mmAq")
    check("14_duct_pressure_equivalence", math.isclose(duct.result["pressure_pa"], 200))
    duct.reset()
    root.update()
    screenshot("V554_Duct.png")
    duct.advanced.set(True)
    duct.update_visibility()
    set_values(duct, check_path=1, pressure=50)
    check("15_path_rows_enabled", all(duct.rows[key].winfo_manager() for key in ("length", "k_sum", "equipment")))
    check("16_insufficient_pressure_flagged", "不足" in duct.status.cget("text") and "預算不足" in duct.details.cget("text"))
    screenshot("V554_Duct_Advanced.png")
    set_values(duct, length="", check_path=0)
    check("17_inactive_path_draft_ignored", duct.result is not None)
    set_values(duct, check_path=1)
    check("18_reactivated_path_error", duct.result is None and "直管長度" in duct.status.cget("text"))

    app.nav["electrical"].invoke()
    check("19_invalid_draft_preserved", power.variables["power"].get() == "not a number")
    power.reset()
    set_values(power, pf=0)
    check("20_advanced_error_revealed", power.advanced.get() and power.rows["pf"].winfo_manager() and "功率因數" in power.status.cget("text"))
    power.reset()
    set_values(power, supply="單相 220V", power=5)
    check("21_single_phase_current", math.isclose(power.result["current_a"], 5000/220/.85))

    app.nav["gas"].invoke()
    root.update()
    gas = app.active_page()
    check("22_gas_four_visible_fields", sum(bool(row.winfo_manager()) for row in gas.rows.values()) == 4)
    check("23_flow_is_required", "所需標準流量" == gas.labels["flow"].cget("text"))
    before = gas.result["actual_lpm"]
    set_values(gas, pressure_unit="kgf/cm²(g)", flow_unit="SCFM")
    check("24_gas_unit_equivalence", math.isclose(gas.result["actual_lpm"], before, rel_tol=1e-12))
    set_values(gas, gas="N2")
    check("25_gas_reference_velocity", float(gas.variables["velocity"].get()) == 12)
    set_values(gas, velocity=7, gas="Ar")
    check("26_custom_velocity_retained", float(gas.variables["velocity"].get()) == 7)
    gas.reset()
    set_values(gas, flow="bad", flow_unit="SCFM")
    check("27_invalid_unit_switch_rolls_back", gas.variables["flow_unit"].get() == "SLPM" and gas.variables["flow"].get() == "bad" and gas.result is None)
    gas.reset()
    root.update()
    screenshot("V554_Gas.png")

    app.nav["lighting"].invoke()
    root.update()
    light = app.active_page()
    check("28_lighting_five_visible_fields", sum(bool(row.winfo_manager()) for row in light.rows.values()) == 5)
    check("29_default_lux", math.isclose(light.result["illuminance_lux"], 640))
    set_values(light, area_mode="面積 坪")
    check("30_ping_switch_equivalence", math.isclose(light.result["area_m2"], 30) and math.isclose(light.result["illuminance_lux"], 640))
    set_values(light, area_mode="體積 m³", area=90, height=3)
    check("31_volume_requires_height", light.rows["height"].winfo_manager() and math.isclose(light.result["area_m2"], 30))
    set_values(light, mode="反算燈數", quantity="unfinished", target=500)
    check("32_reverse_count_interlock", not light.rows["quantity"].winfo_manager() and light.rows["target"].winfo_manager() and light.result["quantity"] == 8)
    light.advanced.set(True)
    light.update_visibility()
    set_values(light, lumen_mode="燈具型錄流明", lumens=2000, efficacy="unfinished")
    check("33_catalog_lumen_interlock", light.rows["lumens"].winfo_manager() and not light.rows["efficacy"].winfo_manager() and light.result["quantity"] == 16)
    light.reset()
    screenshot("V554_Lighting.png")
    check("34_reset_local_only", power.variables["power"].get() == "5" and light.variables["quantity"].get() == "10")
    check("35_copy_current_only", app.copy_result() and "照明照度" in root.clipboard_get() and "每相銅線" not in root.clipboard_get())
    output = Path(directory) / "照明.txt"
    check("36_export_current_formula", app.export_result(output) and "公式" in output.read_text(encoding="utf-8"))

    app.more_choice.set("冷熱水快算")
    app.more.event_generate("<<ComboboxSelected>>")
    root.update()
    water = app.active_page()
    check("37_more_tool_navigation", app.current == "water")
    before = water.result["thermal"]["lpm"]
    set_values(water, flow_unit="US GPM")
    check("38_water_unit_equivalence", math.isclose(water.result["thermal"]["lpm"], before))
    set_values(water, mode="已知熱量", flow="unfinished")
    check("39_water_known_load_interlock", water.result is not None and not water.rows["flow"].winfo_manager() and water.rows["power"].winfo_manager())
    water.reset()
    screenshot("V554_Water.png")
    app.show_tool("air")
    air = app.active_page()
    set_values(air, rh=101)
    check("40_air_error_locator", "相對濕度" in air.status.cget("text") and air.widgets["rh"].cget("style") == "Simple.Invalid.TEntry")
    set_values(air, rh=50, atmosphere=59)
    check("41_air_advanced_locator", air.advanced.get() and "大氣壓" in air.status.cget("text"))
    air.reset()
    screenshot("V554_Air.png")
    app.show_tool("units")
    units = app.active_page()
    set_values(units, category="溫度", unit="°F", value=32)
    check("42_unit_options_linked", "°F" in units.widgets["unit"].cget("values") and math.isclose(units.result["values"]["°C"], 0))
    screenshot("V554_Units.png")

    app.show_tool("electrical")
    power.reset()
    root.geometry("780x560+20+20")
    root.update()
    check("43_compact_actions_visible", all(widget.winfo_rootx()+widget.winfo_width() <= root.winfo_rootx()+root.winfo_width() and widget.winfo_rooty()+widget.winfo_height() <= root.winfo_rooty()+root.winfo_height() for widget in (app.calc_button, app.copy_button, app.export_button)))
    check("44_compact_labels_stack", power.widgets["power"].grid_info()["row"] == 1)
    check("45_compact_cards_stack", power.card_boxes[2].grid_info()["row"] == 2)
    check("46_compact_no_horizontal_cutoff", power.body.winfo_width() <= power.canvas.winfo_width()+2)
    check("46b_hide_unneeded_horizontal_scroll", not power.horizontal.winfo_manager())
    screenshot("V554_Compact.png")
    power.canvas.event_generate("<MouseWheel>", delta=-120)
    root.update()
    check("46c_mousewheel_scrolls_form", power.canvas.yview()[0] > 0)
    root.geometry("1120x830+20+20")
    root.update()
    check("47_full_width_restores_columns", power.card_boxes[2].grid_info()["column"] == 2 and power.widgets["power"].grid_info()["row"] == 0)

    set_values(power, power=12)
    full = app.open_workbench()
    root.update()
    check("48_full_workbench_retained", full.result is not None and full.root.winfo_exists())
    check("49_workbench_single_instance", app.open_workbench() is full)
    full.variables["light_lux"].set("650")
    full.recalculate()
    check("50_no_implicit_data_transfer", power.variables["power"].get() == "12" and power.result is not None)
    power.canvas.yview_moveto(0)
    power.advanced.set(True)
    power.update_visibility()
    root.update()
    power.canvas.event_generate("<MouseWheel>", delta=-120)
    root.update()
    check("50b_wheel_survives_workbench", power.canvas.yview()[0] > 0)
    answer = None
    app.close()
    check("51_unsaved_workbench_cancel_keeps_app", root.winfo_exists() and full.root.winfo_exists())
    answer = False
    app.close()
    check("52_no_callback_errors", not errors)

(ROOT / "evidence/Simple_GUI_Checks.json").write_text(
    json.dumps({"version": "5.5.4", "checks": checks}, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"{len(checks)} real Tk simple-tool interaction checks passed")
