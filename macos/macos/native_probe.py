"""Probe the shipped macOS application without changing its signatures.

Run only on Darwin. This checks the exact release bytes on a native runner;
it does not claim to reproduce a browser's quarantine or a user's macOS beta.
"""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import urllib.request


RELEASE_URL = (
    "https://github.com/azx4121/facility-studio/releases/download/"
    "v5.5.4-beta.1/Facility_Studio_V5_5_4_macOS_OneClick.zip"
)
RELEASE_SHA256 = "aef324d08815257848e4b8080023611b41a4a88eb2cdd03e6ee1a71e5a983b65"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Native application probing requires macOS.")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    observations = []

    def run(name, command, required=True, timeout=90):
        started = time.monotonic()
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, errors="replace",
                timeout=timeout, check=False,
            )
            status = result.returncode
            console = result.stdout + result.stderr
        except subprocess.TimeoutExpired as error:
            status = 124
            parts = (error.stdout or b"", error.stderr or b"")
            console = "\n".join(
                p.decode("utf-8", errors="replace") if isinstance(p, bytes) else p
                for p in parts
            ) + "\nNative process exceeded its time limit."
        (output / (name + ".txt")).write_text(console, encoding="utf-8")
        record = dict(name=name, required=required, returncode=status,
                      passed=status == 0, seconds=round(time.monotonic() - started, 2))
        observations.append(record)
        print(json.dumps(record), flush=True)
        return status

    package = output / "Original_macOS_Release.zip"
    request = urllib.request.Request(RELEASE_URL, headers={"User-Agent": "FacilityStudio-native-probe"})
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=45) as response, package.open("wb") as destination:
        while block := response.read(1024 * 1024):
            destination.write(block)
            digest.update(block)
    if digest.hexdigest() != RELEASE_SHA256:
        raise ValueError("Release SHA-256 does not match the audited original.")
    extracted = output / "extracted"
    if run("archive_extraction", ["/usr/bin/ditto", "-x", "-k", str(package), str(extracted)]):
        raise RuntimeError("Native ZIP extraction failed.")
    app = extracted / "Facility_Studio_V5_5_4_macOS/Facility Studio.app"
    executable = app / "Contents/MacOS/FacilityStudio"
    run("apple_codesign", ["/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=4", str(app)])
    run("gatekeeper_assessment", ["/usr/sbin/spctl", "--assess", "--type", "execute", "--verbose=4", str(app)], required=False)
    for tool in ("electrical", "duct", "gas", "lighting", "water", "air", "units"):
        run("native_tool_" + tool, [str(executable), "--tool", tool,
                                   "--report", str(output / (tool + "_report.txt"))])
    run("native_gui_selftest", [str(executable), "--self-test"], timeout=150)
    app_logs = Path.home() / "Library/Logs/Facility_Studio_V5_5"
    if app_logs.is_dir():
        for source in app_logs.iterdir():
            if source.is_file() and source.suffix in (".txt", ".json", ".log"):
                shutil.copy2(source, output / source.name)
    result = dict(
        platform=platform.platform(), architecture=platform.machine(),
        release_sha256=digest.hexdigest(), quarantine_reproduced=False,
        signatures_changed=False, observations=observations,
        passed=all(o["passed"] for o in observations if o["required"]),
    )
    (output / "Native_Probe.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
