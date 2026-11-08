"""Native Windows runner tests using synthetic Python processes, not the product.

A skip on another OS is explicitly not Windows or product acceptance evidence.
No network isolation, installation, visual UI, or PyInstaller behavior is tested.
"""
import concurrent.futures
import ctypes
import hashlib
from ctypes import wintypes
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

from integration.onefile_validation import _run_windows_job, run_bounded

pytestmark = pytest.mark.skipif(
    sys.platform != 'win32',
    reason='Native Windows process tests require Windows; skips are not product acceptance.',
)


def _base_executable():
    # A Windows venv launcher spawns a short-lived redirect child. These fixtures
    # test process outcomes, not venv redirection; use the real interpreter.
    value = getattr(sys, '_base_executable', None)
    if not value or not Path(value).is_absolute():
        raise RuntimeError('Synthetic base interpreter path must be absolute.')
    executable = Path(value).resolve(strict=True)
    if not executable.is_file():
        raise RuntimeError('Synthetic base interpreter must be an existing file.')
    return str(executable)


def _environment():
    return dict(os.environ, PYTHONUTF8='1', PYTHONUNBUFFERED='1')


def _copied_interpreter_environment(base):
    # A copied real python.exe needs its original DLL and standard library.
    # This is a synthetic runner fixture, never standalone product evidence.
    prefix = Path(sys.base_prefix)
    if not prefix.is_absolute():
        raise RuntimeError('Synthetic base prefix must be absolute.')
    prefix = prefix.resolve(strict=True)
    if not prefix.is_dir():
        raise RuntimeError('Synthetic base prefix must be an existing directory.')
    env = _environment()
    env['PYTHONHOME'] = str(prefix)
    env['PATH'] = str(Path(base).parent) + os.pathsep + env.get('PATH', '')
    return env


@pytest.mark.parametrize('exit_code', [0, 23])
def test_job_returns_code_and_retains_stdout(tmp_path, exit_code):
    log = tmp_path / 'direct.log'
    command = [_base_executable(), '-c',
               f'import sys; print("native stdout 繁體中文", flush=True); '
               f'print("native stderr", file=sys.stderr, flush=True); sys.exit({exit_code})']
    with log.open('w', encoding='utf-8') as output:
        assert _run_windows_job(command, output, _environment(), 10) == exit_code
    text = log.read_text(encoding='utf-8')
    assert 'native stdout 繁體中文' in text
    assert 'native stderr' in text


def test_bounded_success(tmp_path):
    log = tmp_path / 'success.log'
    result = run_bounded([_base_executable(), '-c', 'print("success", flush=True)'],
                         log, _environment(), timeout=10)
    assert result['exit_code'] == 0
    assert result['command'][0] == _base_executable()
    assert 'success' in log.read_text(encoding='utf-8')


def test_bounded_nonzero_retains_stdout(tmp_path):
    log = tmp_path / 'nonzero.log'
    with pytest.raises(RuntimeError, match='exited 17'):
        run_bounded([_base_executable(), '-c',
                     'import sys; print("before failure", flush=True); sys.exit(17)'],
                    log, _environment(), timeout=10)
    assert 'before failure' in log.read_text(encoding='utf-8')


def test_bounded_timeout_retains_stdout(tmp_path):
    log = tmp_path / 'timeout.log'
    with pytest.raises(RuntimeError, match='timed out'):
        run_bounded([_base_executable(), '-c',
                     'import time; print("before timeout", flush=True); time.sleep(60)'],
                    log, _environment(), timeout=3)
    assert 'before timeout' in log.read_text(encoding='utf-8')


def test_unicode_space_executable_and_argument_paths(tmp_path):
    # Copy only the real interpreter image, not a venv launcher or runtime tree.
    # Explicit runtime lookup below lets this short-lived root have no redirect
    # child while still exercising Unicode/space executable and argument paths.
    base = Path(_base_executable())
    folder = tmp_path / '繁體中文 空白路徑'
    folder.mkdir()
    executable = folder / 'python.exe'
    shutil.copyfile(base, executable)
    assert hashlib.sha256(executable.read_bytes()).digest() == hashlib.sha256(base.read_bytes()).digest()
    script = folder / '測試 程式.py'
    script.write_text('import sys\nprint("unicode path " + sys.argv[1], flush=True)\n',
                      encoding='utf-8')
    log = tmp_path / 'unicode.log'
    result = run_bounded([executable, script, '參數 含空白'], log,
                         _copied_interpreter_environment(base), timeout=10)
    assert result['exit_code'] == 0
    assert 'unicode path 參數 含空白' in log.read_text(encoding='utf-8')


_TREE_SCRIPT = r'''
import os
from pathlib import Path
import subprocess
import sys
import time

folder = Path(sys.argv[1])
role = sys.argv[2]
# Hold a real file open so successful folder removal also exercises handle drain.
lock = (folder / (role + '.lock')).open('w')
print('ready ' + role, flush=True)
(folder / (role + '.pid')).write_text(str(os.getpid()), encoding='ascii')
if role == 'root':
    subprocess.Popen([sys.executable, __file__, str(folder), 'child'])
elif role == 'child':
    subprocess.Popen([sys.executable, __file__, str(folder), 'grandchild'])
deadline = time.monotonic() + 60
while time.monotonic() < deadline:
    if role == 'root' and (folder / 'exit-root').exists():
        print('root exiting normally', flush=True)
        break
    time.sleep(0.02)
'''


def _owned_process_api():
    """Use stable handles, not later PID lookups, for assertions and cleanup."""
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.TerminateProcess.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    return kernel


@pytest.mark.parametrize('parent_exit', ['normal', 'timeout'])
def test_child_and_grandchild_are_gone_before_return(tmp_path, parent_exit):
    script = tmp_path / 'synthetic_tree.py'
    script.write_text(_TREE_SCRIPT, encoding='utf-8')
    tree = tmp_path / 'owned tree 繁中'
    tree.mkdir()
    log = tmp_path / 'tree.log'
    kernel = _owned_process_api()
    handles = {}
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = pool.submit(run_bounded, [_base_executable(), script, tree, 'root'],
                         log, _environment(), timeout=12)
    try:
        # Root and descendants stay alive until the explicit gate or timeout.
        # Acquire handles while each newly spawned synthetic PID is still alive.
        deadline = time.monotonic() + 8
        while len(handles) < 3:
            for role in ('root', 'child', 'grandchild'):
                if role in handles:
                    continue
                pid_file = tree / (role + '.pid')
                if not pid_file.exists():
                    continue
                value = pid_file.read_text(encoding='ascii')
                if not value:  # write_text creates the file before writing its PID.
                    continue
                handle = kernel.OpenProcess(0x100000 | 0x1, False, int(value))
                if not handle:
                    raise ctypes.WinError(ctypes.get_last_error())
                handles[role] = handle
            if len(handles) == 3:
                break
            if future.done():
                future.result()  # Surface an early runner failure, if any.
                pytest.fail('Synthetic root exited before descendant readiness.')
            if time.monotonic() >= deadline:
                pytest.fail('Synthetic process tree did not become ready within 8 seconds.')
            time.sleep(0.02)
        for handle in handles.values():
            assert kernel.WaitForSingleObject(handle, 0) == 0x102
        if parent_exit == 'normal':
            (tree / 'exit-root').write_text('go', encoding='ascii')
            assert future.result(timeout=45)['exit_code'] == 0
        else:
            with pytest.raises(RuntimeError, match='timed out'):
                future.result(timeout=45)
        # No grace period here: run_bounded itself must wait for all descendants.
        for role, handle in handles.items():
            assert kernel.WaitForSingleObject(handle, 0) == 0, role + ' survived runner return'
        text = log.read_text(encoding='utf-8')
        assert all('ready ' + role in text for role in handles)
        shutil.rmtree(tree)
        assert not tree.exists()
    finally:
        # Cleanup targets only retained handles of this test's synthetic children.
        # The runner also has a bounded timeout and kernel-owned job cleanup.
        for handle in handles.values():
            if kernel.WaitForSingleObject(handle, 0) == 0x102:
                kernel.TerminateProcess(handle, 1)
            kernel.WaitForSingleObject(handle, 5000)
            kernel.CloseHandle(handle)
        try:
            future.result(timeout=45)
        except (RuntimeError, OSError, subprocess.TimeoutExpired):
            pass
        finally:
            pool.shutdown(wait=False)
