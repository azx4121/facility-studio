"""Validate exact producer bytes on the independent Windows 2025 host.

Python is a test controller only. Existing helpers launch the EXE with a PATH
containing only Windows/System32 and Windows, from fresh EXE-only directories.
System Python launchers may remain there. Every retained job process image must
match the copied EXE; missing process coverage or image queries fail closed.
The application audit hook is not OS network isolation.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from inspect_python_launch import inspect_launch_environment

from private_draft_transfer import (EXE_NAME, MANIFEST_NAME, SOURCE_FIELDS, GateError,
                                    Scope, parse_json, regular_file, require, sha256,
                                    validate_manifest)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--frozen-runner', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--bytes', type=int, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--release-id', type=int, required=True)
    parser.add_argument('--asset-id', type=int, required=True)
    parser.add_argument('--run-id', type=int, required=True)
    parser.add_argument('--run-attempt', type=int, required=True)
    parser.add_argument('--workflow-commit', required=True)
    args = parser.parse_args(argv)
    require(sys.platform == 'win32', 'Native Windows 2025 is mandatory.')
    require(sys.getwindowsversion().build == 26100, 'Expected Windows Server 2025 OS build 26100.')
    require(os.environ.get('GITHUB_SHA') == args.workflow_commit, 'Wrong workflow commit context.')
    sys.dont_write_bytecode = True
    exe = regular_file(args.download / EXE_NAME)
    transfer_path = regular_file(args.download / MANIFEST_NAME)
    require(set(path.name for path in args.download.iterdir()) == {EXE_NAME, MANIFEST_NAME},
            'Download directory contains unexpected files.')
    require(sha256(exe) == args.sha256 and exe.stat().st_size == args.bytes, 'Downloaded EXE identity mismatch.')
    require(sha256(transfer_path) == args.manifest_sha256, 'Downloaded manifest identity mismatch.')
    scope = Scope(args.run_id, args.run_attempt, args.workflow_commit)
    transfer = validate_manifest(parse_json(transfer_path.read_bytes()), scope,
        args.release_id, args.bytes, args.sha256)
    source = args.candidate.resolve()
    integration = source / 'integration'
    sys.path.insert(0, str(integration))
    from source_provenance import expected_source_manifest, verify_source_unchanged
    from onefile_validation import offline_environment, verify_single_exe, valid_process_image_audit
    expected = expected_source_manifest(source, 'windows')
    require(transfer['source_manifest'] == {key: expected[key] for key in SOURCE_FIELDS},
            'Independent reconstructed source differs from producer provenance.')
    evidence = args.evidence.absolute()
    evidence.mkdir(parents=True, exist_ok=False)
    summary_file = evidence / 'Independent_Windows_2025.json'
    summary = {'passed': False, 'native_windows': True, 'host': platform.platform(),
        'os_build': sys.getwindowsversion().build, 'producer_run_id': args.run_id,
        'producer_run_attempt': args.run_attempt, 'workflow_commit': args.workflow_commit,
        'release_id': args.release_id, 'asset_id': args.asset_id,
        'executable_sha256': args.sha256, 'same_producer_bytes': True,
        'source_manifest': transfer['source_manifest'], 'source_provenance_matches': True,
        'launch_path_policy': 'windows-system-directories-only',
        'external_python_absence_claimed': False,
        'standalone_process_image_audit_required': True,
        'standalone_process_image_audit_passed': False,
        'application_launch_attempted': False,
        'application_network_hook': True, 'os_network_isolation_claimed': False,
        'python_installed_on_controller': True, 'installation_performed': False,
        'public_distribution_authorized_by_this_script': False,
        'binary_published': False, 'formal_feed_accepted': False}

    def persist():
        summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

    # Neither application launches nor their logs can inherit these CI credentials.
    # This is a separate test step with no GH_TOKEN configured in the workflow.
    for key in ('GH_TOKEN', 'GITHUB_TOKEN', 'ACTIONS_RUNTIME_TOKEN',
                'ACTIONS_ID_TOKEN_REQUEST_TOKEN', 'ACTIONS_ID_TOKEN_REQUEST_URL'):
        os.environ.pop(key, None)
    persist()
    try:
        test_env = offline_environment(evidence / 'path-check-data')
        preflight = inspect_launch_environment(test_env)
        summary['python_launch_preflight'] = preflight
        persist()  # Preserve the resolved paths even when the gate rejects this host.
        windows = Path(os.environ.get('SystemRoot', 'C:/Windows'))
        require(test_env['PATH'] == str(windows / 'System32') + os.pathsep + str(windows),
                'Launch PATH was not stripped to Windows directories.')
        require(not preflight['unsafe_path_entries'], 'Unsafe relative or empty launch PATH entry.')
        require(test_env.get('FACILITY_TEST_REQUIRE_SAME_IMAGE_CHILDREN') == '1',
                'Standalone process-image audit is not enabled.')
        summary['application_launch_attempted'] = True
        persist()
        frozen = verify_single_exe(exe, evidence / 'single-exe', expected)
        require(frozen.get('passed') is True and frozen.get('executable_sha256') == args.sha256
            and len(frozen.get('records', [])) == 4
            and frozen.get('standalone_process_image_audit_passed') is True
            and all(valid_process_image_audit(row.get('process_image_audit'), row['command'][0])
                    for row in frozen.get('records', [])),
                'Independent frozen suites failed or used different bytes.')
        runner = regular_file(args.frozen_runner)
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1',
                           FACILITY_CAPTURE_SYNTHETIC_UI='1')
        command = [sys.executable, '-B', str(runner), '--exe', str(exe),
            '--sha256', args.sha256, '--candidate', str(source),
            '--evidence', str(evidence / 'external-frozen'), '--screenshots']
        with (evidence / 'external-frozen-controller.log').open('w', encoding='utf-8') as log:
            result = subprocess.run(command, cwd=source, env=environment, stdout=log,
                                    stderr=subprocess.STDOUT, timeout=3600)
        require(result.returncode == 0, 'Independent external CLI/capture controller failed.')
        external = parse_json((evidence / 'external-frozen' / 'Frozen_External_Checks.json').read_bytes())
        require(external.get('passed') is True and external.get('original_exe_unchanged') is True
            and external.get('executable_sha256') == args.sha256
            and external.get('standalone_process_image_audit_passed') is True
            and external.get('screenshots_requested') is True and len(external.get('screenshots', [])) == 8
            and len(external.get('commands', [])) == 118,
            'Independent CLI and eight startup captures did not fully pass.')
        all_external = external['commands'] + [row.get('process', {}) for row in external['screenshots']]
        require(all(valid_process_image_audit(row.get('process_image_audit'), row['command'][0]) for row in all_external),
                'Independent process-image coverage is incomplete.')
        verify_source_unchanged(source, 'windows', expected)
        require(sha256(exe) == args.sha256 and sha256(transfer_path) == args.manifest_sha256,
                'Transferred files changed during validation.')
        summary.update(passed=True, original_exe_unchanged=True,
            standalone_process_image_audit_passed=True,
            frozen_suite_records=len(frozen.get('records', [])),
            external_commands=len(external['commands']), startup_captures=len(external['screenshots']))
    except Exception as error:
        summary['error'] = str(error)
        raise
    finally:
        summary['original_exe_unchanged'] = sha256(exe) == args.sha256
        if not summary['original_exe_unchanged']:
            summary['passed'] = False
        persist()
    print(json.dumps(summary))


if __name__ == '__main__':
    try:
        main()
    except GateError as error:
        print('INDEPENDENT VALIDATION STOPPED: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
