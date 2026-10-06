"""Real Tk keypad, lighting, live chart and asynchronous import interactions."""

from pathlib import Path
import csv
import json
import math
import os
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import ImageGrab
from facility_studio.simple_desktop import SimpleToolsApp
from facility_studio.equipment_schema import SCHEMAS, example

checks, errors = [], []
messagebox.showerror = lambda *args, **kwargs: errors.append(str(args))
messagebox.showinfo = lambda *args, **kwargs: None
messagebox.askyesnocancel = lambda *args, **kwargs: False
messagebox.askyesno = lambda *args, **kwargs: True


def check(name, condition):
    checks.append(dict(name=name, passed=bool(condition)))
    assert condition, name


def values(page, **changes):
    for key, value in changes.items():
        page.variables[key].set(str(value))
    page.calculate()
    root.update()


def pump(condition, timeout=5):
    start = time.monotonic()
    while not condition():
        if time.monotonic() - start > timeout:
            raise AssertionError("GUI event timed out")
        root.update()
        time.sleep(0.01)
    root.update()


def screenshot(window, name):
    root.update()
    window.lift()
    time.sleep(0.1)
    box = (
        window.winfo_rootx(),
        window.winfo_rooty(),
        window.winfo_rootx() + window.winfo_width(),
        window.winfo_rooty() + window.winfo_height(),
    )
    ImageGrab.grab(bbox=box).save(ROOT / "evidence" / name)


with tempfile.TemporaryDirectory(prefix="facility554_gui_") as folder:
    folder = Path(folder)
    os.environ["LOCALAPPDATA"] = str(folder)
    root = tk.Tk()
    root.report_callback_exception = lambda *args: errors.append(str(args))
    app = SimpleToolsApp(root)
    root.geometry("1120x830+15+15")
    root.update()
    power = app.active_page()
    entry = power.widgets["power"]
    check(
        "01_keypad_binding_before_class",
        entry.bindtags().index("FacilityNumericInput")
        < entry.bindtags().index("TEntry"),
    )
    entry.focus_force()
    values(power, power=12)
    entry.icursor("end")
    entry.event_generate("<KeyPress>", keysym="KP_Decimal", state=16)
    root.update()
    check("02_numlock_decimal_inserts", entry.get() == "12.")
    entry.event_generate("<KeyPress-5>")
    pump(lambda: power.result is not None)
    check("03_decimal_live_calculation", math.isclose(power.result["power_kw"], 12.5))
    values(power, power=123)
    entry.selection_range(0, "end")
    entry.event_generate("<KeyPress>", keysym="KP_Decimal", state=16)
    root.update()
    check("04_selection_replaced_once", entry.get() == ".")
    check(
        "05_incomplete_decimal_clears_results",
        power.result is None and app.export_button.instate(["disabled"]),
    )
    values(power, power=123)
    entry.selection_clear()
    entry.icursor(1)
    entry.event_generate("<KeyPress-Delete>")
    root.update()
    check("06_regular_delete_unchanged", entry.get() == "13")
    entry.state(["disabled"])
    entry.event_generate("<KeyPress>", keysym="KP_Decimal", state=16)
    root.update()
    check("07_disabled_input_no_change", entry.get() == "13")
    entry.state(["!disabled"])
    values(power, power=2)
    entry.icursor("end")
    entry.event_generate("<KeyPress-period>")
    root.update()
    check("08_main_period_unchanged", entry.get() == "2.")
    child = tk.Toplevel(root)
    extra = ttk.Entry(child)
    extra.pack()
    root.update()
    extra.focus_force()
    extra.insert(0, "3")
    extra.event_generate("<KeyPress>", keysym="KP_Decimal", state=16)
    root.update()
    check("09_new_child_entry_uses_binding", extra.get() == "3.")
    child.destroy()

    app.show_tool("units")
    units = app.active_page()
    values(units, category="溫度差（升溫／降溫）", unit="°C差", value=5)
    check(
        "10_delta_help",
        "12→7" in units.subtitle.cget("text")
        and "不加32" in units.subtitle.cget("text"),
    )
    check("11_delta_correct", units.result["values"]["°F差"] == 9)
    screenshot(root, "V554_Units_Difference.png")
    values(units, category="閥門流量係數（Kv／Cv）", unit="Kv", value=5)
    check(
        "12_valve_help",
        all(v in units.subtitle.cget("text") for v in ("1bar", "1psi", "型錄")),
    )
    check(
        "13_valve_units_updated",
        set(units.widgets["unit"].cget("values")) == {"Kv", "Cv(US)"},
    )
    screenshot(root, "V554_Units_Valve.png")

    app.show_tool("lighting")
    light = app.active_page()
    values(light, area_mode="體積 m³", area=90, height=3)
    check("14_volume_explicit_label", "立方公尺" in light.labels["area"].cget("text"))
    check("15_volume_hint", "這格填m³，不是m²" in light.hints["area"].cget("text"))
    check("16_height_same_room", "同一空間" in light.labels["height"].cget("text"))
    check("17_volume_to_floor_area", light.result["area_m2"] == 30)
    check(
        "18_published_geometry", "90m³ ÷ 淨高3m＝30.000m²" in light.details.cget("text")
    )
    exported = folder / "照明.txt"
    app.export_result(exported)
    check(
        "19_export_geometry", "90m³ ÷ 淨高 3m" in exported.read_text(encoding="utf-8")
    )
    screenshot(root, "V554_Lighting_Volume.png")
    for mode in ("面積 m²", "面積 坪", "長×寬", "體積 m³", "長×寬", "面積 m²"):
        values(light, area_mode=mode)
        check(
            "20_geometry_preserved_" + mode, math.isclose(light.result["area_m2"], 30)
        )
        check(
            "21_height_interlock_" + mode,
            bool(light.rows["height"].winfo_manager()) == (mode == "體積 m³"),
        )
    values(light, area_mode="體積 m³", height=6)
    check("22_changed_height_changes_area", light.result["area_m2"] == 15)
    values(light, area="unfinished")
    values(light, area_mode="面積 m²")
    check(
        "23_invalid_geometry_switch_rollback",
        light.variables["area_mode"].get() == "體積 m³" and light.result is None,
    )

    app.show_tool("air")
    air = app.active_page()
    values(air, temperature=25, rh=50)
    chart = air.air_chart
    check(
        "24_chart_has_point",
        len(chart.find_withtag("state_point")) == 1
        and len(chart.find_withtag("point_guide")) == 2,
    )
    check("25_chart_tied_to_state", chart.state == air.result["state"])
    check("26_curves_count", len(chart.find_withtag("curve")) == 10)
    check(
        "27_chart_point_matches_gkg",
        math.isclose(chart.plot_data["point"][1], air.result["state"]["w"] * 1000),
    )
    screenshot(root, "V554_Air_Live.png")
    point = chart.point_xy
    air.variables["temperature"].set("35")
    air.variables["rh"].set("70")
    check(
        "28_input_clears_old_point",
        not chart.find_withtag("state_point")
        and app.export_button.instate(["disabled"]),
    )
    pump(lambda: air.result is not None)
    check(
        "29_live_update_without_calculate",
        chart.state["t"] == 35 and chart.state["rh"] == 70 and chart.point_xy != point,
    )
    check(
        "30_live_label_matches",
        "35°C / 70%RH" in chart.itemcget(chart.find_withtag("state_label")[0], "text"),
    )
    air.variables["rh"].set("150")
    pump(lambda: air.pending is None)
    check(
        "31_invalid_chart_and_export_cleared",
        air.result is None
        and chart.state is None
        and not chart.find_withtag("state_point"),
    )
    values(air, rh=100, temperature=22, atmosphere=80)
    check(
        "32_saturated_point_valid",
        chart.state["rh"] == 100 and len(chart.find_withtag("state_point")) == 1,
    )
    check(
        "33_pressure_updates_chart_title",
        "P=80"
        in str(
            [
                chart.itemcget(i, "text")
                for i in chart.find_all()
                if chart.type(i) == "text"
            ]
        ),
    )
    values(air, rh=0)
    check(
        "34_dry_air_point_at_axis",
        chart.plot_data["point"][1] == 0 and air.result["state"]["dewpoint_c"] is None,
    )
    air.reset()

    window = app.open_equipment()
    root.update()
    check("35_single_equipment_window", app.open_equipment() is window)
    template = folder / "設備範本.xlsx"
    check(
        "36_export_excel_template",
        window.export_template(template) and template.is_file(),
    )
    csv_folder = folder / "CSV"
    check(
        "37_export_csv_templates",
        window.export_csv(csv_folder) and len(list(csv_folder.glob("*.csv"))) == 7,
    )
    active = folder / "七系統設備.xlsx"
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(template) as source, zipfile.ZipFile(
        active, "w", compression=zipfile.ZIP_DEFLATED
    ) as out:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename.startswith(
                "xl/worksheets/sheet"
            ) and not item.filename.endswith("sheet1.xml"):
                xml = ET.fromstring(data)
                cell = next(c for c in xml.iter(ns + "c") if c.get("r") == "A6")
                cell.set("t", "n")
                for child in list(cell):
                    cell.remove(child)
                ET.SubElement(cell, ns + "v").text = "1"
                data = ET.tostring(xml, encoding="utf-8", xml_declaration=True)
            out.writestr(item.filename, data)
    check("38_start_async_import", window.start_import(active))
    check("39_no_second_concurrent_import", not window.start_import(active))
    check(
        "40_import_disables_old_export",
        window.result is None and window.report_button.instate(["disabled"]),
    )
    pump(lambda: window.future is None)
    check(
        "41_seven_groups_displayed",
        window.result is not None and len(window.tree.get_children()) == 7,
    )
    check(
        "42_report_enabled_on_success",
        window.report_button.instate(["!disabled"])
        and window.json_button.instate(["!disabled"]),
    )
    check(
        "43_analysis_conditions_visible",
        "定寸絕壓" in window.details.get("1.0", "end")
        and "全檔連接電力" in window.details.get("1.0", "end"),
    )
    report = folder / "設備分析.txt"
    detail = folder / "設備分析.json"
    check(
        "44_export_all_report",
        window.export_report(report)
        and all(s in report.read_text(encoding="utf-8") for s in ("CDA", "PCW", "PV")),
    )
    check(
        "45_export_all_json",
        window.export_json(detail)
        and len(json.loads(detail.read_text(encoding="utf-8"))["groups"]) == 7,
    )
    screenshot(window.win, "V554_Equipment_Import.png")
    window.start_import(csv_folder / "電力.csv")
    pump(lambda: window.future is None)
    check(
        "46_bad_import_clears_previous_result",
        window.result is None and not window.tree.get_children(),
    )
    check(
        "47_error_locates_no_enabled_row",
        "沒有啟用" in window.details.get("1.0", "end"),
    )
    check(
        "48_invalid_export_blocked",
        not window.export_report(folder / "invalid_report.txt"),
    )
    check("49_retry_available", window.import_button.instate(["!disabled"]))
    rows = [
        dict(example("電力"), enabled=1, id="THREE", power=10),
        dict(example("電力"), enabled=1, id="SINGLE", power=4, voltage=220, phases="1"),
    ]
    mixed = folder / "電力多電壓.csv"
    with mixed.open("w", encoding="utf-8-sig", newline="") as out:
        writer = csv.writer(out)
        writer.writerow([c["label"] for c in SCHEMAS["電力"]])
        for record in rows:
            writer.writerow([record[c["key"]] for c in SCHEMAS["電力"]])
    window.start_import(mixed)
    pump(lambda: window.future is None)
    check(
        "50_retry_result_two_groups",
        window.result is not None and len(window.tree.get_children()) == 2,
    )
    index = next(i for i, g in enumerate(window.result["groups"]) if g["phases"] == 1)
    window.tree.selection_set(str(index))
    root.update()
    window.show_group()
    check(
        "51_selection_filters_supply_rows",
        "／SINGLE" in window.details.get("1.0", "end")
        and "／THREE" not in window.details.get("1.0", "end"),
    )
    check(
        "52_selection_keeps_global_total_label",
        "全檔連接電力 14.000kW" in window.details.get("1.0", "end"),
    )
    window.win.geometry("830x560+15+15")
    root.update()
    check(
        "53_import_footer_visible",
        window.report_button.winfo_rooty() + window.report_button.winfo_height()
        <= window.win.winfo_rooty() + window.win.winfo_height(),
    )
    check(
        "54_import_detail_scroll",
        window.details.winfo_height() > 65 and window.tree.winfo_height() > 65,
    )
    check(
        "54a_tree_not_clipped_by_pane",
        window.tree.winfo_y() + window.tree.winfo_height()
        <= window.tree.master.winfo_height(),
    )
    screenshot(window.win, "V554_Equipment_Compact.png")
    window.close()
    window2 = app.open_equipment()
    check("55_reopen_after_close", window2 is not window and window2.win.winfo_exists())
    window2.close()
    root.geometry("780x560+15+15")
    root.update()
    app.show_tool("air")
    root.update()
    check(
        "56_compact_chart_accessible",
        chart.winfo_width() >= 460 and air.canvas.cget("scrollregion"),
    )
    check(
        "57_compact_footer_visible",
        app.calc_button.winfo_rooty() + app.calc_button.winfo_height()
        <= root.winfo_rooty() + root.winfo_height(),
    )
    air.canvas.yview_moveto(0.40)
    root.update()
    screenshot(root, "V554_Air_Compact.png")
    check("58_no_callback_errors", not errors)
    app.close()

(ROOT / "evidence/V554_GUI_Checks.json").write_text(
    json.dumps(
        dict(
            version="5.5.4",
            checks=checks,
            errors=errors,
            platform="real Tk/Xvfb",
            windows_hardware_tested=False,
        ),
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
print(
    f"{len(checks)} actual Tk keyboard/chart/lighting/equipment interaction checks passed"
)
