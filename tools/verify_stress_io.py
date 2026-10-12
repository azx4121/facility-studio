"""Exercise actual generator bytes under a Windows legacy text codec.

The AST inventory is diagnostic. The regression gate checks behavior, so an
equivalent safe implementation need not use particular literal arguments.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def static_inventory(target):
    calls = []
    for node in ast.walk(ast.parse(target.read_text(encoding='utf-8'))):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', None)
        if name not in ('read_text', 'write_text', 'open'):
            continue
        kwargs = {x.arg: x.value for x in node.keywords}
        if name == 'open':
            mode_index = 0 if isinstance(node.func, ast.Attribute) else 1
            mode = kwargs.get('mode', node.args[mode_index] if len(node.args) > mode_index else ast.Constant('r'))
            if isinstance(mode, ast.Constant) and isinstance(mode.value, str) and 'b' in mode.value:
                continue
        encoding = kwargs.get('encoding')
        utf8 = isinstance(encoding, ast.Constant) and encoding.value == 'utf-8'
        lf = name != 'write_text' or (isinstance(kwargs.get('newline'), ast.Constant) and kwargs['newline'].value == '\n')
        calls.append(dict(line=node.lineno, operation=name, explicit_utf8=utf8, lf_writes=lf))
    return dict(text_io_calls=len(calls), explicit_utf8_lf_writes=sum(x['explicit_utf8'] and x['lf_writes'] for x in calls),
                failures=[x for x in calls if not x['explicit_utf8'] or not x['lf_writes']])


WRAPPER = r'''
import json, runpy, sys
from pathlib import Path
original_open = Path.open
def legacy_open(self, mode='r', buffering=-1, encoding=None, errors=None, newline=None):
    if 'b' not in mode and encoding in (None, 'locale'):
        encoding = 'cp1252'
    return original_open(self, mode, buffering, encoding, errors, newline)
Path.open = legacy_open
target, source, source_platform, manifest = sys.argv[1:]
sys.argv = [target, '--source', source, '--platform', source_platform,
            '--manifest', manifest, '--generate', '--seed', '20261013']
try:
    runpy.run_path(target, run_name='__main__')
except SystemExit as error:
    if error.code:
        raise
from facility_studio import api
from facility_studio.project_store import save_project_file
project = json.loads(Path(manifest).read_bytes())['cases'][0]['project']
saved = Path(manifest).with_name('saved-project.json')
save_project_file(saved, project)
assert json.loads(saved.read_bytes().decode('utf-8')) == project
assert api.read_project(saved) == project
print(json.dumps(dict(saved_project_utf8_roundtrip=True)), flush=True)
'''


def verify(target):
    started = time.perf_counter()
    source = Path(__file__).resolve().parents[1]
    source_platform = 'windows' if sys.platform == 'win32' else 'macos'
    digests = []
    inventory = static_inventory(target)
    with tempfile.TemporaryDirectory(prefix='FacilityStudioCodec-') as directory:
        env = dict(os.environ, PYTHONIOENCODING='cp1252', PYTHONUTF8='0',
                   FACILITY_STUDIO_PREFERENCES=str(Path(directory)/'preferences.json'))
        for index in range(2):
            manifest = Path(directory)/('manifest-%d.json' % index)
            result = subprocess.run([sys.executable, '-c', WRAPPER, str(target), str(source),
                                     source_platform, str(manifest)], env=env, capture_output=True)
            if result.returncode:
                raise AssertionError(result.stderr.decode('utf-8', errors='replace'))
            log = result.stdout.decode('utf-8')
            assert json.loads(log.splitlines()[-1])['saved_project_utf8_roundtrip']
            raw = manifest.read_bytes()
            assert b'\r\n' not in raw, 'Manifest must use LF on all operating systems'
            doc = json.loads(raw.decode('utf-8'))
            cases = doc['cases']
            assert len(cases) == 100
            assert any(ord(c)>127 for c in raw.decode('utf-8')), 'Unicode fixture missing'
            physical = [{k:v for k,v in case['project']['inputs'].items() if k!='project_name'} for case in cases]
            assert len({json.dumps(x, sort_keys=True) for x in physical}) == 100
            # Timestamped provenance is metadata; compare every physical recipe,
            # independent reference and expected outcome across two generations.
            normalized = [dict(inputs=c['project']['inputs'], pressure_drop=c['project']['pressure_drop'],
                               reference=c['reference'], expectation=c['expectation']) for c in cases]
            digests.append(hashlib.sha256(json.dumps(normalized,sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest())
    assert digests[0] == digests[1], 'Seeded engineering recipes changed between generations'
    return dict(passed=True, source_platform=source_platform, scenario_count=100,
        distinct_physical_input_count=100, generations=2, stable_recipe_sha256=digests[0],
        simulated_implicit_filesystem_codec='cp1252', inherited_console_codec='cp1252',
        utf8_manifest_verified=True, lf_manifest_verified=True, saved_project_utf8_roundtrip=True,
        static_audit=inventory, seconds=time.perf_counter()-started)


if __name__ == '__main__':
    target = Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).with_name('cleanroom100_stress.py')
    try:
        print(json.dumps(verify(target)))
    except Exception as error:
        print(json.dumps(dict(passed=False, error_type=type(error).__name__, detail=str(error))))
        sys.exit(1)
