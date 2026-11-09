"""Private draft asset handoff only. Never publishes, deletes, or replaces assets.

Network entry points are confined to this repository and GitHub's HTTPS API.
The CLI performs external actions only when explicitly invoked with GH_TOKEN.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY = 'azx4121/facility-studio'
BRANCH = 'validation/facs-v22-windows-20261108'
EXE_NAME = 'Facility-Studio-5.7.3-v22-Windows-x64-Portable.exe'
MANIFEST_NAME = 'Windows_Private_Candidate_Manifest.json'
API = 'https://api.github.com/repos/' + REPOSITORY
WEB = 'https://github.com/' + REPOSITORY
UPLOADS = 'https://uploads.github.com/repos/' + REPOSITORY
SOURCE_FIELDS = ('provenance_schema', 'commit', 'version', 'source_platform',
                 'build_channel', 'source_clean', 'build_inputs_sha256',
                 'product_source_sha256')
ALLOWED_ASSETS = {EXE_NAME, MANIFEST_NAME}
DIGEST = re.compile(r'[0-9a-f]{64}')
COMMIT = re.compile(r'[0-9a-f]{40}')


class GateError(RuntimeError):
    pass


class TransportUncertain(GateError):
    pass


def creation_diagnostic(status, headers, data, category):
    """Bounded constants only; never echo response text, arbitrary headers or URLs."""
    categories = {'transport_uncertain', 'request_failed', 'response_invalid',
                  'ownership_mismatch', 'http_rejected'}
    category = category if category in categories else 'request_failed'
    record = {'operation': 'create_draft', 'http_status': None,
              'request_id': None, 'failure_category': category}
    if type(status) is int and 100 <= status <= 599:
        record['http_status'] = status
    if isinstance(headers, dict):
        for key, value in headers.items():
            if isinstance(key, str) and key.lower() == 'x-github-request-id':
                # GitHub request IDs are colon-separated hexadecimal groups.
                if isinstance(value, str) and re.fullmatch(
                        r'[0-9A-Fa-f]{1,16}(?::[0-9A-Fa-f]{1,16}){3,4}', value):
                    record['request_id'] = value
                break
    if category == 'http_rejected' and isinstance(data, bytes) and len(data) <= 65536:
        try:
            body = parse_json(data)
        except (GateError, RecursionError):
            body = None
        if isinstance(body, dict):
            # Exact recognition only, never reflect server-controlled strings.
            messages = {'Resource not accessible by integration': 'resource_not_accessible',
                        'Not Found': 'not_found', 'Validation Failed': 'validation_failed',
                        'API rate limit exceeded': 'rate_limited'}
            message = body.get('message')
            if isinstance(message, str) and message in messages:
                record['failure_category'] = messages[message]
    print(json.dumps(record, sort_keys=True), flush=True)


def require(condition, message):
    if not condition:
        raise GateError(message)


def positive(value):
    require(str(value).isdigit() and int(value) > 0, 'Expected a positive integer identifier.')
    return int(value)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key.')
        result[key] = value
    return result


def parse_json(data):
    try:
        return json.loads(data, object_pairs_hook=unique_object)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise GateError('Invalid JSON metadata.') from error


def canonical_json(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def regular_file(path):
    path = Path(path).absolute()
    for component in (path, *path.parents):
        info = component.lstat()
        require(not stat.S_ISLNK(info.st_mode) and not (
            getattr(info, 'st_file_attributes', 0) & 0x400), 'Links/reparse points are forbidden.')
    require(path.is_file(), 'A regular file is required.')
    return path


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, token):
        require(bool(token) and '\n' not in token and '\r' not in token, 'GH_TOKEN is required.')
        self.token = token
        # No cookie jar, netrc, inherited proxy, or implicit credential redirects.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, method, url, *, authenticated=False, accept='application/vnd.github+json',
                payload=None, content_type=None, destination=None, limit=8 * 1024 * 1024):
        parsed = urllib.parse.urlsplit(url)
        require(parsed.scheme == 'https' and parsed.port in (None, 443)
                and not parsed.username and not parsed.password and not parsed.fragment,
                'Only ordinary HTTPS requests are permitted.')
        headers = {'Accept': accept, 'User-Agent': 'FACS-private-Windows-validation',
                   'X-GitHub-Api-Version': '2022-11-28'}
        if authenticated:
            require(url.startswith(API + '/') or url.startswith(UPLOADS + '/'),
                    'Refusing to transmit credentials outside the repository API.')
            headers['Authorization'] = 'Bearer ' + self.token
        if content_type:
            headers['Content-Type'] = content_type
        if hasattr(payload, 'fileno'):
            headers['Content-Length'] = str(os.fstat(payload.fileno()).st_size)
        req = urllib.request.Request(url, data=payload, method=method, headers=headers)
        try:
            try:
                response = self.opener.open(req, timeout=180)
            except urllib.error.HTTPError as response_error:
                response = response_error
            with response:
                status = response.status
                info = dict(response.headers)
                if destination is not None and status == 200:
                    with Path(destination).open('xb') as output:
                        count = 0
                        while chunk := response.read(1024 * 1024):
                            count += len(chunk)
                            require(count <= limit, 'Asset exceeded the exact expected byte limit.')
                            output.write(chunk)
                    data = b''
                else:
                    # Never put response bodies or URLs (possibly signed) in logs.
                    data = response.read(min(limit, 8 * 1024 * 1024) + 1)
                    require(len(data) <= min(limit, 8 * 1024 * 1024), 'Oversized API response.')
                return status, info, data
        except (urllib.error.URLError, TimeoutError, OSError):
            # A POST could already have executed. Caller inspects before any retry.
            raise TransportUncertain('Transport failure; outcome may be uncertain. Inspect the exact draft/asset before retry.') from None

    def get_json(self, path):
        status, _, data = self.request('GET', API + path, authenticated=True)
        require(status == 200, 'Authenticated metadata read failed with HTTP ' + str(status) + '.')
        return parse_json(data)

    def pages(self, path):
        results = []
        for page in range(1, 101):
            value = self.get_json(path + '?per_page=100&page=' + str(page))
            require(isinstance(value, list), 'Unexpected paginated metadata.')
            results.extend(value)
            if len(value) < 100:
                return results
        raise GateError('Pagination bound reached; cannot establish a complete inventory.')

    def absent(self, url):
        status, _, _ = self.request('GET', url, authenticated=False, limit=8 * 1024 * 1024)
        require(status == 404, 'Non-public gate requires anonymous HTTP 404; got HTTP ' + str(status) + '.')

    def download_asset(self, asset_id, destination, size, expected_hash):
        require(DIGEST.fullmatch(expected_hash) is not None, 'Expected digest is invalid.')
        require(type(size) is int and 0 < size <= 2 * 1024**3, 'Expected asset size is invalid.')
        url = API + '/releases/assets/' + str(positive(asset_id))
        status, headers, _ = self.request('GET', url, authenticated=True,
            accept='application/octet-stream', destination=destination, limit=size)
        if status in (301, 302, 303, 307, 308):
            # Never carry Authorization to the signed object-storage URL.
            location = headers.get('Location', headers.get('location', ''))
            parsed = urllib.parse.urlsplit(location)
            require(parsed.scheme == 'https' and parsed.hostname in {
                'release-assets.githubusercontent.com', 'objects.githubusercontent.com'},
                'Unexpected asset storage host; refusing redirected download.')
            status, _, _ = self.request('GET', location, authenticated=False,
                accept='application/octet-stream', destination=destination, limit=size)
        require(status == 200, 'Authenticated asset download failed with HTTP ' + str(status) + '.')
        require(Path(destination).stat().st_size == size and sha256(destination) == expected_hash,
                'Downloaded asset bytes or SHA-256 do not match the trusted producer output.')


def verified_public_url(value, kind, name=None):
    require(isinstance(value, str), 'Missing actual GitHub draft/asset URL.')
    parsed = urllib.parse.urlsplit(value)
    require(parsed.scheme == 'https' and parsed.netloc == 'github.com'
        and not parsed.query and not parsed.fragment, 'Unexpected public probe URL origin.')
    parts = parsed.path.strip('/').split('/')
    require(parts[:3] == REPOSITORY.split('/') + ['releases']
        and all(part and part not in {'.', '..'} and '/' not in urllib.parse.unquote(part)
                and '\\' not in urllib.parse.unquote(part) for part in parts),
        'Public probe URL is not confined to the authorized repository releases.')
    if kind == 'release':
        require(len(parts) == 5 and parts[3] == 'tag', 'Unexpected actual draft HTML URL.')
    else:
        require(len(parts) == 6 and parts[3] == 'download'
            and urllib.parse.unquote(parts[-1]) == name, 'Unexpected actual asset download URL.')
    return value


def exact_ui_text(actual, expected_lf):
    """Only the exact LF marker or its exact GitHub UI CRLF serialization."""
    return (isinstance(actual, str) and isinstance(expected_lf, str)
            and '\r' not in expected_lf
            and actual in (expected_lf, expected_lf.replace('\n', '\r\n')))


class Scope:
    def __init__(self, run_id, run_attempt, workflow_commit):
        self.run_id, self.run_attempt = positive(run_id), positive(run_attempt)
        require(COMMIT.fullmatch(workflow_commit) is not None, 'Workflow commit must be a full lowercase SHA.')
        self.commit = workflow_commit
        self.tag = f'facs-v22-windows-private-candidate-{self.run_id}-{self.run_attempt}'
        self.name = f'PRIVATE Windows candidate, run {self.run_id}, attempt {self.run_attempt}'
        self.marker = f'FACS_PRIVATE_WINDOWS_VALIDATION_V1\nRepository: {REPOSITORY}\nRun: {self.run_id}\nAttempt: {self.run_attempt}\nWorkflow commit: {self.commit}\nUNVALIDATED CANDIDATE. Not published. Not approved for distribution.\n'

    def release(self, data, release_id):
        require(isinstance(data, dict), 'Unexpected release metadata.')
        require(type(data.get('id')) is int and data['id'] == positive(release_id), 'Release ID mismatch.')
        require(data.get('draft') is True and data.get('published_at') is None, 'Release is not an unpublished draft.')
        require(data.get('prerelease') is True and data.get('tag_name') == self.tag,
                'Draft tag/type mismatch; refusing unrelated releases.')
        require(data.get('target_commitish') == self.commit and data.get('name') == self.name
                and exact_ui_text(data.get('body'), self.marker), 'Draft ownership marker/commit mismatch.')
        return data

    def gate(self, client, release_id):
        release = self.release(client.get_json('/releases/' + str(positive(release_id))), release_id)
        client.absent(API + '/releases/' + str(release_id))
        client.absent(API + '/releases/tags/' + self.tag)
        client.absent(WEB + '/releases/tag/' + self.tag)
        client.absent(verified_public_url(release.get('html_url'), 'release'))
        return release

    def asset_gate(self, client, asset):
        client.absent(API + '/releases/assets/' + str(positive(asset['id'])))
        client.absent(WEB + '/releases/download/' + self.tag + '/' + asset['name'])
        client.absent(verified_public_url(asset.get('browser_download_url'), 'asset', asset['name']))


def inventory(client, release_id):
    assets = client.pages('/releases/' + str(positive(release_id)) + '/assets')
    require(all(isinstance(row, dict) and row.get('name') in ALLOWED_ASSETS for row in assets),
            'Draft contains an unauthorized asset; stop without deleting/replacing anything.')
    require(len({row['name'] for row in assets}) == len(assets), 'Duplicate asset names are forbidden.')
    return {row['name']: row for row in assets}


def verify_asset(data, name, size, digest, asset_id=None):
    require(isinstance(data, dict) and data.get('name') == name and data.get('state') == 'uploaded',
            'Asset name/state mismatch; partial/starter uploads require inspection.')
    positive(data.get('id'))
    require(asset_id is None or data['id'] == positive(asset_id), 'Asset ID mismatch.')
    require(type(data.get('size')) is int and data['size'] == size, 'Asset metadata byte length mismatch.')
    # GitHub may omit digest. Exact authenticated byte download is always mandatory.
    require(data.get('digest') in (None, 'sha256:' + digest), 'Server asset digest mismatch.')
    return data


def inspection_integer(value, minimum=1):
    # Bound both type and encoded length; bool and arbitrary objects are not IDs.
    return value if type(value) is int and minimum <= value <= 2**63 - 1 else None


def inspection_asset(row):
    """Closed logging projection only; never reflect untrusted strings or objects."""
    name = row.get('name')
    state = row.get('state')
    return {'id': inspection_integer(row.get('id')),
            'name': name if isinstance(name, str) and name in ALLOWED_ASSETS else None,
            'state': state if isinstance(state, str) and state in {'uploaded', 'starter'} else None,
            'bytes': inspection_integer(row.get('size'), 0)}


def inspect_scope(client, scope):
    # Sanitized read-only reconciliation after an uncertain POST, never blind retry.
    matches = [row for row in client.pages('/releases') if row.get('tag_name') == scope.tag]
    print(json.dumps({'inspection_only': True, 'matching_releases': [
        {'id': inspection_integer(row.get('id')),
         'draft': row.get('draft') if type(row.get('draft')) is bool else None, 'tag': scope.tag}
        for row in matches]}), flush=True)
    return matches


def create_or_resume(client, scope, release_id):
    if release_id is not None:
        scope.gate(client, release_id)
        inventory(client, release_id)
        return positive(release_id)
    matches = inspect_scope(client, scope)
    require(not matches, 'A matching release already exists. Inspect and supply its exact --resume-release-id; never create blindly.')
    # Check predictable public routes even before creating an empty draft.
    client.absent(API + '/releases/tags/' + scope.tag)
    client.absent(WEB + '/releases/tag/' + scope.tag)
    payload = canonical_json({'tag_name': scope.tag, 'target_commitish': scope.commit,
        'name': scope.name, 'body': scope.marker, 'draft': True, 'prerelease': True,
        'generate_release_notes': False, 'make_latest': 'false'})
    status, headers, data = None, None, None
    failure_category = 'request_failed'
    try:
        status, headers, data = client.request('POST', API + '/releases', authenticated=True,
            payload=payload, content_type='application/json')
        failure_category = 'http_rejected'
        require(status == 201, 'Draft creation did not return HTTP 201; outcome requires inspection.')
        failure_category = 'response_invalid'
        created = parse_json(data)
        release_id = positive(created.get('id'))
        failure_category = 'ownership_mismatch'
        scope.release(created, release_id)
    except (GateError, TypeError, AttributeError) as error:
        if isinstance(error, TransportUncertain):
            failure_category = 'transport_uncertain'
        creation_diagnostic(status, headers, data, failure_category)
        inspect_scope(client, scope)
        raise GateError('Draft creation uncertain or rejected. Inspected matching releases; do not retry automatically.') from None
    print(json.dumps({'empty_draft_created': True, 'release_id': release_id, 'tag': scope.tag}), flush=True)
    scope.gate(client, release_id)
    require(not inventory(client, release_id), 'New draft is not empty; no upload is permitted.')
    return release_id


def ensure_asset(client, scope, release_id, path, content_type):
    path = regular_file(path)
    name, size, digest = path.name, path.stat().st_size, sha256(path)
    require(name in ALLOWED_ASSETS, 'Only the exact Windows EXE and minimal manifest may be uploaded.')
    scope.gate(client, release_id)  # Fresh check immediately before possible upload.
    assets = inventory(client, release_id)
    if name not in assets:
        try:
            with path.open('rb') as payload:
                status, _, data = client.request('POST', UPLOADS + '/releases/' + str(release_id)
                    + '/assets?name=' + urllib.parse.quote(name, safe=''), authenticated=True,
                    payload=payload, content_type=content_type)
            require(status == 201, 'Asset upload did not return HTTP 201; inspect before retry.')
            uploaded = parse_json(data)
            verify_asset(uploaded, name, size, digest)
        except (GateError, TypeError, AttributeError):
            # Stop even if inspection finds it; explicit resume reconciles bytes.
            rows = inventory(client, release_id)
            print(json.dumps({'inspection_only': True, 'release_id': release_id,
                'assets': [inspection_asset(row) for row in rows.values()]}), flush=True)
            raise GateError('Upload outcome uncertain or rejected. Inspected exact draft assets; no automatic retry.') from None
        assets = inventory(client, release_id)
        require(name in assets, 'Uploaded asset missing from exact draft inventory.')
        require(assets[name]['id'] == uploaded['id'], 'Uploaded ID differs from release inventory.')
    row = verify_asset(assets[name], name, size, digest)
    fresh = client.get_json('/releases/assets/' + str(row['id']))
    verify_asset(fresh, name, size, digest, row['id'])
    scope.gate(client, release_id)
    scope.asset_gate(client, row)
    with tempfile.TemporaryDirectory(prefix='facs-private-recheck-') as folder:
        client.download_asset(row['id'], Path(folder) / name, size, digest)
    scope.gate(client, release_id)
    scope.asset_gate(client, row)
    require(sha256(path) == digest, 'Local producer asset changed during upload/recheck.')
    return row, digest


def validate_source_manifest(source_manifest):
    require(isinstance(source_manifest, dict) and set(source_manifest) == set(SOURCE_FIELDS),
            'Unexpected source manifest fields.')
    require(type(source_manifest['provenance_schema']) is int and source_manifest['provenance_schema'] == 1
        and source_manifest['source_platform'] == 'windows' and source_manifest['source_clean'] is True
        and source_manifest['build_channel'] == 'stable' and source_manifest['version'] == '5.7.3'
        and isinstance(source_manifest['commit'], str) and COMMIT.fullmatch(source_manifest['commit']),
        'Only clean, stable Windows v22 provenance is allowed.')
    for key in ('build_inputs_sha256', 'product_source_sha256'):
        mapping = source_manifest[key]
        require(isinstance(mapping, dict) and bool(mapping) and all(
            isinstance(name, str) and name and isinstance(value, str) and DIGEST.fullmatch(value)
            for name, value in mapping.items()), 'Invalid source file hash inventory.')


def build_manifest(scope, release_id, exe, source_manifest):
    validate_source_manifest(source_manifest)
    return {'schema_version': 1, 'repository': REPOSITORY, 'tag': scope.tag,
        'release_id': positive(release_id), 'workflow_commit': scope.commit,
        'run_id': scope.run_id, 'run_attempt': scope.run_attempt,
        'binary': {'name': EXE_NAME, 'bytes': exe.stat().st_size, 'sha256': sha256(exe)},
        'source_manifest': source_manifest,
        'published': False, 'unvalidated': True, 'formal_feed_accepted': False}


def validate_manifest(data, scope, release_id, size, digest):
    expected_keys = {'schema_version', 'repository', 'tag', 'release_id', 'workflow_commit',
                     'run_id', 'run_attempt', 'binary', 'source_manifest', 'published', 'unvalidated', 'formal_feed_accepted'}
    require(isinstance(data, dict) and set(data) == expected_keys, 'Unexpected transfer manifest structure.')
    require(data['schema_version'] == 1 and data['repository'] == REPOSITORY
        and data['tag'] == scope.tag and data['release_id'] == positive(release_id)
        and data['workflow_commit'] == scope.commit and data['run_id'] == scope.run_id
        and data['run_attempt'] == scope.run_attempt and data['published'] is False and data['unvalidated'] is True
        and data['formal_feed_accepted'] is False, 'Transfer manifest context mismatch.')
    require(data['binary'] == {'name': EXE_NAME, 'bytes': size, 'sha256': digest}, 'Transfer binary identity mismatch.')
    require(isinstance(data['source_manifest'], dict)
        and set(data['source_manifest']) == set(SOURCE_FIELDS), 'Transfer source manifest structure mismatch.')
    validate_source_manifest(data['source_manifest'])
    return data


def stage(client, scope, args):
    exe = regular_file(args.exe)
    require(exe.name == EXE_NAME, 'Wrong executable filename.')
    receipt = parse_json(regular_file(args.build_receipt).read_bytes())
    require(receipt.get('build_exit') == 0 and receipt.get('extended_exit') == 0
        and receipt.get('unchanged') is True and receipt.get('executable_sha256') == sha256(exe)
        and receipt.get('executable_bytes') == exe.stat().st_size,
        'Build/external acceptance receipt does not authorize these unchanged bytes.')
    onefile = parse_json(regular_file(args.onefile_receipt).read_bytes())
    require(onefile.get('passed') is True and onefile.get('native_windows') is True
        and onefile.get('executable_sha256') == sha256(exe), 'Frozen acceptance receipt is missing or mismatched.')
    records = onefile.get('records', [])
    require(len(records) == 4 and {(row.get('path_case'), row.get('suite')) for row in records}
        == {('plain', 'fusion'), ('plain', 'facilities'), ('unicode-space', 'fusion'), ('unicode-space', 'facilities')}
        and all(type(row.get('exit_code')) is int and row['exit_code'] == 0 for row in records),
        'All four frozen EXE runs must pass before any private upload.')
    external = parse_json(regular_file(args.external_receipt).read_bytes())
    require(external.get('passed') is True and external.get('native_windows') is True
        and external.get('original_exe_unchanged') is True and external.get('screenshots_requested') is True
        and external.get('executable_sha256') == sha256(exe)
        and len(external.get('commands', [])) == 118 and len(external.get('screenshots', [])) == 8,
        'Exact 118 external commands and eight startup captures must pass before private upload.')
    manifest = parse_json(regular_file(args.build_manifest).read_bytes())
    source_manifest = {key: manifest[key] for key in SOURCE_FIELDS}
    validate_source_manifest(source_manifest)
    release_id = create_or_resume(client, scope, args.resume_release_id)
    with tempfile.TemporaryDirectory(prefix='facs-private-manifest-') as folder:
        local_manifest = Path(folder) / MANIFEST_NAME
        local_manifest.write_bytes(canonical_json(build_manifest(scope, release_id, exe, source_manifest)))
        asset, digest = ensure_asset(client, scope, release_id, exe, 'application/vnd.microsoft.portable-executable')
        manifest_asset, manifest_digest = ensure_asset(client, scope, release_id, local_manifest, 'application/json')
        require(set(inventory(client, release_id)) == ALLOWED_ASSETS, 'Final asset inventory is incomplete.')
        scope.gate(client, release_id)
        for row in (asset, manifest_asset):
            scope.asset_gate(client, row)
        result = {'release_id': release_id, 'asset_id': asset['id'], 'manifest_asset_id': manifest_asset['id'],
            'sha256': digest, 'bytes': exe.stat().st_size, 'manifest_sha256': manifest_digest,
            'manifest_bytes': local_manifest.stat().st_size, 'tag': scope.tag,
            'run_id': scope.run_id, 'run_attempt': scope.run_attempt, 'workflow_commit': scope.commit}
    if args.github_outputs:
        output = os.environ.get('GITHUB_OUTPUT')
        require(bool(output), 'GITHUB_OUTPUT is missing.')
        with open(output, 'a', encoding='utf-8') as stream:
            for key, value in result.items():
                stream.write(f'{key}={value}\n')
    print(json.dumps(dict(result, draft=True, published=False)), flush=True)
    return result


def download(client, scope, args):
    require(DIGEST.fullmatch(args.sha256) and DIGEST.fullmatch(args.manifest_sha256), 'Invalid trusted hashes.')
    output = Path(args.output).absolute()
    require(not output.exists(), 'Consumer output must be a new directory.')
    output.mkdir(parents=True, exist_ok=False)
    scope.gate(client, args.release_id)
    assets = inventory(client, args.release_id)
    require(set(assets) == ALLOWED_ASSETS, 'Expected exactly two authorized draft assets.')
    for name, asset_id, size, digest in (
        (MANIFEST_NAME, args.manifest_asset_id, args.manifest_bytes, args.manifest_sha256),
        (EXE_NAME, args.asset_id, args.bytes, args.sha256)):
        row = verify_asset(assets[name], name, size, digest, asset_id)
        verify_asset(client.get_json('/releases/assets/' + str(asset_id)), name, size, digest, asset_id)
        scope.asset_gate(client, row)
        client.download_asset(asset_id, output / name, size, digest)
        scope.gate(client, args.release_id)
        scope.asset_gate(client, row)
    data = parse_json((output / MANIFEST_NAME).read_bytes())
    validate_manifest(data, scope, args.release_id, args.bytes, args.sha256)
    print(json.dumps({'downloaded': True, 'release_id': args.release_id,
                      'asset_id': args.asset_id, 'sha256': args.sha256, 'published': False}), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True, type=positive)
    parser.add_argument('--run-attempt', required=True, type=positive)
    parser.add_argument('--workflow-commit', required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    upload = sub.add_parser('stage')
    for name in ('exe', 'build-receipt', 'onefile-receipt', 'external-receipt', 'build-manifest'):
        upload.add_argument('--' + name, required=True, type=Path)
    upload.add_argument('--resume-release-id', type=positive)
    upload.add_argument('--github-outputs', action='store_true')
    fetch = sub.add_parser('download')
    for name in ('release-id', 'asset-id', 'manifest-asset-id', 'bytes', 'manifest-bytes'):
        fetch.add_argument('--' + name, required=True, type=positive)
    fetch.add_argument('--sha256', required=True)
    fetch.add_argument('--manifest-sha256', required=True)
    fetch.add_argument('--output', required=True, type=Path)
    check = sub.add_parser('inspect')
    check.add_argument('--release-id', type=positive)
    args = parser.parse_args(argv)
    require(os.environ.get('GITHUB_REPOSITORY') == REPOSITORY, 'Run only in the authorized repository.')
    require(os.environ.get('GITHUB_REF') == 'refs/heads/' + BRANCH, 'Run only on the authorized validation branch.')
    # Numeric IDs and commit must originate from trusted same-run workflow outputs.
    require(os.environ.get('GITHUB_SHA') == args.workflow_commit, 'Workflow commit does not match current checkout context.')
    scope = Scope(args.run_id, args.run_attempt, args.workflow_commit)
    client = Client(os.environ.get('GH_TOKEN', ''))
    if args.command == 'stage':
        require(str(scope.run_id) == os.environ.get('GITHUB_RUN_ID')
            and str(scope.run_attempt) == os.environ.get('GITHUB_RUN_ATTEMPT'), 'Producer run identity mismatch.')
        stage(client, scope, args)
    elif args.command == 'download':
        download(client, scope, args)
    else:
        inspect_scope(client, scope)
        if args.release_id:
            scope.gate(client, args.release_id)
            assets = inventory(client, args.release_id)
            for row in assets.values():
                scope.asset_gate(client, row)
            print(json.dumps({'release_id': args.release_id, 'draft': True, 'anonymous_404': True,
                'assets': [inspection_asset(row) for row in assets.values()]}))


if __name__ == '__main__':
    try:
        main()
    except (GateError, OSError, KeyError, TypeError, ValueError):
        # No traceback: underlying HTTP exceptions could contain signed URLs.
        # GateError messages are deliberately bounded, constant strings/integers.
        error = sys.exc_info()[1]
        print('PRIVATE TRANSFER STOPPED: ' + (str(error) if isinstance(error, GateError)
            else 'Local data or filesystem validation failed.'), file=sys.stderr)
        raise SystemExit(1)
