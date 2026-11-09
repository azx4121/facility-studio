"""Offline HTTP-contract controls; not proof of a historical remote HTTP status."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
import urllib.error
import urllib.parse

import publish_verified_windows as p
from test_publication import Fixture, FakeClient


TOKEN = 'SYNTHETIC-TOKEN-DO-NOT-LOG'
MARKER = 'SYNTHETIC-SIGNED-QUERY-DO-NOT-LOG'


class Response(io.BytesIO):
    def __init__(self, data, status=200, headers=None):
        super().__init__(data)
        self.status = status
        self.headers = headers or {}


class ArtifactOpener:
    """Exercise the unchanged pinned transport without opening any network socket."""
    def __init__(self, case):
        self.case = case
        self.calls = []
        self.api_status = 302
        self.storage_status = 200
        self.location = 'https://productionresultssa1.blob.core.windows.net/synthetic/'
        self.mutate = lambda data: data

    def open(self, request, timeout):
        self.case.assertEqual(request.get_method(), 'GET')
        self.calls.append(request)
        url = request.full_url
        is_api = url.startswith(p.API + '/')
        identifier = int(url.split('/artifacts/')[1].split('/')[0]) if is_api else int(
            urllib.parse.urlsplit(url).path.rsplit('/', 1)[-1])
        item = self.case.artifacts[identifier]
        data = (self.case.root / item['zip']).read_bytes()
        if is_api:
            self.case.assertEqual(request.get_header('Authorization'), 'Bearer ' + TOKEN)
            # Mirrors the documented Actions API media type. Reverting the fix
            # fails this control before a synthetic storage request can occur.
            self.case.assertEqual(request.get_header('Accept'), 'application/vnd.github+json')
            if self.api_status == 200:
                return Response(self.mutate(data))
            headers = {'Location': self.location + str(identifier) + '?sig=' + MARKER}
            # The real NoRedirect handler returns redirects as HTTPError.
            raise urllib.error.HTTPError(url, self.api_status, 'synthetic', headers,
                io.BytesIO((MARKER + TOKEN).encode()))
        self.case.assertIsNone(request.get_header('Authorization'))
        self.case.assertEqual(request.get_header('Accept'), 'application/zip')
        self.case.assertFalse((self.case.output / item['zip']).exists(),
            'The redirect response must not create the destination file.')
        if self.storage_status == 200:
            return Response(self.mutate(data))
        raise urllib.error.HTTPError(url, self.storage_status, 'synthetic',
            {'Location': 'https://attacker.invalid/?sig=' + MARKER},
            io.BytesIO((MARKER + TOKEN).encode()))


class ArtifactFetchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='artifact-fetch-test-', dir=p.HERE)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / 'downloaded'
        self.fixture = Fixture(self.root)
        self.client = FakeClient(self.fixture)
        self.artifacts = {item['id']: item for role in ('source', 'private')
            for item in self.fixture.lock[role + '_artifacts'].values()}
        for identifier, item in self.artifacts.items():
            self.client.metadata['/actions/artifacts/' + str(identifier)]['size_in_bytes'] = (
                self.root / item['zip']).stat().st_size
        self.transport = p.t.Client(TOKEN)
        self.opener = ArtifactOpener(self)
        self.transport.opener = self.opener
        self.client.request = self.transport.request

    def fetch(self):
        p.fetch_evidence(self.client, self.fixture.lock, self.output)

    def assert_failure(self, message):
        with redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(p.GateError) as caught:
                self.fetch()
        self.assertEqual(str(caught.exception), message)
        diagnostic = str(caught.exception) + output.getvalue()
        for forbidden in (TOKEN, MARKER, 'https://', 'Location'):
            self.assertNotIn(forbidden, diagnostic)

    def test_api_json_redirect_storage_zip_exact_bytes_and_no_token_forwarding(self):
        with redirect_stdout(io.StringIO()) as output:
            self.fetch()
        self.assertEqual(len(self.opener.calls), 8)
        for item in self.artifacts.values():
            self.assertEqual((self.output / item['zip']).read_bytes(),
                (self.root / item['zip']).read_bytes())
        self.assertNotIn(TOKEN, output.getvalue())
        self.assertNotIn(MARKER, output.getvalue())
        self.assertTrue(all(method == 'GET' for method, _, _ in self.client.calls))

    def test_existing_exact_direct_200_behavior_preserved(self):
        self.opener.api_status = 200
        with redirect_stdout(io.StringIO()):
            self.fetch()
        self.assertEqual(len(self.opener.calls), 4)

    def test_api_415_is_http_failure_not_hash_failure(self):
        self.opener.api_status = 415
        self.assert_failure('Raw diagnostic ZIP API request failed with HTTP 415.')
        self.assertEqual(len(self.opener.calls), 1)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_api_permission_failure_has_bounded_status(self):
        self.opener.api_status = 403
        self.assert_failure('Raw diagnostic ZIP API request failed with HTTP 403.')
        self.assertEqual(len(self.opener.calls), 1)

    def test_storage_failure_identifies_storage_without_signed_url(self):
        self.opener.storage_status = 403
        self.assert_failure('Raw diagnostic ZIP storage request failed with HTTP 403.')
        self.assertEqual(len(self.opener.calls), 2)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_storage_second_redirect_is_not_followed(self):
        self.opener.storage_status = 302
        self.assert_failure('Raw diagnostic ZIP storage request failed with HTTP 302.')
        self.assertEqual(len(self.opener.calls), 2)

    def test_short_200_response_remains_exact_size_failure(self):
        self.opener.mutate = lambda data: data[:-1]
        self.assert_failure('Raw diagnostic ZIP byte count differs from exact trusted artifact metadata.')
        self.assertEqual(len(self.opener.calls), 2)

    def test_same_size_wrong_hash_remains_hash_failure(self):
        self.opener.mutate = lambda data: bytes([data[0] ^ 1]) + data[1:]
        self.assert_failure('Raw diagnostic ZIP SHA-256 differs from the exact trusted artifact hash.')
        self.assertEqual(len(self.opener.calls), 2)

    def test_oversized_download_still_stops_in_pinned_transport(self):
        self.opener.mutate = lambda data: data + b'extra'
        self.assert_failure('Asset exceeded the exact expected byte limit.')
        self.assertEqual(len(self.opener.calls), 2)

    def test_metadata_digest_mismatch_stops_before_download(self):
        identifier = next(iter(self.artifacts))
        self.client.metadata['/actions/artifacts/' + str(identifier)]['digest'] = 'sha256:' + '0' * 64
        self.assert_failure('Exact raw diagnostic ZIP is not bound to the successful trusted workflow run.')
        self.assertEqual(self.opener.calls, [])
        self.assertFalse(self.output.exists())

    def test_unknown_storage_host_stops_before_second_request(self):
        self.opener.location = 'https://attacker.invalid/synthetic/'
        self.assert_failure('Unknown Actions artifact storage host; stop for review.')
        self.assertEqual(len(self.opener.calls), 1)

    def test_insecure_storage_scheme_stops_before_second_request(self):
        self.opener.location = 'http://productionresultssa1.blob.core.windows.net/synthetic/'
        self.assert_failure('Unknown Actions artifact storage host; stop for review.')
        self.assertEqual(len(self.opener.calls), 1)

    def test_storage_credentials_are_still_rejected_by_pinned_transport(self):
        self.opener.location = 'https://user:password@productionresultssa1.blob.core.windows.net/synthetic/'
        self.assert_failure('Only ordinary HTTPS requests are permitted.')
        self.assertEqual(len(self.opener.calls), 1)

    def test_storage_nonstandard_port_is_still_rejected_by_pinned_transport(self):
        self.opener.location = 'https://productionresultssa1.blob.core.windows.net:8443/synthetic/'
        self.assert_failure('Only ordinary HTTPS requests are permitted.')
        self.assertEqual(len(self.opener.calls), 1)

    def test_unexpected_status_value_is_not_reflected(self):
        self.client.request = lambda *args, **kwargs: ('https://' + MARKER + TOKEN, {}, b'')
        self.assert_failure('Raw diagnostic ZIP API request failed with HTTP invalid.')

    def test_missing_file_after_200_has_distinct_diagnostic(self):
        self.client.request = lambda *args, **kwargs: (200, {}, b'')
        self.assert_failure('Raw diagnostic ZIP response did not create the expected file.')


if __name__ == '__main__':
    unittest.main()
