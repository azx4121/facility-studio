"""The Windows candidate and the macOS tree must ship the same product code.

Only these files may differ: version.py (platform revision label) and resources/beginner_tutorial.zip
(platform-specific screenshots and wording). Platform behaviour lives behind facility_studio/platform_support.py.

    python tools/verify_platform_sync.py [--windows Source/windows] [--macos macos]
"""
import argparse
import filecmp
import sys
from pathlib import Path

ALLOWED = {"version.py", "resources/beginner_tutorial.zip"}


def files(root):
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--windows", default="Source/windows")
    parser.add_argument("--macos", default="macos")
    args = parser.parse_args()
    w, m = Path(args.windows) / "facility_studio", Path(args.macos) / "facility_studio"
    fw, fm = files(w), files(m)
    problems = [f"only in windows: {f}" for f in sorted(fw - fm)] + [f"only in macos: {f}" for f in sorted(fm - fw)]
    problems += [f"differs: {f}" for f in sorted(fw & fm) if f not in ALLOWED and not filecmp.cmp(w / f, m / f, shallow=False)]
    for line in problems:
        print(line)
    print(f"platform sync: {len(fw & fm)} shared files, {len(problems)} problem(s); allowed to differ: {sorted(ALLOWED)}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
