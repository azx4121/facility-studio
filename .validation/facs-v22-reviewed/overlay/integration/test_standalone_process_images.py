"""Pure audit negatives plus explicitly native process-image coverage."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from integration import onefile_validation as v


def initial():
    return dict(required=True, passed=False, errors=[], images=[])


def test_same_image_complete(tmp_path):
    exe = tmp_path / 'app.exe'
    exe.write_bytes(b'synthetic')
    audit = initial()
    v._record_process_image(audit, 1, str(exe), exe)
    v._record_process_image(audit, 2, str(exe), exe)
    v._complete_process_image_audit(audit, 2, 2)
    assert audit['passed'] is True


@pytest.mark.parametrize('case', ['foreign', 'missing', 'empty', 'query_failure',
                                  'unretained', 'missing_image', 'duplicate_pid', 'disabled', 'zero'])
def test_fail_closed(tmp_path, case):
    exe = tmp_path / 'app.exe'; exe.write_bytes(b'app')
    foreign = tmp_path / 'python.exe'; foreign.write_bytes(b'interpreter')
    audit = initial()
    actual = {'foreign': str(foreign), 'missing': str(tmp_path / 'gone.exe'), 'empty': ''}.get(case, str(exe))
    v._record_process_image(audit, 1, actual, exe)
    total, retained = 1, 1
    if case == 'query_failure': audit['errors'].append('QueryFullProcessImageNameW failed')
    if case == 'unretained': total = 2
    if case == 'missing_image': total = retained = 2
    if case == 'duplicate_pid':
        audit['images'].append(dict(audit['images'][0])); total = retained = 2
    if case == 'disabled': audit['required'] = False
    if case == 'zero': audit['images'] = []; total = retained = 0
    with pytest.raises(RuntimeError, match='process-image audit failed'):
        v._complete_process_image_audit(audit, total, retained)
    assert audit['passed'] is False


def _synthetic_base_executable():
    # A Windows venv python.exe may be venvlauncher.exe, which redirects to a
    # different process image. Test the real base interpreter, not that launcher.
    # This affects synthetic fixtures only; product launches still use the EXE.
    base = getattr(sys, '_base_executable', None)
    if not base:
        raise RuntimeError('Synthetic preflight cannot identify the base interpreter.')
    path = Path(base)
    if not path.is_absolute():
        raise RuntimeError('Synthetic base interpreter path must be absolute.')
    path = path.resolve(strict=True)
    if not path.is_file():
        raise RuntimeError('Synthetic base interpreter must be an existing file.')
    return str(path)


@pytest.mark.skipif(sys.platform != 'win32', reason='Native Windows image-query test; portable skip is not acceptance.')
@pytest.mark.parametrize('foreign', [False, True])
def test_native_child_identity(tmp_path, foreign, record_property):
    base = _synthetic_base_executable()
    env = dict(os.environ, FACILITY_TEST_REQUIRE_SAME_IMAGE_CHILDREN='1')
    if foreign:
        child = [str(Path(os.environ['SystemRoot']) / 'System32' / 'cmd.exe'), '/c', 'ping -n 3 127.0.0.1 >nul']
    else:
        child = [base, '-c', 'import time; time.sleep(1)']
    code = 'import subprocess; subprocess.run(' + repr(child) + ', check=True)'
    command = [base, '-c', code]
    if foreign:
        with pytest.raises(RuntimeError, match='process-image audit failed') as caught:
            v.run_bounded(command, tmp_path / 'process.log', env, timeout=20)
        audit = json.loads(str(caught.value).split('Standalone process-image audit failed: ', 1)[1])
        assert any(error.startswith('Unexpected external process image: ') for error in audit['errors'])
        assert audit['passed'] is False
    else:
        record = v.run_bounded(command, tmp_path / 'process.log', env, timeout=20)
        assert record['process_image_audit']['passed'] is True
        assert record['process_image_audit']['total_job_processes'] == 2
        audit = record['process_image_audit']
    record_property('process_image_preflight', json.dumps(dict(schema_version=1,
        expected='denied' if foreign else 'allowed', passed=True, command=command,
        synthetic_controller_executable=sys.executable, synthetic_base_executable=base,
        process_image_audit=audit)))


def test_expected_nonzero_preserves_audit(tmp_path, monkeypatch):
    monkeypatch.setattr(v.sys, 'platform', 'win32')
    def job(command, output, env, timeout, audit):
        audit.update(required=True, passed=True, errors=[], images=[dict(pid=1, image=str(command[0]))],
                     total_job_processes=1, retained_process_handles=1)
        return 2
    monkeypatch.setattr(v, '_run_windows_job', job)
    with pytest.raises(RuntimeError, match='acceptance exited 2') as caught:
        v.run_bounded([tmp_path / 'app.exe'], tmp_path / 'refusal.log', {}, timeout=10)
    assert caught.value.process_record['exit_code'] == 2
    assert caught.value.process_record['process_image_audit']['passed'] is True


def test_hardlink_alias_rejected(tmp_path):
    exe = tmp_path / 'app.exe'; exe.write_bytes(b'app')
    alias = tmp_path / 'python.exe'; os.link(exe, alias)
    audit = initial()
    v._record_process_image(audit, 1, str(alias), exe)
    with pytest.raises(RuntimeError, match='process-image audit failed'):
        v._complete_process_image_audit(audit, 1, 1)


def test_synthetic_base_uses_underlying_interpreter(tmp_path, monkeypatch):
    base = tmp_path / 'base-python.exe'; base.write_bytes(b'synthetic')
    monkeypatch.setattr(sys, '_base_executable', str(base))
    assert _synthetic_base_executable() == str(base.resolve())


@pytest.mark.parametrize('base', [None, '', 'relative-python.exe'])
def test_synthetic_base_rejects_missing_or_relative(base, monkeypatch):
    monkeypatch.setattr(sys, '_base_executable', base)
    with pytest.raises(RuntimeError, match='Synthetic'):
        _synthetic_base_executable()


def test_synthetic_base_rejects_nonexistent(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, '_base_executable', str(tmp_path / 'missing.exe'))
    with pytest.raises(FileNotFoundError):
        _synthetic_base_executable()
