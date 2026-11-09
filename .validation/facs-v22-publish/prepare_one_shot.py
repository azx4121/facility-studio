"""Render four local activation files after complete evidence/pixel acceptance.

Never contacts GitHub, creates commits/branches, or publishes. The returned
activation commit SHA must be obtained and independently verified later before
creating its exact-SHA branch. No commit can contain its own expected SHA.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import secrets

import publish_verified_windows as p
import one_shot_guard as g


def prepare(lock_path, lock_sha, review_path, review_sha, evidence_root,
            operation, release_id, hours, output):
    lock = p.pinned_json(lock_path, lock_sha)
    review = p.pinned_json(review_path, review_sha)
    p.offline_gate(lock, evidence_root, review)
    p.require(type(hours) is int and 1 <= hours <= 24, 'One-shot lifetime must be 1..24 hours.')
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    invocation = dict(schema_version=1, repository=p.REPO, publisher_commit=lock['publisher_commit'],
        operation=operation, lock_sha256=lock_sha, review_sha256=review_sha,
        prepared_at=now.isoformat(), expires_at=(now + dt.timedelta(hours=hours)).isoformat(),
        nonce=secrets.token_hex(32), resume_release_id=release_id)
    g.validate_invocation(invocation, lock, operation, release_id, now)
    raw_invocation = p.t.canonical_json(invocation)
    invocation_sha = p.digest(raw_invocation)
    workflow = (p.HERE/'one-shot-publication.yml.template').read_text(encoding='utf-8')
    replacements = {'PUBLISHER_COMMIT': lock['publisher_commit'], 'LOCK_SHA256': lock_sha,
        'REVIEW_SHA256': review_sha, 'INVOCATION_SHA256': invocation_sha, 'OPERATION': operation,
        'RESUME_ID': '' if release_id is None else str(release_id)}
    for name, value in replacements.items():
        p.require('REPLACE_' + name in workflow, 'One-shot template is missing a required exact pin.')
        workflow = workflow.replace('REPLACE_' + name, value)
    p.require('REPLACE_' not in workflow, 'An activation template placeholder remains.')
    output = Path(output).absolute()
    p.require(not output.exists(), 'Local activation output must be new.')
    output.mkdir(parents=True, exist_ok=False)
    contents = {g.WORKFLOW: workflow.encode('utf-8'), g.LOCK_FILE: p.t.regular_file(lock_path).read_bytes(),
        g.REVIEW_FILE: p.t.regular_file(review_path).read_bytes(), g.INVOCATION_FILE: raw_invocation}
    plan = dict(schema_version=1, repository=p.REPO, publisher_commit=lock['publisher_commit'],
        activation_commit=None, activation_branch=None, operation=operation, expires_at=invocation['expires_at'],
        invocation_sha256=invocation_sha, prepared_locally_only=True, files={})
    for name, raw in contents.items():
        target = output/'activation-files'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        plan['files'][name] = dict(bytes=len(raw), sha256=p.digest(raw), git_blob_sha=g.git_blob_sha(raw), mode='100644')
    (output/'ACTIVATION_PLAN.json').write_bytes(p.t.canonical_json(plan))
    print(json.dumps({'local_activation_files_prepared': True, 'file_count': 4,
        'publisher_commit': lock['publisher_commit'], 'invocation_sha256': invocation_sha,
        'activated': False, 'expires_at': invocation['expires_at']}))
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lock',type=Path,required=True)
    parser.add_argument('--lock-sha256',required=True)
    parser.add_argument('--review',type=Path,required=True)
    parser.add_argument('--review-sha256',required=True)
    parser.add_argument('--evidence-root',type=Path,required=True)
    parser.add_argument('--operation',choices=['preflight','publish','inspect','verify-public','stage-existing'],required=True)
    parser.add_argument('--release-id',type=int)
    parser.add_argument('--hours',type=int,default=2)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    prepare(args.lock,args.lock_sha256,args.review,args.review_sha256,args.evidence_root,
        args.operation,args.release_id,args.hours,args.output)


if __name__=='__main__':
    try:
        main()
    except (p.GateError, OSError, KeyError, TypeError, ValueError):
        raise SystemExit('ONE-SHOT PREPARATION STOPPED: final pinned evidence, inspection, or invocation is invalid.')
