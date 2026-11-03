import argparse
import json
import sys
from .json_io import read_json_file
from .engine import calculate, read_project
from .reports import report
from .schema import default_project
from .utils import atomic_text


def _configure_redirected_streams():
    """CLI pipes/files are strict UTF-8; leave interactive terminals unchanged."""
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and not stream.isatty() and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="strict")


def main():
    _configure_redirected_streams()
    parser = argparse.ArgumentParser(description="Redirected stdout and stderr use UTF-8.")
    parser.add_argument(
        "--language",
        choices=("zh-Hant", "en"),
        help="UI / text-report language; stored engineering data stays canonical",
    )
    parser.add_argument("--project")
    parser.add_argument("--dossier-check", help="核對已存設計審查 JSON；0=文件齊備，3=待處理，2=格式錯誤")
    parser.add_argument("--capacity-plan", help="核對容量與擴建計畫 JSON；0=初篩正常與N−1容量足夠，3=待資料或不足，2=格式錯誤")
    parser.add_argument("--capacity-workspace", help="核對來源快照的目前整案 JSON；未提供則綁定計畫保持待覆核")
    parser.add_argument("--report")
    parser.add_argument("--result")
    parser.add_argument("--write-default")
    parser.add_argument(
        "--full", action="store_true", help="Open the complete engineering workbench"
    )
    from .simple_schema import TOOLS
    parser.add_argument("--tool", choices=tuple(TOOLS))
    parser.add_argument("--tool-input", help="JSON inputs for one independent tool")
    parser.add_argument(
        "--gui-smoke",
        action="store_true",
        help="Check the actual simple-tool GUI without keeping it open",
    )
    parser.add_argument(
        "--equipment", help="Analyze a public Excel/CSV equipment schedule"
    )
    parser.add_argument(
        "--equipment-system",
        default="電力",
        help="System for a CSV schedule (Electrical / 電力, PCW, CDA, N2, EXHAUST, DI, PV)",
    )
    parser.add_argument(
        "--export-equipment-template", help="Write the public equipment Excel template"
    )
    args = parser.parse_args()
    from . import i18n

    if args.language:
        i18n.set_language(args.language, persist=False)
    if args.capacity_plan:
        from .capacity_planning import read_plan, evaluate_plan, capacity_report
        from .design_workflow import capacity_source_binding
        from .workspace_store import read_workspace
        try:
            binding = capacity_source_binding(read_workspace(args.capacity_workspace)) if args.capacity_workspace else None
            state = evaluate_plan(read_plan(args.capacity_plan), current_binding=binding)
            if args.report:
                atomic_text(args.report, capacity_report(state))
            else:
                print(capacity_report(state))
            if args.result:
                atomic_text(args.result, json.dumps(state, ensure_ascii=False, indent=2, allow_nan=False))
            groups = [g for a in state["alternatives"] for g in a["groups"]]
            ready = bool(groups) and all(a["groups"] and not a["issues"] for a in state["alternatives"])
            ready = ready and all(g["normal_status"] == g["n_minus_one_status"] == "初篩容量足夠" for g in groups)
            return 0 if ready else 3
        except (OSError, ValueError, TypeError, KeyError) as error:
            print(str(error), file=sys.stderr)
            return 2
    if args.dossier_check:
        from pathlib import Path
        from .design_basis import load_revision, evaluate
        try:
            state = evaluate(load_revision(args.dossier_check), Path(args.dossier_check).parent)
            print(json.dumps(state, ensure_ascii=False, indent=2, allow_nan=False))
            return 0 if state["can_submit"] else 3
        except (OSError, ValueError, TypeError) as error:
            print(str(error), file=sys.stderr)
            return 2
    args.equipment_system = i18n.canonical_choice(
        args.equipment_system, ("電力", "PCW", "CDA", "N2", "EXHAUST", "DI", "PV")
    )
    if args.export_equipment_template:
        from .equipment_io import export_template

        export_template(args.export_equipment_template)
        return 0
    if args.equipment:
        from .equipment_io import load_equipment, save_equipment_result
        from .equipment_analysis import analyze_equipment, equipment_report

        try:
            result = analyze_equipment(
                load_equipment(args.equipment, args.equipment_system)
            )
            if args.report:
                atomic_text(args.report, equipment_report(result))
            if args.result:
                save_equipment_result(args.result, result)
            if not args.report:
                print(equipment_report(result))
            return 0
        except Exception as error:
            print(i18n.translate(error), file=sys.stderr)
            return 2
    if args.tool:
        from .simple_engines import calculate_tool
        from .simple_schema import defaults
        from .simple_reports import tool_report

        try:
            inputs = defaults(args.tool)
            if args.tool_input:
                from pathlib import Path

                raw = read_json_file(args.tool_input)
                if not isinstance(raw, dict) or set(raw) - set(inputs):
                    raise ValueError("簡易工具輸入含未知欄位或不是JSON物件")
                inputs.update({key: str(value) for key, value in raw.items()})
            result = calculate_tool(args.tool, inputs)
            if args.report:
                atomic_text(args.report, tool_report(result, inputs))
            if args.result:
                atomic_text(
                    args.result,
                    json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False),
                )
            if not args.report:
                print(tool_report(result, inputs))
            return 0
        except Exception as error:
            print(i18n.translate(error), file=sys.stderr)
            return 2
    if args.write_default:
        atomic_text(
            args.write_default,
            json.dumps(default_project(), ensure_ascii=False, indent=2),
        )
        return 0
    if args.project:
        try:
            source = read_json_file(args.project)
            r = calculate(source if source.get("kind") == "facility_workspace" else read_project(args.project))
            if args.report:
                atomic_text(args.report, report(r))
            if args.result:
                atomic_text(
                    args.result,
                    json.dumps(r, ensure_ascii=False, indent=2, allow_nan=False),
                )
            if not args.report:
                print(report(r))
            return 0
        except Exception as e:
            print(i18n.translate(e), file=sys.stderr)
            return 2
    import tkinter as tk

    from .industrial_theme import enable_high_dpi

    enable_high_dpi()
    root = tk.Tk()
    if args.full:
        from .desktop import DesktopApp

        DesktopApp(root)
    else:
        from .simple_desktop import SimpleToolsApp

        app = SimpleToolsApp(root)
        if args.gui_smoke:
            root.withdraw()
            from .simple_schema import TOOLS
            for tool in TOOLS:
                app.show_tool(tool)
                root.update()
                if app.active_page().result is None:
                    root.destroy()
                    return 2
            equipment = app.open_equipment()
            equipment.win.withdraw()
            root.update()
            from .equipment_io import load_equipment
            from pathlib import Path

            template = Path(__file__).with_name("resources") / "Equipment_Template.xlsx"
            if len(load_equipment(template)["systems"]) != 7:
                app.close()
                return 2
            app.close()
            return 0
    root.mainloop()
    return 0
