"""Pure offline tests: mocked GitHub, synthetic bytes, no network or release writes."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import urllib.parse

import private_draft_transfer as transfer


class FakeClient:
    """In-memory server with explicit public/draft and uncertain-write switches."""
    def __init__(self, scope):
        self.scope = scope
        self.release = None
        self.assets = {}
        self.blobs = {}
        self.calls = []
        self.public_release = False
        self.public_assets = False
        self.uncertain_create = False
        self.uncertain_upload = False

    def metadata(self, asset_id):
        return next(row for row in self.assets.values() if row['id'] == asset_id)

    def pages(self, path):
        self.calls.append(('pages', path))
        if path == '/releases':
            return [] if self.release is None else [copy.deepcopy(self.release)]
        if path == '/releases/55/assets':
            return list(copy.deepcopy(self.assets).values())
        raise AssertionError(path)

    def get_json(self, path):
        self.calls.append(('get_json', path))
        if path == '/releases/55':
            return copy.deepcopy(self.release)
        prefix = '/releases/assets/'
        if path.startswith(prefix):
            return copy.deepcopy(self.metadata(int(path[len(prefix):])))
        raise AssertionError(path)

    def absent(self, url):
        self.calls.append(('absent', url))
        if self.public_release or (self.public_assets and ('/assets/' in url or '/download/' in url)):
            raise transfer.GateError('Non-public gate requires anonymous HTTP 404; got HTTP 200.')

    def request(self, method, url, **kwargs):
        self.calls.append((method, url))
        assert method == 'POST' and kwargs['authenticated'] is True
        if url == transfer.API + '/releases':
            self.release = json.loads(kwargs['payload'])
            self.release.update(id=55, published_at=None, html_url=transfer.WEB + '/releases/tag/untagged-actual-private')
            if self.uncertain_create:
                raise transfer.GateError('Transport failure; uncertain outcome.')
            return 201, {}, transfer.canonical_json(self.release)
        prefix = transfer.UPLOADS + '/releases/55/assets?name='
        assert url.startswith(prefix)
        name = urllib.parse.unquote(url[len(prefix):])
        value = kwargs['payload'].read()
        asset_id = 100 + len(self.assets)
        row = {'id': asset_id, 'name': name, 'size': len(value), 'state': 'uploaded',
               'digest': 'sha256:' + hashlib.sha256(value).hexdigest(),
               'browser_download_url': transfer.WEB + '/releases/download/untagged-actual-private/' + name}
        self.assets[name], self.blobs[asset_id] = row, value
        if self.uncertain_upload:
            raise transfer.GateError('Transport failure; uncertain outcome.')
        return 201, {}, transfer.canonical_json(row)

    def download_asset(self, asset_id, destination, size, digest):
        self.calls.append(('download', asset_id))
        value = self.blobs[asset_id]
        assert not Path(destination).exists()
        Path(destination).write_bytes(value)
        transfer.require(len(value) == size and hashlib.sha256(value).hexdigest() == digest,
                         'Downloaded asset hash mismatch.')


class DraftGateTests(unittest.TestCase):
    def setUp(self):
        self.scope = transfer.Scope(123, 1, 'a' * 40)
        self.client = FakeClient(self.scope)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.exe = Path(self.temp.name) / transfer.EXE_NAME
        self.exe.write_bytes(b'MZ synthetic unit-test bytes, never a real executable')

    def create(self):
        with mock.patch('sys.stdout', new_callable=io.StringIO):
            return transfer.create_or_resume(self.client, self.scope, None)

    def upload_count(self):
        return sum(method == 'POST' and '/assets?' in path for method, path in self.client.calls)

    def test_create_empty_private_draft_and_probe_all_routes(self):
        self.assertEqual(self.create(), 55)
        self.assertTrue(self.client.release['draft'])
        self.assertEqual(self.client.assets, {})
        self.assertIn(('absent', transfer.API + '/releases/55'), self.client.calls)
        self.assertIn(('absent', transfer.API + '/releases/tags/' + self.scope.tag), self.client.calls)
        self.assertIn(('absent', transfer.WEB + '/releases/tag/' + self.scope.tag), self.client.calls)
        self.assertIn(('absent', transfer.WEB + '/releases/tag/untagged-actual-private'), self.client.calls)

    def test_public_release_never_uploads(self):
        self.create()
        self.client.public_release = True
        with self.assertRaises(transfer.GateError):
            transfer.ensure_asset(self.client, self.scope, 55, self.exe, 'application/octet-stream')
        self.assertEqual(self.upload_count(), 0)

    def test_published_release_never_uploads(self):
        self.create()
        self.client.release['draft'] = False
        with self.assertRaises(transfer.GateError):
            transfer.ensure_asset(self.client, self.scope, 55, self.exe, 'application/octet-stream')
        self.assertEqual(self.upload_count(), 0)

    def test_wrong_id_and_unrelated_macos_release_rejected(self):
        self.create()
        for field, value in [('id', 56), ('tag_name', 'facs-v22-r3-macos-arm64-unvalidated'),
            ('target_commitish', 'b' * 40), ('body', 'unrelated'), ('published_at', '2026-11-08')]:
            with self.subTest(field=field):
                data = copy.deepcopy(self.client.release)
                data[field] = value
                with self.assertRaises(transfer.GateError):
                    self.scope.release(data, 55)

    def test_existing_tag_requires_explicit_exact_id(self):
        self.create()
        before = len([x for x in self.client.calls if x[0] == 'POST'])
        with mock.patch('sys.stdout', new_callable=io.StringIO):
            with self.assertRaises(transfer.GateError):
                transfer.create_or_resume(self.client, self.scope, None)
        self.assertEqual(len([x for x in self.client.calls if x[0] == 'POST']), before)
        self.assertEqual(transfer.create_or_resume(self.client, self.scope, 55), 55)

    def test_uncertain_creation_inspected_without_retry(self):
        self.client.uncertain_create = True
        with mock.patch('sys.stdout', new_callable=io.StringIO):
            with self.assertRaises(transfer.GateError):
                transfer.create_or_resume(self.client, self.scope, None)
        self.assertIsNotNone(self.client.release)
        self.assertEqual(sum(x == ('POST', transfer.API + '/releases') for x in self.client.calls), 1)
        self.assertEqual(self.client.calls[-1], ('pages', '/releases'))

    def test_unknown_assets_cannot_be_added_or_replaced(self):
        self.create()
        self.client.assets['mac.zip'] = {'id': 77, 'name': 'mac.zip'}
        with self.assertRaises(transfer.GateError):
            transfer.ensure_asset(self.client, self.scope, 55, self.exe, 'application/octet-stream')
        self.assertEqual(self.upload_count(), 0)

    def test_upload_metadata_anonymous_probes_and_authenticated_bytes(self):
        self.create()
        row, digest = transfer.ensure_asset(self.client, self.scope, 55, self.exe, 'application/octet-stream')
        self.assertEqual(self.upload_count(), 1)
        self.assertEqual(digest, transfer.sha256(self.exe))
        self.assertIn(('absent', transfer.WEB + '/releases/download/untagged-actual-private/' + self.exe.name), self.client.calls)
        self.assertIn(('download', row['id']), self.client.calls)
        self.assertIn(('absent', transfer.API + '/releases/assets/' + str(row['id'])), self.client.calls)
        self.assertIn(('absent', transfer.WEB + '/releases/download/' + self.scope.tag + '/' + self.exe.name), self.client.calls)

    def test_resume_verified_asset_without_uploading_again(self):
        self.create()
        row, _ = transfer.ensure_asset(self.client, self.scope, 55, self.exe, 'application/octet-stream')
        again, _ = transfer.ensure_asset(self.client, self.scope, 55, self.exe, 'application/octet-stream')
        self.assertEqual(row['id'], again['id'])
        self.assertEqual(self.upload_count(), 1)
        self.assertEqual(sum(x == ('download', row['id']) for x in self.client.calls), 2)

    def test_uncertain_upload_inspected_not_retried(self):
        self.create()
        self.client.uncertain_upload = True
        with mock.patch('sys.stdout', new_callable=io.StringIO):
            with self.assertRaises(transfer.GateError):
                transfer.ensure_asset(self.client, self.scope, 55, self.exe, 'application/octet-stream')
        self.assertEqual(self.upload_count(), 1)
        self.assertEqual(self.client.calls[-1], ('pages', '/releases/55/assets'))
        self.assertIn(self.exe.name, self.client.assets)

    def test_public_asset_blocks_success(self):
        self.create()
        self.client.public_assets = True
        with self.assertRaises(transfer.GateError):
            transfer.ensure_asset(self.client, self.scope, 55, self.exe, 'application/octet-stream')
        self.assertEqual(self.upload_count(), 1)
        self.assertFalse(any(x[0] == 'download' for x in self.client.calls))

    def test_asset_with_corrupt_bytes_fails_even_without_server_digest(self):
        self.create()
        row, _ = transfer.ensure_asset(self.client, self.scope, 55, self.exe, 'application/octet-stream')
        self.client.assets[self.exe.name]['digest'] = None
        self.client.blobs[row['id']] = b'X' * self.exe.stat().st_size
        with self.assertRaises(transfer.GateError):
            transfer.ensure_asset(self.client, self.scope, 55, self.exe, 'application/octet-stream')
        self.assertEqual(self.upload_count(), 1)

    def test_partial_upload_is_never_replaced(self):
        self.create()
        self.client.assets[self.exe.name] = {'id': 100, 'name': self.exe.name, 'state': 'starter', 'size': 0}
        with self.assertRaises(transfer.GateError):
            transfer.ensure_asset(self.client, self.scope, 55, self.exe, 'application/octet-stream')
        self.assertEqual(self.upload_count(), 0)

    def test_duplicate_asset_names_fail(self):
        with mock.patch.object(self.client, 'pages', return_value=[{'name': self.exe.name}, {'name': self.exe.name}]):
            with self.assertRaises(transfer.GateError):
                transfer.inventory(self.client, 55)

    def test_unapproved_filename_no_network(self):
        path = self.exe.with_name('other.exe')
        path.write_bytes(b'MZ')
        with self.assertRaises(transfer.GateError):
            transfer.ensure_asset(self.client, self.scope, 55, path, 'application/octet-stream')
        self.assertEqual(self.client.calls, [])


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.client = transfer.Client('test-token-never-transmitted')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'download.exe'

    def test_anonymous_only_exact_404_passes(self):
        for status in (200, 302, 401, 403, 429, 500):
            with self.subTest(status=status), mock.patch.object(self.client, 'request', return_value=(status, {}, b'')) as call:
                with self.assertRaises(transfer.GateError):
                    self.client.absent(transfer.API + '/releases/55')
                self.assertFalse(call.call_args.kwargs['authenticated'])
        with mock.patch.object(self.client, 'request', return_value=(404, {}, b'')):
            self.client.absent(transfer.API + '/releases/55')

    def test_auth_cannot_target_external_or_other_repository(self):
        for url in ('https://example.com', 'https://api.github.com/repos/other/project/releases',
                    'http://api.github.com/repos/' + transfer.REPOSITORY + '/releases'):
            with self.subTest(url=url), mock.patch.object(self.client.opener, 'open') as opened:
                with self.assertRaises(transfer.GateError):
                    self.client.request('GET', url, authenticated=True)
                opened.assert_not_called()

    def test_redirect_download_strips_auth(self):
        value = b'unit bytes'
        digest = hashlib.sha256(value).hexdigest()
        calls = []
        def respond(method, url, **kwargs):
            calls.append((url, kwargs['authenticated']))
            if len(calls) == 1:
                return 302, {'Location': 'https://release-assets.githubusercontent.com/example?secret=signed'}, b''
            Path(kwargs['destination']).write_bytes(value)
            return 200, {}, b''
        with mock.patch.object(self.client, 'request', side_effect=respond):
            self.client.download_asset(100, self.output, len(value), digest)
        self.assertEqual([auth for _, auth in calls], [True, False])
        self.assertEqual(calls[0][0], transfer.API + '/releases/assets/100')

    def test_redirect_unknown_storage_fails_without_second_request(self):
        with mock.patch.object(self.client, 'request', return_value=(302, {'Location': 'https://evil.example/token'}, b'')) as request:
            with self.assertRaises(transfer.GateError):
                self.client.download_asset(100, self.output, 4, 'a' * 64)
        self.assertEqual(request.call_count, 1)

    def test_second_redirect_not_followed(self):
        with mock.patch.object(self.client, 'request', side_effect=[
                (302, {'Location': 'https://objects.githubusercontent.com/file?signature=secret'}, b''),
                (302, {'Location': 'https://evil.example'}, b'')]) as request:
            with self.assertRaises(transfer.GateError):
                self.client.download_asset(100, self.output, 4, 'a' * 64)
        self.assertEqual(request.call_count, 2)

    def test_metadata_json_is_not_treated_as_binary_success(self):
        def respond(*args, **kwargs):
            Path(kwargs['destination']).write_bytes(b'{}')
            return 200, {}, b''
        with mock.patch.object(self.client, 'request', side_effect=respond):
            with self.assertRaises(transfer.GateError):
                self.client.download_asset(100, self.output, 2, 'a' * 64)


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.source = {'provenance_schema': 1, 'version': '5.7.3', 'commit': 'b' * 40,
            'source_platform': 'windows', 'source_clean': True, 'build_channel': 'stable',
            'build_inputs_sha256': {'integration/build.py': 'a' * 64},
            'product_source_sha256': {'windows/facility_studio/app.py': 'b' * 64}}

    def test_duplicate_keys_rejected(self):
        with self.assertRaises(transfer.GateError):
            transfer.parse_json('{"draft":true,"draft":false}')

    def test_clean_windows_provenance_required(self):
        transfer.validate_source_manifest(self.source)
        for key, value in [('source_platform', 'macos'), ('source_clean', False),
                           ('build_channel', 'non-release'), ('commit', 'short'),
                           ('build_inputs_sha256', {}), ('provenance_schema', True)]:
            with self.subTest(key=key):
                changed = dict(self.source, **{key: value})
                with self.assertRaises(transfer.GateError):
                    transfer.validate_source_manifest(changed)

    def test_manifest_binds_all_same_run_identity(self):
        scope = transfer.Scope(123, 1, 'a' * 40)
        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder) / transfer.EXE_NAME
            exe.write_bytes(b'MZ')
            manifest = transfer.build_manifest(scope, 55, exe, self.source)
        transfer.validate_manifest(manifest, scope, 55, 2, hashlib.sha256(b'MZ').hexdigest())
        for key, value in [('release_id', 56), ('run_attempt', 2), ('published', True),
                           ('tag', 'facs-v22-r3-macos-arm64-unvalidated'), ('repository', 'other/repo')]:
            with self.subTest(key=key):
                with self.assertRaises(transfer.GateError):
                    transfer.validate_manifest(dict(manifest, **{key: value}), scope, 55, 2,
                                               hashlib.sha256(b'MZ').hexdigest())

    def test_scope_rejects_shell_or_tag_injection(self):
        for value in ('1\nPUBLIC=1', '-1', '1;exit', '', True):
            with self.subTest(value=value):
                with self.assertRaises(transfer.GateError):
                    transfer.Scope(value, 1, 'a' * 40)

    def test_workflow_has_no_public_binary_artifact_or_publish(self):
        workflow = (Path(__file__).parent / 'private-windows-handoff.yml').read_text()
        self.assertEqual(workflow.count('uses: actions/upload-artifact'), 2)
        self.assertIn('path: ${{ runner.temp }}/facs-private-diagnostics-2022/**', workflow)
        self.assertIn('path: ${{ runner.temp }}/facs-private-diagnostics-2025/**', workflow)
        self.assertNotIn('path: ${{ env.PRIVATE_INPUT }}', workflow)
        self.assertNotIn('gh release edit', '\n'.join(x for x in workflow.splitlines() if not x.startswith('#')))
        self.assertNotIn('contents: write\njobs:', workflow)
        self.assertIn('persist-credentials: false', workflow)
        self.assertIn('runs-on: windows-2022', workflow)
        self.assertIn('runs-on: windows-2025', workflow)
        self.assertIn('needs: build-private-candidate', workflow)


class ExpandedPreflightTests(unittest.TestCase):
    def setUp(self):
        import argparse
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        root = Path(self.folder.name)
        self.scope = transfer.Scope(123, 1, 'a' * 40)
        self.client = FakeClient(self.scope)
        self.exe = root / transfer.EXE_NAME
        self.exe.write_bytes(b'MZ test fixture')
        self.digest = transfer.sha256(self.exe)
        self.receipt = {'build_exit': 0, 'extended_exit': 0, 'unchanged': True,
            'executable_sha256': self.digest, 'executable_bytes': self.exe.stat().st_size}
        self.onefile = {'passed': True, 'native_windows': True, 'executable_sha256': self.digest,
            'records': [{'path_case': path, 'suite': suite, 'exit_code': 0}
                        for path in ('plain', 'unicode-space') for suite in ('fusion', 'facilities')]}
        self.external = {'passed': True, 'native_windows': True, 'original_exe_unchanged': True,
            'screenshots_requested': True, 'executable_sha256': self.digest,
            'commands': [{} for _ in range(118)], 'screenshots': [{} for _ in range(8)]}
        self.manifest = {'provenance_schema': 1, 'version': '5.7.3', 'commit': 'b' * 40,
            'source_platform': 'windows', 'source_clean': True, 'build_channel': 'stable',
            'build_inputs_sha256': {'integration/build.py': 'a' * 64},
            'product_source_sha256': {'windows/facility_studio/app.py': 'b' * 64}}
        self.args = argparse.Namespace(exe=self.exe, build_receipt=root / 'build.json',
            onefile_receipt=root / 'onefile.json', external_receipt=root / 'external.json',
            build_manifest=root / 'manifest.json', resume_release_id=None, github_outputs=False)
        self.persist()

    def persist(self):
        for path, data in ((self.args.build_receipt, self.receipt),
            (self.args.onefile_receipt, self.onefile), (self.args.external_receipt, self.external),
            (self.args.build_manifest, self.manifest)):
            path.write_bytes(transfer.canonical_json(data))

    def test_success_transfers_only_exact_two_authorized_assets(self):
        with mock.patch('sys.stdout', new_callable=io.StringIO):
            result = transfer.stage(self.client, self.scope, self.args)
        self.assertEqual(set(self.client.assets), transfer.ALLOWED_ASSETS)
        self.assertEqual(result['sha256'], self.digest)
        self.assertEqual(result['run_attempt'], 1)
        manifest = transfer.parse_json(self.client.blobs[result['manifest_asset_id']])
        self.assertIs(manifest['unvalidated'], True)
        self.assertIs(manifest['published'], False)

    def test_missing_one_of_four_runs_prevents_all_network(self):
        self.onefile['records'].pop()
        self.persist()
        with self.assertRaises(transfer.GateError):
            transfer.stage(self.client, self.scope, self.args)
        self.assertEqual(self.client.calls, [])

    def test_duplicate_of_four_runs_prevents_all_network(self):
        self.onefile['records'][-1] = self.onefile['records'][0]
        self.persist()
        with self.assertRaises(transfer.GateError):
            transfer.stage(self.client, self.scope, self.args)
        self.assertEqual(self.client.calls, [])

    def test_missing_external_command_prevents_all_network(self):
        self.external['commands'].pop()
        self.persist()
        with self.assertRaises(transfer.GateError):
            transfer.stage(self.client, self.scope, self.args)
        self.assertEqual(self.client.calls, [])

    def test_missing_startup_capture_prevents_all_network(self):
        self.external['screenshots'].pop()
        self.persist()
        with self.assertRaises(transfer.GateError):
            transfer.stage(self.client, self.scope, self.args)
        self.assertEqual(self.client.calls, [])

    def test_failed_external_summary_prevents_all_network(self):
        self.external['passed'] = False
        self.persist()
        with self.assertRaises(transfer.GateError):
            transfer.stage(self.client, self.scope, self.args)
        self.assertEqual(self.client.calls, [])

    def test_actual_url_must_be_exact_repo_and_expected_asset(self):
        urls = [
            'https://evil.example/azx4121/facility-studio/releases/tag/x',
            transfer.WEB + '/issues/123',
            'https://github.com/other/repo/releases/tag/x',
            transfer.WEB + '/releases/tag/a%2Fb',
            transfer.WEB + '/releases/tag/x?token=secret']
        for url in urls:
            with self.subTest(url=url), self.assertRaises(transfer.GateError):
                transfer.verified_public_url(url, 'release')
        with self.assertRaises(transfer.GateError):
            transfer.verified_public_url(transfer.WEB + '/releases/download/untagged/other.exe',
                                        'asset', transfer.EXE_NAME)

    def test_actual_untagged_url_public_stops_before_upload(self):
        with mock.patch('sys.stdout', new_callable=io.StringIO):
            transfer.create_or_resume(self.client, self.scope, None)
        original = self.client.absent
        def probe(url):
            if 'untagged-actual-private' in url:
                raise transfer.GateError('Actual untagged draft became public.')
            original(url)
        with mock.patch.object(self.client, 'absent', side_effect=probe):
            with self.assertRaises(transfer.GateError):
                transfer.ensure_asset(self.client, self.scope, 55, self.exe, 'application/octet-stream')
        self.assertFalse(any(method == 'POST' and '/assets?' in path for method, path in self.client.calls))


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        import prepare_diagnostics
        self.diagnostics = prepare_diagnostics
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.evidence = self.root / 'facs-v22-evidence'
        self.evidence.mkdir()
        self.output = self.root / 'diagnostics'

    def test_exe_zip_and_download_are_never_copied(self):
        (self.evidence / 'report.json').write_text('{"passed":true}')
        (self.evidence / 'screen.png').write_bytes(b'\x89PNG\r\n\x1a\n test')
        (self.evidence / 'candidate.exe').write_bytes(b'MZ secret candidate')
        (self.evidence / 'source-v22.zip').write_bytes(b'PK source archive')
        with mock.patch('sys.stdout', new_callable=io.StringIO):
            self.diagnostics.prepare([self.evidence], self.output)
        names = [path.name for path in self.output.rglob('*') if path.is_file()]
        self.assertIn('report.json', names)
        self.assertIn('screen.png', names)
        self.assertNotIn('candidate.exe', names)
        self.assertNotIn('source-v22.zip', names)

    def test_disguised_executable_leaves_no_upload_destination(self):
        (self.evidence / 'candidate.png').write_bytes(b'MZ hidden executable')
        with self.assertRaises(transfer.GateError):
            self.diagnostics.prepare([self.evidence], self.output)
        self.assertFalse(self.output.exists())

    def test_download_directory_not_an_accepted_source(self):
        folder = self.root / 'facs-private-input'
        folder.mkdir()
        with self.assertRaises(transfer.GateError):
            self.diagnostics.prepare([folder], self.output)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
