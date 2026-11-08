"""Run exact sealed v22 on native Windows. Preserve every failure; never publish."""
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ['RUNNER_TEMP']) / 'facs-v22-exact-source'
EVIDENCE = Path(os.environ['RUNNER_TEMP']) / 'facs-v22-evidence'


def prepare():
    if sys.platform != 'win32':
        raise RuntimeError('Native Windows required')
    EVIDENCE.mkdir(exist_ok=False)
    ROOT.mkdir(exist_ok=False)
    data = base64.b64decode(''.join(p.read_text() for p in sorted(HERE.glob('source.part*.b64'))), validate=True)
    provenance = json.loads((HERE / 'provenance.json').read_text())
    assert hashlib.sha256(data).hexdigest() == provenance['source_archive_sha256']
    archive = EVIDENCE / 'source-v22.zip'
    archive.write_bytes(data)
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            p = Path(info.filename)
            assert not p.is_absolute() and '..' not in p.parts and '\\' not in info.filename
            assert (info.external_attr >> 16) & 0o170000 in (0, 0o100000)
        z.extractall(ROOT)
    manifest = json.loads((HERE / 'SOURCE_MANIFEST.json').read_text())
    actual = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file()}
    assert actual == {f['path'] for f in manifest['files']}
    for f in manifest['files']:
        b = (ROOT / f['path']).read_bytes()
        assert len(b) == f['bytes'] and hashlib.sha256(b).hexdigest() == f['sha256'], f['path']
    provenance.update(host_os=platform.platform(), host_python=sys.version, native_windows=True,
                      workflow_commit=os.environ['GITHUB_SHA'], source_identity_verified=True,
                      original_source_files=len(actual), binary_built=False, binary_published=False,
                      formal_feed_accepted=False)
    (EVIDENCE / 'input-provenance.json').write_text(json.dumps(provenance, indent=2))
    print('Verified exact source:', len(actual), 'files')


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
    result = dict(passed=all(r['exit_code']==0 for r in receipts), native_windows=True,
                  host_os=platform.platform(), python=sys.version, commands=receipts,
                  full_results_preserved=True, frozen_binary_tested=False,
                  single_exe_built=False, downloadable_release_published=False,
                  formal_feed_accepted=False)
    (EVIDENCE / 'SUMMARY.json').write_text(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    if sys.argv[1] == 'prepare':
        prepare()
    else:
        raise SystemExit(tests())
