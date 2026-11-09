"""Offline synthetic negative controls. Never evidence of Windows/product acceptance."""
import copy
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import publish_verified_windows as p
import cold_test_fixtures
import r6_test_fixtures


def encoded(value):
    return p.t.canonical_json(value)


def xml(count, skip=False, reported=None, native=False):
    cases = []
    for index in range(count):
        name = p.SKIP if skip and index == count - 1 else 'test_' + str(index)
        classname = 'integration.test_onefile_process_native' if native and index < 8 else 'integration.test_synthetic'
        cases.append(f'<testcase name="{name}" classname="{classname}">' + ('<skipped />' if skip and index == count - 1 else '') + '</testcase>')
    return (f'<testsuites><testsuite tests="{reported or count}" skipped="{int(skip)}" failures="0" errors="0">'
        + ''.join(cases) + '</testsuite></testsuites>').encode()


def startup_xml():
    cases=[]
    for launch in range(4):
        for entry in ('simple','workbench'):
            for language in ('en','zh-Hant'):
                cases.append(f'<testcase classname="integration.test_windows_startup_placement" name="test_native_untouched_launch_contains_outer_visible_frame_and_client[{launch}-{entry}-{language}]" />')
    return ('<testsuites><testsuite tests="16" skipped="0" failures="0" errors="0">'+''.join(cases)+'</testsuite></testsuites>').encode()


def startup_display(width,height):
    return dict(native_windows=True,passed=True,exact=True,requested=[width,height],frozen_binary_tested=False,
        command=['python','-B','-m','pytest','D:/source/integration/test_windows_startup_placement.py','-k','native_untouched','--capture=sys'],
        selected=dict(width=width,height=height),test_return=0,apply_return=0,command_exit_code=0,restore_return=0,
        after=dict(screen=[width,height],work_area=[0,0,width,height-40],current_mode=dict(width=width,height=height)),
        tk=dict(screen=[width,height],windowing='win32'))


def source_files(version):
    trusted = p.pinned_json(p.HERE / 'trusted-source-provenance.json', p.t.sha256(p.HERE / 'trusted-source-provenance.json'))
    result = {
        'reviewed-source-provenance.json': trusted,
        'reviewed-SUMMARY.json': dict(passed=True, native_windows=True, native_process_passed=True,
            unexpected_skips_rejected=True, original_failures_preserved=True, command_exit=0, native_process_count=8,
            skips=[p.SKIP], allowed_skip=p.SKIP, host=f'Windows-{version}Server-10.0.20348-SP0'),
        'command-receipts.json': [dict(name=n, exit_code=0) for n in p.SOURCE_COMMANDS],
        'full-integration.xml': xml(8494, skip=True, reported=8584, native=True),
        'full-integration.log': b'8493 passed, 1 skipped, 12 warnings, 90 subtests passed in 601s',
        'corrected-tcl-bootstrap.xml': xml(100),
        'small-screen.xml': xml(3),
        'display-small.json': dict(passed=True, native_windows=True, requested=[1024, 768], exact=True),
        'tk-lifecycle/SUMMARY.json': dict(passed=True, native_windows=True, source_python_files_unchanged=True,
            attempts=[dict(round=r, group=g, passed=True, exit_code=0,
                junit=dict(accepted=True, failures=0, errors=0, skipped=0 if g == 'isolated' else 1,
                    required_targets_missing=[], exceptional_results=[] if g == 'isolated' else [{'name': p.SKIP}]))
                for r in (1, 2, 3) for g in ('isolated', 'module-context', 'prefix')]),
    }
    for width,height in ((1920,1080),(1024,768)):
        result[f'startup-placement-{width}-{height}.xml']=startup_xml()
        result[f'startup-display-{width}-{height}.json']=startup_display(width,height)
    source = p.t.parse_json((p.HERE/'trusted-source-manifest.json').read_bytes())
    cold_test_fixtures.add(result, source, startup_display)
    return {k: v if isinstance(v, bytes) else encoded(v) for k, v in result.items()}


def frozen(sha):
    return dict(passed=True, native_windows=True, executable_sha256=sha,
        records=[dict(path_case=c, suite=s, exit_code=0) for c in ('plain', 'unicode-space') for s in ('fusion', 'facilities')])


def private_files(version, lock):
    trusted = p.pinned_json(p.HERE / 'trusted-source-provenance.json', p.t.sha256(p.HERE / 'trusted-source-provenance.json'))
    source = p.pinned_json(p.HERE / 'trusted-source-manifest.json', p.t.sha256(p.HERE / 'trusted-source-manifest.json'))
    c = lock['candidate']
    result = {'0-facs-v22-evidence/reviewed-source-provenance.json': dict(trusted, workflow_commit=lock['private_run']['commit'])}
    if version == '2022':
        cold_test_fixtures.add(result, source, startup_display, '0-facs-v22-evidence/prebuild-')
        result['0-facs-v22-evidence/prebuild-startup-placement.xml']=startup_xml()
        result['0-facs-v22-evidence/prebuild-startup-display.json']=startup_display(1920,1080)
        result['0-facs-v22-evidence/candidate-build-result.json'] = dict(build_exit=0, extended_exit=0,
            unchanged=True, executable_sha256=c['sha256'], executable_bytes=c['bytes'])
        result['1-evidence/Build_Manifest.json'] = source
        result['1-evidence/single-exe/Single_EXE_Verification.json'] = frozen(c['sha256'])
        prefix = '0-facs-v22-evidence/external-frozen'
    else:
        result['1-facs-v22-independent-2025/Independent_Windows_2025.json'] = dict(
            passed=True, native_windows=True, same_producer_bytes=True, source_provenance_matches=True,
            external_python_removed_from_tested_launch_path=True, original_exe_unchanged=True, os_build=26100,
            producer_run_id=lock['private_run']['id'], producer_run_attempt=c['producer_attempt'],
            workflow_commit=lock['private_run']['commit'], release_id=c['release_id'], asset_id=c['asset_id'],
            executable_sha256=c['sha256'], source_manifest=source, frozen_suite_records=4, external_commands=118,
            startup_captures=8, os_network_isolation_claimed=False, formal_feed_accepted=False, binary_published=False)
        result['1-facs-v22-independent-2025/single-exe/Single_EXE_Verification.json'] = frozen(c['sha256'])
        prefix = '1-facs-v22-independent-2025/external-frozen'
    external = dict(passed=True, native_windows=True, original_exe_unchanged=True, screenshots_requested=True,
        external_python_removed_from_child_path=True, executable_sha256=c['sha256'],
        os_network_isolation_claimed=False, engineering_or_formal_feed_approval_claimed=False,
        commands=[dict(passed=True, exit_code=code, expected_exit=code, label=label) for label,code in p.expected_external_commands().items()],
        artifacts=[], screenshots=[])
    review = []
    for path_case in ('plain', 'unicode-space'):
        for language in ('en', 'zh-Hant'):
            for mode in ('simple', 'full'):
                relative = f'{path_case}/{language}-{mode}-startup/startup.png'
                pixels = b'\x89PNG\r\n\x1a\nSYNTHETIC-NOT-A-SCREENSHOT:' + (version + relative).encode()
                sha = p.digest(pixels)
                result[prefix + '/' + relative] = pixels
                external['screenshots'].append(dict(screenshot='D:/synthetic/' + relative, passed=True,
                    closed_cleanly=True, executable_sha256=c['sha256'], language_argument=language,
                    mode_argument=mode, process=dict(exit_code=0), screenshot_sha256=sha))
                external['artifacts'].append(dict(path=relative, bytes=len(pixels), sha256=sha))
                review.append(dict(os=version, path=prefix + '/' + relative, sha256=sha,
                    pixels_reviewed=True, startup_labels_readable=True, startup_language_appropriate=True, visible_window_complete=True))
    result[prefix + '/Frozen_External_Checks.json'] = external
    return {k: v if isinstance(v, bytes) else encoded(v) for k, v in result.items()}, review


class Fixture:
    def __init__(self, root):
        self.root = root
        self.binary = b'MZ-SYNTHETIC-OFFLINE-NOT-AN-EXECUTABLE'
        self.lock = dict(schema_version=1, repository=p.REPO, publisher_commit='f' * 40,
            source_identity=dict(snapshot_commit=json.loads((p.HERE/'trusted-source-manifest.json').read_text())['commit'],
                provenance=dict(file='trusted-source-provenance.json',sha256=p.t.sha256(p.HERE/'trusted-source-provenance.json')),
                source_manifest=dict(file='trusted-source-manifest.json',sha256=p.t.sha256(p.HERE/'trusted-source-manifest.json')),
                passed_tests=8493,passed_subtests=90),
            source_run=dict(id=302, attempt=1, commit=json.loads((p.HERE/'trusted-source-provenance.json').read_text())['workflow_commit'], workflow_id=101,
                jobs={'2022': dict(id=201, attempt=1), '2025': dict(id=202, attempt=1)}),
            private_run=dict(id=303, attempt=1, commit='a' * 40, workflow_id=102,
                jobs={'2022': dict(id=203, attempt=1), '2025': dict(id=204, attempt=1)}),
            candidate=dict(release_id=401, asset_id=501, manifest_asset_id=502, producer_attempt=1,
                bytes=len(self.binary), sha256=p.digest(self.binary), manifest_bytes=1, manifest_sha256='b'*64),
            source_artifacts={}, private_artifacts={})
        source = p.pinned_json(p.HERE / 'trusted-source-manifest.json', p.t.sha256(p.HERE / 'trusted-source-manifest.json'))
        scope = p.candidate_scope(self.lock)
        candidate = self.lock['candidate']
        manifest = dict(schema_version=1, repository=p.REPO, tag=scope.tag, release_id=401,
            workflow_commit='a'*40, run_id=303, run_attempt=1,
            binary=dict(name=p.EXE, bytes=len(self.binary), sha256=candidate['sha256']), source_manifest=source,
            published=False, unvalidated=True, formal_feed_accepted=False)
        self.manifest = encoded(manifest)
        candidate.update(manifest_bytes=len(self.manifest), manifest_sha256=p.digest(self.manifest))
        self.files = {}
        captures = []
        for index, (role, version) in enumerate((r, v) for r in ('source', 'private') for v in ('2022', '2025')):
            if role == 'source':
                files = source_files(version)
            else:
                files, more = private_files(version, self.lock)
                captures.extend(more)
            files = r6_test_fixtures.enrich(files, role, version, p.EXE, startup_display)
            key = role + version
            self.files[key] = files
            self.lock[role + '_artifacts'][version] = dict(id=601+index, zip=key+'.zip', sha256='')
            self.zip(role, version)
        self.review = dict(schema_version=2, repository=p.REPO, pixel_inspection_completed=True,
            approved_for_public_release=True, blocking_findings=[], reviewer='SYNTHETIC OFFLINE FIXTURE', reviewer_role='ai_assistant', review_method='direct_image_inspection',
            reviewed_at='2026-01-01T00:00:00Z', source_snapshot_commit=self.lock['source_identity']['snapshot_commit'],
            private_run_id=303, executable_sha256=candidate['sha256'],
            private_artifact_sha256={k:v['sha256'] for k,v in self.lock['private_artifacts'].items()}, captures=captures)

    def zip(self, role, version):
        item = self.lock[role + '_artifacts'][version]
        with zipfile.ZipFile(self.root / item['zip'], 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for key, value in self.files[role+version].items():
                archive.writestr(key, value)
        item['sha256'] = p.t.sha256(self.root / item['zip'])

    def change(self, role, version, name, mutate):
        key = role+version
        value = p.t.parse_json(self.files[key][name])
        mutate(value)
        self.files[key][name] = encoded(value)
        self.zip(role, version)
        if role == 'private':
            self.review['private_artifact_sha256'][version] = self.lock['private_artifacts'][version]['sha256']

    def gate(self):
        return p.offline_gate(self.lock, self.root, self.review)


class FakeClient:
    def __init__(self, fixture):
        self.fixture = fixture
        self.lock = fixture.lock
        self.calls = []
        self.metadata = {}
        self.releases = {}
        self.asset_data = {}
        self.uncertain = None
        self.corrupt_public = False
        self.tag_sha = None
        for role in ('source', 'private'):
            run = self.lock[role+'_run']
            self.metadata['/actions/runs/'+str(run['id'])] = dict(id=run['id'], run_attempt=run['attempt'],
                workflow_id=run['workflow_id'], head_sha=run['commit'], head_branch=p.t.BRANCH,
                repository=dict(full_name=p.REPO), head_repository=dict(full_name=p.REPO), status='completed',
                conclusion='success', event='push', path='.github/workflows/' +
                ('validate-v22-reviewed.yml' if role == 'source' else 'private-windows-handoff.yml'))
            for version, job in run['jobs'].items():
                steps = p.SOURCE_STEPS if role == 'source' else p.PRIVATE_STEPS[version]
                if role == 'source' or version == '2022': steps = [steps[-1], *steps[:-1]]
                name = f'reviewed-native (windows-{version})' if role == 'source' else (
                    'build-private-candidate' if version == '2022' else 'verify-same-bytes-2025')
                self.metadata['/actions/jobs/'+str(job['id'])] = dict(id=job['id'], run_id=run['id'],
                    run_attempt=job['attempt'], head_sha=run['commit'], name=name, status='completed', conclusion='success',
                    labels=['windows-'+version], steps=[dict(name=s, number=index+1, status='completed', conclusion='success') for index,s in enumerate(steps)])
                artifact = self.lock[role+'_artifacts'][version]
                self.metadata['/actions/artifacts/'+str(artifact['id'])] = dict(id=artifact['id'],
                    name=('v22-reviewed-native-windows-' if role == 'source' else 'v22-private-handoff-diagnostics-windows-')+version,
                    expired=False, digest='sha256:'+artifact['sha256'],
                    workflow_run=dict(id=run['id'], head_sha=run['commit'], head_branch=p.t.BRANCH))
        scope = p.candidate_scope(self.lock)
        self.releases[401] = dict(id=401, draft=True, prerelease=True, published_at=None,
            tag_name=scope.tag, target_commitish=scope.commit, name=scope.name, body=scope.marker,
            html_url=p.WEB+'/releases/tag/untagged-401')
        self.add_asset(501, 401, p.EXE, fixture.binary)
        self.add_asset(502, 401, p.t.MANIFEST_NAME, fixture.manifest)

    def add_asset(self, asset_id, release_id, name, data):
        tag = self.releases[release_id]['tag_name']
        self.asset_data[asset_id] = (release_id, data, dict(id=asset_id, name=name, state='uploaded', size=len(data),
            digest='sha256:'+p.digest(data), browser_download_url=p.WEB+'/releases/download/'+tag+'/'+name))
        return self.asset_data[asset_id][2]

    def get_json(self, path):
        self.calls.append(('GET', p.API+path, True))
        if path in self.metadata:
            return copy.deepcopy(self.metadata[path])
        if path.startswith('/releases/assets/'):
            return copy.deepcopy(self.asset_data[int(path.split('/')[-1])][2])
        if path.startswith('/releases/'):
            return copy.deepcopy(self.releases[int(path.split('/')[-1])])
        if path.startswith('/git/ref/tags/'):
            return {'object': {'type':'commit', 'sha':self.lock['private_run']['commit']}}
        raise AssertionError('Unexpected get '+path)

    def pages(self, path):
        self.calls.append(('GET', p.API+path, True))
        if path == '/releases':
            return copy.deepcopy(list(self.releases.values()))
        release_id = int(path.split('/')[2])
        return copy.deepcopy([row for rid, data, row in self.asset_data.values() if rid == release_id])

    def absent(self, url):
        self.calls.append(('GET', url, False))
        for rid, row in self.releases.items():
            if not row['draft'] and (url.endswith('/'+str(rid)) or row['tag_name'] in url):
                raise p.GateError('Synthetic anonymous public route is not 404.')

    def download_asset(self, asset_id, destination, size, expected_hash):
        self.calls.append(('DOWNLOAD', str(asset_id), True))
        data = self.asset_data[asset_id][1]
        p.require(len(data) == size and p.digest(data) == expected_hash, 'Synthetic downloaded hash mismatch.')
        Path(destination).write_bytes(data)

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs.get('authenticated', False)))
        if method == 'POST' and url == p.API+'/releases':
            value = p.t.parse_json(kwargs['payload'])
            value.update(id=402, published_at=None, html_url=p.WEB+'/releases/tag/untagged-402')
            self.releases[402] = value
            if self.uncertain == 'create':
                raise p.GateError('Synthetic uncertain create.')
            return 201, {}, encoded(value)
        if method == 'POST' and url.startswith(p.UPLOADS):
            release_id = int(url.split('/releases/')[1].split('/')[0])
            name = p.urllib.parse.parse_qs(p.urllib.parse.urlsplit(url).query)['name'][0]
            data = kwargs['payload'].read()
            row = self.add_asset(max(self.asset_data)+1, release_id, name, data)
            if self.uncertain == 'upload':
                raise p.GateError('Synthetic uncertain upload.')
            return 201, {}, encoded(row)
        if method == 'PATCH':
            release_id = int(url.rsplit('/',1)[-1])
            row = self.releases[release_id]
            row.update(draft=False, published_at='2026-11-08T00:00:00Z', html_url=p.WEB+'/releases/tag/'+row['tag_name'])
            if self.uncertain == 'publish':
                raise p.GateError('Synthetic uncertain publish.')
            return 200, {}, encoded(row)
        if method == 'GET' and '/git/ref/tags/' in url:
            return (404, {}, b'{}') if self.tag_sha is None else (200, {}, encoded({'object':{'type':'commit','sha':self.tag_sha}}))
        if method == 'GET' and '/releases/download/' in url:
            matches = [(rid,data,row) for rid,data,row in self.asset_data.values() if row['browser_download_url']==url]
            p.require(len(matches)==1, 'Missing synthetic download.')
            rid,data,row=matches[0]
            if self.corrupt_public:
                data += b'corrupt'
            Path(kwargs['destination']).write_bytes(data)
            return 200, {}, b''
        if method == 'GET' and '/releases/' in url:
            if '/tags/' in url:
                tag = url.rsplit('/',1)[-1]
                values = [r for r in self.releases.values() if r['tag_name']==tag]
            else:
                values = [self.releases[int(url.rsplit('/',1)[-1])]]
            p.require(len(values)==1, 'Wrong synthetic release.')
            return 200, {}, encoded(values[0])
        raise AssertionError('Unexpected '+method+' '+url)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='offline-test-', dir=p.HERE)
        self.root = Path(self.temp.name)
        self.f = Fixture(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def assertGate(self, fn):
        with self.assertRaises((p.GateError, KeyError, TypeError, ValueError)):
            fn()

    def test_complete_synthetic_offline_gate(self):
        self.assertEqual(self.f.gate()['commit'], self.f.lock['source_identity']['snapshot_commit'])

    def test_all_missing_ids_fail_closed(self):
        for key in ('release_id','asset_id','manifest_asset_id','producer_attempt'):
            lock = copy.deepcopy(self.f.lock); lock['candidate'][key] = None
            self.assertGate(lambda: p.validate_lock(lock))

    def test_missing_pixel_inspection_receipt(self):
        self.assertGate(lambda: p.review_gate({}, [], self.f.lock))

    def test_false_pixel_inspection(self):
        self.f.review['pixel_inspection_completed'] = False
        self.assertGate(self.f.gate)

    def test_blocking_inspection_finding(self):
        self.f.review['blocking_findings'] = ['Synthetic clipped window']
        self.assertGate(self.f.gate)

    def test_individual_pixel_review_missing(self):
        self.f.review['captures'][0]['pixels_reviewed'] = False
        self.assertGate(self.f.gate)

    def test_pixel_inspection_binds_binary(self):
        self.f.review['executable_sha256'] = '0'*64
        self.assertGate(self.f.gate)

    def test_pixel_inspection_binds_archive(self):
        self.f.review['private_artifact_sha256']['2025'] = '0'*64
        self.assertGate(self.f.gate)

    def test_pixel_inspection_binds_pixels(self):
        self.f.review['captures'][0]['sha256'] = '0'*64
        self.assertGate(self.f.gate)

    def test_missing_screenshot_review(self):
        self.f.review['captures'].pop()
        self.assertGate(self.f.gate)

    def test_duplicate_screenshot_review(self):
        self.f.review['captures'][0] = self.f.review['captures'][1]
        self.assertGate(self.f.gate)

    def test_changed_diagnostic_archive(self):
        with (self.root/'private2022.zip').open('ab') as output:
            output.write(b'corruption')
        self.assertGate(self.f.gate)

    def test_source_failed_command(self):
        self.f.change('source','2022','command-receipts.json', lambda r:r[0].update(exit_code=1))
        self.assertGate(self.f.gate)

    def test_source_missing_command(self):
        self.f.change('source','2022','command-receipts.json', lambda r:r.pop())
        self.assertGate(self.f.gate)

    def test_source_failed_lifecycle(self):
        self.f.change('source','2025','tk-lifecycle/SUMMARY.json', lambda r:r['attempts'][0].update(passed=False))
        self.assertGate(self.f.gate)

    def test_source_unexpected_lifecycle_skip(self):
        self.f.change('source','2025','tk-lifecycle/SUMMARY.json', lambda r:r['attempts'][0]['junit'].update(skipped=1))
        self.assertGate(self.f.gate)

    def test_source_failed_small_screen(self):
        self.f.change('source','2025','display-small.json', lambda r:r.update(passed=False))
        self.assertGate(self.f.gate)

    def test_source_changed_equations(self):
        self.f.change('source','2022','reviewed-source-provenance.json', lambda r:r.update(product_equations_changed=True))
        self.assertGate(self.f.gate)

    def test_source_junit_failure(self):
        self.f.files['source2022']['full-integration.xml'] = self.f.files['source2022']['full-integration.xml'].replace(b'<testcase ', b'<testcase ',1).replace(b'</testcase>',b'<failure /></testcase>',1)
        self.f.zip('source','2022')
        self.assertGate(self.f.gate)

    def test_source_unexpected_skip(self):
        self.f.files['source2022']['full-integration.xml'] = self.f.files['source2022']['full-integration.xml'].replace(p.SKIP.encode(), b'test_unexpected_skip')
        self.f.zip('source','2022')
        self.assertGate(self.f.gate)

    def test_source_missing_bootstrap(self):
        self.f.files['source2022']['corrected-tcl-bootstrap.xml'] = xml(99)
        self.f.zip('source','2022')
        self.assertGate(self.f.gate)

    def test_producer_hash_mismatch(self):
        self.f.change('private','2022','0-facs-v22-evidence/candidate-build-result.json', lambda r:r.update(executable_sha256='0'*64))
        self.assertGate(self.f.gate)

    def test_producer_source_file_hash_mismatch(self):
        self.f.change('private','2022','1-evidence/Build_Manifest.json', lambda r:r['product_source_sha256'].update({'facility_studio/fusion_settings.py':'0'*64}))
        self.assertGate(self.f.gate)

    def test_consumer_wrong_asset_id(self):
        self.f.change('private','2025','1-facs-v22-independent-2025/Independent_Windows_2025.json', lambda r:r.update(asset_id=999))
        self.assertGate(self.f.gate)

    def test_consumer_wrong_os(self):
        self.f.change('private','2025','1-facs-v22-independent-2025/Independent_Windows_2025.json', lambda r:r.update(os_build=20348))
        self.assertGate(self.f.gate)

    def test_failed_frozen_suite(self):
        self.f.change('private','2025','1-facs-v22-independent-2025/single-exe/Single_EXE_Verification.json', lambda r:r['records'][0].update(exit_code=1))
        self.assertGate(self.f.gate)

    def test_duplicate_frozen_suite(self):
        self.f.change('private','2025','1-facs-v22-independent-2025/single-exe/Single_EXE_Verification.json', lambda r:r['records'].__setitem__(0,r['records'][1]))
        self.assertGate(self.f.gate)

    def test_missing_external_command(self):
        self.f.change('private','2022','0-facs-v22-evidence/external-frozen/Frozen_External_Checks.json', lambda r:r['commands'].pop())
        self.assertGate(self.f.gate)

    def test_failed_external_command(self):
        self.f.change('private','2022','0-facs-v22-evidence/external-frozen/Frozen_External_Checks.json', lambda r:r['commands'][0].update(exit_code=1))
        self.assertGate(self.f.gate)

    def test_capture_close_failure(self):
        self.f.change('private','2022','0-facs-v22-evidence/external-frozen/Frozen_External_Checks.json', lambda r:r['screenshots'][0].update(closed_cleanly=False))
        self.assertGate(self.f.gate)

    def test_changed_screenshot_pixel_bytes(self):
        key='0-facs-v22-evidence/external-frozen/plain/en-simple-startup/startup.png'
        self.f.files['private2022'][key] += b'mutation'
        self.f.zip('private','2022')
        self.assertGate(self.f.gate)

    def test_archive_traversal_rejected(self):
        self.f.files['private2022']['../bad.json']=b'{}'
        self.f.zip('private','2022')
        self.assertGate(self.f.gate)

    def test_archive_binary_rejected(self):
        self.f.files['private2022']['bad.exe']=b'MZ'
        self.f.zip('private','2022')
        self.assertGate(self.f.gate)

    def test_trusted_file_corruption_rejected(self):
        file=self.root/'pinned.json'; file.write_bytes(b'{}')
        self.assertGate(lambda:p.pinned_json(file,'0'*64))

    def test_duplicate_json_key_rejected(self):
        self.assertGate(lambda:p.t.parse_json(b'{"passed":false,"passed":true}'))

    def test_live_gate_requires_exact_successful_runs_jobs_and_artifacts(self):
        p.online_gate(FakeClient(self.f),self.f.lock)

    def test_live_gate_rejects_still_running_workflow(self):
        c=FakeClient(self.f); c.metadata['/actions/runs/303']['status']='in_progress'
        self.assertGate(lambda:p.online_gate(c,self.f.lock))

    def test_live_gate_rejects_failure(self):
        c=FakeClient(self.f); c.metadata['/actions/runs/303']['conclusion']='failure'
        self.assertGate(lambda:p.online_gate(c,self.f.lock))

    def test_live_gate_rejects_other_commit(self):
        c=FakeClient(self.f); c.metadata['/actions/runs/303']['head_sha']='0'*40
        self.assertGate(lambda:p.online_gate(c,self.f.lock))

    def test_live_gate_rejects_fork(self):
        c=FakeClient(self.f); c.metadata['/actions/runs/303']['head_repository']={'full_name':'other/repo'}
        self.assertGate(lambda:p.online_gate(c,self.f.lock))

    def test_live_gate_rejects_skipped_required_step(self):
        c=FakeClient(self.f); c.metadata['/actions/jobs/204']['steps'][0]['conclusion']='skipped'
        self.assertGate(lambda:p.online_gate(c,self.f.lock))

    def test_live_gate_rejects_artifact_digest_mismatch(self):
        c=FakeClient(self.f); c.metadata['/actions/artifacts/604']['digest']='sha256:'+'0'*64
        self.assertGate(lambda:p.online_gate(c,self.f.lock))

    def test_live_gate_rejects_expired_artifact(self):
        c=FakeClient(self.f); c.metadata['/actions/artifacts/604']['expired']=True
        self.assertGate(lambda:p.online_gate(c,self.f.lock))

    def test_live_gate_rejects_unknown_artifact_digest(self):
        c=FakeClient(self.f); c.metadata['/actions/artifacts/604']['digest']=None
        self.assertGate(lambda:p.online_gate(c,self.f.lock))

    def test_private_release_must_remain_draft(self):
        c=FakeClient(self.f); c.releases[401]['draft']=False
        self.assertGate(lambda:p.verify_private(c,self.f.lock))

    def stage(self, c):
        source=self.f.gate()
        p.online_gate(c,self.f.lock)
        files=p.prepare_payloads(c,self.f.lock,source,self.root/'exact-bytes')
        final=p.FinalRelease(self.f.lock)
        rid=final.create(c)
        assets=[final.upload(c,rid,path) for path in files]
        return final,rid,assets

    def test_full_synthetic_publication_preserves_private_and_macos_scope(self):
        c=FakeClient(self.f)
        original=copy.deepcopy(c.releases[401])
        with redirect_stdout(io.StringIO()) as output:
            final,rid,assets=self.stage(c)
            final.publish(c,rid,assets)
        self.assertEqual(c.releases[401],original)
        self.assertFalse(c.releases[rid]['draft'])
        self.assertIn('published_and_anonymous_download_verified',output.getvalue())
        writes=[(method,url) for method,url,auth in c.calls if method in {'POST','PATCH','DELETE','PUT'}]
        self.assertEqual(len([x for x in writes if x[0]=='POST']),4)
        self.assertEqual([x for x in writes if x[0]=='PATCH'],[('PATCH',p.API+'/releases/402')])
        self.assertFalse(any('/401' in url or method in {'DELETE','PUT'} for method,url in writes))
        self.assertEqual({x['name'] for x in assets},p.ASSETS)
        self.assertNotIn(p.t.MANIFEST_NAME,{x['name'] for x in assets})

    def test_no_writes_when_private_hash_mismatched(self):
        c=FakeClient(self.f); rid,data,row=c.asset_data[501]; c.asset_data[501]=(rid,data+b'bad',row)
        with redirect_stdout(io.StringIO()):
            self.assertGate(lambda:self.stage(c))
        self.assertFalse(any(m in {'POST','PATCH','DELETE'} for m,u,a in c.calls))

    def test_private_release_cannot_be_resumed_as_final(self):
        c=FakeClient(self.f)
        self.assertGate(lambda:p.FinalRelease(self.f.lock).create(c,401))
        self.assertFalse(any(m in {'POST','PATCH','DELETE'} for m,u,a in c.calls))

    def test_uncertain_create_is_inspected_not_retried(self):
        c=FakeClient(self.f); c.uncertain='create'
        with redirect_stdout(io.StringIO()):
            self.assertGate(lambda:p.FinalRelease(self.f.lock).create(c))
            self.assertGate(lambda:p.FinalRelease(self.f.lock).create(c))
        self.assertEqual(sum(m=='POST' for m,u,a in c.calls),1)
        self.assertTrue(c.releases[402]['draft'])

    def test_uncertain_upload_is_inspected_not_retried(self):
        c=FakeClient(self.f)
        with redirect_stdout(io.StringIO()):
            final=p.FinalRelease(self.f.lock); rid=final.create(c)
            file=self.root/p.EXE; file.write_bytes(self.f.binary)
            c.uncertain='upload'
            self.assertGate(lambda:final.upload(c,rid,file))
        self.assertEqual(sum(m=='POST' and u.startswith(p.UPLOADS) for m,u,a in c.calls),1)
        self.assertFalse(any(m=='PATCH' for m,u,a in c.calls))

    def test_explicit_resume_reconciles_existing_asset_without_overwrite(self):
        c=FakeClient(self.f)
        with redirect_stdout(io.StringIO()):
            final=p.FinalRelease(self.f.lock); rid=final.create(c)
            file=self.root/p.EXE; file.write_bytes(self.f.binary)
            row=final.upload(c,rid,file)
            self.assertEqual(final.create(c,rid),rid)
            self.assertEqual(final.upload(c,rid,file),row)
        self.assertEqual(sum(m=='POST' and u.startswith(p.UPLOADS) for m,u,a in c.calls),1)

    def test_starter_asset_cannot_be_replaced(self):
        c=FakeClient(self.f)
        with redirect_stdout(io.StringIO()):
            final=p.FinalRelease(self.f.lock); rid=final.create(c)
            row=c.add_asset(503,rid,p.EXE,self.f.binary); row['state']='starter'
            file=self.root/p.EXE; file.write_bytes(self.f.binary)
            self.assertGate(lambda:final.upload(c,rid,file))
        self.assertFalse(any(m in {'PATCH','DELETE'} or (m=='POST' and u.startswith(p.UPLOADS)) for m,u,a in c.calls))

    def test_uncertain_publish_is_inspected_not_retried(self):
        c=FakeClient(self.f)
        with redirect_stdout(io.StringIO()):
            final,rid,assets=self.stage(c); c.uncertain='publish'
            self.assertGate(lambda:final.publish(c,rid,assets))
            self.assertGate(lambda:final.publish(c,rid,assets))
        self.assertEqual(sum(m=='PATCH' for m,u,a in c.calls),1)
        self.assertFalse(c.releases[rid]['draft'])

    def test_anonymous_download_mismatch_stops_without_delete(self):
        c=FakeClient(self.f)
        with redirect_stdout(io.StringIO()):
            final,rid,assets=self.stage(c); c.corrupt_public=True
            self.assertGate(lambda:final.publish(c,rid,assets))
        self.assertFalse(c.releases[rid]['draft'])
        self.assertFalse(any(m=='DELETE' for m,u,a in c.calls))

    def test_changed_workflow_after_staging_prevents_publish(self):
        c=FakeClient(self.f)
        with redirect_stdout(io.StringIO()):
            final,rid,assets=self.stage(c)
            c.metadata['/actions/runs/303']['status']='in_progress'
            self.assertGate(lambda:final.publish(c,rid,assets))
        self.assertFalse(any(m=='PATCH' for m,u,a in c.calls))

    def test_publication_note_has_measured_scope_and_safety_limits(self):
        note=p.release_note(self.f.lock)
        for phrase in ('Windows Server 2022 and 2025','No claim of end-user Windows 10/11','Not code-signed',
                       'No formal FEED approval','remain intentionally restricted','equations were not changed'):
            self.assertIn(phrase,note)

    def test_credentials_for_other_host_rejected_before_transport(self):
        client=p.t.Client('SYNTHETIC-TOKEN-NOT-SECRET')
        with patch.object(client.opener,'open',side_effect=AssertionError('Network must not run')):
            self.assertGate(lambda:client.request('GET','https://attacker.invalid/',authenticated=True))
            self.assertGate(lambda:client.request('POST','https://api.github.com/repos/other/repo/releases',authenticated=True))

    def test_duplicate_external_commands_rejected(self):
        self.f.change('private','2022','0-facs-v22-evidence/external-frozen/Frozen_External_Checks.json',
            lambda r:r.update(commands=[r['commands'][0]] * 118))
        self.assertGate(self.f.gate)

    def test_missing_refusal_expected_exit_rejected(self):
        self.f.change('private','2022','0-facs-v22-evidence/external-frozen/Frozen_External_Checks.json',
            lambda r:[x.update(expected_exit=0, exit_code=0) for x in r['commands'] if x['expected_exit']==2])
        self.assertGate(self.f.gate)

    def test_wrong_tag_prevents_publication_before_patch(self):
        c=FakeClient(self.f)
        with redirect_stdout(io.StringIO()):
            final,rid,assets=self.stage(c)
            c.tag_sha='0'*40
            self.assertGate(lambda:final.publish(c,rid,assets))
        self.assertFalse(any(m=='PATCH' for m,u,a in c.calls))
        self.assertTrue(c.releases[rid]['draft'])

    def test_wrong_tag_prevents_explicit_resume(self):
        c=FakeClient(self.f)
        with redirect_stdout(io.StringIO()):
            final=p.FinalRelease(self.f.lock); rid=final.create(c)
            c.tag_sha='0'*40
            self.assertGate(lambda:final.create(c,rid))
        self.assertFalse(any(m=='PATCH' for m,u,a in c.calls))

    def test_source_snapshot_lock_mismatch_rejected(self):
        self.f.lock['source_identity']['snapshot_commit']='0'*40
        self.assertGate(self.f.gate)

    def test_source_counts_lock_mismatch_rejected(self):
        self.f.lock['source_identity']['passed_tests']+=1
        self.assertGate(self.f.gate)

    def test_source_run_commit_lock_mismatch_rejected(self):
        self.f.lock['source_run']['commit']='0'*40
        self.assertGate(self.f.gate)

    def test_read_only_artifact_fetch_strips_token_on_storage_redirect(self):
        c=FakeClient(self.f)
        for role in ('source','private'):
            for artifact in self.f.lock[role+'_artifacts'].values():
                c.metadata['/actions/artifacts/'+str(artifact['id'])]['size_in_bytes']=(self.root/artifact['zip']).stat().st_size
        requests=[]
        def request(method,url,**kwargs):
            requests.append((url,kwargs.get('authenticated',False)))
            if url.startswith(p.API):
                identifier=int(url.split('/artifacts/')[1].split('/')[0])
                return 302, {'Location':'https://productionresultssa1.blob.core.windows.net/synthetic/'+str(identifier)+'?sig=DO-NOT-LOG'}, b''
            identifier=int(url.split('?')[0].rsplit('/',1)[-1])
            artifact=next(a for role in ('source','private') for a in self.f.lock[role+'_artifacts'].values() if a['id']==identifier)
            Path(kwargs['destination']).write_bytes((self.root/artifact['zip']).read_bytes())
            return 200,{},b''
        c.request=request
        with redirect_stdout(io.StringIO()) as output:
            p.fetch_evidence(c,self.f.lock,self.root/'downloaded')
        self.assertEqual(len(requests),8)
        self.assertTrue(all(auth==url.startswith(p.API) for url,auth in requests))
        self.assertNotIn('DO-NOT-LOG',output.getvalue())
        self.assertFalse(any(m in {'POST','PATCH','DELETE'} for m,u,a in c.calls))

    def test_artifact_unknown_storage_host_fails_before_redirect(self):
        c=FakeClient(self.f)
        for role in ('source','private'):
            for artifact in self.f.lock[role+'_artifacts'].values():
                c.metadata['/actions/artifacts/'+str(artifact['id'])]['size_in_bytes']=(self.root/artifact['zip']).stat().st_size
        calls=[]
        def request(method,url,**kwargs):
            calls.append(url)
            return 302, {'Location':'https://attacker.invalid/?sig=DO-NOT-LOG'}, b''
        c.request=request
        self.assertGate(lambda:p.fetch_evidence(c,self.f.lock,self.root/'downloaded'))
        self.assertEqual(len(calls),1)

    def test_dispatch_staging_preserves_exact_utf8_bytes(self):
        import write_invocation as w
        raw='{"reviewer":"發布審查員"}'
        environment={'RUNNER_TEMP':str(self.root),'GITHUB_ENV':str(self.root/'github-env'),
            'PUBLICATION_LOCK_JSON':raw,'PUBLICATION_REVIEW_JSON':raw,
            'PUBLICATION_LOCK_SHA256':p.digest(raw.encode()),'PUBLICATION_REVIEW_SHA256':p.digest(raw.encode()),
            'GH_TOKEN':'SYNTHETIC-DO-NOT-WRITE'}
        with patch.dict(p.os.environ,environment,clear=True),redirect_stdout(io.StringIO()):
            w.main()
        folder=next(self.root.glob('facs-final-invocation-*'))
        self.assertEqual((folder/'lock.json').read_bytes(),raw.encode())
        self.assertNotIn('SYNTHETIC-DO-NOT-WRITE',(self.root/'github-env').read_text())

    def test_dispatch_input_hash_mismatch_stops_before_staging(self):
        import write_invocation as w
        environment={'RUNNER_TEMP':str(self.root),'GITHUB_ENV':str(self.root/'github-env'),
            'PUBLICATION_LOCK_JSON':'{}','PUBLICATION_REVIEW_JSON':'{}',
            'PUBLICATION_LOCK_SHA256':'0'*64,'PUBLICATION_REVIEW_SHA256':'0'*64}
        with patch.dict(p.os.environ,environment,clear=True):
            self.assertGate(w.main)
        self.assertFalse(list(self.root.glob('facs-final-invocation-*')))

    def test_native_startup_missing_dimension_rejected(self):
        del self.f.files['source2022']['startup-placement-1024-768.xml']
        self.f.zip('source','2022')
        self.assertGate(self.f.gate)

    def test_native_startup_skip_rejected(self):
        key='startup-placement-1920-1080.xml'
        self.f.files['source2025'][key]=self.f.files['source2025'][key].replace(b' />',b'><skipped /></testcase>',1)
        self.f.zip('source','2025')
        self.assertGate(self.f.gate)

    def test_native_startup_duplicate_launch_rejected(self):
        key='startup-placement-1920-1080.xml'
        self.f.files['source2022'][key]=self.f.files['source2022'][key].replace(b'[1-simple-en]',b'[0-simple-en]')
        self.f.zip('source','2022')
        self.assertGate(self.f.gate)

    def test_native_startup_wrong_measured_display_rejected(self):
        self.f.change('source','2025','startup-display-1024-768.json',lambda r:r['after'].update(screen=[1920,1080]))
        self.assertGate(self.f.gate)

    def test_native_startup_nonexact_display_rejected(self):
        self.f.change('source','2022','startup-display-1920-1080.json',lambda r:r.update(exact=False))
        self.assertGate(self.f.gate)

    def test_producer_prebuild_startup_is_mandatory(self):
        del self.f.files['private2022']['0-facs-v22-evidence/prebuild-startup-placement.xml']
        self.f.zip('private','2022')
        self.assertGate(self.f.gate)

    def test_producer_prebuild_wrong_native_windowing_rejected(self):
        self.f.change('private','2022','0-facs-v22-evidence/prebuild-startup-display.json',lambda r:r['tk'].update(windowing='x11'))
        self.assertGate(self.f.gate)

    def test_source_native_startup_must_precede_complete_suite(self):
        c=FakeClient(self.f)
        c.metadata['/actions/jobs/201']['steps'][0]['number']=999
        self.assertGate(lambda:p.online_gate(c,self.f.lock))

    def test_producer_native_startup_must_precede_build(self):
        c=FakeClient(self.f)
        c.metadata['/actions/jobs/203']['steps'][0]['number']=999
        self.assertGate(lambda:p.online_gate(c,self.f.lock))

    def test_no_post_retry_or_delete_implementation(self):
        code=(p.HERE/'publish_verified_windows.py').read_text()
        self.assertNotIn("request('DELETE'",code)
        self.assertNotIn('subprocess',code)
        self.assertNotIn('pip install',code)


if __name__=='__main__':
    unittest.main()
