"""Unit/mocked packaging guards only: these tests are NOT native Windows evidence.

Synthetic PE bytes, a mocked PyInstaller reader and mocked process execution do
not prove that a real frozen application launches, renders or works offline.
"""
import copy
import hashlib
import json
import struct
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from integration import build, onefile_validation as validation, windows_installer
from integration.test_acceptance_validation import manifest, report


def synthetic_pe():
    """Structurally plausible AMD64 PE32+ header, not an executable program."""
    data = bytearray(512)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 0x3c, 0x80)
    data[0x80:0x84] = b'PE\x00\x00'
    struct.pack_into('<HHIIIHH', data, 0x84, 0x8664, 1, 0, 0, 0, 240, 0x22)
    struct.pack_into('<H', data, 0x98, 0x20b)
    return bytes(data)


@pytest.fixture
def exe(tmp_path):
    path = tmp_path / 'Synthetic.exe'
    path.write_bytes(synthetic_pe())
    return path


@pytest.fixture
def archive(monkeypatch):
    state = SimpleNamespace(payload=json.dumps(manifest()).encode(), opened=[], extracted=[])

    class Reader:
        def __init__(self, path):
            state.opened.append(path)

        def extract(self, name):
            state.extracted.append(name)
            if isinstance(state.payload, Exception):
                raise state.payload
            return state.payload

    for name in ('PyInstaller', 'PyInstaller.archive', 'PyInstaller.archive.readers'):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    sys.modules['PyInstaller.archive.readers'].CArchiveReader = Reader
    return state


def test_reads_actual_exe_archive_not_sibling_manifest(exe, archive):
    exe.with_name('Build_Manifest.json').write_text('{"untrusted": true}')
    assert validation.validate_onefile_manifest(exe, manifest()) == manifest()
    assert archive.opened == [str(exe)]
    assert archive.extracted == ['Build_Manifest.json']


@pytest.mark.parametrize('payload', [b'{', b'null', b'[]', b'\xff',
                                    b'{"commit":"a","commit":"b"}',
                                    KeyError('Build_Manifest.json'), None])
def test_missing_corrupt_or_duplicate_archive_manifest_is_rejected(exe, archive, payload):
    archive.payload = payload
    with pytest.raises(RuntimeError):
        validation.validate_onefile_manifest(exe, manifest())


@pytest.mark.parametrize('field,value', [
    ('commit', 'b' * 40), ('source_platform', 'macos'), ('source_clean', False),
    ('build_channel', 'non-release'), ('version', '5.7.2'),
    ('build_inputs_sha256', {'integration/entry.py': '2' * 64}),
])
def test_embedded_provenance_mismatch_rejected(exe, archive, field, value):
    changed = copy.deepcopy(manifest())
    changed[field] = value
    archive.payload = json.dumps(changed).encode()
    with pytest.raises(RuntimeError):
        validation.validate_onefile_manifest(exe, manifest())


@pytest.mark.parametrize('field', list(manifest()))
def test_missing_manifest_fields_rejected(exe, archive, field):
    changed = manifest()
    del changed[field]
    archive.payload = json.dumps(changed).encode()
    with pytest.raises(RuntimeError):
        validation.validate_onefile_manifest(exe, manifest())


def test_nonwindows_source_rejected_even_when_matching(exe, archive):
    source = manifest('macos')
    archive.payload = json.dumps(source).encode()
    with pytest.raises(RuntimeError):
        validation.validate_onefile_manifest(exe, source)


def test_dirty_manifest_requires_explicit_nonrelease_opt_in(exe, archive):
    source = dict(manifest(), source_clean=False, build_channel='non-release')
    archive.payload = json.dumps(source).encode()
    with pytest.raises(RuntimeError):
        validation.validate_onefile_manifest(exe, source)
    assert validation.validate_onefile_manifest(exe, source, allow_non_release=True) == source


def test_direct_archive_validation_rejects_symlink(exe, archive):
    alias = exe.with_name('Alias.exe')
    alias.symlink_to(exe)
    with pytest.raises(RuntimeError):
        validation.validate_onefile_manifest(alias, manifest())


def test_verification_rejects_symlink_before_resolving(exe, archive, tmp_path, monkeypatch):
    alias = exe.with_name('Alias.exe')
    alias.symlink_to(exe)
    monkeypatch.setattr(validation.sys, 'platform', 'win32')
    def must_not_launch(*args, **kwargs):
        pytest.fail('A symlink must be rejected before launching an executable')
    monkeypatch.setattr(validation, 'run_bounded', must_not_launch)
    with pytest.raises(RuntimeError):
        validation.verify_single_exe(alias, tmp_path / 'evidence', manifest())


def test_unsupported_host_does_not_launch_or_write_evidence(exe, tmp_path, monkeypatch):
    monkeypatch.setattr(validation.sys, 'platform', 'linux')
    evidence = tmp_path / 'evidence'
    with pytest.raises(RuntimeError, match='Native Windows'):
        validation.verify_single_exe(exe, evidence, manifest())
    assert not evidence.exists()


def mock_acceptance_runner(monkeypatch, *, mutate=None):
    calls = []
    def run(command, log, env, **kwargs):
        executable, flag, output = map(Path, command)
        suite = 'fusion' if str(flag) == '--fusion-self-test' else 'facilities'
        payload = report(suite)
        if mutate:
            mutate(payload)
        output.write_text(json.dumps(payload))
        calls.append((executable, hashlib.sha256(executable.read_bytes()).hexdigest(),
                      list(executable.parent.iterdir()), env))
        return dict(command=list(map(str, command)), exit_code=0, elapsed_seconds=0)
    monkeypatch.setattr(validation, 'run_bounded', run)
    return calls


def test_mocked_plain_and_unicode_path_copies_have_identical_bytes(exe, archive, tmp_path, monkeypatch):
    monkeypatch.setattr(validation.sys, 'platform', 'win32')
    calls = mock_acceptance_runner(monkeypatch)
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    result = validation.verify_single_exe(exe, tmp_path / 'evidence', manifest())
    assert result['passed'] is True  # Mock control flow, not a real accepted EXE.
    assert len(calls) == 4
    assert {p.parent.name for p, *_ in calls} == {'portable', '繁體中文 空白路徑'}
    assert all(d == digest and entries == [p] for p, d, entries, env in calls)
    assert hashlib.sha256(exe.read_bytes()).hexdigest() == digest
    assert {r['suite'] for r in result['records']} == {'fusion', 'facilities'}
    assert result['installation_performed'] is False
    assert result['formal_feed_accepted'] is False
    assert all(env['FACILITY_TEST_BLOCK_NETWORK'] == '1' for *_, env in calls)


@pytest.mark.parametrize('field,value', [('passed', False), ('frozen', False), ('checks', []),
                                         ('build_provenance_sha256', '9' * 64)])
def test_exit_zero_cannot_override_invalid_frozen_acceptance(exe, archive, tmp_path, monkeypatch, field, value):
    monkeypatch.setattr(validation.sys, 'platform', 'win32')
    mock_acceptance_runner(monkeypatch, mutate=lambda payload: payload.update({field: value}))
    evidence = tmp_path / 'evidence'
    with pytest.raises(RuntimeError):
        validation.verify_single_exe(exe, evidence, manifest())
    summary = json.loads((evidence / 'Single_EXE_Verification.json').read_text())
    assert summary['passed'] is False


def test_offline_environment_removes_external_python_and_tcl(monkeypatch, tmp_path):
    for key in ('PYTHONHOME', 'pythonpath', 'TCL_LIBRARY', 'TK_LIBRARY'):
        monkeypatch.setenv(key, '/untrusted')
    monkeypatch.setenv('SystemRoot', 'C:/Windows')
    env = validation.offline_environment(tmp_path / 'data')
    assert not {'PYTHONHOME', 'PYTHONPATH', 'TCL_LIBRARY', 'TK_LIBRARY'} & {k.upper() for k in env}
    assert env['FACILITY_STUDIO_FUSION_DATA'] == str(tmp_path / 'data')
    assert env['FACILITY_TEST_BLOCK_NETWORK'] == '1'
    assert env['PYTHONUTF8'] == '1'
    assert '/untrusted' not in env['PATH']


@pytest.fixture
def mocked_build(tmp_path, monkeypatch):
    root = tmp_path / 'source'
    root.mkdir()
    for name in ('LICENSE', 'LICENSE_LEGACY_MIT', 'THIRD_PARTY_NOTICES.md', 'macos/macos/PsychroLib-LICENSE.txt'):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('Synthetic license fixture')
    hvac = tmp_path / 'dependency/hvac'
    (hvac / 'fluids').mkdir(parents=True)
    (hvac / 'fluids/__init__.py').write_text('from .water import Water\nfrom .ice import Ice\n')
    python = tmp_path / 'python'
    python.mkdir()
    (python / 'LICENSE.txt').write_text('Synthetic Python license fixture')
    monkeypatch.setattr(build, 'ROOT', root)
    monkeypatch.setattr(build.sys, 'platform', 'win32')
    monkeypatch.setattr(build.sys, 'base_prefix', str(python))
    monkeypatch.setattr(build.importlib.metadata, 'distribution', lambda name: SimpleNamespace(locate_file=lambda name: hvac))
    monkeypatch.setattr(build.importlib.metadata, 'distributions', lambda: [])
    monkeypatch.setattr(build, 'verify_source_unchanged', lambda *args: None)
    output = tmp_path / 'output'
    commands = []
    def run(args, log, **kwargs):
        commands.append(list(map(str, args)))
        toc = output / 'work' / build.NAME / 'PYZ-00.toc'
        toc.parent.mkdir(parents=True)
        toc.write_text('[]')
        executable = output / 'dist' / (build.NAME + '.exe')
        executable.parent.mkdir()
        executable.write_bytes(synthetic_pe())
    monkeypatch.setattr(build, 'run', run)
    def no_installer(*args, **kwargs):
        pytest.fail('Single EXE builds must never build or verify an installer')
    monkeypatch.setattr(windows_installer, 'build', no_installer)
    monkeypatch.setattr(windows_installer, 'verify', no_installer)
    return output, commands


def test_mocked_onefile_build_selects_flag_and_never_installer(mocked_build, monkeypatch):
    output, commands = mocked_build
    calls = []
    monkeypatch.setattr(validation, 'verify_single_exe', lambda *args, **kwargs: calls.append(args))
    assert build._build(output, 'windows', manifest(), False, onefile=True) == 0
    assert len(commands) == 1
    assert '--onefile' in commands[0] and '--onedir' not in commands[0]
    assert len(calls) == 1
    artifact = output / 'Facility-Studio-5.7.3-v22-Windows-x64-Portable.exe'
    assert artifact.read_bytes() == (output / 'dist' / (build.NAME + '.exe')).read_bytes()
    assert (output / 'SHA256SUMS.txt').read_text().startswith(hashlib.sha256(artifact.read_bytes()).hexdigest())
    assert not list(output.glob('*.zip'))


def test_failed_frozen_gate_never_creates_delivery_artifact(mocked_build, monkeypatch):
    output, commands = mocked_build
    def fail(*args, **kwargs):
        raise RuntimeError('Synthetic frozen acceptance failure')
    monkeypatch.setattr(validation, 'verify_single_exe', fail)
    with pytest.raises(RuntimeError, match='Synthetic frozen acceptance failure'):
        build._build(output, 'windows', manifest(), False, onefile=True)
    assert '--onefile' in commands[0]
    assert not list(output.glob('*.exe'))
    assert not (output / 'SHA256SUMS.txt').exists()


@pytest.mark.parametrize('host,source', [('linux', 'windows'), ('darwin', 'macos'), ('win32', 'macos')])
def test_onefile_build_rejects_unsupported_host_or_source(tmp_path, monkeypatch, host, source):
    monkeypatch.setattr(build.sys, 'platform', host)
    output = tmp_path / 'output'
    with pytest.raises(RuntimeError):
        build._build(output, source, manifest(source), False, onefile=True)
    assert not output.exists()


def test_cli_passes_windows_onefile_option(tmp_path, monkeypatch):
    monkeypatch.setattr(build.sys, 'platform', 'win32')
    monkeypatch.setattr(build.sys, 'version_info', (3, 12, 0))
    monkeypatch.setattr(build.sys, 'argv', ['build.py', '--output', str(tmp_path / 'output'), '--windows-onefile'])
    monkeypatch.setattr(build, 'expected_source_manifest', lambda *args, **kwargs: manifest())
    calls = []
    monkeypatch.setattr(build, '_build', lambda *args, **kwargs: calls.append((args, kwargs)) or 0)
    assert build.main() == 0
    assert calls[0][1] == {'onefile': True}


@pytest.mark.parametrize('target', ['copy-before-launch', 'copy-after-launch', 'original'])
def test_executable_mutation_cannot_pass_verification(exe, archive, tmp_path, monkeypatch, target):
    monkeypatch.setattr(validation.sys, 'platform', 'win32')
    mock_acceptance_runner(monkeypatch)
    original_run = validation.run_bounded
    if target == 'copy-before-launch':
        original_copy = validation.shutil.copy2
        def corrupt_copy(source, destination, *args, **kwargs):
            value = original_copy(source, destination, *args, **kwargs)
            Path(destination).write_bytes(Path(destination).read_bytes() + b'changed')
            return value
        monkeypatch.setattr(validation.shutil, 'copy2', corrupt_copy)
    else:
        def corrupt_run(command, log, env, **kwargs):
            value = original_run(command, log, env, **kwargs)
            changed = exe if target == 'original' else Path(command[0])
            changed.write_bytes(changed.read_bytes() + b'changed')
            return value
        monkeypatch.setattr(validation, 'run_bounded', corrupt_run)
    evidence = tmp_path / 'evidence'
    with pytest.raises(RuntimeError):
        validation.verify_single_exe(exe, evidence, manifest())
    assert json.loads((evidence / 'Single_EXE_Verification.json').read_text())['passed'] is False


def test_verification_rejects_symlinked_parent_directory(exe, archive, tmp_path, monkeypatch):
    alias = tmp_path / 'alias-directory'
    alias.symlink_to(exe.parent, target_is_directory=True)
    monkeypatch.setattr(validation.sys, 'platform', 'win32')
    def must_not_launch(*args, **kwargs):
        pytest.fail('A symlinked parent directory must be rejected before launch')
    monkeypatch.setattr(validation, 'run_bounded', must_not_launch)
    with pytest.raises(RuntimeError):
        validation.verify_single_exe(alias / exe.name, tmp_path / 'evidence', manifest())


@pytest.mark.parametrize('case', ['mz-only', 'bad-signature', 'x86-machine', 'pe32-magic'])
def test_synthetic_non_x64_pe_headers_rejected(exe, archive, case):
    data = bytearray(synthetic_pe())
    if case == 'mz-only':
        data = bytearray(b'MZnot a real PE')
    elif case == 'bad-signature':
        data[0x80:0x84] = b'NOPE'
    elif case == 'x86-machine':
        struct.pack_into('<H', data, 0x84, 0x14c)
    else:
        struct.pack_into('<H', data, 0x98, 0x10b)
    exe.write_bytes(data)
    with pytest.raises(RuntimeError):
        validation.validate_onefile_manifest(exe, manifest())
    assert not archive.opened
