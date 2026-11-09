"""Stage explicitly supplied manual-dispatch lock/review inputs, without network."""
import hashlib
import os
from pathlib import Path
import re
import sys
import uuid


def main():
    records = []
    for kind in ('LOCK', 'REVIEW'):
        raw = os.environ['PUBLICATION_' + kind + '_JSON'].encode('utf-8')
        expected = os.environ['PUBLICATION_' + kind + '_SHA256']
        if not re.fullmatch('[0-9a-f]{64}', expected) or hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('Explicit dispatch input/hash mismatch.')
        if not 2 <= len(raw) <= 32768:
            raise ValueError('Explicit dispatch input exceeds bounds.')
        records.append((kind.lower(), raw))
    directory = Path(os.environ['RUNNER_TEMP']) / ('facs-final-invocation-' + uuid.uuid4().hex)
    directory.mkdir(exist_ok=False)
    for kind, raw in records:
        (directory / (kind + '.json')).write_bytes(raw)
    with open(os.environ['GITHUB_ENV'], 'a', encoding='utf-8') as stream:
        for kind in ('lock', 'review'):
            stream.write('FACS_RELEASE_' + kind.upper() + '=' + str(directory / (kind + '.json')) + '\n')
        stream.write('FACS_RELEASE_EVIDENCE=' + str(directory / 'evidence') + '\n')
    print('Pinned lock and review inputs staged locally; no release action performed.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, KeyError, ValueError):
        print('INPUT STAGING STOPPED: missing or mismatched explicit inputs.', file=sys.stderr)
        raise SystemExit(1)
