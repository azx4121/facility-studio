"""Build the reviewed candidate, retain diagnostic evidence only, no publication."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(os.environ['RUNNER_TEMP']) / 'facs-v22-exact-source'
EVIDENCE = Path(os.environ['RUNNER_TEMP']) / 'facs-v22-evidence'
OUTPUT = Path(os.environ['RUNNER_TEMP']) / 'facs-v22-extended-build'
HERE = Path(__file__).resolve().parent


def main():
    assert sys.platform == 'win32'
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1',
                       FACILITY_CAPTURE_SYNTHETIC_UI='1')
    commands = [sys.executable, 'integration/build.py', '--windows-onefile', '--output', str(OUTPUT)]
    with (EVIDENCE / 'candidate-build.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(commands, cwd=ROOT, env=environment, stdout=log,
                                stderr=subprocess.STDOUT, timeout=2400)
    receipt = dict(build_exit=result.returncode, binary_published=False,
                   public_download_ready=False, formal_feed_accepted=False)
    (EVIDENCE / 'candidate-build-result.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    if result.returncode:
        return result.returncode
    executable = OUTPUT / 'Facility-Studio-5.7.3-v22-Windows-x64-Portable.exe'
    sha256 = hashlib.sha256(executable.read_bytes()).hexdigest()
    command = [sys.executable, str(HERE / 'frozen_checks/run_frozen_cli.py'),
               '--exe', str(executable), '--sha256', sha256, '--candidate', str(ROOT),
               '--evidence', str(EVIDENCE / 'external-frozen'), '--screenshots']
    with (EVIDENCE / 'external-frozen.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=ROOT, env=environment, stdout=log,
                                stderr=subprocess.STDOUT, timeout=3600)
    receipt.update(executable_sha256=sha256, executable_bytes=executable.stat().st_size,
                   extended_exit=result.returncode, unchanged=hashlib.sha256(executable.read_bytes()).hexdigest()==sha256)
    (EVIDENCE / 'candidate-build-result.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt))
    return result.returncode if receipt['unchanged'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
