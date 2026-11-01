"""Verify the delivered universal macOS ZIP on a second native architecture."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import shutil
import time


def retain_ui_timing(output, *, since, name="Native_UITiming.json"):
    """Retain completed event turns even if a later turn/process times out."""
    source = Path.home() / "Library/Logs/Facility_Studio_V5_5/Native_UITiming.json"
    if source.is_file() and source.stat().st_mtime >= since:
        try:
            json.loads(source.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        shutil.copy2(source, output / name)


def verify_dmg(path, output):
    """Verify the read-only delivery image and detach it even on failure."""
    mount = output / "dmg-mounted"
    mount.mkdir()
    attached = False
    try:
        with (output / "DMG_Attach.txt").open("w") as file:
            subprocess.run(
                [
                    "/usr/bin/hdiutil",
                    "attach",
                    "-readonly",
                    "-nobrowse",
                    "-noautoopen",
                    "-mountpoint",
                    str(mount),
                    str(path.resolve()),
                ],
                stdout=file,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=60,
            )
        attached = True
        app = mount / "Facility Studio.app"
        if not (mount / "Applications").is_symlink():
            raise ValueError("The DMG is missing its Applications shortcut.")
        with (output / "DMG_Apple_Signature.txt").open("w") as file:
            subprocess.run(
                [
                    "/usr/bin/codesign",
                    "--verify",
                    "--deep",
                    "--strict",
                    str(app),
                ],
                stdout=file,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=60,
            )
        with (output / "DMG_Native_GUI.txt").open("w") as file:
            started = time.time()
            try:
                subprocess.run(
                    [str(app / "Contents/MacOS/FacilityStudio"), "--self-test"],
                    stdout=file,
                    stderr=subprocess.STDOUT,
                    check=True,
                    timeout=SELF_TEST_TIMEOUT_SECONDS,
                )
            finally:
                retain_ui_timing(output, since=started, name="DMG_Native_UITiming.json")
    finally:
        if attached:
            subprocess.run(
                [
                    "/usr/bin/hdiutil",
                    "detach",
                    str(mount),
                ],
                check=True,
                timeout=60,
            )


# Whole-process limit of one delivered-app self-test. The Intel runner needs more than the earlier 300 s (one run ended
# at 300 s with every check passed so far); the per-interaction 5 s budget inside the self-test is unchanged.
SELF_TEST_TIMEOUT_SECONDS = 480


def print_self_test_failure(console):
    """Show the end of the self-test console and every failed check; never changes the pass/fail decision."""
    try:
        lines = console.read_text(encoding="utf-8", errors="replace").splitlines()
        print("--- self-test console (last 60 lines) ---", flush=True)
        print("\n".join(lines[-60:]), flush=True)
    except OSError as error:
        print("self-test console unavailable: " + str(error), flush=True)
    result = Path.home() / "Library/Logs/Facility_Studio_V5_5/Mac_Acceptance.json"
    try:
        data = json.loads(result.read_text(encoding="utf-8"))
        failed = [item for item in data.get("checks", []) if not item.get("passed")]
        print("--- failed checks: " + str(len(failed)) + " of " + str(len(data.get("checks", []))) + " ---", flush=True)
        for item in failed[:20]:
            print(json.dumps(item, ensure_ascii=False)[:600], flush=True)
        for key in ("callback_errors", "execution_errors"):
            if data.get(key):
                print(key + ": " + json.dumps(data[key], ensure_ascii=False)[:1500], flush=True)
    except (OSError, ValueError) as error:
        print("self-test result unavailable: " + str(error), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--checksums", type=Path, required=True)
    parser.add_argument("--dmg", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Native delivery verification requires macOS.")
    expected = {
        line.split()[1]: line.split()[0]
        for line in args.checksums.read_text().splitlines()
    }
    digest = hashlib.sha256(args.package.read_bytes()).hexdigest()
    if expected.get(args.package.name) != digest:
        raise ValueError("The delivered ZIP SHA-256 did not match the build.")
    if expected.get(args.dmg.name) != hashlib.sha256(args.dmg.read_bytes()).hexdigest():
        raise ValueError("The delivered DMG SHA-256 did not match the build.")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "/usr/bin/ditto",
            "-x",
            "-k",
            str(args.package.resolve()),
            str(output / "extracted"),
        ],
        check=True,
    )
    app = output / "extracted/Facility_Studio_V5_6_0_macOS_mac7/Facility Studio.app"
    with (output / "Apple_Signature.txt").open("w") as file:
        subprocess.run(
            [
                "/usr/bin/codesign",
                "--verify",
                "--deep",
                "--strict",
                "--verbose=4",
                str(app),
            ],
            stdout=file,
            stderr=subprocess.STDOUT,
            check=True,
            timeout=60,
        )
    with (output / "Native_GUI_Console.txt").open("w", encoding="utf-8") as file:
        started = time.time()
        try:
            subprocess.run(
                [str(app / "Contents/MacOS/FacilityStudio"), "--self-test"],
                stdout=file,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=SELF_TEST_TIMEOUT_SECONDS,
            )
        except BaseException:
            # The console and result stay in the evidence artifact; also print what failed so the CI log names it.
            print_self_test_failure(output / "Native_GUI_Console.txt")
            raise
        finally:
            retain_ui_timing(output, since=started)
    path = Path.home() / "Library/Logs/Facility_Studio_V5_5/Mac_Acceptance.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    assert result["passed"] and result["architecture"] == platform.machine()
    (output / "Mac_Acceptance.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2)
    )
    for pattern in ("English_*.png", "V556_*.png", "Native_UITiming.json"):
        for evidence in path.parent.glob(pattern):
            shutil.copy2(evidence, output / evidence.name)
    verify_dmg(args.dmg, output)
    print(
        json.dumps(
            dict(
                passed=True,
                architecture=platform.machine(),
                package_sha256=digest,
                native_checks=len(result["checks"]),
            )
        )
    )


if __name__ == "__main__":
    main()
