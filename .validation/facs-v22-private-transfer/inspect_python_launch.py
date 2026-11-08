"""Read-only Windows launch preflight; never runs, moves or removes Python.

A successful PATH scan does not prove Python is absent from the machine or
inaccessible by absolute path. Windows implicit process-search directories are
reported separately. Controller cwd lookup is diagnostic, not child cwd proof.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

NAMES = ('python.exe', 'python3.exe', 'py.exe')


def inspect_launch_environment(env, *, pathsep=None):
    separator = os.pathsep if pathsep is None else pathsep
    root = Path(env.get('SystemRoot', 'C:/Windows'))
    entries = env['PATH'].split(separator)
    scans = []
    for origin, directories in (
        ('launch_path', entries),
        ('windows_implicit_search', [str(root / 'System32'), str(root / 'System'), str(root)]),
    ):
        for entry in directories:
            directory = Path(entry)
            for name in NAMES:
                candidate = directory / name
                # exists() is deliberately conservative: a directory/reparse
                # candidate is not evidence of absence either.
                if candidate.exists() or candidate.is_symlink():
                    scans.append(dict(origin=origin, name=name, path=str(candidate.absolute())))
    unsafe_entries = [entry for entry in entries if not entry or not Path(entry).is_absolute()]
    return dict(schema_version=1, launch_path=env['PATH'], path_entries=entries,
                controller_cwd=str(Path.cwd()), controller_python=sys.executable,
                controller_python_version=sys.version,
                controller_pathext=os.environ.get('PATHEXT'),
                child_pathext=env.get('PATHEXT'),
                controller_which={name: shutil.which(name, path=env['PATH']) for name in NAMES},
                reachable_candidates=scans, unsafe_path_entries=unsafe_entries,
                path_and_implicit_directory_scan_passed=not scans and not unsafe_entries,
                absolute_path_execution_blocked=False, machine_python_absence_claimed=False,
                process_execution_policy_enforced=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != 'win32':
        parser.error('Native Windows is required for this host preflight.')
    root = Path(os.environ.get('SystemRoot', 'C:/Windows'))
    env = dict(os.environ, PATH=str(root / 'System32') + os.pathsep + str(root))
    receipt = inspect_launch_environment(env)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, indent=2)
    print(json.dumps(receipt))
    # Reachable controller/system Python is reported, not a standalone-EXE failure.
    return 0 if not receipt['unsafe_path_entries'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
