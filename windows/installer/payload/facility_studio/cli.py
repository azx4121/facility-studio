import argparse
import json
import sys
from .json_io import read_json_file
from .engine import calculate, read_project
from .reports import report
from .schema import default_project
from .utils import atomic_text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--language",
        choices=("zh-Hant", "en"),
        help="UI / text-report language; stored engineering data stays canonical",
    )
    parser.add_argument("--project")
    parser.add_argument("--report")
    parser.add_argument("--result")
    parser.add_argument("--write-default")
    parser.add_argument(
        "--full", action="store_true", help="Open the complete engineering workbench"
    )
    parser.add_argument(
        "--tool",
        choices=("electrical", "duct", "gas", "lighting", "water", "air", "units"),
    )
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
            r = calculate(read_project(args.project))
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

    root = tk.Tk()
    if args.full:
        from .desktop import DesktopApp

        DesktopApp(root)
    else:
        from .simple_desktop import SimpleToolsApp

        app = SimpleToolsApp(root)
        if args.gui_smoke:
            root.withdraw()
            for tool in (
                "electrical",
                "duct",
                "gas",
                "lighting",
                "water",
                "air",
                "units",
            ):
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
