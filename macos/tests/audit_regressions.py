"""Verify F01–F06 formulas and real Windows UI paths; --gui needs a display."""
import argparse
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from facility_studio.audit_acceptance import run_checks, run_ui


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gui', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    checks = run_checks()
    formula_count = len(checks)
    if args.gui:
        with tempfile.TemporaryDirectory(prefix='facility-audit-regression-') as temp:
            os.environ['FACILITY_STUDIO_PREFERENCES'] = str(Path(temp) / 'prefs.json')
            os.environ['LOCALAPPDATA'] = str(Path(temp) / 'user-data')
            from facility_studio.localized_tk import tk
            from facility_studio.simple_desktop import SimpleToolsApp
            root = tk.Tk()
            errors = []
            root.report_callback_exception = lambda *exc: errors.append(''.join(traceback.format_exception(*exc)))
            app = SimpleToolsApp(root)

            def check(name, action):
                assert action() is not False, name
                checks.append(dict(name=name, passed=True))

            try:
                workbench = app.open_workbench()
                workbench.root.report_callback_exception = root.report_callback_exception
                run_ui(root, app, workbench, check, root.update, args.output)
                check('F01–F06 no unhandled GUI callback errors', lambda: not errors)
            finally:
                root.destroy()
    result = dict(passed=True, platform=platform.platform(), checks=len(checks),
                  formula_checks=formula_count, gui_checks=len(checks)-formula_count, assertions=checks)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'assertions'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
