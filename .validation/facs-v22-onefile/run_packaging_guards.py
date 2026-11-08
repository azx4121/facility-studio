"""Native tests of packaging guards only; never build or publish a product."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent


def prepare():
    source_runner = HERE.parent / 'facs-v22-windows' / 'run_native_validation.py'
    spec = importlib.util.spec_from_file_location('sealed_v22_preparation', source_runner)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.prepare()
    root, evidence = module.ROOT, module.EVIDENCE
    overlay = json.loads((HERE / 'overlay.json').read_text(encoding='utf-8'))
    for row in overlay:
        source = HERE / 'overlay' / row['path']
        assert hashlib.sha256(source.read_bytes()).hexdigest() == row['sha256']
        target = root / row['path']
        assert row['path'].startswith('integration/') and '/' not in row['path'][12:]
        if row['original_sha256'] is None:
            assert not target.exists()
        else:
            assert hashlib.sha256(target.read_bytes()).hexdigest() == row['original_sha256']
        shutil.copy2(source, target)
    (evidence / 'packaging-overlay.json').write_text(json.dumps(overlay, indent=2), encoding='utf-8')


def tests():
    root = Path(os.environ['RUNNER_TEMP']) / 'facs-v22-exact-source'
    evidence = Path(os.environ['RUNNER_TEMP']) / 'facs-v22-evidence'
    report = evidence / 'packaging-guards.xml'
    assert sys.platform == 'win32'
    targets = ['integration/test_onefile_validation.py', 'integration/test_onefile_process_native.py',
               'integration/test_acceptance_validation.py', 'integration/test_source_provenance.py']
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', PYTHONPATH=str(root))
    command = [sys.executable, '-m', 'pytest', *targets, '-q', '--tb=short', '--junitxml='+str(report)]
    with (evidence / 'packaging-guards.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=600)
    tree = ET.parse(report)
    native = [c for c in tree.iter('testcase') if c.get('classname', '').endswith('test_onefile_process_native')]
    native_ok = len(native) == 8 and all(not any(c.find(k) is not None for k in ('failure', 'error', 'skipped')) for c in native)
    summary = dict(passed=result.returncode == 0 and native_ok, native_process_cases=len(native),
                   native_process_cases_passed=native_ok, exit_code=result.returncode,
                   command=command, product_built=False, product_native_acceptance=False,
                   binary_published=False, formal_feed_accepted=False)
    (evidence / 'packaging-SUMMARY.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary))
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    if sys.argv[1] == 'prepare':
        prepare()
    else:
        raise SystemExit(tests())
