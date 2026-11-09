"""Read-only authorization checks for a reviewed exact-SHA activation branch.

The branch suffix supplies the activation commit's independently known SHA.
The activation commit changes only four publication files over reviewed code.
No ref, workflow, tag, release, or file is written by this module.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import urllib.parse

REPOSITORY = 'azx4121/facility-studio'
BRANCH_PREFIX = 'validation/facs-v22-publish-'
WORKFLOW = '.github/workflows/private-windows-handoff.yml'
ROOT = '.validation/facs-v22-publish/'
LOCK_FILE = ROOT + 'one-shot-lock.json'
REVIEW_FILE = ROOT + 'one-shot-pixel-inspection.json'
INVOCATION_FILE = ROOT + 'one-shot-invocation.json'
ALLOWED_CHANGED = {WORKFLOW, LOCK_FILE, REVIEW_FILE, INVOCATION_FILE}
SHA = re.compile('[0-9a-f]{40}')
HASH = re.compile('[0-9a-f]{64}')


def require(value, message):
    if not value:
        raise ValueError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate activation JSON key.')
        result[key] = value
    return result


def read_file(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        info = part.lstat()
        require(not stat.S_ISLNK(info.st_mode) and not (getattr(info, 'st_file_attributes', 0) & 0x400),
                'Linked activation files are forbidden.')
    require(path.is_file() and path.stat().st_size <= 1024 * 1024, 'Invalid activation file.')
    return path.read_bytes()


def git_blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()


def git_read(workspace, *arguments):
    # Git is used only for local identity/cleanliness reads, never network or writes.
    environment = {key: value for key, value in os.environ.items()
        if not key.startswith('GIT_') and key not in {'GH_TOKEN', 'GITHUB_TOKEN',
            'ACTIONS_RUNTIME_TOKEN', 'ACTIONS_ID_TOKEN_REQUEST_TOKEN', 'ACTIONS_ID_TOKEN_REQUEST_URL'}}
    try:
        result = subprocess.run(['git', '--no-optional-locks', '-c', 'core.fsmonitor=false',
        '-C', str(workspace), *arguments], env=environment, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        raise ValueError('Cannot complete local activation checkout verification.') from None
    require(result.returncode == 0, 'Cannot verify local activation checkout.')
    return result.stdout


def validate_invocation(data, lock, command, release_id, now=None):
    require(set(data) == {'schema_version', 'repository', 'publisher_commit', 'operation', 'lock_sha256',
        'review_sha256', 'prepared_at', 'expires_at', 'nonce', 'resume_release_id'}, 'Unexpected activation schema.')
    require(data['schema_version'] == 1 and data['repository'] == REPOSITORY
        and data['publisher_commit'] == lock['publisher_commit'], 'Activation code/repository mismatch.')
    require(data['operation'] in {'preflight', 'publish', 'inspect', 'verify-public', 'stage-existing'}, 'Unsupported activation operation.')
    require(command in {'fetch-evidence', 'preflight'} or command == data['operation'],
            'Activation does not authorize this command.')
    require(HASH.fullmatch(data['lock_sha256']) and HASH.fullmatch(data['review_sha256'])
        and HASH.fullmatch(data['nonce']), 'Invalid activation digest/nonce.')
    expected_id = data['resume_release_id']
    require(expected_id is None or (type(expected_id) is int and expected_id > 0), 'Invalid deliberate resume ID.')
    if command not in {'fetch-evidence', 'preflight'}:
        require(release_id == expected_id, 'Runtime release ID differs from the explicitly reviewed invocation.')
    if data['operation'] in {'verify-public', 'stage-existing'}:
        require(expected_id is not None, 'Public reconciliation needs an exact inspected release ID.')
    prepared = dt.datetime.fromisoformat(data['prepared_at'].replace('Z', '+00:00'))
    expires = dt.datetime.fromisoformat(data['expires_at'].replace('Z', '+00:00'))
    now = now or dt.datetime.now(dt.timezone.utc)
    require(prepared.tzinfo is not None and expires.tzinfo is not None
        and prepared <= now < expires and dt.timedelta(0) < expires - prepared <= dt.timedelta(hours=24),
            'Activation is not yet valid, expired, or has an excessive lifetime.')
    return data


def authorize(client, lock, invocation_path, invocation_sha256, lock_path, review_path,
              command, release_id=None):
    environment = os.environ
    activation = environment.get('GITHUB_SHA', '')
    require(SHA.fullmatch(activation), 'Missing exact activation commit.')
    branch = BRANCH_PREFIX + activation
    ref = 'refs/heads/' + branch
    require(environment.get('GITHUB_REPOSITORY') == REPOSITORY
        and environment.get('GITHUB_REF') == ref and environment.get('GITHUB_EVENT_NAME') == 'push'
        and environment.get('GITHUB_RUN_ATTEMPT') == '1'
        and environment.get('GITHUB_JOB') == 'verify-same-bytes-2025'
        and environment.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/' + WORKFLOW + '@' + ref,
            'Only the exact activation-SHA branch, approved job, and first push attempt may proceed.')
    require(environment.get('FACS_EXPECTED_PUBLISHER_COMMIT') == lock['publisher_commit'],
            'Workflow does not pin the exact reviewed publisher parent.')
    require(activation != lock['publisher_commit'], 'Activation must be a distinct child of reviewed publisher code.')
    workspace = Path(environment['GITHUB_WORKSPACE']).absolute()
    require(git_read(workspace, 'rev-parse', '--verify', 'HEAD').decode('ascii').strip() == activation
        and git_read(workspace, 'status', '--porcelain', '--untracked-files=all') == b'',
            'Activation checkout is not the exact clean pinned commit.')
    fixed_paths = {LOCK_FILE: lock_path, INVOCATION_FILE: invocation_path}
    if review_path is not None:
        fixed_paths[REVIEW_FILE] = review_path
    require(all(Path(path).absolute() == workspace / name for name, path in fixed_paths.items()),
            'Activation files must use their exact committed repository paths.')
    payloads = {name: read_file(workspace / name) for name in ALLOWED_CHANGED}
    require(isinstance(invocation_sha256, str) and HASH.fullmatch(invocation_sha256)
        and hashlib.sha256(payloads[INVOCATION_FILE]).hexdigest() == invocation_sha256,
            'Invocation bytes differ from the workflow-pinned digest.')
    invocation = validate_invocation(json.loads(payloads[INVOCATION_FILE], object_pairs_hook=unique_object),
        lock, command, release_id)
    require(hashlib.sha256(payloads[LOCK_FILE]).hexdigest() == invocation['lock_sha256']
        and json.loads(payloads[LOCK_FILE], object_pairs_hook=unique_object) == lock
        and hashlib.sha256(payloads[REVIEW_FILE]).hexdigest() == invocation['review_sha256'],
            'Activation lock/pixel-inspection bytes differ from reviewed hashes.')

    # The exact activation SHA is known before the parent creates its matching
    # branch. The commit must be one direct child of reviewed publisher code;
    # no product, main, transport, guard, or publisher code can change here.
    commit = client.get_json('/commits/' + activation + '?per_page=100')
    require(commit.get('sha') == activation and [p.get('sha') for p in commit.get('parents', [])]
        == [lock['publisher_commit']], 'Activation parent differs from the exact reviewed publisher commit.')
    files = commit.get('files', [])
    require(len(files) == 4 and {f.get('filename') for f in files} == ALLOWED_CHANGED,
            'Activation changed paths outside the four necessary publication files.')
    for row in files:
        name = row['filename']
        expected_status = 'modified' if name == WORKFLOW else 'added'
        require(row.get('status') == expected_status and row.get('sha') == git_blob_sha(payloads[name])
            and not row.get('previous_filename'), 'Activation file status/blob differs from exact committed bytes.')
    live_ref = client.get_json('/git/ref/heads/' + branch)
    require(live_ref.get('ref') == ref and live_ref.get('object', {}).get('type') == 'commit'
        and live_ref['object'].get('sha') == activation, 'Activation branch moved or was retired; stop immediately.')
    run_id = environment.get('GITHUB_RUN_ID', '')
    require(run_id.isdigit() and int(run_id) > 0, 'Missing activation run ID.')
    run = client.get_json('/actions/runs/' + run_id)
    require(run.get('id') == int(run_id) and run.get('head_sha') == activation
        and run.get('head_branch') == branch and run.get('path') == WORKFLOW
        and run.get('workflow_id') == lock['private_run']['workflow_id']
        and run.get('event') == 'push' and run.get('run_attempt') == 1
        and run.get('status') == 'in_progress' and run.get('conclusion') is None
        and run.get('repository', {}).get('full_name') == REPOSITORY
        and run.get('head_repository', {}).get('full_name') == REPOSITORY,
            'Live activation run is not the first authorized push of this exact commit.')
    history_path = ('/actions/workflows/' + str(lock['private_run']['workflow_id'])
        + '/runs?head_sha=' + activation + '&event=push&branch='
        + urllib.parse.quote(branch, safe='') + '&per_page=100&page=1')
    history = client.get_json(history_path)
    matches = history.get('workflow_runs', [])
    require(type(history.get('total_count')) is int and history['total_count'] == 1
        and len(matches) == 1 and matches[0].get('id') == int(run_id)
        and matches[0].get('head_sha') == activation and matches[0].get('head_branch') == branch
        and matches[0].get('workflow_id') == lock['private_run']['workflow_id']
        and matches[0].get('event') == 'push' and matches[0].get('run_attempt') == 1,
            'Activation has prior or ambiguous push-run history; never replay this activation commit.')
    return invocation
