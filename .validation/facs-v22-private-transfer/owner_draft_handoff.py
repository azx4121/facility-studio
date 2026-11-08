"""LOCAL REVIEW CANDIDATE. Owner UI verification is a separate required prerequisite.

The record is a scoped handoff, not permission supplied by arbitrary repository data.
No remote record writer, release creation, discovery adoption or metadata editor.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.parse

import private_draft_transfer as t

PURPOSE = 'FACS_OWNER_PRIVATE_WINDOWS_DRAFT_V1'
PREFIX = '.validation/facs-v22-owner-handoffs/'
MAX_BYTES = 2048
MAX_TTL = 7200  # Covers the existing bounded 100-minute build, not indefinite reuse.
MAX_WAIT = 300
INTERVAL = 10
FIELDS = {'repository', 'purpose', 'workflow_sha', 'run_id', 'run_attempt', 'release_id', 'expires_at'}
PINS = {'record', 'commit', 'blob', 'sha256'}


def integer(value):
    t.require(type(value) is int and value > 0, 'Expected a positive JSON integer.')
    return value


def sha(value):
    t.require(isinstance(value, str) and t.COMMIT.fullmatch(value), 'Expected an exact commit/blob SHA.')
    return value


def path_for(scope):
    return PREFIX + f'{scope.run_id}-{scope.run_attempt}.json'


def decode_record(raw, scope, now):
    t.require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_BYTES, 'Record size invalid.')
    value = t.parse_json(raw)
    t.require(isinstance(value, dict) and set(value) == FIELDS, 'Record schema mismatch.')
    for key in ('run_id', 'run_attempt', 'release_id', 'expires_at'):
        integer(value[key])
    t.require(value['repository'] == t.REPOSITORY and value['purpose'] == PURPOSE,
              'Record repository/purpose mismatch.')
    t.require(value['workflow_sha'] == scope.commit and value['run_id'] == scope.run_id
              and value['run_attempt'] == scope.run_attempt, 'Record run scope mismatch.')
    t.require(now < value['expires_at'] <= now + MAX_TTL, 'Record expired or expiry too distant.')
    t.require(raw == t.canonical_json(value), 'Record must have canonical bytes.')
    return value


class ReadTimeoutOpener:
    """Cap each handoff/control GET's network idle timeout without changing uploads."""
    def __init__(self, opener):
        self.opener = opener

    def open(self, request, timeout=180):
        if request.get_method() == 'GET':
            timeout = min(timeout, 10)
        return self.opener.open(request, timeout=timeout)


class OwnerClient(t.Client):
    """Defense in depth: existing transfer code cannot create or edit any release."""
    def __init__(self, token):
        super().__init__(token)
        self.opener = ReadTimeoutOpener(self.opener)

    def request(self, method, url, **kwargs):
        allowed_upload = getattr(self, 'approved_release_id', None)
        prefix = t.UPLOADS + '/releases/' + str(allowed_upload) + '/assets?name='
        t.require(method == 'GET' or (method == 'POST' and allowed_upload is not None
                  and url in {prefix + urllib.parse.quote(name) for name in t.ALLOWED_ASSETS}),
                  'Owner handoff forbids release creation or metadata writes.')
        if method == 'POST':
            t.require(callable(getattr(self, 'before_upload', None)), 'Upload requires a fresh handoff gate.')
            self.before_upload()
        return super().request(method, url, **kwargs)


def read_record(client, scope, now):
    # Resolve only the fixed approved branch, then read immutable commit content.
    ref = client.get_json('/git/ref/heads/' + t.BRANCH)
    t.require(isinstance(ref, dict) and ref.get('ref') == 'refs/heads/' + t.BRANCH
              and isinstance(ref.get('object'), dict) and ref['object'].get('type') == 'commit',
              'Unexpected branch identity.')
    commit = sha(ref['object'].get('sha'))
    path = path_for(scope)
    status, _, raw = client.request('GET', t.API + '/contents/' + path + '?ref=' + commit,
                                   authenticated=True, limit=16384)
    if status == 404:
        return None  # The only pollable failure; auth/ref/schema failures stop immediately.
    t.require(status == 200, 'Handoff content read failed.')
    data = t.parse_json(raw)
    t.require(isinstance(data, dict) and data.get('type') == 'file' and data.get('path') == path
              and data.get('encoding') == 'base64' and type(data.get('size')) is int
              and 0 < data['size'] <= MAX_BYTES and isinstance(data.get('content'), str),
              'Unexpected handoff content metadata.')
    blob = sha(data.get('sha'))
    try:
        content = base64.b64decode(data['content'].replace('\n', ''), validate=True)
    except (ValueError, UnicodeError):
        raise t.GateError('Invalid record encoding.') from None
    t.require(len(content) == data['size'], 'Record size mismatch.')
    actual_blob = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
    t.require(actual_blob == blob, 'Record Git blob identity mismatch.')
    record = decode_record(content, scope, now)
    return {'record': record, 'commit': commit, 'blob': blob,
            'sha256': hashlib.sha256(content).hexdigest()}


def empty_gate(client, scope, release_id):
    scope.gate(client, release_id)
    t.require(not t.inventory(client, release_id), 'Owner draft must remain empty before staging.')


def wait_record(client, scope, seconds=MAX_WAIT, clock=time.time, monotonic=time.monotonic, sleep=time.sleep):
    t.require(type(seconds) is int and 0 <= seconds <= MAX_WAIT, 'Wait bound invalid.')
    deadline = monotonic() + seconds
    # Finite attempt cap in addition to monotonic deadline, even with a broken test clock.
    for attempt in range(seconds // INTERVAL + 1):
        if attempt and monotonic() >= deadline:
            break
        receipt = read_record(client, scope, int(clock()))
        t.require(monotonic() <= deadline, 'Handoff wait deadline exceeded.')
        if receipt is not None:
            empty_gate(client, scope, receipt['record']['release_id'])
            return receipt
        remaining = deadline - monotonic()
        if remaining <= 0 or attempt == seconds // INTERVAL:
            break
        sleep(min(INTERVAL, remaining))
    raise t.GateError('Owner handoff not received within bounded wait.')


def recheck(client, scope, receipt, release_id, now, *, require_empty=True):
    t.require(isinstance(receipt, dict) and set(receipt) == PINS, 'Receipt schema mismatch.')
    # Equality includes commit, blob, digest and every closed record field.
    fresh = read_record(client, scope, now)
    t.require(fresh is not None and fresh == receipt, 'Pinned handoff changed or disappeared.')
    t.require(integer(release_id) == fresh['record']['release_id'], 'Explicit release ID mismatch.')
    if require_empty:
        empty_gate(client, scope, release_id)
    else:
        scope.gate(client, release_id)


def context(scope):
    t.require(os.environ.get('GITHUB_REPOSITORY') == t.REPOSITORY
              and os.environ.get('GITHUB_REF') == 'refs/heads/' + t.BRANCH
              and os.environ.get('GITHUB_SHA') == scope.commit
              and os.environ.get('GITHUB_RUN_ID') == str(scope.run_id)
              and os.environ.get('GITHUB_RUN_ATTEMPT') == str(scope.run_attempt),
              'Owner handoff workflow context mismatch.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True, type=t.positive)
    parser.add_argument('--run-attempt', required=True, type=t.positive)
    parser.add_argument('--workflow-commit', required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    wait = commands.add_parser('wait')
    wait.add_argument('--receipt', required=True, type=Path)
    wait.add_argument('--seconds', type=int, default=MAX_WAIT)
    stage = commands.add_parser('stage')
    stage.add_argument('--receipt', required=True, type=Path)
    stage.add_argument('--resume-release-id', required=True, type=t.positive)
    for name in ('exe', 'build-receipt', 'onefile-receipt', 'external-receipt', 'build-manifest'):
        stage.add_argument('--' + name, required=True, type=Path)
    stage.add_argument('--github-outputs', action='store_true')
    # This command ONLY emits a local record, AFTER owner UI and privacy verification.
    record = commands.add_parser('record')
    record.add_argument('--release-id', required=True, type=t.positive)
    record.add_argument('--expires-at', required=True, type=int)
    record.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    scope = t.Scope(args.run_id, args.run_attempt, args.workflow_commit)
    if args.command == 'record':
        value = dict(repository=t.REPOSITORY, purpose=PURPOSE, workflow_sha=scope.commit,
                     run_id=scope.run_id, run_attempt=scope.run_attempt,
                     release_id=args.release_id, expires_at=args.expires_at)
        raw = t.canonical_json(value)
        decode_record(raw, scope, int(time.time()))
        with args.output.open('xb') as stream:
            stream.write(raw)
        return
    context(scope)
    client = OwnerClient(os.environ.get('GH_TOKEN', ''))
    if args.command == 'wait':
        print(json.dumps({'workflow_sha': scope.commit, 'run_id': scope.run_id,
                          'run_attempt': scope.run_attempt, 'handoff_path': path_for(scope)}), flush=True)
        receipt = wait_record(client, scope, args.seconds)
        with args.receipt.open('xb') as stream:
            stream.write(t.canonical_json(receipt))
        # Only closed integer ID output; neither URLs nor record-supplied commands.
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
            stream.write('release_id=' + str(receipt['record']['release_id']) + '\n')
    else:
        receipt_path = t.regular_file(args.receipt)
        t.require(receipt_path.stat().st_size <= 8192, 'Oversized handoff receipt.')
        receipt = t.parse_json(receipt_path.read_bytes())
        recheck(client, scope, receipt, args.resume_release_id, int(time.time()))
        client.approved_release_id = args.resume_release_id
        client.before_upload = lambda: recheck(client, scope, receipt, args.resume_release_id,
                                                int(time.time()), require_empty=False)
        # Stage's existing source/build/native checks and per-upload privacy gates remain.
        t.stage(client, scope, args)


if __name__ == '__main__':
    try:
        main()
    except (t.GateError, OSError, ValueError, TypeError, KeyError, RecursionError):
        # No payloads, URLs, token strings, or underlying exception text.
        print('OWNER HANDOFF STOPPED: gate failure; inspect before any new action.')
        raise SystemExit(1)
