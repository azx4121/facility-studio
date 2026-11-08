"""Offline only. Socket deny also protects imported transport regression tests."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import unittest
from unittest import mock
import owner_draft_handoff as h
import private_draft_transfer as t


def deny_socket(*args, **kwargs):
    raise AssertionError('Network forbidden in offline suite')

socket.socket.connect = deny_socket
socket.socket.connect_ex = deny_socket
socket.create_connection = deny_socket


class OwnerHandoffTests(unittest.TestCase):
    def setUp(self):
        self.scope = t.Scope(12345, 2, 'a' * 40)
        self.now = 100000
        self.value = dict(repository=t.REPOSITORY, purpose=h.PURPOSE, workflow_sha=self.scope.commit,
                          run_id=12345, run_attempt=2, release_id=55, expires_at=self.now + 7000)
        self.client = mock.Mock()
        self.client.get_json.return_value = {'ref': 'refs/heads/' + t.BRANCH,
                                             'object': {'type': 'commit', 'sha': 'b' * 40}}
        self.install(self.value)

    def install(self, value):
        raw = t.canonical_json(value)
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        self.metadata = dict(type='file', path=h.path_for(self.scope), encoding='base64',
                             size=len(raw), content=base64.b64encode(raw).decode(), sha=blob)
        self.client.request.return_value = (200, {}, t.canonical_json(self.metadata))

    def read(self):
        return h.read_record(self.client, self.scope, self.now)

    def test_valid_pins_exact_content(self):
        receipt = self.read()
        self.assertEqual(receipt['record'], self.value)
        self.assertEqual(receipt['commit'], 'b' * 40)
        self.assertEqual(receipt['blob'], self.metadata['sha'])
        self.assertEqual(receipt['sha256'], hashlib.sha256(t.canonical_json(self.value)).hexdigest())
        self.assertEqual(self.client.request.call_args.args[1],
                         t.API + '/contents/' + h.path_for(self.scope) + '?ref=' + 'b' * 40)

    def test_closed_scope_and_integer_types(self):
        changes = [('repository', 'other/repo'), ('purpose', 'url'), ('workflow_sha', 'b' * 40),
                   ('run_id', 1), ('run_attempt', 1), ('run_id', True), ('release_id', True),
                   ('release_id', '55'), ('release_id', 0), ('expires_at', self.now),
                   ('expires_at', self.now + h.MAX_TTL + 1), ('url', 'https://evil'),
                   ('command', 'echo evil'), ('credentials', 'secret')]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                data = dict(self.value, **{key: value})
                self.install(data)
                with self.assertRaises(t.GateError): self.read()
        for key in self.value:
            data = dict(self.value); del data[key]; self.install(data)
            with self.assertRaises(t.GateError): self.read()

    def test_duplicate_deep_multiple_and_oversized_data(self):
        for raw in (b'{"x":1,"x":2}', b'[' * 1500 + b']' * 1500, b'{}{}', b' ' * 2049,
                    b'NaN', t.canonical_json([self.value])):
            with self.subTest(raw=raw[:20]), self.assertRaises(t.GateError):
                h.decode_record(raw, self.scope, self.now)
        with mock.patch.object(t.json, 'loads', side_effect=RecursionError):
            with self.assertRaises(t.GateError): t.parse_json(b'[]')

    def test_content_metadata_must_match(self):
        for key, value in [('type', 'symlink'), ('path', 'other'), ('encoding', 'none'),
                           ('sha', 'c' * 40), ('size', True), ('size', 2049), ('content', '%%%')]:
            data = dict(self.metadata, **{key: value})
            self.client.request.return_value = (200, {}, t.canonical_json(data))
            with self.subTest(key=key), self.assertRaises(t.GateError): self.read()

    def test_only_missing_content_can_poll(self):
        self.client.request.return_value = (404, {}, b'')
        self.assertIsNone(self.read())
        for status in (301, 401, 403, 429, 500):
            self.client.request.return_value = (status, {}, b'')
            with self.assertRaises(t.GateError): self.read()
        self.client.get_json.side_effect = t.GateError('Ref missing')
        with self.assertRaises(t.GateError): self.read()

    def test_wrong_ref_and_noncommit_fail(self):
        for ref in ({'ref': 'refs/heads/main', 'object': {'type': 'commit', 'sha': 'b' * 40}},
                    {'ref': 'refs/heads/' + t.BRANCH, 'object': {'type': 'tag', 'sha': 'b' * 40}}):
            self.client.get_json.return_value = ref
            with self.assertRaises(t.GateError): self.read()

    def test_poll_is_bounded_and_invalid_never_retried(self):
        self.client.request.return_value = (404, {}, b'')
        sleep = mock.Mock()
        with self.assertRaises(t.GateError):
            h.wait_record(self.client, self.scope, 20, clock=lambda:self.now, monotonic=lambda:0, sleep=sleep)
        self.assertEqual(self.client.request.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        for error in (t.GateError('Invalid'), t.TransportUncertain('Unknown')):
            with mock.patch.object(h, 'read_record', side_effect=error) as read:
                with self.assertRaises(t.GateError): h.wait_record(self.client, self.scope, 20)
                self.assertEqual(read.call_count, 1)
        for seconds in (-1, 301, True):
            with self.assertRaises(t.GateError): h.wait_record(self.client, self.scope, seconds)

    def test_empty_gate_and_recheck_pins(self):
        receipt = self.read()
        with mock.patch.object(h, 'empty_gate') as gate:
            h.recheck(self.client, self.scope, receipt, 55, self.now)
            gate.assert_called_once_with(self.client, self.scope, 55)
        for field, value in [('commit', 'c' * 40), ('blob', 'd' * 40), ('sha256', 'e' * 64)]:
            changed = dict(receipt, **{field: value})
            with self.assertRaises(t.GateError): h.recheck(self.client, self.scope, changed, 55, self.now)
        with self.assertRaises(t.GateError): h.recheck(self.client, self.scope, receipt, 56, self.now)
        with self.assertRaises(t.GateError): h.recheck(self.client, self.scope, receipt, 55, self.now+7000)
        self.client.request.return_value = (404, {}, b'')
        with self.assertRaises(t.GateError): h.recheck(self.client, self.scope, receipt, 55, self.now)

    def test_empty_inventory_mandatory(self):
        with mock.patch.object(self.scope, 'gate'), mock.patch.object(t, 'inventory', return_value={'x': {}}):
            with self.assertRaises(t.GateError): h.empty_gate(self.client, self.scope, 55)

    def test_creation_and_metadata_writes_impossible(self):
        client = h.OwnerClient('test-token')
        client.approved_release_id = 55
        for method, url in [('POST', t.API + '/releases'), ('PATCH', t.API + '/releases/55'),
                            ('DELETE', t.API + '/releases/55'),
                            ('POST', t.UPLOADS + '/releases/56/assets?name=' + t.EXE_NAME)]:
            with self.assertRaises(t.GateError): client.request(method, url)
        with self.assertRaises(t.GateError):
            client.request('POST', t.UPLOADS + '/releases/55/assets?name=' + t.EXE_NAME)
        client.before_upload = mock.Mock(side_effect=t.GateError('Changed'))
        with self.assertRaises(t.GateError):
            client.request('POST', t.UPLOADS + '/releases/55/assets?name=' + t.EXE_NAME)
        client.before_upload.assert_called_once()

    def test_deep_asset_response_reconciles_once_and_stops(self):
        from test_private_transfer import FakeClient
        import tempfile
        import io
        client = FakeClient(self.scope)
        # In-memory fixture only, never a remote create.
        with mock.patch('sys.stdout', new_callable=io.StringIO):
            t.create_or_resume(client, self.scope, None)
        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder) / t.EXE_NAME
            exe.write_bytes(b'MZ synthetic')
            original = t.parse_json
            def deep(data):
                if data == b'deep-response':
                    with mock.patch.object(t.json, 'loads', side_effect=RecursionError):
                        return original(data)
                return original(data)
            with mock.patch.object(client, 'request', return_value=(201, {}, b'deep-response')) as post, \
                    mock.patch.object(t, 'parse_json', side_effect=deep), \
                    mock.patch('sys.stdout', new_callable=io.StringIO) as output:
                with self.assertRaises(t.GateError):
                    t.ensure_asset(client, self.scope, 55, exe, 'application/octet-stream')
                self.assertEqual(post.call_count, 1)
                self.assertIn('inspection_only', output.getvalue())
                self.assertEqual(client.calls[-1], ('pages', '/releases/55/assets'))

    def test_control_get_timeout_is_short(self):
        import urllib.request
        opener = mock.Mock()
        h.ReadTimeoutOpener(opener).open(urllib.request.Request(t.API + '/git/ref/heads/' + t.BRANCH))
        self.assertEqual(opener.open.call_args.kwargs['timeout'], 10)

    def test_inspection_projection_rejects_untrusted_objects_and_strings(self):
        malicious = ['https://evil.test/SECRET', {'secret': ['SECRET']}, ['SECRET'], True,
                     -1, 2**256]
        for value in malicious:
            with self.subTest(value=value):
                row = t.inspection_asset(dict(id=value, name=value, size=value, state=value))
                self.assertEqual(row, dict(id=None, name=None, bytes=None, state=None))
                self.assertNotIn('SECRET', json.dumps(row))
        self.assertEqual(t.inspection_asset(dict(id=55, name=t.EXE_NAME, size=0, state='starter')),
                         dict(id=55, name=t.EXE_NAME, bytes=0, state='starter'))

    def test_malicious_upload_failure_inventory_is_redacted_and_stops(self):
        from test_private_transfer import FakeClient
        import tempfile
        import io
        for value in ('https://evil.test/SECRET', {'nested': ['SECRET']}, ['SECRET'], True, 2**256):
            client = FakeClient(self.scope)
            with mock.patch('sys.stdout', new_callable=io.StringIO):
                t.create_or_resume(client, self.scope, None)
            def fail(*args, **kwargs):
                client.assets[t.EXE_NAME] = dict(name=t.EXE_NAME, id=value, size=value, state=value)
                return (403, {}, b'SECRET')
            with tempfile.TemporaryDirectory() as folder:
                exe = Path(folder) / t.EXE_NAME
                exe.write_bytes(b'MZ synthetic')
                with mock.patch.object(client, 'request', side_effect=fail) as post, \
                        mock.patch('sys.stdout', new_callable=io.StringIO) as output:
                    with self.assertRaises(t.GateError):
                        t.ensure_asset(client, self.scope, 55, exe, 'application/octet-stream')
                    self.assertEqual(post.call_count, 1)
                    self.assertEqual(client.calls[-1], ('pages', '/releases/55/assets'))
                    record = json.loads(output.getvalue())
                    self.assertTrue(record['inspection_only'])
                    self.assertEqual(record['assets'], [dict(name=t.EXE_NAME, id=None, bytes=None, state=None)])
                    self.assertNotIn('SECRET', output.getvalue())

    def test_release_inspection_redacts_nonboolean_draft_and_noninteger_id(self):
        import io
        client = mock.Mock()
        client.pages.return_value = [dict(tag_name=self.scope.tag, id={'SECRET': 1}, draft='SECRET')]
        with mock.patch('sys.stdout', new_callable=io.StringIO) as output:
            t.inspect_scope(client, self.scope)
        self.assertEqual(json.loads(output.getvalue())['matching_releases'],
                         [dict(id=None, draft=None, tag=self.scope.tag)])
        self.assertNotIn('SECRET', output.getvalue())

    def test_explicit_resume_is_required_before_client(self):
        with mock.patch.object(h, 'OwnerClient') as client:
            with self.assertRaises(SystemExit):
                h.main(['--run-id','12345','--run-attempt','2','--workflow-commit','a'*40,'stage',
                        '--receipt','receipt','--exe','exe','--build-receipt','build',
                        '--onefile-receipt','one','--external-receipt','ext','--build-manifest','manifest'])
            client.assert_not_called()

    def test_workflow_preserves_preflights_and_no_moving_checkout(self):
        from test_private_transfer import workflow_under_test
        workflow = workflow_under_test(__file__, os.environ.get('GITHUB_WORKSPACE')).read_text()
        self.assertLess(workflow.index('owner_draft_handoff.py'), workflow.index('Reconstruct reviewed source'))
        self.assertIn('--resume-release-id $env:OWNER_RELEASE_ID', workflow)
        self.assertIn('ref: ${{ github.sha }}', workflow)
        self.assertNotIn('ref: validation/', workflow)
        for guard in ('test_standalone_process_images.py', 'test_windows_startup_placement.py',
                      'test_windows_english_startup_native.py', 'test_windows_cold_startup.py',
                      'validate_downloaded_candidate.py', 'persist-credentials: false'):
            self.assertIn(guard, workflow)
