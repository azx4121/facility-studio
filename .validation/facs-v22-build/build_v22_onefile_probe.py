"""Build/test a non-published candidate and retain only diagnostic evidence."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(os.environ['RUNNER_TEMP']) / 'facs-v22-exact-source'
EVIDENCE = Path(os.environ['RUNNER_TEMP']) / 'facs-v22-evidence'
OUTPUT = Path(os.environ['RUNNER_TEMP']) / 'facs-v22-onefile-build'


def main():
    assert sys.platform == 'win32'
    environment = dict(os.environ, GIT_AUTHOR_NAME='FACS Reproducible Validation',
        GIT_AUTHOR_EMAIL='validation@users.noreply.github.com',
        GIT_COMMITTER_NAME='FACS Reproducible Validation',
        GIT_COMMITTER_EMAIL='validation@users.noreply.github.com',
        GIT_AUTHOR_DATE='2026-11-08T00:00:00Z', GIT_COMMITTER_DATE='2026-11-08T00:00:00Z',
        PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT, env=environment, stderr=subprocess.STDOUT).decode().strip()
    git('init', '-q')
    git('add', '-f', '.')
    original = json.loads((Path(__file__).parent.parent / 'facs-v22-windows/SOURCE_MANIFEST.json').read_text())
    for row in original['files']:
        if row['mode'] == '100755':
            git('update-index', '--chmod=+x', '--', row['path'])
    git('commit', '-q', '-m', 'Record exact v22 plus reviewed single EXE packaging overlay')
    origin = dict(kind='local-reconstructed-source-snapshot-not-a-published-release',
                  source_snapshot_commit=git('rev-parse', 'HEAD'), source_tree=git('rev-parse', 'HEAD^{tree}'),
                  workflow_commit=os.environ['GITHUB_SHA'], original_source_inventory_sha256=original['inventory_sha256'],
                  overlay=json.loads((EVIDENCE / 'packaging-overlay.json').read_text()),
                  binary_publication_authorized_by_this_workflow=False, formal_feed_accepted=False)
    (EVIDENCE / 'candidate-build-origin.json').write_text(json.dumps(origin, indent=2), encoding='utf-8')
    command = [sys.executable, 'integration/build.py', '--windows-onefile', '--output', str(OUTPUT)]
    with (EVIDENCE / 'candidate-build.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=2400)
    receipt = dict(command=command, exit_code=result.returncode,
                   binary_published=False, public_download_ready=False, formal_feed_accepted=False)
    (EVIDENCE / 'candidate-build-result.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt))
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
