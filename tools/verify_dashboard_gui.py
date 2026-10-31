#!/usr/bin/env python3
"""Tk source smoke checks for either source tree, using a real display.

On a Linux CI host run with xvfb-run. No screenshots, PIL, native executables or
OS DPI settings are used. Results identify the source tree and the actual host;
passing these checks does not certify a Windows EXE or a macOS application.
"""

import argparse
import json
import math
from pathlib import Path
import platform as host_platform
import sys
import tempfile
import traceback
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def _pump(root):
    root.update_idletasks()
    root.update()


def _dispose(root):
    # Cancel Tcl events without deleting callback commands through the wrong
    # widget. Each callback's owning widget deletes its command during destroy.
    try:
        for token in root.tk.splitlist(root.tk.call("after", "info")):
            root.tk.call("after", "cancel", token)
        root.destroy()
    except Exception:
        pass


def _main_checks(check, errors):
    import tkinter as tk
    from facility_studio.desktop import DesktopApp
    from facility_studio.field_state import main_inactive
    from facility_studio.main_view import hidden_system_equipment

    root = tk.Tk()
    root.report_callback_exception = lambda kind, value, tb: errors.append(str(value))
    try:
        app = DesktopApp(root)
        _pump(root)

        def apply(system, view, **updates):
            app.suspended = True
            try:
                app.variables["sys_type"].set(system)
                app.view_mode.set(view)
                for key, value in updates.items():
                    app.variables[key].set(value)
                app.interlocks()
                app.update_visibility()
            finally:
                app.suspended = False
            _pump(root)

        def visible(key):
            return app.form_rows[key].winfo_manager() == "grid"

        def disabled(key):
            return str(app.widgets[key].cget("state")) == "disabled"

        systems = {"MAU": "MAU+FFU+DCC (全外氣/無塵室)", "FCU": "FCU (風機盤管+外氣)",
                   "RCU": "RCU (機房空調箱+外氣)", "AHU": "AHU (OA+RA 混合)"}
        drafts = {"en_fcu_cmh": "1234.5", "fcu_rt": "12.3", "en_rcu_rt": "17.7",
                  "upw_res": "17.123", "dcc_airflow_cmh": "4567.8"}
        app.suspended = True
        for key, value in drafts.items():
            app.variables[key].set(value)
        app.suspended = False
        for view in ("基本模式", "進階模式"):
            for architecture, system in systems.items():
                apply(system, view)
                excluded = hidden_system_equipment(system)
                for key in ("en_fcu_cmh", "fcu_rt", "en_rcu_rt"):
                    expected = architecture == ("RCU" if key == "en_rcu_rt" else "FCU")
                    prefix = view + "/" + architecture + "/" + key
                    check(prefix + " grid visibility", visible(key) == expected)
                    check(prefix + " architecture helper", (key not in excluded) == expected)
                    check(prefix + " active input state", disabled(key) != expected)
                if architecture != "MAU":
                    for key in ("ffu_topology", "ffu_airflow_basis", "ffu_size", "dcc_airflow_mode"):
                        check(view + "/" + architecture + "/" + key + " hidden", not visible(key))
                check(view + "/" + architecture + " retains drafts", all(app.variables[key].get() == value for key, value in drafts.items()))
        apply(systems["MAU"], "進階模式", upw_quality_mode="自動參考值",
              ffu_topology="獨立FFU循環（MAU直接入室）", dcc_airflow_mode="沿用 FFU 循環")
        for key in ("upw_res", "dcc_airflow_cmh", "ffu_airflow_basis"):
            check("advanced inactive draft visible " + key, visible(key))
            check("advanced inactive draft disabled " + key, disabled(key))
            check("inactive rules match " + key, key in main_inactive(app.snapshot()["inputs"]))
        for view in ("基本模式", "進階模式"):
            apply(systems["MAU"], view, ffu_topology="獨立FFU循環（MAU直接入室）")
            check(view + " independent topology selectable", visible("ffu_topology") and not disabled("ffu_topology"))
            check(view + " independent basis disabled", disabled("ffu_airflow_basis"))
            for basis in ("FFU總送風（已含OA）", "室內基本循環（另加OA）"):
                apply(systems["MAU"], view, ffu_topology="MAU入靜壓箱經FFU送風", ffu_airflow_basis=basis)
                check(view + "/" + basis + " selectable", visible("ffu_airflow_basis") and not disabled("ffu_airflow_basis"))
                check(view + "/" + basis + " retained", app.variables["ffu_airflow_basis"].get() == basis)
            apply(systems["MAU"], view, dcc_airflow_mode="獨立 DCC 循環")
            check(view + " independent DCC flow enabled", visible("dcc_airflow_cmh") and not disabled("dcc_airflow_cmh"))
        check("architecture switches preserve every numeric draft", all(app.variables[key].get() == value for key, value in drafts.items()))
        from facility_studio import i18n
        for language in ("zh-Hant", "en"):
            i18n.set_language(language, persist=False)
            root.geometry("880x560+0+0")
            _pump(root)
            left, top = root.winfo_rootx(), root.winfo_rooty()
            right, bottom = left + root.winfo_width(), top + root.winfo_height()
            for index, toolbar in enumerate(app.action_toolbars):
                for control in toolbar.winfo_children():
                    check(language + "/toolbar" + str(index) + "/" + str(control) + " fits minimum client",
                          control.winfo_ismapped() and left <= control.winfo_rootx()
                          and control.winfo_rootx() + control.winfo_width() <= right
                          and top <= control.winfo_rooty()
                          and control.winfo_rooty() + control.winfo_height() <= bottom)
        i18n.set_language("zh-Hant", persist=False)
        check("main callbacks complete without errors", not errors)
        return str(root.tk.call("info", "patchlevel"))
    finally:
        _dispose(root)


def _simple_checks(check, errors, directory):
    import tkinter as tk
    from facility_studio.simple_desktop import SimpleToolsApp
    from facility_studio.simple_schema import TOOLS
    from facility_studio.industrial_theme import Theme

    root = tk.Tk()
    root.report_callback_exception = lambda kind, value, tb: errors.append(str(value))
    try:
        app = SimpleToolsApp(root)
        _pump(root)
        for tool in TOOLS:
            app.show_tool(tool)
            _pump(root)
            page = app.active_page()
            check(tool + " computes valid defaults", page.result is not None)
            check(tool + " has KPI cards", len(page.result_box.cards) >= 3)
            check(tool + " has structured result rows", len(page.result_table.tree.get_children()) > 0)
            for key, widget in page.widgets.items():
                if widget.winfo_ismapped() and widget.winfo_manager() == "grid":
                    check(tool + "/" + key + " fits its row", widget.winfo_x() >= 0 and widget.winfo_x() + widget.winfo_width() <= widget.master.winfo_width() + 2)
        # Measure rendered style colors for both idle and hovered navigation.
        # The selected button uses a separate style and must remain legible too.
        from tkinter import ttk
        style = ttk.Style(root)

        def luminance(color):
            rgb = [value / 65535 for value in root.winfo_rgb(color)]
            linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4
                      for v in rgb]
            return sum(v * weight for v, weight in zip(linear, (.2126, .7152, .0722)))

        for tool, button in app.nav.items():
            for state in ((), ("active",)):
                name = button.cget("style")
                light, dark = sorted((luminance(style.lookup(name, color, state=state))
                                      for color in ("foreground", "background")), reverse=True)
                check(tool + "/" + ("hover" if state else "idle") + " navigation contrast",
                      (light + .05) / (dark + .05) >= 4.5)
        app.show_tool("cleanroom")
        room = app.active_page()
        # Heat loads refuse to adopt a lighting result for a different floor area than the cleanroom (win.9 and the
        # macOS port); put both tools on the same area, as a user adopting both for one room would.
        app.show_tool("lighting")
        lighting = app.active_page()
        lighting.variables["area_mode"].set("面積 m²")
        lighting.variables["area"].set(room.variables["area"].get())
        lighting.calculate(True)
        _pump(root)
        app.show_tool("cleanroom")
        app.show_tool("heat_loads")
        heat = app.active_page()
        check("cleanroom transfers into heat", heat.import_upstream())
        check("FFU count transfer", int(heat.variables["ffu_count"].get()) == room.result["ffu_count"])
        app.show_tool("water")
        water = app.active_page()
        check("heat transfers into water", water.import_upstream())
        check("thermal kW become LPM through water heat balance", math.isclose(water.result["thermal"]["lpm"], 60000 * heat.result["q_total_kw"] / (1000 * 4.1868 * float(water.variables["delta"].get()))))
        app.show_tool("pumps")
        pump = app.active_page()
        check("water transfers into pump", pump.import_upstream())
        check("pump receives actual water flow", math.isclose(pump.result["flow_lpm"], water.result["pipe"]["lpm"]))
        app.show_tool("electrical")
        electrical = app.active_page()
        check("listed devices transfer into electrical", electrical.import_upstream())
        room.variables["ach"].set("80")
        _pump(root)
        for name, page in (("heat", heat), ("water", water), ("pump", pump), ("electrical", electrical)):
            check(name + " becomes stale after upstream edit", page.result is None and page.upstream_stale)
        heat.calculate()
        check("stale upstream result cannot be calculated as current", heat.result is None)
        room.calculate()
        check("edited upstream result recovers", room.result is not None)
        for tool in ("heat_loads", "water", "pumps", "electrical"):
            app.show_tool(tool)
            check(tool + " can explicitly reimport", app.active_page().import_upstream())
        app.show_tool("cleanroom")
        room.variables["area"].set("bad")
        room.calculate(True)
        _pump(root)
        check("invalid input receives inline style", room.result is None and room.widgets["area"].cget("style") == "Simple.Invalid.TEntry")
        check("invalid result export is blocked", app.export_result(directory / "invalid.txt") is False)
        room.variables["area"].set("200")
        root.focus_force()
        room.widgets["area"].focus_set()
        _pump(root)
        room.widgets["area"].event_generate("<Return>", when="tail")
        _pump(root)
        check("Return key calculates a repaired input", room.result is not None)
        # The adopted lighting result must describe the same 200 m2 room before heat loads accept both.
        app.show_tool("lighting")
        lighting.variables["area"].set("200")
        lighting.calculate(True)
        _pump(root)
        for tool in ("heat_loads", "water", "pumps", "electrical"):
            app.show_tool(tool)
            check(tool + " reimports repaired inputs", app.active_page().import_upstream())
        check("valid current tool exports HTML", app.export_result(directory / "electrical.html"))
        check("current pipeline exports an executive overview", app.export_summary(directory / "overview.html"))
        check("overview contains seven equipment rows", (directory / "overview.html").read_text(encoding="utf-8").count('scope="row"') == 7)
        app.show_tool("cleanroom")
        root.geometry("1440x880")
        _pump(root)
        check("wide form uses two panels", not room._stacked)
        check("form labels and inputs occupy aligned columns", all(room.labels[key].grid_info()["column"] == 0 and room.widgets[key].grid_info()["column"] == 1 for key in room.rows))
        root.geometry("900x650")
        _pump(root)
        # Both platforms stack the panels below 680 scaled pixels of page width and the minimum window keeps two
        # panels visible, so check that the layout follows that rule.
        check("narrow form follows the stacking threshold", room._stacked == (room.winfo_width() < Theme.px(680)))
        app.show_tool("electrical")
        electrical = app.active_page()
        electrical.advanced.set(True)
        electrical.update_visibility()
        _pump(root)
        electrical.canvas.yview_moveto(1)
        _pump(root)
        electrical.reset()
        _pump(root)
        entry = electrical.widgets["power"]
        electrical.reveal(entry)
        entry.focus_force()
        _pump(root)
        check("reset restores a current manual result", electrical.result is not None and not electrical.upstream_sources and not electrical.upstream_stale)
        check("reset and reveal restore the power entry to the viewport",
              entry.winfo_ismapped() and root.focus_get() is entry
              and electrical.canvas.winfo_rooty() <= entry.winfo_rooty()
              and entry.winfo_rooty() + entry.winfo_height() <= electrical.canvas.winfo_rooty() + electrical.canvas.winfo_height())
        baseline = float(root.tk.call("tk", "scaling"))
        for factor in (1.25, 1.5):
            root.tk.call("tk", "scaling", 96 / 72 * factor)
            Theme.apply(root)
            root.geometry(f"{round(1100 * factor)}x{round(700 * factor)}")
            _pump(root)
            check("Tk scaling " + str(factor) + " completes without callback errors", not errors)
        root.tk.call("tk", "scaling", baseline)
        check("simple-tool callbacks complete without errors", not errors)
    finally:
        _dispose(root)


def _ahu_checks(check, errors):
    import tkinter as tk
    from facility_studio.ahu_desktop import AHUWindow
    from facility_studio.ahu_schema import NM_DEFAULTS

    root = tk.Tk()
    root.withdraw()
    root.report_callback_exception = lambda kind, value, tb: errors.append(str(value))
    window = None
    try:
        window = AHUWindow(root)
        _pump(root)
        check("MAU default calculation is available", window.result is not None)
        check("MAU has six KPI cards", len(window.kpis.cards) == 6)
        check("MAU details use structured rows", len(window.table.get_children()) > 6)
        window.nb.select(1)
        _pump(root)
        window.scada.redraw()
        _pump(root)
        check("SCADA contains vector equipment and airflow", len(window.scada.find_all()) >= 70)
        texts = [window.scada.itemcget(item, "text") for item in window.scada.find_all() if window.scada.type(item) == "text"]
        check("single MAU leaves room and return states unspecified", sum("未提供" in text for text in texts) == 2)
        colors = {window.scada.itemcget(item, "fill").upper() for item in window.scada.find_all()}
        check("SCADA uses the five engineering airflow / coil colors", {"#10B981", "#06B6D4", "#F97316", "#3B82F6", "#F59E0B"} <= colors)
        window.win.geometry("980x720")
        _pump(root)
        window.scada.redraw()
        check("SCADA rescales for a narrower view", 0 < window.scada._scale < 1)
        window.vars["flow"].set("")
        window.calculate()
        _pump(root)
        check("invalid MAU flow is identified inline", window.result is None and window.bad_key == "flow" and "Invalid" in window.widgets["flow"].cget("style"))
        check("MAU retains the last valid details as a prior result", window.last_good_result is not None and len(window.table.get_children()) > 6)
        window.vars["flow"].set(NM_DEFAULTS["flow"])
        window.calculate_from_keyboard()
        _pump(root)
        check("MAU keyboard calculation repairs the result and schematic", window.result is not None and window.scada.result is window.result)
        check("MAU callbacks complete without errors", not errors)
    finally:
        if window is not None:
            window.close(force=True)
        _dispose(root)


def run_checks(source_platform):
    source_root = ROOT / source_platform
    package_root = source_root / "facility_studio"
    if not package_root.is_dir():
        raise ValueError("Selected source tree is missing: " + str(source_root))
    loaded = sys.modules.get("facility_studio")
    if loaded and Path(loaded.__file__).resolve().parent != package_root.resolve():
        raise RuntimeError("Run each source platform in a fresh Python process")
    sys.path.insert(0, str(source_root))
    from facility_studio import i18n
    i18n.set_language("zh-Hant", persist=False)
    checks, errors = [], []

    def check(name, condition):
        if not condition:
            raise AssertionError(name + (": " + "; ".join(errors) if errors else ""))
        checks.append(dict(name=name, passed=True))

    with tempfile.TemporaryDirectory(prefix="facility_dashboard_gui_") as directory:
        # Redirect the recovery function for these unsaved fixtures. No user
        # workspace, autosave directory or historical package is modified.
        with patch("facility_studio.project_store.app_data", return_value=Path(directory)):
            tk_version = _main_checks(check, errors)
            _simple_checks(check, errors, Path(directory))
            _ahu_checks(check, errors)
    return {"kind": "source-tk-dashboard-smoke", "source_platform": source_platform,
            "host_os": host_platform.system(), "python": host_platform.python_version(),
            "tk_patchlevel": tk_version, "native_binary_acceptance": False,
            "passed": True, "check_count": len(checks), "checks": checks}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("windows", "macos"), required=True)
    parser.add_argument("--output", type=Path, help="Optional JSON evidence path")
    args = parser.parse_args(argv)
    try:
        result = run_checks(args.platform)
    except Exception as error:
        result = {"kind": "source-tk-dashboard-smoke", "source_platform": args.platform,
                  "host_os": host_platform.system(), "python": host_platform.python_version(),
                  "native_binary_acceptance": False, "passed": False,
                  "error": type(error).__name__ + ": " + str(error)}
        traceback.print_exc()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "checks"}, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
