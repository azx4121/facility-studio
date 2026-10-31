"""Run F07 formula and real-widget checks; --gui requires a display."""
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from facility_studio.lighting_acceptance import run_checks, run_ui


def main():
    checks = run_checks()
    if '--gui' in sys.argv:
        with tempfile.TemporaryDirectory(prefix='facility-lighting-') as temp:
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
                run_ui(root, app, check, root.update)
                check('F07 no unhandled GUI callback errors', lambda: not errors)
            finally:
                root.destroy()
    print(json.dumps(dict(passed=True, checks=len(checks), formula_checks=2500, gui='--gui' in sys.argv)))


if __name__ == '__main__':
    main()
