"""Native UI acceptance for V5.5.6's novice and source-transfer contracts."""

import copy
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from . import i18n
from .schema import VERSION
from .utils import project_hash
from .workspace_store import read_workspace
from .tutorial_help import prepare_tutorial


def run(root, app, main, check, pump, output=None):
    from .ahu_desktop import AHUWindow
    from .equipment_view import EquipmentWindow
    from .equipment_analysis import analyze_equipment
    from .equipment_io import Cell
    from .equipment_schema import SYSTEMS, SCHEMA_ID, example
    from .contributions import ahu_contribution

    original = copy.deepcopy(main.session_snapshot())
    original_path = main.path
    original_saved = main.saved_workspace_hash
    original_hash = main.saved_hash
    original_language = i18n.language()
    original_scope = main.task_scope.get()
    original_geometry = main.root.geometry()
    child = equipment = None

    def capture(window, name):
        if output is None:
            return
        from PIL import ImageGrab
        destination = Path(output)
        if destination.suffix:
            destination = destination.parent
        destination.mkdir(parents=True, exist_ok=True)
        window.lift()
        pump()
        try:
            ImageGrab.grab().save(destination / name)
        except (OSError, RuntimeError) as exc:
            print("V556 screenshot unavailable: " + str(exc), flush=True)
    with tempfile.TemporaryDirectory(prefix="facility-v556-ui-") as directory:
        try:
            i18n.set_language("zh-Hant", persist=False)
            folder = prepare_tutorial(directory)
            main.apply_workspace(read_workspace(folder / "02_Practice_MAU_and_AHU.json"))
            main.root.deiconify()
            width = min(1100, main.root.winfo_screenwidth() - 60)
            height = min(840, main.root.winfo_screenheight() - 80)
            main.root.geometry(f"{width}x{height}+20+20")
            main.task_scope.set("空調與熱負荷")
            main.update_visibility()
            pump()
            check("V556 basic task hides utility navigation but preserves inputs", lambda: not main.nav[3].winfo_manager() and bool(main.nav[8].winfo_manager()) and "gas2_q" in main.snapshot()["inputs"])
            check("V556 climate inputs precede the psychrometric plot", lambda: main.widgets["oa_t"].winfo_rooty() < main.plot.get_tk_widget().winfo_rooty())
            adopted = main.snapshot()["inputs"]["light_u"]
            main.show_page(2)
            pump()
            check("V556 basic adopted references are visible", lambda: bool(main.assumption_labels[2].cget("text")) and main.snapshot()["inputs"]["light_u"] == adopted)
            main.show_page(0)
            main.recalculate()
            from . import __version__
            from .simple_reports import tool_report
            from .html_report import summary_html
            check("V556 diagnostics and model share the product version", lambda: __version__ == VERSION)
            check("V556 quick-tool title uses the product version", lambda: VERSION in root.title())
            check("V556 quick-tool report uses the product version", lambda: VERSION in tool_report(app.pages["electrical"].result, app.pages["electrical"].data()).splitlines()[0])
            check("V556 printable report uses the product version", lambda: "V" + VERSION + "｜" in summary_html(main.result))
            def toolbar_fit():
                pump()
                left = main.root.winfo_rootx()
                right = left + main.root.winfo_width()
                for toolbar in main.action_toolbars:
                    for control in toolbar.winfo_children():
                        if not control.winfo_ismapped() or control.winfo_rootx() < left or control.winfo_rootx() + control.winfo_width() > right:
                            raise AssertionError("Workbench action outside client bounds: " + str(control))
                return True
            for lang in ("zh-Hant", "en"):
                i18n.set_language(lang, persist=False)
                main.root.geometry("880x560+0+0")
                check("V556 wrapped workbench actions at minimum size: " + lang, toolbar_fit)
                main.view_mode.set("進階模式")
                pump()
                credit = next(widget for widget in main.nav[0].master.winfo_children() if hasattr(widget, "cget") and widget.winfo_class() == "Label" and "DESIGNED" in str(widget.cget("text")))
                check("V556 author remains visible in compact workbench: " + lang, lambda: credit.winfo_ismapped() == 1)
                main.view_mode.set("基本模式")
            i18n.set_language("zh-Hant", persist=False)
            main.root.geometry(f"{width}x{height}+20+20")
            main.show_page(0)
            pump()
            capture(main.root, "V556_Workbench_Basic.png")
            last_hash = main.result["hash"]
            main.variables["oa_t"].set("invalid")
            check("V556 stale report retained immediately with exports disabled", lambda: main.result is None and main.last_good_result["hash"] == last_hash and main.export_button.instate(["disabled"]) and "待重算" in main.text.get("1.0", "end"))
            main.recalculate()
            check("V556 invalid input retains only a clearly stale report", lambda: main.result is None and main.last_good_result is not None and "不能匯出" in main.text.get("1.0", "end"))
            main.variables["oa_t"].set("35")
            main.recalculate()
            pump()
            check("V556 corrected inputs restore current result and export", lambda: main.ensure_result() and main.export_button.instate(["!disabled"]))

            gas = app.pages["gas"]
            app.show_tool("gas")
            gas.reset()
            gas.calculate()
            standard = gas.result["standard_lpm"]
            diameter = gas.result["minimum_id_mm"]
            gas.variables["flow_basis"].set("管內實際流量")
            gas.calculate()
            pump()
            check("V556 gas basis switch preserves demand", lambda: gas.variables["flow_unit"].get() == "ALPM" and abs(gas.result["standard_lpm"] - standard) < 1e-8 and abs(gas.result["minimum_id_mm"] - diameter) < 1e-8)
            gas.variables["flow_basis"].set("標準流量")
            gas.calculate()
            check("V556 gas reverse basis switch preserves input", lambda: gas.variables["flow_unit"].get() == "SLPM" and abs(float(gas.variables["flow"].get()) - standard) < 1e-8)
            duct = app.pages["duct"]
            app.show_tool("duct")
            duct.variables["check_path"].set("0")
            duct.variables["pressure"].set("unknown")
            duct.calculate()
            pump()
            check("V556 dimension-only duct mode does not require pressure", lambda: duct.result is not None and not duct.rows["pressure"].winfo_manager())
            duct.variables["check_path"].set("1")
            duct.calculate()
            pump()
            check("V556 pressure-check mode exposes required route data", lambda: duct.result is None and bool(duct.rows["pressure"].winfo_manager()) and bool(duct.rows["length"].winfo_manager()))
            duct.variables["pressure"].set("200")
            duct.calculate()

            document = main.session_snapshot()["ahus"][0]
            child = AHUWindow(main.root, main, document=document)
            pump()
            check("V556 AHU chart is a capacity-checked demand target", lambda: child.result is not None and "缺口" in child.summary.cget("text") and "目標" in child.summary.cget("text"))
            capture(child.win, "V556_AHU_Stages.png")
            child.vars["summer_t"].set("unknown")
            child.calculate()
            check("V556 AHU stale table retained and return disabled", lambda: child.result is None and child.last_good_result is not None and bool(child.table.get_children()) and str(child.return_button.cget("state")) == "disabled" and "待重算" in child.text.get("1.0", "end"))
            child.vars["summer_t"].set("35")
            child.calculate()
            entry = ahu_contribution(child.result, child.ahu_id, main.snapshot()["inputs"])
            with patch("facility_studio.session_controller.messagebox.askyesnocancel", return_value=False), patch("facility_studio.workspace_view.messagebox.askokcancel", return_value=True):
                check("V556 first actual AHU contribution is previewed and applied", lambda: main.apply_contribution(entry))
                first = float(main.variables["e_np_heat"].get())
                check("V556 repeated actual AHU return is idempotent", lambda: main.apply_contribution(entry) and abs(float(main.variables["e_np_heat"].get()) - first) < 1e-8)
                second = copy.deepcopy(entry)
                second.update(id="ui-second-unit", name="Second unit")
                check("V556 another actual AHU adds only its demand", lambda: main.apply_contribution(second) and abs(float(main.variables["e_np_heat"].get()) - 2 * first) < 1e-8)
            target_path = Path(directory) / "editable-workspace.json"
            check("V556 editable workspace saves ledger and AHUs", lambda: main.save_workspace(target_path) and len(read_workspace(target_path)["demand_ledger"]["entries"]) == 2)
            before_bytes = target_path.read_bytes()
            old_id = main.project_id
            with patch("facility_studio.session_controller.filedialog.asksaveasfilename", return_value=str(Path(directory) / "new-scheme.json")):
                check("V556 duplicate creates a new project identity", lambda: main.duplicate_workspace() and main.project_id != old_id and target_path.read_bytes() == before_bytes)
            # Duplicating correctly closed the project-bound AHU window.
            child = None
            check("V556 duplicate retains both demand sources", lambda: len(main.demand_ledger["entries"]) == 2)
            with patch("facility_studio.session_controller.filedialog.asksaveasfilename", return_value=""):
                check("V556 Save-as cancellation preserves active path", lambda: not main.save_workspace_as() and str(main.path).endswith("new-scheme.json"))

            row = dict(example("電力"), enabled=1, power=10, quantity=1, usage=Cell(.5, number_format="0%", numeric=True), pf=1)
            imported = dict(schema_id=SCHEMA_ID, source_name="percentage.xlsx", systems=SYSTEMS, records=[dict(system="電力", row=6, cells={k: v if isinstance(v, Cell) else Cell(v) for k, v in row.items()})])
            equipment = EquipmentWindow(main.root, main_app=main)
            equipment.display_result(analyze_equipment(imported))
            equipment.tree.selection_set("0")
            equipment.show_group()
            pump()
            check("V556 equipment shows normalized percentage and enables explicit transfer", lambda: "50.0%" in equipment.details.get("1.0", "end") and equipment.transfer_button.instate(["!disabled"]))
            capture(equipment.win, "V556_Equipment_Transfer.png")
            with patch("facility_studio.session_controller.messagebox.askyesnocancel", return_value=False), patch("facility_studio.workspace_view.messagebox.askokcancel", return_value=True):
                equipment.transfer_group()
            check("V556 equipment transfer changes only selected supply group", lambda: abs(float(main.variables["e_up_eq"].get()) - 5) < 1e-8 and len(main.demand_ledger["entries"]) == 3)
            source_count = len(main.demand_ledger["entries"])
            with patch("facility_studio.workspace_view.messagebox.askokcancel", return_value=False):
                equipment.transfer_group()
            check("V556 transfer cancellation retains demand ledger", lambda: len(main.demand_ledger["entries"]) == source_count)
            i18n.set_language("en", persist=False)
            pump()
            check("V556 new transfer controls switch to English", lambda: "Preview" in equipment.transfer_button.cget("text") and "source" not in str(main.variables["project_name"].get()).lower())
            i18n.set_language("zh-Hant", persist=False)
            app.show_tool("air")
            air = app.pages["air"]
            air.calculate()
            old_point = air.air_chart.plot_data["point"]
            air.variables["temperature"].set("invalid")
            air.calculate()
            check("V556 invalid air input retains an explicitly stale point", lambda: air.result is None and air.air_chart.stale and air.air_chart.plot_data["point"] == old_point and bool(air.air_chart.find_withtag("stale_label")))
            air.reset()
            with patch("facility_studio.tutorial_help.webbrowser.open", return_value=True) as launch:
                app.tutorial_button.invoke()
            check("V556 beginner help follows selected quick tool", lambda: launch.call_args.args[0].endswith("#air"))
        finally:
            if equipment and equipment.win.winfo_exists():
                equipment.close(force=True)
            if child and child.win.winfo_exists():
                child.close(force=True)
            main.apply_workspace(original, original_path)
            main.saved_workspace_hash = original_saved
            main.saved_hash = original_hash
            main.task_scope.set(original_scope)
            main.root.geometry(original_geometry)
            main.show_page(0)
            i18n.set_language(original_language, persist=False)
            pump()
