"""Fail-closed final release preparation. No external action occurs on import.

No rebuild, private-release update, deletion, replacement, or automatic retry.
Publication requires explicit `publish`, a pinned lock, and pixel-inspection receipt.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
from types import SimpleNamespace
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
import cold_receipts
import process_receipts
import semantic_receipts
import native_process_receipts

HERE = Path(__file__).resolve().parent
# Existing audited transfer transport, not vendored or changed by this package.
TRANSFER = HERE.parent / 'private_transfer' / 'private_draft_transfer.py'
if not TRANSFER.exists():
    TRANSFER = HERE.parent / 'facs-v22-private-transfer' / 'private_draft_transfer.py'
if hashlib.sha256(TRANSFER.read_bytes()).hexdigest() != 'be2815ea0bafa69e5158c1e9f7e59cd9c96ba462ef70323e5eb83b0d62fc3101':
    raise RuntimeError('Approved private transfer transport has changed; review before using credentials.')
spec = importlib.util.spec_from_file_location('publication_transfer', TRANSFER)
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
require, GateError = t.require, t.GateError
REPO, API, WEB, UPLOADS = t.REPOSITORY, t.API, t.WEB, t.UPLOADS
EXE = t.EXE_NAME
SKIP = 'test_tk9_side_buttons_do_not_scroll_page'
SOURCE_COMMANDS = {'runtime-tk', 'full-integration', 'capacity-isolated', 'safety-isolated',
    'lighting-widgets', 'engineering-audit', 'report-interactions', 'dashboard-formulas',
    'dashboard-reports', 'dashboard-widgets', 'tutorial'}
ASSETS = {EXE, 'SHA256SUMS.txt', 'Windows_Verification.txt'}
SOURCE_STEPS = ['Untouched native-menu startup at frozen and small desktop sizes',
    'Native bilingual menus and selector fit at both desktop sizes',
    'Cold real-entry native startup at frozen and small desktop sizes',
    'Full native suites with verified large desktop and sys capture',
    'Corrected fresh Tcl and Tk bootstrap contract',
    'Repeated isolated, module-context and predecessor Tk lifecycle checks',
    'Real 1024 by 768 header, wheel and dialog reachability checks',
    'Preserve every outcome without publishing binaries',
    'Native same-image and foreign-image process audit controls']
PRIVATE_STEPS = {
 '2022': ['Require untouched native-menu startup before expensive EXE build',
          'Require native bilingual menus and selector fit before EXE build',
          'Require cold real-entry startup at both desktop sizes before EXE build',
          'Build once and pass Windows 2022 frozen checks before private transfer',
          'Stage only in verified non-public Windows draft',
          'Retain producer screenshots and diagnostics, never binary assets',
          'Require native process-image controls before EXE build'],
 '2025': ['Require native process-image controls before independent EXE validation',
          'Authenticated exact-ID download and anonymous visibility checks',
          'Test identical EXE on Windows 2025 with same-image process audit',
          'Recheck draft is still anonymous-unreadable after native testing',
          'Report same-byte result only',
          'Retain consumer screenshots and diagnostics, never downloaded assets'],
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pinned_json(path, expected):
    require(isinstance(expected, str) and t.DIGEST.fullmatch(expected), 'Missing trusted SHA-256.')
    raw = t.regular_file(path).read_bytes()
    require(digest(raw) == expected, 'Pinned local file changed.')
    return t.parse_json(raw)


def positive(value):
    require(type(value) is int and value > 0, 'Positive integer ID required, not a placeholder or boolean.')
    return value


def safe_relative(value):
    require(isinstance(value, str) and value and '\\' not in value and ':' not in value,
            'Unsafe evidence path.')
    path = PurePosixPath(value)
    require(not path.is_absolute() and all(x not in {'', '.', '..'} for x in value.split('/')),
            'Unsafe evidence path.')
    return value


def validate_lock(lock):
    require(lock.get('schema_version') == 1 and lock.get('repository') == REPO,
            'Wrong publication lock schema/repository.')
    require(t.COMMIT.fullmatch(lock.get('publisher_commit', '')) is not None,
            'Pin the final reviewed publisher commit before running.')
    for role in ('source', 'private'):
        run = lock[role + '_run']
        positive(run['id']); positive(run['attempt']); positive(run['workflow_id'])
        require(isinstance(run.get('commit'), str) and t.COMMIT.fullmatch(run['commit']), 'Pin exact tested workflow commit.')
        require(set(run['jobs']) == {'2022', '2025'}, 'Both exact native job IDs are required.')
        require(set(lock[role + '_artifacts']) == {'2022', '2025'}, 'Both diagnostic artifacts are required.')
        for version in ('2022', '2025'):
            job = run['jobs'][version]
            positive(job['id']); positive(job['attempt'])
            require(job['attempt'] <= run['attempt'], 'Invalid producer/job attempt.')
            item = lock[role + '_artifacts'][version]
            positive(item['id']); safe_relative(item['zip'])
            require(t.DIGEST.fullmatch(item.get('sha256', '')) is not None, 'Pin raw diagnostic ZIP SHA-256.')
    identity = lock['source_identity']
    require(isinstance(identity.get('snapshot_commit'), str) and t.COMMIT.fullmatch(identity['snapshot_commit']),
            'Pin the final revalidated source snapshot, not an earlier candidate.')
    for kind in ('provenance', 'source_manifest'):
        safe_relative(identity[kind]['file'])
        require(t.DIGEST.fullmatch(identity[kind].get('sha256', '')), 'Pin independently reviewed source identity files.')
    require(type(identity.get('passed_tests')) is int and identity['passed_tests'] >= 8493
        and type(identity.get('passed_subtests')) is int and identity['passed_subtests'] >= 90,
            'Pin complete final source test totals; earlier reduced suites cannot qualify.')
    candidate = lock['candidate']
    for key in ('release_id', 'asset_id', 'manifest_asset_id', 'bytes', 'manifest_bytes', 'producer_attempt'):
        positive(candidate[key])
    require(candidate['asset_id'] != candidate['manifest_asset_id'], 'Candidate asset IDs must be distinct.')
    require(candidate['producer_attempt'] == lock['private_run']['jobs']['2022']['attempt'],
            'Producer attempt differs from exact successful build job.')
    for key in ('sha256', 'manifest_sha256'):
        require(t.DIGEST.fullmatch(candidate.get(key, '')) is not None, 'Missing trusted candidate hash.')
    require(0 < candidate['bytes'] <= 2 * 1024**3 and candidate['manifest_bytes'] <= 4 * 1024**2,
            'Candidate byte lengths exceed bounds.')
    ids = [x['id'] for role in ('source', 'private') for x in lock[role + '_artifacts'].values()]
    require(len(set(ids)) == 4, 'Diagnostic artifact IDs must be distinct.')
    return lock


class Evidence:
    """Read exact members in place. No archive member is executed or extracted."""
    def __init__(self, path, expected):
        path = t.regular_file(path)
        require(t.sha256(path) == expected, 'Diagnostic archive hash mismatch.')
        self.archive = zipfile.ZipFile(path)
        files = [i for i in self.archive.infolist() if not i.is_dir()]
        require(0 < len(files) <= 20000 and sum(i.file_size for i in files) <= 512 * 1024**2,
                'Diagnostic archive exceeds review bounds.')
        self.names = {i.filename for i in files}
        require(len(self.names) == len(files), 'Duplicate archive members.')
        for item in self.archive.infolist():
            safe_relative(item.filename.rstrip('/'))
            require(not stat.S_ISLNK(item.external_attr >> 16) and not item.flag_bits & 1,
                    'Linked or encrypted artifact member.')
            require(PurePosixPath(item.filename).suffix.lower() not in {'.exe', '.dll', '.pyd', '.so', '.dylib'},
                    'Binary asset found in diagnostic archive.')

    def read(self, name):
        safe_relative(name)
        require(name in self.names, 'Required exact diagnostic member missing.')
        require(self.archive.getinfo(name).file_size <= 32 * 1024**2, 'Oversized diagnostic member.')
        return self.archive.read(name)

    def json(self, name):
        return t.parse_json(self.read(name))

    def close(self):
        self.archive.close()


def junit(evidence, name, case_count, skip_names=(), reported_tests=None):
    raw = evidence.read(name)
    require(b'<!DOCTYPE' not in raw and b'<!ENTITY' not in raw, 'Unsafe JUnit document.')
    doc = ET.fromstring(raw)
    suites, cases = list(doc.iter('testsuite')), list(doc.iter('testcase'))
    require(len(suites) == 1 and len(cases) == case_count, 'Unexpected JUnit suite/case count.')
    suite = suites[0]
    require(suite.get('errors') == '0' and suite.get('failures') == '0'
        and int(suite.get('skipped', '-1')) == len(skip_names)
        and int(suite.get('tests', '-1')) == (reported_tests or case_count), 'JUnit aggregate failure/count mismatch.')
    require(not list(doc.iter('error')) and not list(doc.iter('failure')), 'JUnit contains a failure.')
    require([c.get('name') for c in cases if c.find('skipped') is not None] == list(skip_names),
            'Unexpected or missing expected skip.')
    return cases


def measured_display_gate(evidence, display_name, width, height, target, selector=None):
    display = evidence.json(display_name)
    size = [width, height]
    after, tk = display.get('after', {}), display.get('tk', {})
    require(display.get('native_windows') is True and display.get('passed') is True
        and display.get('exact') is True and display.get('requested') == size
        and display.get('frozen_binary_tested') is False
        and after.get('screen') == size and tk.get('screen') == size and tk.get('windowing') == 'win32'
        and after.get('current_mode', {}).get('width') == width
        and after.get('current_mode', {}).get('height') == height
        and display.get('selected', {}).get('width') == width
        and display.get('selected', {}).get('height') == height
        and all(type(display.get(key)) is int and display[key] == 0
            for key in ('test_return', 'apply_return', 'command_exit_code', 'restore_return')),
            'Untouched startup was not tested on the required measured exact native desktop.')
    work = after.get('work_area', [])
    require(len(work) == 4 and all(type(n) is int for n in work)
        and 0 <= work[0] < work[2] <= width and 0 <= work[1] < work[3] <= height,
            'Native startup work-area measurement is invalid.')
    command = display.get('command', [])
    require(isinstance(command, list) and sum(isinstance(x, str) and x.replace('\\', '/').endswith(target) for x in command) == 1
        and '--capture=sys' in command
        and (selector is None or any(command[index:index+2] == ['-k', selector] for index in range(len(command)))),
            'Native display receipt does not target the required untouched startup tests.')

    return work


def native_startup_gate(evidence, junit_name, display_name, width, height, cold_source=None):
    cases = junit(evidence, junit_name, 16)
    expected = {f'[{launch}-{entry}-{language}]' for launch in range(4)
                for entry in ('simple', 'workbench') for language in ('en', 'zh-Hant')}
    require(len({c.get('name') for c in cases}) == 16
        and all(c.get('classname', '').endswith('test_windows_cold_startup' if cold_source is not None else 'test_windows_startup_placement')
            and (cold_receipts.CASE.fullmatch(c.get('name', '')) is not None if cold_source is not None else c.get('name', '').startswith('test_native_untouched_')) for c in cases)
        and {c.get('name', '')[c.get('name', '').find('['):] for c in cases} == expected,
            'Native startup must cover all sixteen distinct untouched launches, modes, and languages.')
    work = measured_display_gate(evidence, display_name, width, height,
        '/test_windows_cold_startup.py' if cold_source is not None else '/test_windows_startup_placement.py',
        'cold_real_entry' if cold_source is not None else 'native_untouched')

    if cold_source is not None:
        expected_hashes = cold_receipts.hashes(cold_source)
        for case in cases:
            match = cold_receipts.CASE.fullmatch(case.get('name', ''))
            props = case.findall('./properties/property')
            readouts = [prop for prop in props if prop.get('name') == 'cold_startup_readout']
            require(len(readouts) == 1, 'Each cold case needs exactly one independent readout.')
            report = t.parse_json(readouts[0].get('value', '').encode('utf-8'))
            cold_receipts.validate_report(report, match.group(2), match.group(3), expected_hashes,
                                          width, height, require)
            require(report['settled']['work'] == work, 'Cold native work area differs from display receipt.')


def process_preflight_gate(evidence, prefix=''):
    try:
        native_process_receipts.verify(evidence.read(prefix + 'process-image-preflight.xml'))
    except (ValueError, TypeError, KeyError):
        raise GateError('Native same-image positive/foreign-image negative controls failed.') from None
    process_receipts.launch_preflight(evidence.json(prefix + 'python-launch-preflight.json'), require)


def semantic_gate(evidence, width, height, prefix=''):
    label = f'{width}-{height}'
    measured_display_gate(evidence, prefix + f'native-language-fit-display-{label}.json', width, height,
        '/test_windows_english_startup_native.py')
    try:
        semantic_receipts.verify(evidence.read(prefix + f'native-language-fit-{label}.xml'),
                                 'frozen1920' if width == 1920 else 'small1024')
    except (ValueError, TypeError, KeyError):
        raise GateError('Native bilingual menu or selector text/vertical bounds failed.') from None


def source_gate(evidence, version, trusted, identity, source_manifest):
    process_preflight_gate(evidence)
    for width, height in ((1920, 1080), (1024, 768)):
        label = f'{width}-{height}'
        native_startup_gate(evidence, f'startup-placement-{label}.xml', f'startup-display-{label}.json', width, height)
        native_startup_gate(evidence, f'cold-startup-placement-{label}.xml', f'cold-startup-display-{label}.json', width, height, source_manifest)
        semantic_gate(evidence, width, height)
    summary = evidence.json('reviewed-SUMMARY.json')
    for key in ('passed', 'native_windows', 'native_process_passed', 'unexpected_skips_rejected', 'original_failures_preserved'):
        require(summary.get(key) is True, 'Source acceptance flag missing.')
    require(summary.get('command_exit') == 0 and summary.get('native_process_count') == 8
        and summary.get('skips') == [SKIP] and summary.get('allowed_skip') == SKIP,
            'Incomplete source acceptance summary.')
    require(summary.get('host', '').startswith('Windows-' + version + 'Server-10.0.'), 'Source OS mismatch.')
    require(evidence.json('reviewed-source-provenance.json') == trusted, 'Source/correction provenance mismatch.')
    receipts = evidence.json('command-receipts.json')
    require(len(receipts) == 11 and {r.get('name') for r in receipts} == SOURCE_COMMANDS
        and all(type(r.get('exit_code')) is int and r['exit_code'] == 0 for r in receipts),
            'All 11 source commands must pass.')
    total = identity['passed_tests'] + 1
    cases = junit(evidence, 'full-integration.xml', total, [SKIP], total + identity['passed_subtests'])
    native = [c for c in cases if c.get('classname', '').endswith('test_onefile_process_native')]
    require(len(native) == 8 and all(c.find('skipped') is None for c in native), 'Native process tests missing.')
    summary_pattern = (str(identity['passed_tests']) + r' passed, 1 skipped, \d+ warnings, '
        + str(identity['passed_subtests']) + ' subtests passed').encode('ascii')
    require(re.search(summary_pattern, evidence.read('full-integration.log')),
            'Complete source test totals not present.')
    junit(evidence, 'corrected-tcl-bootstrap.xml', 100)
    junit(evidence, 'small-screen.xml', 3)
    small = evidence.json('display-small.json')
    require(small.get('passed') is True and small.get('native_windows') is True
        and small.get('requested') == [1024, 768] and small.get('exact') is True,
            'Measured small-screen gate is missing.')
    life = evidence.json('tk-lifecycle/SUMMARY.json')
    attempts = life.get('attempts', [])
    require(life.get('passed') is True and life.get('native_windows') is True
        and life.get('source_python_files_unchanged') is True and len(attempts) == 9
        and {(a.get('round'), a.get('group')) for a in attempts}
            == {(r, g) for r in (1, 2, 3) for g in ('isolated', 'module-context', 'prefix')},
            'Incomplete lifecycle matrix.')
    for row in attempts:
        report = row.get('junit', {})
        require(row.get('passed') is True and type(row.get('exit_code')) is int and row['exit_code'] == 0
            and report.get('accepted') is True and report.get('failures') == 0 and report.get('errors') == 0
            and report.get('required_targets_missing') == [], 'Lifecycle attempt did not pass.')
        expected = [] if row['group'] == 'isolated' else [SKIP]
        require([x.get('name') for x in report.get('exceptional_results', [])] == expected
            and report.get('skipped') == len(expected), 'Unexpected lifecycle skip.')


def frozen_gate(data, sha, expected_exe_name=EXE):
    process_receipts.summary(data, require)
    records = data.get('records', [])
    require(data.get('passed') is True and data.get('native_windows') is True
        and data.get('executable_sha256') == sha and len(records) == 4
        and {(r.get('path_case'), r.get('suite')) for r in records}
            == {(p, s) for p in ('plain', 'unicode-space') for s in ('fusion', 'facilities')}
        and all(type(r.get('exit_code')) is int and r['exit_code'] == 0 for r in records),
            'All four same-byte frozen suite runs must pass.')
    for row in records:
        process_receipts.record(row, expected_exe_name, require)


def expected_external_commands():
    tools = ('electrical', 'duct', 'gas', 'lighting', 'water', 'air', 'units', 'cleanroom',
             'heat_loads', 'pumps', 'liquid', 'vacuum')
    matrix = {}
    for case in ('plain', 'unicode-space'):
        labels = {}
        for language in ('en', 'zh-Hant'):
            labels.update({language + '-tool-' + tool: 0 for tool in tools})
            labels.update({language + '-' + action: 0 for action in ('template-export', 'template-import', 'equipment-csv', 'gui-smoke')})
            labels.update({language + '-disabled-template-' + state: 2 for state in ('fresh', 'stale')})
        labels.update({'electrical-hp': 0, 'electrical-zero': 0, 'project-json-roundtrip': 0})
        labels.update({action + str(n): 0 for n in range(3) for action in ('project-default-save-', 'project-read-')})
        labels.update({'reject-' + kind + '-' + state: 2 for kind in ('unknown-key', 'bad-number',
            'negative-load', 'invalid-json', 'nonfinite-json', 'project', 'equipment') for state in ('fresh', 'stale')})
        require(len(labels) == 59, 'Internal external-command coverage inventory is incomplete.')
        matrix.update({case + '/' + name: code for name, code in labels.items()})
    return matrix


def external_gate(evidence, prefix, sha, version):
    data = evidence.json(prefix + '/Frozen_External_Checks.json')
    process_receipts.summary(data, require)
    for key in ('passed', 'native_windows', 'original_exe_unchanged', 'screenshots_requested'):
        require(data.get(key) is True, 'External frozen acceptance flag missing.')
    require(data.get('executable_sha256') == sha and data.get('os_network_isolation_claimed') is False
        and data.get('engineering_or_formal_feed_approval_claimed') is False,
            'Frozen identity/scope mismatch.')
    commands = data.get('commands', [])
    expected_commands = expected_external_commands()
    require(len(commands) == 118 and {x.get('label') for x in commands} == set(expected_commands)
        and all(x.get('passed') is True and type(x.get('exit_code')) is int
            and type(x.get('expected_exit')) is int
            and x['exit_code'] == x['expected_exit'] == expected_commands[x['label']] for x in commands),
            'All 118 distinct expected external commands and exit outcomes must pass.')
    for row in commands:
        process_receipts.record(row, EXE, require)
    artifacts = data.get('artifacts', [])
    by_path = {}
    for artifact in artifacts:
        path = artifact.get('path')
        require(isinstance(path, str) and not any(ord(c) < 32 or ord(c) == 127 for c in path),
                'Unsafe external artifact path.')
        path = safe_relative(path.replace('\\', '/'))
        require(path not in by_path, 'Duplicate external artifact paths.')
        by_path[path] = artifact
    require(len(by_path) == len(artifacts), 'Duplicate external artifact paths.')
    captures = data.get('screenshots', [])
    require(len(captures) == 8, 'Eight actual startup screenshots are required per OS.')
    result = []
    for path_case in ('plain', 'unicode-space'):
        for language in ('en', 'zh-Hant'):
            for mode in ('simple', 'full'):
                suffix = f'{path_case}/{language}-{mode}-startup/startup.png'
                matches = [c for c in captures if c.get('screenshot', '').replace('\\', '/').endswith('/' + suffix)]
                require(len(matches) == 1, 'Startup screenshot matrix is incomplete or duplicated.')
                row = matches[0]
                process_receipts.record(row.get('process'), EXE, require)
                require(row.get('passed') is True and row.get('closed_cleanly') is True
                    and row.get('executable_sha256') == sha and row.get('language_argument') == language
                    and row.get('mode_argument') == mode and row.get('process', {}).get('exit_code') == 0,
                        'Startup capture/close did not pass.')
                require(suffix in by_path, 'Startup screenshot artifact is missing.')
                raw = evidence.read(prefix + '/' + suffix)
                value = digest(raw)
                require(raw.startswith(b'\x89PNG\r\n\x1a\n') and row.get('screenshot_sha256') == value
                    and by_path[suffix].get('sha256') == value and by_path[suffix].get('bytes') == len(raw),
                        'Screenshot pixels differ from captured/tested evidence.')
                result.append({'os': version, 'path': prefix + '/' + suffix, 'sha256': value})
    return result


def private_gate(evidence, version, lock, trusted, source_manifest):
    candidate = lock['candidate']
    sha = candidate['sha256']
    process_preflight_gate(evidence, '0-facs-v22-evidence/')
    provenance = evidence.json('0-facs-v22-evidence/reviewed-source-provenance.json')
    expected = dict(trusted, workflow_commit=lock['private_run']['commit'])
    require(provenance == expected, 'Build/consumer source differs from complete native source acceptance.')
    if version == '2022':
        native_startup_gate(evidence, '0-facs-v22-evidence/prebuild-startup-placement.xml',
            '0-facs-v22-evidence/prebuild-startup-display.json', 1920, 1080)
        for width, height in ((1920, 1080), (1024, 768)):
            label = f'{width}-{height}'
            native_startup_gate(evidence, f'0-facs-v22-evidence/prebuild-cold-startup-placement-{label}.xml',
                f'0-facs-v22-evidence/prebuild-cold-startup-display-{label}.json', width, height, source_manifest)
            semantic_gate(evidence, width, height, '0-facs-v22-evidence/prebuild-')
        receipt = evidence.json('0-facs-v22-evidence/candidate-build-result.json')
        require(receipt.get('build_exit') == 0 and receipt.get('extended_exit') == 0
            and receipt.get('unchanged') is True and receipt.get('executable_sha256') == sha
            and receipt.get('executable_bytes') == candidate['bytes'], 'Producer build receipt mismatch.')
        built = evidence.json('1-evidence/Build_Manifest.json')
        require({k: built.get(k) for k in t.SOURCE_FIELDS} == source_manifest,
                'Built source inventory differs from independently pinned original plus reviewed corrections.')
        frozen_gate(evidence.json('1-evidence/single-exe/Single_EXE_Verification.json'), sha, 'Facility Studio 5.7.3.exe')
        prefix = '0-facs-v22-evidence/external-frozen'
    else:
        receipt = evidence.json('1-facs-v22-independent-2025/Independent_Windows_2025.json')
        process_receipts.summary(receipt, require)
        process_receipts.launch_preflight(receipt.get('python_launch_preflight'), require)
        require(receipt.get('python_installed_on_controller') is True and receipt.get('application_launch_attempted') is True,
                'Controller/actual application launch disclosure missing.')
        for key in ('passed', 'native_windows', 'same_producer_bytes', 'source_provenance_matches',
                    'original_exe_unchanged'):
            require(receipt.get(key) is True, 'Independent same-byte acceptance flag missing.')
        expected_fields = {'os_build': 26100, 'producer_run_id': lock['private_run']['id'],
            'producer_run_attempt': candidate['producer_attempt'], 'workflow_commit': lock['private_run']['commit'],
            'release_id': candidate['release_id'], 'asset_id': candidate['asset_id'],
            'executable_sha256': sha, 'source_manifest': source_manifest,
            'frozen_suite_records': 4, 'external_commands': 118, 'startup_captures': 8,
            'os_network_isolation_claimed': False, 'formal_feed_accepted': False, 'binary_published': False}
        require(all(receipt.get(k) == v for k, v in expected_fields.items()), 'Independent candidate identity/scope mismatch.')
        frozen_gate(evidence.json('1-facs-v22-independent-2025/single-exe/Single_EXE_Verification.json'), sha)
        prefix = '1-facs-v22-independent-2025/external-frozen'
    return external_gate(evidence, prefix, sha, version)


def review_gate(receipt, captures, lock):
    require(receipt.get('schema_version') == 2 and receipt.get('pixel_inspection_completed') is True
        and receipt.get('approved_for_public_release') is True and receipt.get('blocking_findings') == [],
            'An explicit completed pixel-inspection receipt is required.')
    require(receipt.get('reviewer_role') in {'ai_assistant', 'human'}
        and receipt.get('review_method') == 'direct_image_inspection',
            'Identify the actual AI assistant or human who directly inspected the image pixels.')
    require(isinstance(receipt.get('reviewer'), str) and len(receipt['reviewer'].strip()) >= 2,
            'Reviewer identity missing.')
    timestamp = dt.datetime.fromisoformat(receipt['reviewed_at'].replace('Z', '+00:00'))
    require(timestamp.tzinfo is not None and timestamp <= dt.datetime.now(dt.timezone.utc), 'Invalid pixel inspection time.')
    require(receipt.get('repository') == REPO and receipt.get('source_snapshot_commit') == lock['source_identity']['snapshot_commit']
        and receipt.get('private_run_id') == lock['private_run']['id']
        and receipt.get('executable_sha256') == lock['candidate']['sha256']
        and receipt.get('private_artifact_sha256') == {k: v['sha256'] for k, v in lock['private_artifacts'].items()},
            'Pixel inspection is not bound to the exact tested candidate and screenshot archives.')
    rows = receipt.get('captures', [])
    require(len(rows) == 16 and len(captures) == 16, 'Review all sixteen exact startup screenshots.')
    expected = {(c['os'], c['path'], c['sha256']) for c in captures}
    require({(c['os'], c['path'], c['sha256']) for c in rows} == expected and len(expected) == 16,
            'Pixel inspection screenshot IDs/hashes differ.')
    for row in rows:
        require(all(row.get(k) is True for k in ('pixels_reviewed', 'startup_labels_readable',
            'startup_language_appropriate', 'visible_window_complete')), 'An individual screenshot remains unreviewed or failed.')


def offline_gate(lock, root, receipt):
    validate_lock(lock)
    identity = lock['source_identity']
    trusted = pinned_json(HERE / identity['provenance']['file'], identity['provenance']['sha256'])
    source = pinned_json(HERE / identity['source_manifest']['file'], identity['source_manifest']['sha256'])
    t.validate_source_manifest(source)
    require(trusted.get('snapshot_commit') == identity['snapshot_commit'] == source['commit']
        and trusted.get('workflow_commit') == lock['source_run']['commit']
        and trusted.get('product_equations_changed') is False and trusted.get('macos_product_changed') is False,
            'Final source snapshot, validation commit, or restricted change scope mismatches the lock.')
    captures = []
    for role in ('source', 'private'):
        for version, item in lock[role + '_artifacts'].items():
            archive = Evidence(root / item['zip'], item['sha256'])
            try:
                if role == 'source':
                    source_gate(archive, version, trusted, identity, source)
                else:
                    captures.extend(private_gate(archive, version, lock, trusted, source))
            finally:
                archive.close()
    review_gate(receipt, captures, lock)
    return source


def online_gate(client, lock):
    for role in ('source', 'private'):
        pinned = lock[role + '_run']
        run = client.get_json('/actions/runs/' + str(pinned['id']))
        require(run.get('id') == pinned['id'] and run.get('run_attempt') == pinned['attempt']
            and run.get('workflow_id') == pinned['workflow_id'] and run.get('head_sha') == pinned['commit']
            and run.get('head_branch') == t.BRANCH and run.get('repository', {}).get('full_name') == REPO
            and run.get('head_repository', {}).get('full_name') == REPO
            and run.get('status') == 'completed' and run.get('conclusion') == 'success'
            and run.get('event') in {'push', 'workflow_dispatch'}, 'Exact workflow run is not completed/successful with trusted provenance.')
        path = '.github/workflows/' + ('validate-v22-reviewed.yml' if role == 'source' else 'private-windows-handoff.yml')
        require(run.get('path') == path, 'Wrong validation workflow path.')
        for version, expected in pinned['jobs'].items():
            job = client.get_json('/actions/jobs/' + str(expected['id']))
            name = f'reviewed-native (windows-{version})' if role == 'source' else (
                'build-private-candidate' if version == '2022' else 'verify-same-bytes-2025')
            require(job.get('id') == expected['id'] and job.get('run_id') == pinned['id']
                and job.get('run_attempt') == expected['attempt'] and job.get('head_sha') == pinned['commit']
                and job.get('name') == name and job.get('status') == 'completed'
                and job.get('conclusion') == 'success' and 'windows-' + version in job.get('labels', []),
                    'Exact native validation job does not match or did not pass.')
            for step in (SOURCE_STEPS if role == 'source' else PRIVATE_STEPS[version]):
                matches = [x for x in job.get('steps', []) if x.get('name') == step]
                require(len(matches) == 1 and matches[0].get('status') == 'completed'
                    and matches[0].get('conclusion') == 'success', 'A required native validation step did not pass.')
            if role == 'source':
                ordered_names = [SOURCE_STEPS[-1], *SOURCE_STEPS[:4]]
            elif version == '2022':
                ordered_names = [PRIVATE_STEPS['2022'][-1], *PRIVATE_STEPS['2022'][:4]]
            else:
                ordered_names = PRIVATE_STEPS['2025'][:3]
            ordered_steps = [next(step for step in job['steps'] if step['name'] == name) for name in ordered_names]
            require(all(type(step.get('number')) is int for step in ordered_steps)
                and all(a['number'] < b['number'] for a,b in zip(ordered_steps,ordered_steps[1:])),
                    'Native process controls, warm/cold/semantic gates must precede full suites/build/consumer launches.')
            artifact = lock[role + '_artifacts'][version]
            metadata = client.get_json('/actions/artifacts/' + str(artifact['id']))
            artifact_name = ('v22-reviewed-native-windows-' if role == 'source'
                else 'v22-private-handoff-diagnostics-windows-') + version
            require(metadata.get('id') == artifact['id'] and metadata.get('name') == artifact_name
                and metadata.get('expired') is False and metadata.get('digest') == 'sha256:' + artifact['sha256']
                and metadata.get('workflow_run', {}).get('id') == pinned['id']
                and metadata.get('workflow_run', {}).get('head_sha') == pinned['commit']
                and metadata.get('workflow_run', {}).get('head_branch') == t.BRANCH,
                    'Exact raw diagnostic ZIP is not bound to the successful trusted workflow run.')


def fetch_evidence(client, lock, directory):
    """Read-only retrieval of pinned GitHub Actions ZIPs; never expose signed URLs."""
    online_gate(client, lock)
    directory = Path(directory).absolute()
    require(not directory.exists(), 'Evidence download directory must be new.')
    directory.mkdir(parents=True, exist_ok=False)
    for role in ('source', 'private'):
        for item in lock[role + '_artifacts'].values():
            metadata = client.get_json('/actions/artifacts/' + str(item['id']))
            size = positive(metadata['size_in_bytes'])
            require(size <= 512 * 1024**2, 'Raw diagnostic ZIP exceeds download bound.')
            output = directory / safe_relative(item['zip'])
            output.parent.mkdir(parents=True, exist_ok=True)
            # The Actions API negotiates JSON and returns a download redirect;
            # the separate unauthenticated storage request negotiates ZIP bytes.
            phase = 'API'
            status, headers, _ = client.request('GET', API + '/actions/artifacts/' + str(item['id']) + '/zip',
                authenticated=True, accept='application/vnd.github+json', destination=output, limit=size)
            if status in (301, 302, 303, 307, 308):
                location = headers.get('Location', headers.get('location', ''))
                parsed = urllib.parse.urlsplit(location)
                allowed = parsed.hostname in {'release-assets.githubusercontent.com', 'objects.githubusercontent.com'} or (
                    parsed.hostname is not None and re.fullmatch(r'productionresultssa[a-z0-9]+\.blob\.core\.windows\.net', parsed.hostname))
                require(parsed.scheme == 'https' and allowed, 'Unknown Actions artifact storage host; stop for review.')
                # GH_TOKEN is deliberately NOT forwarded to object storage.
                phase = 'storage'
                status, _, _ = client.request('GET', location, authenticated=False,
                    accept='application/zip', destination=output, limit=size)
            # Keep HTTP failures distinct from exact-byte failures. Only a bounded
            # status and fixed phase may enter diagnostics, never URLs or bodies.
            status_text = str(status) if type(status) is int and 100 <= status <= 599 else 'invalid'
            require(status == 200, 'Raw diagnostic ZIP ' + phase + ' request failed with HTTP ' + status_text + '.')
            require(output.is_file(), 'Raw diagnostic ZIP response did not create the expected file.')
            require(output.stat().st_size == size,
                    'Raw diagnostic ZIP byte count differs from exact trusted artifact metadata.')
            require(t.sha256(output) == item['sha256'],
                    'Raw diagnostic ZIP SHA-256 differs from the exact trusted artifact hash.')
    print('Exact diagnostic ZIPs downloaded and hashed. No release state changed.')


def candidate_scope(lock):
    return t.Scope(lock['private_run']['id'], lock['candidate']['producer_attempt'], lock['private_run']['commit'])


def verify_private(client, lock):
    candidate = lock['candidate']
    scope = candidate_scope(lock)
    scope.gate(client, candidate['release_id'])
    rows = t.inventory(client, candidate['release_id'])
    require(set(rows) == t.ALLOWED_ASSETS, 'Private candidate inventory changed.')
    for name, key, count, sha in [(EXE, 'asset_id', 'bytes', 'sha256'),
                                (t.MANIFEST_NAME, 'manifest_asset_id', 'manifest_bytes', 'manifest_sha256')]:
        row = t.verify_asset(rows[name], name, candidate[count], candidate[sha], candidate[key])
        scope.asset_gate(client, row)
    return scope


def release_note(lock):
    c = lock['candidate']
    return (f'Facility Studio 5.7.3 v22 | Windows x64 portable\n\n'
        f'Single EXE; no Python installation needed by the app. Exact tested bytes, not rebuilt.\n'
        f'SHA-256: {c["sha256"]}\n'
        f'Source snapshot: {lock["source_identity"]["snapshot_commit"]}\n'
        f'Source native validation: {WEB}/actions/runs/{lock["source_run"]["id"]}\n'
        f'Same-EXE native validation: {WEB}/actions/runs/{lock["private_run"]["id"]}\n\n'
        'Measured on GitHub-hosted Windows Server 2022 and 2025. Python was installed for the test controllers; '
        'this is not a Python-free-host test. Each actual EXE launch audited all retained Job process images '
        'and required every image to be the same copied EXE; no external Python process was used in those launches. '
        'Native positive and foreign-image-negative controls passed on all source/build/consumer hosts. '
        'Both source runs: '
        f'{lock["source_identity"]["passed_tests"]:,} tests passed, '
        f'{lock["source_identity"]["passed_subtests"]} subtests passed, one expected Tk 9 skip; all 11 commands, '
        '100 bootstrap checks, 9 lifecycle attempts, and 3 small-screen tests passed. '
        'Each source host also passed 16 untouched native-menu startup cases at each of 1920x1080 and 1024x768; '
        'the producer passed the 16-case 1920x1080 warm startup prebuild gate. '
        'Both source hosts and the producer separately passed 16 cold real-entry source launches at each resolution; '
        'source cold checks do not replace actual frozen-EXE validation. '
        'Both source hosts and producer also passed native bilingual menu and selector text/visibility/bounds checks '
        'at both desktop sizes. Native top menus were read as Win32 strings; owner-drawn popup command labels '
        'were checked as exact Tk label metadata matched to native item order/type/state/count, not popup pixel proof. '
        'No native item-data-to-callback-pointer mapping was claimed. '
        'Same EXE on each OS: 4 frozen suite runs, 118 CLI checks, 8 startup captures; '
        'all 16 startup screenshots separately reviewed.\n\n'
        'No claim of end-user Windows 10/11, high-DPI, full GUI interaction, or installation testing. '
        'Not code-signed; signing/reputation warnings may appear. No formal FEED approval. '
        'Automatic ampacity, wire, NFB, voltage-drop and PE selections remain intentionally restricted. '
        'Source engineering equations were not changed. Startup review does not certify all screens or translations.\n')


class FinalRelease:
    def __init__(self, lock, before_write=None):
        self.lock = lock
        self.before_write = before_write
        self.tag = f'facs-v22-windows-verified-{lock["private_run"]["id"]}-{lock["candidate"]["producer_attempt"]}'
        self.name = 'Facility Studio 5.7.3 v22 Windows x64 Portable'
        self.body = release_note(lock)
        self.commit = lock['private_run']['commit']

    def metadata(self, row, release_id, draft):
        require(row.get('id') == positive(release_id) and row.get('draft') is draft
            and row.get('tag_name') == self.tag and row.get('target_commitish') == self.commit
            and row.get('name') == self.name and t.exact_ui_text(row.get('body'), self.body) and row.get('prerelease') is False,
                'Final release scope/state mismatch; unrelated releases must not be modified.')
        require((row.get('published_at') is None) if draft else bool(row.get('published_at')),
                'Final publication timestamp/state mismatch.')
        t.verified_public_url(row.get('html_url'), 'release')
        require(draft or row['html_url'] == WEB + '/releases/tag/' + self.tag, 'Published release HTML URL differs from exact final tag.')
        return row

    def gate(self, client, release_id, draft=True):
        row = self.metadata(client.get_json('/releases/' + str(positive(release_id))), release_id, draft)
        if draft:
            for url in (API + '/releases/' + str(release_id), API + '/releases/tags/' + self.tag,
                        WEB + '/releases/tag/' + self.tag, row['html_url']):
                client.absent(url)
        return row

    def inventory(self, client, release_id):
        rows = client.pages('/releases/' + str(positive(release_id)) + '/assets')
        require(all(x.get('name') in ASSETS for x in rows) and len({x['name'] for x in rows}) == len(rows),
                'Unexpected/duplicate final assets; never replace or delete.')
        return {x['name']: x for x in rows}

    def inspect(self, client, release_id=None):
        # Server metadata is untrusted. Only fixed enums, scoped names and bounded
        # numeric IDs/counts may reach a diagnostic, including uncertain writes.
        def number(value):
            return value if type(value) is int and 0 < value <= 2**63-1 else None
        if release_id is None:
            rows = [r for r in client.pages('/releases')
                    if isinstance(r, dict) and r.get('tag_name') == self.tag]
        else:
            require(number(release_id) is not None, 'Invalid exact inspection ID.')
            rows = [client.get_json('/releases/' + str(release_id))]
        sanitized = []
        for raw in rows:
            r = raw if isinstance(raw, dict) else {}
            rid = number(r.get('id'))
            assets = []
            if rid is not None and (release_id is None or rid == release_id):
                for raw_asset in client.pages('/releases/' + str(rid) + '/assets'):
                    a = raw_asset if isinstance(raw_asset, dict) else {}
                    name, state = a.get('name'), a.get('state')
                    assets.append(dict(id=number(a.get('id')),
                        name=name if type(name) is str and name in ASSETS else 'unknown',
                        state=state if type(state) is str and state in {'uploaded', 'starter'} else 'unknown',
                        bytes=number(a.get('size'))))
            sanitized.append(dict(id=rid, draft=r.get('draft') if type(r.get('draft')) is bool else None,
                tag=self.tag if r.get('tag_name') == self.tag else 'unknown', assets=assets))
        print(json.dumps({'inspection_only': True, 'releases': sanitized}), flush=True)
        return rows

    def tag_gate(self, client):
        status, _, raw = client.request('GET', API + '/git/ref/tags/' + self.tag, authenticated=True)
        if status == 404:
            return
        require(status == 200, 'Cannot establish final tag identity before publication.')
        row = t.parse_json(raw)
        require(row.get('object', {}).get('type') == 'commit'
            and row['object'].get('sha') == self.commit, 'Final tag targets untested code; stop before publishing.')

    def create(self, client, resume_id=None):
        if resume_id is not None:
            require(resume_id != self.lock['candidate']['release_id'], 'Never mutate the private candidate release.')
            self.gate(client, resume_id)
            self.tag_gate(client)
            self.inventory(client, resume_id)
            return positive(resume_id)
        require(not self.inspect(client), 'Matching final release exists. Inspect exact ID; no automatic create/resume.')
        client.absent(API + '/releases/tags/' + self.tag)
        client.absent(WEB + '/releases/tag/' + self.tag)
        status, _, _ = client.request('GET', API + '/git/ref/tags/' + self.tag, authenticated=True)
        require(status == 404, 'Existing or unreadable final tag; inspect rather than alter it.')
        payload = t.canonical_json({'tag_name': self.tag, 'target_commitish': self.commit, 'name': self.name,
            'body': self.body, 'draft': True, 'prerelease': False, 'generate_release_notes': False, 'make_latest': 'false'})
        if self.before_write is not None:
            self.before_write()
        try:
            status, _, raw = client.request('POST', API + '/releases', authenticated=True,
                payload=payload, content_type='application/json')
            require(status == 201, 'Final draft creation outcome uncertain or rejected.')
            row = t.parse_json(raw)
            release_id = positive(row['id'])
            self.metadata(row, release_id, True)
        except (GateError, ValueError, TypeError, KeyError):
            self.inspect(client)
            raise GateError('STOP: final draft creation uncertain/rejected; inspect exact ID before any authorized retry.') from None
        print(json.dumps({'final_draft_id': release_id, 'published': False}), flush=True)
        self.gate(client, release_id)
        require(not self.inventory(client, release_id), 'New final draft was not empty.')
        return release_id

    def upload(self, client, release_id, path):
        path = t.regular_file(path)
        require(path.name in ASSETS, 'Only final EXE, SHA-256, and verification note may be uploaded.')
        size, sha = path.stat().st_size, t.sha256(path)
        self.gate(client, release_id)
        rows = self.inventory(client, release_id)
        if path.name not in rows:
            if self.before_write is not None:
                self.before_write()
            try:
                with path.open('rb') as stream:
                    status, _, raw = client.request('POST', UPLOADS + '/releases/' + str(release_id)
                        + '/assets?name=' + urllib.parse.quote(path.name, safe=''), authenticated=True,
                        payload=stream, content_type='application/octet-stream' if path.name == EXE else 'text/plain')
                require(status == 201, 'Final upload outcome uncertain or rejected.')
                uploaded = t.verify_asset(t.parse_json(raw), path.name, size, sha)
            except (GateError, ValueError, TypeError, KeyError):
                self.inspect(client, release_id)
                raise GateError('STOP: upload uncertain/rejected; inspect exact asset IDs, never retry blindly.') from None
            rows = self.inventory(client, release_id)
            require(rows.get(path.name, {}).get('id') == uploaded['id'], 'Uploaded final asset ID differs from inventory.')
        row = t.verify_asset(rows[path.name], path.name, size, sha)
        t.verify_asset(client.get_json('/releases/assets/' + str(row['id'])), path.name, size, sha, row['id'])
        self.gate(client, release_id)
        client.absent(API + '/releases/assets/' + str(row['id']))
        client.absent(t.verified_public_url(row['browser_download_url'], 'asset', path.name))
        with tempfile.TemporaryDirectory(prefix='facs-final-readback-') as folder:
            client.download_asset(row['id'], Path(folder) / path.name, size, sha)
        require(t.sha256(path) == sha, 'Local payload changed while uploading.')
        return {'id': row['id'], 'name': path.name, 'size': size, 'sha256': sha}

    def stage_existing(self, client, release_id, files, recheck_evidence):
        """Asset-only staging into one explicitly authorized existing owner draft."""
        positive(release_id)
        require(release_id != self.lock['candidate']['release_id'], 'Never modify the private candidate release.')
        require(callable(self.before_write), 'Owner staging requires an exact one-shot activation guard.')
        self.before_write()
        recheck_evidence()
        online_gate(client, self.lock)
        verify_private(client, self.lock)
        self.gate(client, release_id)
        self.tag_gate(client)
        require(len(files) == 3 and {path.name for path in files} == ASSETS, 'Exact three final payloads required.')
        expected = {path.name: (path.stat().st_size, t.sha256(path)) for path in files}
        rows = self.inventory(client, release_id)
        # Validate every pre-existing asset before the first upload, not lazily.
        for name, row in rows.items():
            size, sha = expected[name]
            t.verify_asset(row, name, size, sha)
            t.verify_asset(client.get_json('/releases/assets/' + str(row['id'])), name, size, sha, row['id'])
            client.absent(API + '/releases/assets/' + str(row['id']))
            client.absent(t.verified_public_url(row['browser_download_url'], 'asset', name))
            with tempfile.TemporaryDirectory(prefix='facs-owner-existing-readback-') as folder:
                client.download_asset(row['id'], Path(folder) / name, size, sha)
        assets = []
        for path in files:
            self.tag_gate(client)
            assets.append(self.upload(client, release_id, path))
        recheck_evidence()
        online_gate(client, self.lock)
        verify_private(client, self.lock)
        self.gate(client, release_id)
        self.tag_gate(client)
        rows = self.inventory(client, release_id)
        require(set(rows) == ASSETS, 'Final owner draft inventory is incomplete.')
        for asset in assets:
            t.verify_asset(rows[asset['name']], asset['name'], asset['size'], asset['sha256'], asset['id'])
        self.before_write()  # Recheck live lease/expiry even though no write follows.
        result = dict(status='READY_FOR_OWNER_UI_PUBLICATION', release_id=release_id,
            tag=self.tag, target_commitish=self.commit, assets=assets,
            draft=True, published=False, owner_ui_publication_required=True)
        print(json.dumps(result), flush=True)
        return result

    def publish(self, client, release_id, assets):
        online_gate(client, self.lock)
        verify_private(client, self.lock)
        self.gate(client, release_id)
        rows = self.inventory(client, release_id)
        require(set(rows) == ASSETS and {x['name'] for x in assets} == ASSETS and len(assets) == 3,
                'Final draft has incomplete asset inventory.')
        for asset in assets:
            t.verify_asset(rows[asset['name']], asset['name'], asset['size'], asset['sha256'], asset['id'])
        self.tag_gate(client)  # Final pre-PATCH check, including explicitly resumed drafts.
        if self.before_write is not None:
            self.before_write()
        try:
            status, _, raw = client.request('PATCH', API + '/releases/' + str(positive(release_id)),
                authenticated=True, payload=t.canonical_json({'draft': False, 'make_latest': 'false'}),
                content_type='application/json')
            require(status == 200, 'Publication outcome uncertain or rejected.')
            self.metadata(t.parse_json(raw), release_id, False)
        except (GateError, ValueError, TypeError, KeyError):
            self.inspect(client, release_id)
            raise GateError('STOP: publication outcome uncertain/rejected. Inspect exact release ID; do not republish or delete.') from None
        self.verify_public(client, release_id, assets)

    def verify_public(self, client, release_id, assets):
        final = self.gate(client, release_id, draft=False)
        status, _, raw = client.request('GET', API + '/releases/' + str(release_id), authenticated=False)
        require(status == 200, 'Anonymous final release metadata unavailable.')
        self.metadata(t.parse_json(raw), release_id, False)
        status, _, raw = client.request('GET', API + '/releases/tags/' + self.tag, authenticated=False)
        require(status == 200, 'Anonymous final tag metadata unavailable.')
        self.metadata(t.parse_json(raw), release_id, False)
        tag = client.get_json('/git/ref/tags/' + self.tag)
        require(tag.get('object', {}).get('type') == 'commit' and tag['object'].get('sha') == self.commit,
                'Published tag points to an unexpected commit.')
        rows = self.inventory(client, release_id)
        require(set(rows) == ASSETS and len(assets) == 3 and {a['name'] for a in assets} == ASSETS,
                'Final public inventory incomplete or changed.')
        for asset in assets:
            row = t.verify_asset(rows[asset['name']], asset['name'], asset['size'], asset['sha256'], asset['id'])
            url = t.verified_public_url(row['browser_download_url'], 'asset', asset['name'])
            require(url == WEB + '/releases/download/' + self.tag + '/' + asset['name'], 'Unexpected final download URL.')
            with tempfile.TemporaryDirectory(prefix='facs-final-anonymous-') as folder:
                destination = Path(folder) / asset['name']
                status, headers, _ = client.request('GET', url, authenticated=False,
                    accept='application/octet-stream', destination=destination, limit=asset['size'])
                if status in (301, 302, 303, 307, 308):
                    location = headers.get('Location', headers.get('location', ''))
                    require(urllib.parse.urlsplit(location).hostname in {
                        'release-assets.githubusercontent.com', 'objects.githubusercontent.com'},
                            'Unexpected anonymous download redirect host.')
                    status, _, _ = client.request('GET', location, authenticated=False,
                        accept='application/octet-stream', destination=destination, limit=asset['size'])
                require(status == 200 and destination.stat().st_size == asset['size']
                    and t.sha256(destination) == asset['sha256'], 'Anonymous final download differs from trusted tested bytes.')
        verify_private(client, self.lock)
        print(json.dumps({'published_and_anonymous_download_verified': True, 'release_id': release_id,
            'url': final['html_url'], 'exe_url': rows[EXE]['browser_download_url'],
            'sha256': self.lock['candidate']['sha256'], 'private_candidate_unchanged': True}), flush=True)


def prepare_payloads(client, lock, source, directory):
    candidate = lock['candidate']
    scope = verify_private(client, lock)
    args = SimpleNamespace(**candidate, output=directory)
    t.download(client, scope, args)
    manifest = t.parse_json((directory / t.MANIFEST_NAME).read_bytes())
    require(manifest['source_manifest'] == source, 'Exact private manifest differs from trusted source file inventory.')
    # Original manifest is kept local and is NEVER in the final asset allowlist.
    (directory / 'Windows_Verification.txt').write_text(release_note(lock), encoding='utf-8', newline='\n')
    lines = [f'{t.sha256(directory / name)}  {name}\n' for name in (EXE, 'Windows_Verification.txt')]
    (directory / 'SHA256SUMS.txt').write_text(''.join(lines), encoding='ascii', newline='\n')
    return [directory / name for name in sorted(ASSETS)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['offline', 'fetch-evidence', 'preflight', 'publish', 'inspect', 'verify-public', 'stage-existing'])
    parser.add_argument('--lock', type=Path, required=True)
    parser.add_argument('--lock-sha256', required=True)
    parser.add_argument('--review', type=Path)
    parser.add_argument('--review-sha256')
    parser.add_argument('--evidence-root', type=Path)
    parser.add_argument('--release-id', type=int)
    parser.add_argument('--one-shot-invocation', type=Path)
    parser.add_argument('--invocation-sha256')
    args = parser.parse_args(argv)
    lock = validate_lock(pinned_json(args.lock, args.lock_sha256))
    final = FinalRelease(lock)
    if args.command == 'stage-existing':
        positive(args.release_id)
        require(args.release_id != lock['candidate']['release_id'], 'Never modify the private candidate release.')
        require(args.one_shot_invocation is not None, 'Owner staging requires an exact one-shot invocation.')
    if args.command == 'offline':
        receipt = pinned_json(args.review, args.review_sha256)
        offline_gate(lock, args.evidence_root, receipt)
        print('Offline evidence gates passed. No workflow/API state checked; no publication performed.')
        return
    require(os.environ.get('GITHUB_REPOSITORY') == REPO, 'Wrong publication repository.')
    client = t.Client(os.environ.get('GH_TOKEN', ''))
    if args.one_shot_invocation is not None:
        import one_shot_guard
        def authorize_activation():
            try:
                one_shot_guard.authorize(client, lock, args.one_shot_invocation, args.invocation_sha256,
                    args.lock, args.review, args.command, args.release_id)
            except (ValueError, OSError, KeyError, TypeError):
                raise GateError('Exact one-shot activation context/invocation failed; no write is permitted.') from None
        authorize_activation()
        final.before_write = authorize_activation
    else:
        require(os.environ.get('GITHUB_REF') == 'refs/heads/' + t.BRANCH
            and os.environ.get('GITHUB_SHA') == lock['publisher_commit'],
                'Run only from the pinned reviewed publisher commit or a verified exact-SHA one-shot activation.')
    if args.command == 'inspect':
        final.inspect(client, args.release_id)
        return
    if args.command == 'fetch-evidence':
        fetch_evidence(client, lock, args.evidence_root)
        return
    receipt = pinned_json(args.review, args.review_sha256)
    source = offline_gate(lock, args.evidence_root, receipt)
    online_gate(client, lock)
    with tempfile.TemporaryDirectory(prefix='facs-final-payloads-') as folder:
        files = prepare_payloads(client, lock, source, Path(folder) / 'exact-tested-bytes')
        if args.command == 'preflight':
            print('All local and live gates passed, exact private bytes downloaded. No public release created or modified.')
            return
        if args.command == 'verify-public':
            positive(args.release_id)
            rows = final.inventory(client, args.release_id)
            assets = [{'id': rows[p.name]['id'], 'name': p.name, 'size': p.stat().st_size, 'sha256': t.sha256(p)} for p in files]
            final.verify_public(client, args.release_id, assets)
            return
        if args.command == 'stage-existing':
            def recheck_evidence():
                require(pinned_json(args.review, args.review_sha256) == receipt, 'Pixel-inspection receipt changed during staging.')
                offline_gate(lock, args.evidence_root, receipt)
            final.stage_existing(client, args.release_id, files, recheck_evidence)
            return
        release_id = final.create(client, args.release_id)
        assets = [final.upload(client, release_id, path) for path in files]
        # Re-read the pinned pixel-inspection receipt after all uploads, before publication.
        require(pinned_json(args.review, args.review_sha256) == receipt, 'Pixel-inspection receipt changed during staging.')
        final.publish(client, release_id, assets)


if __name__ == '__main__':
    try:
        main()
    except (GateError, OSError, KeyError, TypeError, ValueError, AttributeError, zipfile.BadZipFile, ET.ParseError):
        error = sys.exc_info()[1]
        # No traceback or arbitrary response/local data, URLs, or credentials.
        print('PUBLICATION STOPPED: ' + (str(error) if isinstance(error, GateError)
            else 'Required local evidence or metadata is invalid.'), file=sys.stderr)
        raise SystemExit(1)
