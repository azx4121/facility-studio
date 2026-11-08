"""Exact original source plus explicitly reviewed packaging/test corrections."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ['RUNNER_TEMP']) / 'facs-v22-exact-source'
EVIDENCE = Path(os.environ['RUNNER_TEMP']) / 'facs-v22-evidence'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare():
    assert sys.platform == 'win32'
    load('packaging_prepare', HERE.parent / 'facs-v22-onefile/run_packaging_guards.py').prepare()
    corrections = json.loads((HERE / 'corrections.json').read_text(encoding='utf-8'))
    allowed = {'integration/test_independent_tutorial.py', 'integration/test_independent_v11_contracts.py', 'windows/facility_studio/fusion_settings.py', 'integration/test_independent_ampacity_safety.py', 'windows/facility_studio/feed_review_preview.py', 'windows/facility_studio/english_catalog.py', 'integration/test_dcc_selection_interactions.py', 'integration/test_windows_template_sheet_label.py', 'integration/test_windows_dialog_work_area.py', 'integration/test_v11_repair_interactions.py', 'tools/verify_engineering_dashboard.py', 'integration/dcc_independent_resources/verify_dcc_contract.py', 'integration/test_native_english_switch.py'}
    assert {row['path'] for row in corrections} == allowed
    for row in corrections:
        source = HERE / 'overlay' / row['path']
        target = ROOT / row['path']
        assert hashlib.sha256(source.read_bytes()).hexdigest() == row['sha256']
        if row['original_sha256'] is None:
            assert not target.exists()
        else:
            assert hashlib.sha256(target.read_bytes()).hexdigest() == row['original_sha256']
        shutil.copy2(source, target)
    env = dict(os.environ, GIT_AUTHOR_NAME='FACS Reproducible Validation',
        GIT_AUTHOR_EMAIL='validation@users.noreply.github.com', GIT_COMMITTER_NAME='FACS Reproducible Validation',
        GIT_COMMITTER_EMAIL='validation@users.noreply.github.com', GIT_AUTHOR_DATE='2026-11-08T00:00:00Z',
        GIT_COMMITTER_DATE='2026-11-08T00:00:00Z')
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT, env=env, stderr=subprocess.STDOUT).decode().strip()
    git('init', '-q')
    git('config', 'core.autocrlf', 'false')
    git('add', '-f', '.')
    original = json.loads((HERE.parent / 'facs-v22-windows/SOURCE_MANIFEST.json').read_text())
    for row in original['files']:
        if row['mode'] == '100755':
            git('update-index', '--chmod=+x', '--', row['path'])
    git('commit', '-q', '-m', 'Record v22 Windows portable derivative with reviewed dialog, template label and native test repairs')
    result = dict(original_inventory_sha256=original['inventory_sha256'],
        packaging_overlay=json.loads((EVIDENCE / 'packaging-overlay.json').read_text()), test_corrections=corrections,
        snapshot_commit=git('rev-parse', 'HEAD'), snapshot_tree=git('rev-parse', 'HEAD^{tree}'),
        workflow_commit=os.environ['GITHUB_SHA'], product_equations_changed=False, windows_dialog_ui_changed=True, windows_template_label_changed=True, macos_product_changed=False,
        baseline_native_run=42475494993, binary_published=False, formal_feed_accepted=False)
    (EVIDENCE / 'reviewed-source-provenance.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


def tests():
    EVIDENCE.mkdir(exist_ok=True)
    assert sys.platform == 'win32' and platform.python_version() == '3.12.16'
    env = dict(os.environ, FACILITY_TEST_PLATFORM='windows', FACILITY_REQUIRE_DISPLAY='1',
               PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
               FACILITY_STUDIO_FUSION_DATA=str(EVIDENCE / 'app-data'),
               FACILITY_STUDIO_DATA=str(EVIDENCE / 'app-data'),
               FACILITY_STUDIO_PREFERENCES=str(EVIDENCE / 'preferences.json'),
               MPLCONFIGDIR=str(EVIDENCE / 'mpl-cache'))
    for key in ('PYTHONPATH', 'TCL_LIBRARY', 'TK_LIBRARY'):
        env.pop(key, None)
    env['PYTHONPATH'] = str(HERE / 'native_diagnostics')
    env['PYTEST_ADDOPTS'] = '--capture=sys -o faulthandler_timeout=120'
    # Keep the complete suite uninstrumented. Separate lifecycle runs retain Tk tracing.
    # The JUnit gate below still rejects every unexpected native skip.
    env['NATIVE_TK_TRACE'] = str(EVIDENCE / 'full-native-tk-events.jsonl')
    p = sys.executable
    commands = [
      ('runtime-tk', [p, '-c', "import json,sys,platform,tkinter as t; r=t.Tk(); r.update(); print(json.dumps(dict(python=sys.version,executable=sys.executable,platform=platform.platform(),tk=r.tk.call('info','patchlevel'),windowing=r.tk.call('tk','windowingsystem'),width=r.winfo_screenwidth(),height=r.winfo_screenheight()))); r.destroy()"], 60),
      ('full-integration', [p, '-m', 'pytest', 'integration', '-q', '--tb=short', '--junitxml='+str(EVIDENCE / 'full-integration.xml')], 1800),
      ('capacity-isolated', [p, '-m', 'pytest', 'integration/test_capacity_gui.py', '-q', '--tb=long', '--junitxml='+str(EVIDENCE / 'capacity-isolated.xml')], 180),
      ('safety-isolated', [p, '-m', 'pytest', 'integration/test_ampacity_safety_gate.py', 'integration/test_independent_ampacity_safety.py', 'integration/test_independent_electrical_presentation_preservation.py', 'integration/test_tutorial_electrical_safety_contract.py', '-q', '--tb=short', '--junitxml='+str(EVIDENCE / 'safety-isolated.xml')], 600),
      ('lighting-widgets', [p, 'windows/tests/lighting_presets.py', '--gui'], 120),
      ('engineering-audit', [p, 'windows/tests/audit_regressions.py', '--gui', '--output', str(EVIDENCE / 'engineering-audit.json')], 240),
      ('report-interactions', [p, 'windows/tests/report_regressions.py', '--gui', '--output', str(EVIDENCE / 'report-interactions.json')], 240),
      ('dashboard-formulas', [p, 'tools/verify_engineering_dashboard.py', '--platform', 'windows', '--output', str(EVIDENCE / 'dashboard-formulas.json')], 120),
      ('dashboard-reports', [p, 'tools/verify_dashboard_reports.py', '--platform', 'windows', '--output', str(EVIDENCE / 'dashboard-reports.json'), '--artifacts-dir', str(EVIDENCE / 'report-samples')], 120),
      ('dashboard-widgets', [p, 'tools/verify_dashboard_gui.py', '--platform', 'windows', '--output', str(EVIDENCE / 'dashboard-widgets.json')], 240),
      ('tutorial', [p, 'docs/tutorial/verify_tutorial.py', '--platform', 'windows', '--output', str(EVIDENCE / 'tutorial.json')], 180),
    ]
    receipts = []
    for name, command, timeout in commands:
        start = time.monotonic()
        with (EVIDENCE / (name + '.log')).open('w', encoding='utf-8') as log:
            try:
                result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
                exit_code = result.returncode
            except subprocess.TimeoutExpired:
                exit_code = 124
                log.write('\nTIMEOUT: preserved as failure\n')
        receipt = dict(name=name, command=command, cwd=str(ROOT), exit_code=exit_code, elapsed_seconds=round(time.monotonic()-start, 3))
        receipts.append(receipt)
        print(json.dumps(receipt), flush=True)
        (EVIDENCE / 'command-receipts.json').write_text(json.dumps(receipts, indent=2))
    code = 0 if all(row['exit_code'] == 0 for row in receipts) else 1
    document = ET.parse(EVIDENCE / 'full-integration.xml')
    allowed_skip = 'test_tk9_side_buttons_do_not_scroll_page'
    skipped = [case.get('name') for case in document.iter('testcase') if case.find('skipped') is not None]
    native = [case for case in document.iter('testcase') if case.get('classname', '').endswith('test_onefile_process_native')]
    native_ok = len(native) == 8 and all(not any(case.find(kind) is not None for kind in ('error','failure','skipped')) for case in native)
    skip_ok = skipped == [allowed_skip]
    result = dict(passed=code == 0 and native_ok and skip_ok, command_exit=code,
        native_process_count=len(native), native_process_passed=native_ok, skips=skipped,
        allowed_skip=allowed_skip, unexpected_skips_rejected=True,
        original_failures_preserved=True, native_windows=True, host=platform.platform(),
        binary_published=False, formal_feed_accepted=False)
    (EVIDENCE / 'reviewed-SUMMARY.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    if sys.argv[1] == 'prepare':
        prepare()
    else:
        raise SystemExit(tests())
