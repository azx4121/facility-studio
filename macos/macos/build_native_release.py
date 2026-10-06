"""Rebuild mac.2 on macOS using verified runtime bytes and Apple's signer."""

import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

from bounded_fonts import patch_font_discovery
from native_probe import RELEASE_SHA256, RELEASE_URL
from native_sign import sign_app

ROOT = Path(__file__).resolve().parents[1]
VERSION = "5.5.4-mac.2"
PACKAGE_NAME = "Facility_Studio_V5_5_4_macOS_mac2"


def command(args, log, timeout=180):
    with Path(log).open("w", encoding="utf-8") as output:
        subprocess.run(args, stdout=output, stderr=subprocess.STDOUT,
                       check=True, timeout=timeout)


def main():
    import urllib.request

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Release building and acceptance require native macOS.")
    output = args.output.resolve()
    if output.exists():
        parser.error("Choose a fresh output directory; existing files are retained.")
    output.mkdir(parents=True)
    evidence = output / "evidence"
    evidence.mkdir()
    original = output / "Original_Runtime_Release.zip"
    request = urllib.request.Request(RELEASE_URL, headers={"User-Agent": "FacilityStudio-native-rebuild"})
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=45) as response, original.open("wb") as file:
        while block := response.read(1024 * 1024):
            file.write(block)
            digest.update(block)
    if digest.hexdigest() != RELEASE_SHA256:
        raise ValueError("The original runtime package was not the audited release.")
    extracted = output / "runtime"
    command(["/usr/bin/ditto", "-x", "-k", str(original), str(extracted)], evidence / "Extraction.txt")
    old_root = extracted / "Facility_Studio_V5_5_4_macOS"
    app = old_root / "Facility Studio.app"
    source = app / "Contents/Resources/app"
    shutil.rmtree(source)
    source.mkdir()
    required = (
        "Facility_Studio_V5_5.py", "facility_studio", "Default_Project.json",
        "LICENSE", "LICENSE_GUIDE.md", "LICENSE_LEGACY_MIT", "THIRD_PARTY_NOTICES.md",
        "MAC_RUNTIME_PATCHES.md",
    )
    for name in required:
        path = ROOT / name
        if path.is_dir():
            shutil.copytree(path, source / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        elif path.is_file():
            shutil.copy2(path, source / name)
        else:
            raise ValueError("Required source file missing: " + name)
    shutil.copy2(ROOT / "macos/bootstrap.py", app / "Contents/Resources/bootstrap.py")
    shutil.copy2(ROOT / "macos/mac_selftest.py", source / "mac_selftest.py")
    font_patches = {}
    for architecture in ("arm64", "x86_64"):
        font_patches[architecture] = patch_font_discovery(
            app / "Contents/Resources/python-packages" / architecture)
    plist_path = app / "Contents/Info.plist"
    with plist_path.open("rb") as file:
        info = plistlib.load(file)
    info["CFBundleVersion"] = "5.5.4.2"
    with plist_path.open("wb") as file:
        plistlib.dump(info, file)
    print("Applying Apple native signatures...", flush=True)
    signing = sign_app(app, evidence / "Apple_Native_Signing.txt")
    launcher = app / "Contents/MacOS/FacilityStudio"
    for tool in ("electrical", "duct", "gas", "lighting", "water", "air", "units"):
        command([str(launcher), "--tool", tool, "--report", str(evidence / (tool + "_Report.txt"))],
                evidence / (tool + "_Native.txt"), timeout=30)
    print("Running cold-cache native GUI acceptance...", flush=True)
    command([str(launcher), "--self-test"], evidence / "Native_GUI_Console.txt", timeout=180)
    acceptance = Path.home() / "Library/Logs/Facility_Studio_V5_5/Mac_Acceptance.json"
    result = json.loads(acceptance.read_text(encoding="utf-8"))
    if not result["passed"]:
        raise ValueError("Native Mac acceptance did not pass.")
    shutil.copy2(acceptance, evidence / "Mac_Acceptance.json")
    stage = output / PACKAGE_NAME
    stage.mkdir()
    shutil.move(str(app), stage / "Facility Studio.app")
    app = stage / "Facility Studio.app"
    for name in ("LICENSE", "LICENSE_GUIDE.md", "LICENSE_LEGACY_MIT", "THIRD_PARTY_NOTICES.md",
                 "README_macOS.txt", "MAC_RUNTIME_PATCHES.md"):
        shutil.copy2(ROOT / name, stage / name)
    for name in ("Install_on_Mac.command", "Verify_on_Mac.command"):
        target = stage / name
        shutil.copy2(ROOT / "macos" / name, target)
        target.chmod(0o755)
        subprocess.run(["/bin/bash", "-n", str(target)], check=True)
    shutil.copy2(ROOT / "facility_studio/resources/Equipment_Template.xlsx",
                 stage / "Facility_Studio_Equipment_Template.xlsx")
    manifest = dict(version=VERSION, source_commit=__import__("os").environ.get("GITHUB_SHA"),
                    runtime_source_sha256=RELEASE_SHA256, font_patches=font_patches,
                    signing=signing, native_acceptance=result,
                    browser_quarantine_reproduced=False)
    (evidence / "Mac2_Build.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copytree(evidence, stage / "Verification")
    from make_package import zip_tree

    source_zip = stage / "Source_and_Verification.zip"
    zip_tree(ROOT, source_zip, "Facility_Studio_macOS_Source")
    delivered_zip = output / "Facility_Studio_V5_5_4_macOS_mac2_OneClick.zip"
    command(["/usr/bin/ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(stage), str(delivered_zip)],
            evidence / "ZIP_Creation.txt")
    roundtrip = output / "roundtrip"
    command(["/usr/bin/ditto", "-x", "-k", str(delivered_zip), str(roundtrip)], evidence / "ZIP_Extraction.txt")
    delivered_app = roundtrip / PACKAGE_NAME / "Facility Studio.app"
    command(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(delivered_app)],
            evidence / "Delivered_Apple_Signature.txt")
    command([str(delivered_app / "Contents/MacOS/FacilityStudio"), "--self-test"],
            evidence / "Delivered_GUI_Console.txt", timeout=180)
    # A standard DMG supports dragging the app to Applications without scripts.
    dmg_stage = output / "dmg-stage"
    dmg_stage.mkdir()
    command(["/usr/bin/ditto", str(app), str(dmg_stage / "Facility Studio.app")], evidence / "DMG_Copy.txt")
    (dmg_stage / "Applications").symlink_to("/Applications")
    shutil.copy2(ROOT / "README_macOS.txt", dmg_stage / "請先閱讀.txt")
    dmg = output / "Facility_Studio_V5_5_4_macOS_mac2.dmg"
    command(["/usr/bin/hdiutil", "create", "-volname", "Facility Studio 5.5.4", "-srcfolder",
             str(dmg_stage), "-format", "UDZO", str(dmg)], evidence / "DMG_Creation.txt")
    from verify_native_release import verify_dmg

    verify_dmg(dmg, evidence)
    checksums = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in (delivered_zip, dmg)}
    (output / "SHA256SUMS.txt").write_text("".join(f"{value}  {name}\n" for name, value in checksums.items()))
    print(json.dumps(dict(version=VERSION,files=checksums,native_gui_checks=len(result["checks"])), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
