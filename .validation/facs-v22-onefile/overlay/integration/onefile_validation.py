"""Validate the onefile archive and run unchanged bytes with test safeguards.

This is a packaging gate, not a replacement for source suites, native visual
review, independent 2022/2025 execution, signing or engineering approval.
The application network hook is not OS network isolation; only the launch PATH
is stripped of external Python locations.
"""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import time

try:
    from .acceptance_validation import _unique_object, _validate_manifest, validate_acceptance
    from .source_provenance import PROVENANCE_FIELDS
except ImportError:
    from acceptance_validation import _unique_object, _validate_manifest, validate_acceptance
    from source_provenance import PROVENANCE_FIELDS


def _regular_executable(executable):
    """Check the supplied path before resolving away links or reparse points."""
    executable = Path(executable)
    if not executable.is_absolute():
        executable = Path.cwd() / executable
    for component in (executable, *executable.parents):
        metadata = component.lstat()
        if stat.S_ISLNK(metadata.st_mode) or (getattr(metadata, 'st_file_attributes', 0)
                                             & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)):
            raise RuntimeError('Executable paths must not contain links or reparse points.')
    if not executable.is_file() or executable.suffix.lower() != '.exe':
        raise RuntimeError('A regular single EXE is required.')
    return executable


def _validate_amd64_pe(executable):
    """Require a complete AMD64 COFF header and PE32+ optional header."""
    with executable.open('rb') as stream:
        size = os.fstat(stream.fileno()).st_size
        dos = stream.read(64)
        if len(dos) != 64 or dos[:2] != b'MZ':
            raise RuntimeError('The single EXE has an invalid DOS header.')
        offset = struct.unpack_from('<I', dos, 60)[0]
        if offset < 64 or offset > size - 24:
            raise RuntimeError('The single EXE has an invalid PE offset.')
        stream.seek(offset)
        header = stream.read(24)
        if header[:4] != b'PE\0\0' or struct.unpack_from('<H', header, 4)[0] != 0x8664:
            raise RuntimeError('The single EXE must be an AMD64 Windows PE executable.')
        optional_size = struct.unpack_from('<H', header, 20)[0]
        optional = stream.read(optional_size)
        if (optional_size < 112 or len(optional) != optional_size
                or struct.unpack_from('<H', optional)[0] != 0x20b):
            raise RuntimeError('The single EXE has an invalid PE32+ optional header.')


def validate_onefile_manifest(executable, expected_manifest, *, allow_non_release=False):
    """Read the manifest out of the actual EXE; never trust a sibling file."""
    from PyInstaller.archive.readers import CArchiveReader
    executable = _regular_executable(executable)
    _validate_amd64_pe(executable)
    commit = expected_manifest.get('commit')
    _validate_manifest(expected_manifest, commit, 'expected source', allow_non_release=allow_non_release)
    if expected_manifest['source_platform'] != 'windows':
        raise RuntimeError('Single EXE provenance must identify Windows source.')
    try:
        archive = CArchiveReader(str(executable))
        data = archive.extract('Build_Manifest.json')
        manifest = json.loads(data.decode('utf-8'), object_pairs_hook=_unique_object)
    except (KeyError, OSError, UnicodeError, ValueError, TypeError, AttributeError) as error:
        raise RuntimeError('Cannot read the embedded onefile source manifest.') from error
    _validate_manifest(manifest, commit, executable, allow_non_release=allow_non_release)
    for field in PROVENANCE_FIELDS:
        if manifest[field] != expected_manifest[field]:
            raise RuntimeError('Embedded single EXE provenance mismatch: ' + field)
    return manifest


def offline_environment(data_directory):
    env = dict(os.environ)
    for key in list(env):
        if key.upper() in {'PYTHONHOME', 'PYTHONPATH', 'TCL_LIBRARY', 'TK_LIBRARY'}:
            del env[key]
    system_root = Path(env.get('SystemRoot', 'C:/Windows'))
    env.update(PATH=str(system_root / 'System32') + os.pathsep + str(system_root),
               FACILITY_STUDIO_FUSION_DATA=str(data_directory),
               FACILITY_TEST_BLOCK_NETWORK='1', PYTHONUTF8='1')
    return env


def _run_windows_job(command, output, env, timeout):
    """Assign a suspended process to a kill-on-close job before any app code runs.

    No breakaway flag is allowed. Closing the job also kills surviving children
    when the parent exits normally. If the host disallows job assignment, fail
    closed rather than execute without process-tree containment.
    """
    import ctypes
    from ctypes import wintypes as w
    import msvcrt

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    SIZE_T = ctypes.c_size_t
    class STARTUPINFO(ctypes.Structure):
        _fields_ = [('cb', w.DWORD), ('lpReserved', w.LPWSTR), ('lpDesktop', w.LPWSTR),
                    ('lpTitle', w.LPWSTR), ('dwX', w.DWORD), ('dwY', w.DWORD),
                    ('dwXSize', w.DWORD), ('dwYSize', w.DWORD),
                    ('dwXCountChars', w.DWORD), ('dwYCountChars', w.DWORD),
                    ('dwFillAttribute', w.DWORD), ('dwFlags', w.DWORD),
                    ('wShowWindow', w.WORD), ('cbReserved2', w.WORD),
                    ('lpReserved2', ctypes.POINTER(ctypes.c_byte)),
                    ('hStdInput', w.HANDLE), ('hStdOutput', w.HANDLE), ('hStdError', w.HANDLE)]
    class STARTUPINFOEX(ctypes.Structure):
        _fields_ = [('StartupInfo', STARTUPINFO), ('lpAttributeList', ctypes.c_void_p)]
    class PROCESS_INFORMATION(ctypes.Structure):
        _fields_ = [('hProcess', w.HANDLE), ('hThread', w.HANDLE),
                    ('dwProcessId', w.DWORD), ('dwThreadId', w.DWORD)]
    class BASIC_LIMIT(ctypes.Structure):
        _fields_ = [('PerProcessUserTimeLimit', ctypes.c_longlong),
                    ('PerJobUserTimeLimit', ctypes.c_longlong), ('LimitFlags', w.DWORD),
                    ('MinimumWorkingSetSize', SIZE_T), ('MaximumWorkingSetSize', SIZE_T),
                    ('ActiveProcessLimit', w.DWORD), ('Affinity', SIZE_T),
                    ('PriorityClass', w.DWORD), ('SchedulingClass', w.DWORD)]
    class BASIC_ACCOUNTING(ctypes.Structure):
        _fields_ = [(name, ctypes.c_longlong) for name in
                    ('TotalUserTime', 'TotalKernelTime', 'ThisPeriodTotalUserTime',
                     'ThisPeriodTotalKernelTime')] + [(name, w.DWORD) for name in
                    ('TotalPageFaultCount', 'TotalProcesses', 'ActiveProcesses',
                     'TotalTerminatedProcesses')]
    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in
                    ('ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
                     'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]
    class EXTENDED_LIMIT(ctypes.Structure):
        _fields_ = [('BasicLimitInformation', BASIC_LIMIT), ('IoInfo', IO_COUNTERS),
                    ('ProcessMemoryLimit', SIZE_T), ('JobMemoryLimit', SIZE_T),
                    ('PeakProcessMemoryUsed', SIZE_T), ('PeakJobMemoryUsed', SIZE_T)]
    def bind(name, args, result=w.BOOL):
        function = getattr(kernel, name)
        function.argtypes, function.restype = args, result
        return function
    create_job = bind('CreateJobObjectW', [ctypes.c_void_p, w.LPCWSTR], w.HANDLE)
    set_job = bind('SetInformationJobObject', [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD])
    assign = bind('AssignProcessToJobObject', [w.HANDLE, w.HANDLE])
    close = bind('CloseHandle', [w.HANDLE])
    initialize = bind('InitializeProcThreadAttributeList',
                      [ctypes.c_void_p, w.DWORD, w.DWORD, ctypes.POINTER(SIZE_T)])
    update = bind('UpdateProcThreadAttribute',
                  [ctypes.c_void_p, w.DWORD, SIZE_T, ctypes.c_void_p, SIZE_T,
                   ctypes.c_void_p, ctypes.c_void_p])
    delete = bind('DeleteProcThreadAttributeList', [ctypes.c_void_p], None)
    create = bind('CreateProcessW', [w.LPCWSTR, w.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
                  w.BOOL, w.DWORD, ctypes.c_void_p, w.LPCWSTR,
                  ctypes.POINTER(STARTUPINFOEX), ctypes.POINTER(PROCESS_INFORMATION)])
    resume = bind('ResumeThread', [w.HANDLE], w.DWORD)
    wait = bind('WaitForSingleObject', [w.HANDLE, w.DWORD], w.DWORD)
    get_code = bind('GetExitCodeProcess', [w.HANDLE, ctypes.POINTER(w.DWORD)])
    terminate = bind('TerminateProcess', [w.HANDLE, w.UINT])
    terminate_job = bind('TerminateJobObject', [w.HANDLE, w.UINT])
    open_process = bind('OpenProcess', [w.DWORD, w.BOOL, w.DWORD], w.HANDLE)
    in_job = bind('IsProcessInJob', [w.HANDLE, w.HANDLE, ctypes.POINTER(w.BOOL)])
    query_job = bind('QueryInformationJobObject', [w.HANDLE, ctypes.c_int,
                     ctypes.c_void_p, w.DWORD, ctypes.c_void_p])
    def checked(value):
        if not value:
            raise ctypes.WinError(ctypes.get_last_error())
        return value

    job = checked(create_job(None, None))
    info = PROCESS_INFORMATION()
    attribute_list = None
    attributes_initialized = False
    inherited = []
    assigned = False
    members = {}

    def capture_members():
        # Keep handles open: this both provides an actual waitable exit barrier
        # and prevents PID reuse from confusing later snapshots.
        capacity = 16
        while capacity <= 65536:
            class PROCESS_LIST(ctypes.Structure):
                _fields_ = [('NumberOfAssignedProcesses', w.DWORD),
                            ('NumberOfProcessIdsInList', w.DWORD),
                            ('ProcessIdList', SIZE_T * capacity)]
            listing = PROCESS_LIST()
            if query_job(job, 3, ctypes.byref(listing), ctypes.sizeof(listing), None):
                break
            error = ctypes.get_last_error()
            if error != 234:  # ERROR_MORE_DATA: the job grew beyond this buffer.
                raise ctypes.WinError(error)
            capacity = max(capacity * 2, listing.NumberOfAssignedProcesses)
        else:
            raise RuntimeError('Windows test job exceeded the process tracking bound.')
        for pid in listing.ProcessIdList[:listing.NumberOfProcessIdsInList]:
            if pid in members:
                continue
            handle = open_process(0x100000 | 0x1000, False, pid)
            if not handle:
                error = ctypes.get_last_error()
                if error == 87:  # It already exited; final coverage must still match.
                    continue
                raise ctypes.WinError(error)
            owned = w.BOOL()
            try:
                checked(in_job(handle, job, ctypes.byref(owned)))
                if owned.value:
                    members[pid] = handle
                    handle = None
            finally:
                if handle:
                    close(handle)

    try:
        limits = EXTENDED_LIMIT()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        checked(set_job(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)))
        with open(os.devnull, 'rb') as stdin:
            handles = (msvcrt.get_osfhandle(stdin.fileno()), msvcrt.get_osfhandle(output.fileno()))
            for handle in handles:
                old = os.get_handle_inheritable(handle)
                os.set_handle_inheritable(handle, True)
                inherited.append((handle, old))
            size = SIZE_T()
            initialize(None, 1, 0, ctypes.byref(size))
            attribute_list = ctypes.create_string_buffer(size.value)
            checked(initialize(attribute_list, 1, 0, ctypes.byref(size)))
            attributes_initialized = True
            allowed_handles = (w.HANDLE * len(handles))(*handles)
            checked(update(attribute_list, 0, 0x20002, allowed_handles,
                           ctypes.sizeof(allowed_handles), None, None))
            startup = STARTUPINFOEX()
            startup.StartupInfo.cb = ctypes.sizeof(startup)
            startup.StartupInfo.dwFlags = 0x100  # STARTF_USESTDHANDLES
            startup.StartupInfo.hStdInput = handles[0]
            startup.StartupInfo.hStdOutput = startup.StartupInfo.hStdError = handles[1]
            startup.lpAttributeList = ctypes.cast(attribute_list, ctypes.c_void_p)
            environment = ctypes.create_unicode_buffer(
                '\0'.join(f'{key}={value}' for key, value in sorted(env.items(), key=lambda pair: pair[0].upper())) + '\0\0')
            arguments = ctypes.create_unicode_buffer(subprocess.list2cmdline([str(x) for x in command]))
            checked(create(str(command[0]), arguments, None, None, True,
                           0x4 | 0x400 | 0x80000, environment, str(Path(command[0]).parent),
                           ctypes.byref(startup), ctypes.byref(info)))
            # Restore inheritance immediately after creation, before the child runs.
            for handle, old in inherited:
                os.set_handle_inheritable(handle, old)
            inherited.clear()
            checked(assign(job, info.hProcess))
            assigned = True
            members[info.dwProcessId] = info.hProcess
            if resume(info.hThread) == 0xffffffff:
                raise ctypes.WinError(ctypes.get_last_error())
            deadline = time.monotonic() + max(timeout, 0)
            while True:
                capture_members()
                remaining = max(0, int((deadline - time.monotonic()) * 1000))
                status = wait(info.hProcess, min(10, remaining))
                if status == 0:
                    break
                if status != 0x102:
                    raise ctypes.WinError(ctypes.get_last_error())
                if time.monotonic() >= deadline:
                    raise subprocess.TimeoutExpired(command, timeout)
            code = w.DWORD()
            checked(get_code(info.hProcess, ctypes.byref(code)))
            return code.value
    finally:
        try:
            if assigned:
                capture_members()
                checked(terminate_job(job, 1))
                # ActiveProcesses can reach zero before process handles signal.
                # Wait the actual retained objects, including launcher descendants.
                deadline = time.monotonic() + 30
                for handle in members.values():
                    remaining = max(0, int((deadline - time.monotonic()) * 1000))
                    if wait(handle, remaining) != 0:
                        raise RuntimeError('Windows test process did not terminate within 30 seconds.')
                while True:
                    accounting = BASIC_ACCOUNTING()
                    checked(query_job(job, 1, ctypes.byref(accounting),
                                      ctypes.sizeof(accounting), None))
                    if accounting.ActiveProcesses == 0:
                        # A PID-list snapshot can miss a short-lived child or one
                        # created while termination starts. Never claim full drain
                        # without a retained, signaled handle for every job member.
                        if accounting.TotalProcesses != len(members):
                            raise RuntimeError(
                                'Cannot prove Windows test process-tree drain: '
                                f'{accounting.TotalProcesses} job processes, '
                                f'{len(members)} retained process handles.')
                        break
                    if time.monotonic() >= deadline:
                        raise RuntimeError('Windows test job did not drain within 30 seconds.')
                    time.sleep(0.02)
            elif info.hProcess:
                checked(terminate(info.hProcess, 1))
            if info.hProcess and wait(info.hProcess, 30000) != 0:
                raise RuntimeError('Windows test root did not terminate within 30 seconds.')
        finally:
            close(job)  # Fail-safe kernel termination even if querying the job fails.
            for pid, handle in members.items():
                if handle != info.hProcess:
                    close(handle)
            if info.hProcess:
                close(info.hProcess)
            if info.hThread:
                close(info.hThread)
            for handle, old in inherited:
                try:
                    os.set_handle_inheritable(handle, old)
                except OSError:
                    pass  # The local null-input file may already have closed.
            if attributes_initialized:
                delete(attribute_list)


def run_bounded(command, log, env, *, timeout=180):
    """Stop this launched test's whole process tree, including bootloader children."""
    start = time.monotonic()
    with Path(log).open('w', encoding='utf-8') as output:
        try:
            if sys.platform == 'win32':
                code = _run_windows_job(command, output, env, timeout)
            else:
                # Portable unit-test route, never a substitute for the Windows gate.
                import signal
                process = subprocess.Popen([str(item) for item in command], stdout=output,
                    stderr=subprocess.STDOUT, env=env, cwd=Path(command[0]).parent,
                    start_new_session=True)
                try:
                    code = process.wait(timeout=timeout)
                finally:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=30)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError('Single EXE acceptance timed out; inspect ' + str(log)) from error
    if code:
        raise RuntimeError(f'Single EXE acceptance exited {code}; inspect {log}')
    return dict(command=[str(item) for item in command], exit_code=code,
                elapsed_seconds=round(time.monotonic()-start, 3))

def verify_single_exe(executable, evidence, expected_manifest, *, allow_non_release=False):
    if sys.platform != 'win32':
        raise RuntimeError('Native Windows execution is required for single EXE acceptance.')
    executable = _regular_executable(executable).resolve()
    evidence = Path(evidence).resolve()
    evidence.mkdir(parents=True, exist_ok=False)
    validate_onefile_manifest(executable, expected_manifest, allow_non_release=allow_non_release)
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    records = []
    result = dict(passed=False, native_windows=True, host=platform.platform(),
                  executable_sha256=digest, frozen_suites=['fusion', 'facilities'],
                  external_python_removed_from_path=True, application_network_hook=True,
                  installation_performed=False, formal_feed_accepted=False, records=records)
    summary = evidence / 'Single_EXE_Verification.json'
    summary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='facs-single-exe-') as temporary:
        temp = Path(temporary)
        for label, folder in (('plain', 'portable'), ('unicode-space', '繁體中文 空白路徑')):
            destination = temp / folder
            destination.mkdir()
            copied = destination / executable.name
            shutil.copy2(executable, copied)
            if list(destination.iterdir()) != [copied]:
                raise RuntimeError('Portable launch must start with only the single EXE.')
            if hashlib.sha256(copied.read_bytes()).hexdigest() != digest:
                raise RuntimeError('Portable launch copy differs from the tested binary.')
            for suite in ('fusion', 'facilities'):
                report = evidence / (label + '-' + suite + '.json')
                command = [copied, '--' + suite + '-self-test', report]
                data_directory = evidence / 'data' / label / suite
                data_directory.mkdir(parents=True, exist_ok=False)
                record = run_bounded(command, report.with_suffix('.log'),
                                     offline_environment(data_directory))
                validate_acceptance(report, expected_commit=expected_manifest['commit'],
                                    expected_manifest=expected_manifest, expected_suite=suite,
                                    allow_non_release=allow_non_release)
                records.append(dict(record, path_case=label, suite=suite))
                summary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            if hashlib.sha256(copied.read_bytes()).hexdigest() != digest:
                raise RuntimeError('Portable executable changed during verification.')
    if hashlib.sha256(executable.read_bytes()).hexdigest() != digest:
        raise RuntimeError('Original single EXE changed during verification.')
    result['passed'] = True
    summary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result
