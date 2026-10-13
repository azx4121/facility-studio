"""Probe the shipped macOS application without changing its signatures.

Run only on Darwin. This checks the exact release bytes on a native runner;
it does not claim to reproduce a browser's quarantine or a user's macOS beta.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request


RELEASE_URL = (
    "https://github.com/azx4121/facility-studio/releases/download/"
    "v5.5.4-beta.1/Facility_Studio_V5_5_4_macOS_OneClick.zip"
)
RELEASE_SHA256 = "aef324d08815257848e4b8080023611b41a4a88eb2cdd03e6ee1a71e5a983b65"

# The RELEASE_* constants above are the pinned bootstrap runtime imported by
# build_native_release.py. Keep them separate from the public product probe.
PROBE_RELEASE_URL = (
    "https://github.com/azx4121/facility-studio/releases/download/"
    "v5.6.0-mac.4/Facility_Studio_V5_6_0_macOS_mac4.dmg"
)
PROBE_RELEASE_SHA256 = "e7d0033a3d3256b530539a6bdaa7d7d670ff043828dd69a5166e5e9ba2b679c8"


def source_hashes(app):
    """Verify the original Python modules are untouched by external tracing."""
    resources = Path(app) / 'Contents/Resources'
    paths = list((resources/'app').rglob('*.py')) + [resources/'bootstrap.py']
    return {str(path.relative_to(app)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths) if path.is_file()}


def crash_identity(text):
    """Apple .ips may contain separate header and payload JSON objects."""
    decoder = json.JSONDecoder()
    result = {}
    remaining = text.lstrip()
    for _ in range(2):
        try:
            value, end = decoder.raw_decode(remaining)
        except ValueError:
            break
        if isinstance(value, dict):
            result.update({key: value[key] for key in
                           ('pid', 'procName', 'procPath', 'app_name', 'captureTime', 'timestamp')
                           if key in value})
        remaining = remaining[end:].lstrip()
    return result


def faulting_thread_summary(text):
    """Surface the actual faulting native thread, not a sampled Python stack."""
    remaining = text.lstrip()
    decoder = json.JSONDecoder()
    payload = {}
    for _ in range(2):
        try:
            value, end = decoder.raw_decode(remaining)
        except ValueError:
            break
        if isinstance(value, dict) and 'threads' in value:
            payload = value
        remaining = remaining[end:].lstrip()
    threads, images = payload.get('threads', []), payload.get('usedImages', [])
    index = payload.get('faultingThread')
    if not isinstance(index, int) or not isinstance(threads, list) or not 0 <= index < len(threads):
        return None
    thread = threads[index]
    frames = []
    for frame in thread.get('frames', [])[:20]:
        row = {key: frame[key] for key in ('symbol', 'symbolLocation', 'imageOffset') if key in frame}
        image_index = frame.get('imageIndex')
        if isinstance(image_index, int) and isinstance(images, list) and 0 <= image_index < len(images):
            row['image'] = images[image_index].get('name', images[image_index].get('path', ''))
        frames.append(row)
    return dict(index=index, name=thread.get('name'), queue=thread.get('queue'),
                frames=frames, exception=payload.get('exception'))


def collect_probe_crashes(report_directory, output, process_records, app):
    """Copy only recent reports tied to a probe PID and this specific App.

    Never copy unrelated user reports. Candidate names are narrowed before
    reading; both time and PID/path identity are required before retention.
    """
    retained = []
    report_directory, output, app = Path(report_directory), Path(output), Path(app).resolve()
    if not report_directory.is_dir() or not process_records:
        return retained
    collected_at = time.time()
    for source in report_directory.glob('*.ips'):
        if not source.name.startswith(('FacilityStudio', 'Facility Studio', 'Python')):
            continue
        if source.is_symlink() or source.stat().st_size > 16*1024*1024:
            continue
        modified = source.stat().st_mtime
        candidates = [record for record in process_records
                      if record['started_at'] <= modified <= collected_at]
        if not candidates:
            continue
        text = source.read_text(encoding='utf-8', errors='replace')
        identity = crash_identity(text)
        if not isinstance(identity.get('pid'), int) or identity['pid'] <= 0:
            continue
        matches = [record for record in candidates if identity.get('pid') == record['pid']]
        captured = identity.get('captureTime', identity.get('timestamp', ''))
        try:
            captured_at = datetime.fromisoformat(captured.replace(' +', '+').replace(' -', '-')).timestamp()
        except (TypeError, ValueError, AttributeError):
            continue
        matches = [record for record in matches
                   if record['started_at'] <= captured_at <= record['finished_at']+30]
        path = identity.get('procPath', '')
        if not matches or not isinstance(path, str):
            continue
        # The external helper is outside the App by design. Its exact path,
        # PID and App argument must all match this probe's invocation record.
        matches = [record for record in matches if path.startswith(str(app)+'/')
                   or (record.get('diagnostic_executable') == path
                       and record.get('app_path') == str(app))]
        if not matches:
            continue
        output.mkdir(parents=True, exist_ok=True)
        target = output/('ProbeCrash_'+str(identity['pid'])+'_'+source.name)
        target.write_text(text, encoding='utf-8')
        retained.append(dict(file=target.name, identity=identity,
                             faulting_thread=faulting_thread_summary(text),
                             phases=[record['name'] for record in matches]))
    return retained


def sample_matches_process(text, pid, executable):
    """Retain a native sample only when its header identifies this helper."""
    process = re.search(r'^Process:\s+.*\[(\d+)\]\s*$', text, re.MULTILINE)
    path = re.search(r'^Path:\s+(.+?)\s*$', text, re.MULTILINE)
    return bool(process and path and int(process[1]) == pid
                and Path(path[1]).resolve() == Path(executable).resolve())


def sample_probe_process(process, executable, output, phase):
    """Sample only the still-running helper created by this exact probe."""
    executable, output = Path(executable).resolve(), Path(output)
    if process.poll() is not None:
        return dict(attempted=False, reason='Probe process already exited')
    if executable.name != 'FacilityStudioProbe':
        raise ValueError('Native sampling is restricted to the external diagnostic helper')
    candidate = output/(phase+'_sample-candidate.tmp')
    record = dict(attempted=True, pid=process.pid, executable=str(executable),
                  duration_seconds=3, retained=False)
    try:
        result = subprocess.run(['/usr/bin/sample', str(process.pid), '3', '-file', str(candidate)],
                                capture_output=True, text=True, timeout=8, check=False)
        record['returncode'] = result.returncode
        if candidate.is_file() and candidate.stat().st_size <= 16*1024*1024:
            text = candidate.read_text(encoding='utf-8', errors='replace')
            if sample_matches_process(text, process.pid, executable):
                target = output/(phase+'_native_sample.txt')
                candidate.replace(target)
                record.update(retained=True, file=target.name)
            else:
                record['reason'] = 'Sample header did not match the probe PID and exact helper path'
        else:
            record['reason'] = 'No bounded native sample file was produced'
    except (OSError, subprocess.TimeoutExpired) as error:
        record['reason'] = type(error).__name__
    finally:
        candidate.unlink(missing_ok=True)
    (output/(phase+'_native_sample.json')).write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument('--app', type=Path, help='Existing unchanged App; skips release download.')
    parser.add_argument('--package', type=Path, help='Local public mac.4 DMG, checked against its fixed SHA256.')
    parser.add_argument('--self-test-repeats', type=int, default=1)
    parser.add_argument('--switches', type=int, default=100)
    parser.add_argument('--focus-watchdog', action='store_true',
                        help='Run only the accelerated continuous watchdog probe; prior controls remain separate evidence.')
    parser.add_argument('--focused-repeats', type=int, default=3)
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Native application probing requires macOS.")
    if args.self_test_repeats < 1 or args.switches < 2 or args.focused_repeats < 1:
        parser.error('Use at least one original self-test and two language switches.')
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error('Choose a fresh output directory; previous evidence is retained.')
    output.mkdir(parents=True, exist_ok=True)
    observations = []
    selected_app = None
    reports = Path.home()/'Library/Logs/DiagnosticReports'
    retained_crashes = {}
    crash_collection_errors = []
    original_hashes = {}

    def checkpoint(active=None):
        if selected_app is not None:
            try:
                for crash in collect_probe_crashes(reports, output, observations, selected_app):
                    retained_crashes[crash['file']] = crash
            except OSError as error:
                crash_collection_errors.append(str(error))
        summary = dict(platform=platform.platform(), architecture=platform.machine(),
                       observations=observations, active_process=active,
                       original_source_hashes=original_hashes,
                       crash_reports=list(retained_crashes.values()),
                       crash_collection_errors=crash_collection_errors,
                       complete=False, created_at_utc=datetime.now(timezone.utc).isoformat())
        temporary = output/'Native_Probe_Checkpoint.json.tmp'
        temporary.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        temporary.replace(output/'Native_Probe_Checkpoint.json')

    def run(name, command, required=True, timeout=90, env=None, diagnostic=False):
        started = time.monotonic()
        wall_started = time.time()
        process = None
        native_sample = None
        try:
            with (output/(name+'.txt')).open('w', encoding='utf-8') as console:
                process = subprocess.Popen(command, stdout=console, stderr=subprocess.STDOUT, env=env)
                print(json.dumps(dict(phase=name, pid=process.pid, event='process.started')), flush=True)
                active = dict(name=name, pid=process.pid, started_at=wall_started)
                if diagnostic:
                    active.update(diagnostic_executable=str(Path(command[0]).resolve()),
                                  app_path=str(selected_app.resolve()))
                checkpoint(active)
                try:
                    # Reserve a bounded native sampling window before the
                    # parent's existing hard process deadline and kill.
                    status = process.wait(timeout=timeout-10 if diagnostic else timeout)
                except subprocess.TimeoutExpired:
                    if diagnostic and process.poll() is None:
                        print(json.dumps(dict(phase=name, pid=process.pid, event='native.sample.begin')), flush=True)
                        native_sample = sample_probe_process(process, command[0], output, name)
                        print(json.dumps(dict(phase=name, pid=process.pid, event='native.sample.end',
                                              retained=native_sample.get('retained', False))), flush=True)
                    remaining = max(.01, timeout-(time.monotonic()-started))
                    try:
                        status = process.wait(timeout=remaining)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                        status = 124
                        console.write('\nNative process exceeded its time limit.\n')
        except OSError as error:
            status = 125
            (output/(name+'.txt')).write_text(str(error)+'\n', encoding='utf-8')
        record = dict(name=name, required=required, returncode=status,
                      pid=process.pid if process else None,
                      started_at=wall_started, finished_at=time.time(),
                      passed=status == 0, seconds=round(time.monotonic() - started, 2))
        if native_sample is not None:
            record['native_sample'] = native_sample
        if diagnostic:
            record.update(diagnostic_executable=str(Path(command[0]).resolve()),
                          app_path=str(selected_app.resolve()))
        console_text = (output/(name+'.txt')).read_text(encoding='utf-8', errors='replace')
        record['periodic_dump_count'] = console_text.count('Timeout (0:00:')
        if '--periodic-dump' in command:
            record['requested_periodic_dump_seconds'] = int(command[command.index('--periodic-dump')+1])
        elif '--self-test' in command:
            record['requested_periodic_dump_seconds'] = 25  # Audited original self-test constant.
        if '--output' in command:
            diagnostic = Path(command[command.index('--output')+1])/'Diagnostic_Summary.json'
            if diagnostic.is_file():
                details = json.loads(diagnostic.read_text(encoding='utf-8'))
                record['completed_switches'] = details.get('completed_switches')
                record['active_language_switch_seconds'] = details.get('active_language_switch_seconds')
                record['periodic_exposure_verified'] = (
                    record.get('requested_periodic_dump_seconds', 0) > 0
                    and record['periodic_dump_count'] > 0
                    and (record['active_language_switch_seconds'] or 0) >= 25)
        observations.append(record)
        if status < 0:
            time.sleep(3)  # Preserve a fresh native crash report before another phase.
        checkpoint()
        print(json.dumps(record), flush=True)
        return status

    package_digest = None
    if args.app:
        app = args.app.resolve()
    else:
        package = args.package or output/'Original_mac4.dmg'
        if not args.package:
            request = urllib.request.Request(PROBE_RELEASE_URL, headers={'User-Agent': 'FacilityStudio-native-probe'})
            with urllib.request.urlopen(request, timeout=45) as response, package.open('wb') as destination:
                while block := response.read(1024*1024):
                    destination.write(block)
        package_digest = hashlib.sha256(package.read_bytes()).hexdigest()
        if package_digest != PROBE_RELEASE_SHA256:
            raise ValueError('Public mac.4 DMG SHA256 mismatch.')
        mount = output/'dmg-mounted'
        mount.mkdir()
        if run('dmg_attach', ['/usr/bin/hdiutil', 'attach', '-readonly', '-nobrowse',
                             '-noautoopen', '-mountpoint', str(mount), str(package.resolve())]):
            raise RuntimeError('Public DMG attachment failed.')
        app = output/'extracted/Facility Studio.app'
        try:
            if run('app_copy', ['/usr/bin/ditto', str(mount/'Facility Studio.app'), str(app)]):
                raise RuntimeError('Native App copy failed.')
        finally:
            run('dmg_detach', ['/usr/bin/hdiutil', 'detach', str(mount)])
    executable = app / "Contents/MacOS/FacilityStudio"
    if not executable.is_file():
        parser.error('The selected App has no FacilityStudio launcher.')
    before_hashes = source_hashes(app)
    original_hashes = before_hashes
    selected_app = app
    signature_before = run("apple_codesign_before", ["/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=4", str(app)])
    run("gatekeeper_assessment", ["/usr/sbin/spctl", "--assess", "--type", "execute", "--verbose=4", str(app)], required=False)
    for tool in (() if args.focus_watchdog else ("electrical", "duct", "gas", "lighting", "water", "air", "units")):
        run("native_tool_" + tool, [str(executable), "--tool", tool,
                                   "--report", str(output / (tool + "_report.txt"))])
    app_logs = Path.home() / "Library/Logs/Facility_Studio_V5_5"
    for index in range(0 if args.focus_watchdog else args.self_test_repeats):
        name = 'original_launcher_selftest_%d' % (index+1)
        run(name, [str(executable), '--self-test'], timeout=300)
        observation = observations[-1]
        for filename in ('Mac_Acceptance.json', 'Native_UITiming.json'):
            source = app_logs/filename
            if source.is_file() and source.stat().st_mtime >= observation['started_at']:
                shutil.copy2(source, output/(name+'_'+filename))
    framework = app/'Contents/Frameworks/Python.framework/Versions/3.13'
    helper = output/'FacilityStudioProbe'
    launcher_source = Path(__file__).with_name('native_diagnostic_launcher.c').resolve()
    compiled = run('diagnostic_launcher_compile', ['/usr/bin/clang', '-O2', '-Wall', '-Wextra', '-Werror',
                   str(launcher_source), '-o', str(helper)], timeout=90)
    signed = run('diagnostic_launcher_sign', ['/usr/bin/codesign', '--force', '--sign', '-', str(helper)]) if compiled == 0 else 125
    env = dict(os.environ, PYTHONHOME=str(framework), PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1')
    for name in ('PYTHONPATH', 'PYTHONSTARTUP', 'PYTHONUSERBASE', 'PYTHONEXECUTABLE', '__PYVENV_LAUNCHER__'):
        env.pop(name, None)
    script = Path(__file__).with_name('native_gui_diagnostic.py').resolve()
    runtime_validated = False
    if compiled == 0 and signed == 0:
        runtime_output = output/'instrumented_runtime'
        runtime_validated = run('instrumented_runtime', [str(helper), str(app), str(script),
            '--app', str(app), '--output', str(runtime_output), '--mode', 'runtime'],
            env=env, diagnostic=True) == 0
        for source in runtime_output.glob('*'):
            if source.suffix in ('.json', '.txt'):
                shutil.copy2(source, output/('instrumented_runtime_'+source.name))
    planned = [('continuous', 1)] * args.focused_repeats if args.focus_watchdog else [
        ('continuous', 0), ('continuous', 25), ('continuous', 1), ('segmented', 25), ('selftest', 25)]
    for attempt, (mode, periodic) in enumerate(planned if runtime_validated else (), 1):
        name = 'instrumented_'+mode+'_dump'+str(periodic)
        if args.focus_watchdog:
            name += '_attempt'+str(attempt)
        destination = output/name
        run(name, [str(helper), str(app), str(script), '--app', str(app), '--output', str(destination),
                   '--mode', mode, '--switches', str(args.switches), '--periodic-dump', str(periodic)],
            timeout=300 if mode == 'selftest' else 180, env=env, diagnostic=True)
        for source in destination.glob('*.txt'):
            shutil.copy2(source, output/(name+'_'+source.name))
        for source in destination.glob('*.json'):
            shutil.copy2(source, output/(name+'_'+source.name))
    # Only this probe's processes and App path qualify for crash retention.
    if any(record['returncode'] < 0 for record in observations):
        time.sleep(5)  # CrashReporter writes asynchronously after process exit.
    checkpoint()
    crashes = list(retained_crashes.values())
    signature_after = run('apple_codesign_after', ['/usr/bin/codesign', '--verify', '--deep', '--strict', '--verbose=4', str(app)])
    after_hashes = source_hashes(app)
    result = dict(
        platform=platform.platform(), architecture=platform.machine(),
        release_url=PROBE_RELEASE_URL if not args.app else None,
        release_sha256=package_digest, quarantine_reproduced=False,
        original_source_hashes=before_hashes, sources_unchanged=before_hashes == after_hashes,
        signatures_modified_by_probe=False,
        external_diagnostic_runtime_validated=runtime_validated,
        focused_watchdog_probe=args.focus_watchdog,
        original_launcher_control_runs=0 if args.focus_watchdog else args.self_test_repeats,
        prior_control_evidence_reused=args.focus_watchdog,
        signature_verification_before=signature_before, signature_verification_after=signature_after,
        observations=observations, crash_reports=crashes,
        crash_collection_errors=crash_collection_errors,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        diagnostic_entrypoint_caveat='Instrumented variants use an external C helper embedding the original App libpython/home, with sys.executable identifying the original launcher. Cocoa main-bundle identity still differs from the original signed executable.',
        passed=runtime_validated and before_hashes == after_hashes and all(o["passed"] for o in observations if o["required"]),
    )
    (output / "Native_Probe.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
