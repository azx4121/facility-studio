"""Verify the delivered universal macOS ZIP on a second native architecture."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys


def verify_dmg(path, output):
    """Verify the read-only delivery image and detach it even on failure."""
    mount = output / "dmg-mounted"
    mount.mkdir()
    attached = False
    try:
        with (output / "DMG_Attach.txt").open("w") as file:
            subprocess.run([
                "/usr/bin/hdiutil", "attach", "-readonly", "-nobrowse", "-noautoopen",
                "-mountpoint", str(mount), str(path.resolve()),
            ], stdout=file, stderr=subprocess.STDOUT, check=True, timeout=60)
        attached = True
        app = mount / "Facility Studio.app"
        if not (mount / "Applications").is_symlink():
            raise ValueError("The DMG is missing its Applications shortcut.")
        with (output / "DMG_Apple_Signature.txt").open("w") as file:
            subprocess.run([
                "/usr/bin/codesign", "--verify", "--deep", "--strict", str(app),
            ], stdout=file, stderr=subprocess.STDOUT, check=True, timeout=60)
        with (output / "DMG_Native_GUI.txt").open("w") as file:
            subprocess.run([
                str(app / "Contents/MacOS/FacilityStudio"), "--self-test",
            ], stdout=file, stderr=subprocess.STDOUT, check=True, timeout=180)
    finally:
        if attached:
            subprocess.run([
                "/usr/bin/hdiutil", "detach", str(mount),
            ], check=True, timeout=60)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--checksums", type=Path, required=True)
    parser.add_argument("--dmg", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Native delivery verification requires macOS.")
    expected = {line.split()[1]: line.split()[0] for line in args.checksums.read_text().splitlines()}
    digest = hashlib.sha256(args.package.read_bytes()).hexdigest()
    if expected.get(args.package.name) != digest:
        raise ValueError("The delivered ZIP SHA-256 did not match the build.")
    if expected.get(args.dmg.name) != hashlib.sha256(args.dmg.read_bytes()).hexdigest():
        raise ValueError("The delivered DMG SHA-256 did not match the build.")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run(["/usr/bin/ditto", "-x", "-k", str(args.package.resolve()), str(output / "extracted")], check=True)
    app = output / "extracted/Facility_Studio_V5_5_4_macOS_mac2/Facility Studio.app"
    with (output / "Apple_Signature.txt").open("w") as file:
        subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=4", str(app)],
                       stdout=file,stderr=subprocess.STDOUT,check=True,timeout=60)
    with (output / "Native_GUI_Console.txt").open("w") as file:
        subprocess.run([str(app / "Contents/MacOS/FacilityStudio"), "--self-test"],
                       stdout=file,stderr=subprocess.STDOUT,check=True,timeout=180)
    path = Path.home() / "Library/Logs/Facility_Studio_V5_5/Mac_Acceptance.json"
    result = json.loads(path.read_text())
    assert result["passed"] and result["architecture"] == platform.machine()
    (output / "Mac_Acceptance.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
    verify_dmg(args.dmg, output)
    print(json.dumps(dict(passed=True,architecture=platform.machine(),package_sha256=digest,
                          native_checks=len(result["checks"]))))


if __name__ == "__main__":
    main()
