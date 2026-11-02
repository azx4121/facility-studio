"""Build and test an isolated Universal sandbox. Never publishes a Release."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import urllib.request

from native_probe import RELEASE_URL, RELEASE_SHA256
from native_sign import MACHO_MAGIC, relocate_framework_build_configuration
from bounded_fonts import patch_font_discovery
from prepare_feed_runtime import prepare

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "Facility Studio 工程驗證沙盒.app"
PACKAGE = "Facility-Studio-FEED-Sandbox-5.6.1-1"


def command(args, log, env=None, timeout=300):
    with Path(log).open("w") as file:
        result = subprocess.run(
            [str(x) for x in args],
            stdout=file,
            stderr=subprocess.STDOUT,
            env=env,
            timeout=timeout,
        )
    if result.returncode:
        print(Path(log).read_text(errors="replace")[-16000:], flush=True)
        raise RuntimeError(f"Command failed ({result.returncode}): {args[0]}")


def sign(app, log):
    config = (
        app
        / "Contents/Frameworks/Python.framework/Versions/3.13/Frameworks/Tcl.framework/Versions/8.6/tclConfig.sh"
    )
    if config.is_file():
        relocate_framework_build_configuration(app)
    binaries = []
    for p in app.rglob("*"):
        if p.is_file() and not p.is_symlink():
            with p.open("rb") as f:
                if f.read(4) in MACHO_MAGIC:
                    binaries.append(p)
    frameworks = sorted(
        (p for p in app.rglob("*.framework") if p.is_dir() and not p.is_symlink()),
        key=lambda p: len(p.parts),
        reverse=True,
    )
    with log.open("w") as f:
        for p in [*binaries, *frameworks, app]:
            subprocess.run(
                [
                    "/usr/bin/codesign",
                    "--force",
                    "--sign",
                    "-",
                    "--timestamp=none",
                    str(p),
                ],
                stdout=f,
                stderr=subprocess.STDOUT,
                check=True,
                timeout=60,
            )
        subprocess.run(
            ["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)],
            stdout=f,
            stderr=subprocess.STDOUT,
            check=True,
            timeout=60,
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-app", type=Path)
    parser.add_argument("--cache", type=Path)
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("打包與原生驗收必須在 macOS 執行。")
    output = args.output.resolve()
    if output.exists():
        parser.error("請使用新的輸出目錄；保留所有既有檔案。")
    output.mkdir(parents=True)
    evidence = output / "evidence"
    evidence.mkdir()
    cache = args.cache or output / "downloads"
    cache.mkdir(parents=True, exist_ok=True)
    app = output / APP_NAME
    if args.base_app:
        command(
            ["/usr/bin/codesign", "--verify", "--deep", "--strict", args.base_app],
            evidence / "base-signature.txt",
        )
        command(["/usr/bin/ditto", args.base_app, app], evidence / "copy-runtime.txt")
    else:
        archive = cache / "Original_Runtime_Release.zip"
        if not archive.exists():
            with (
                urllib.request.urlopen(RELEASE_URL, timeout=90) as src,
                archive.open("xb") as dst,
            ):
                while block := src.read(1024 * 1024):
                    dst.write(block)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != RELEASE_SHA256:
            raise ValueError("官方基底執行環境 SHA-256 不符。")
        extracted = output / "runtime"
        command(
            ["/usr/bin/ditto", "-x", "-k", archive, extracted],
            evidence / "extract-runtime.txt",
        )
        command(
            [
                "/usr/bin/ditto",
                extracted / "Facility_Studio_V5_5_4_macOS/Facility Studio.app",
                app,
            ],
            evidence / "copy-runtime.txt",
        )
    resources = app / "Contents/Resources"
    source = resources / "app"
    assert source.resolve().is_relative_to(output)
    shutil.rmtree(source)
    source.mkdir()
    for name in (
        "Facility_Studio_V5_5.py",
        "facility_studio",
        "Default_Project.json",
        "LICENSE",
        "LICENSE_GUIDE.md",
        "LICENSE_LEGACY_MIT",
        "THIRD_PARTY_NOTICES.md",
        "MAC_RUNTIME_PATCHES.md",
    ):
        p = ROOT / name
        if p.is_dir():
            shutil.copytree(
                p, source / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
            )
        else:
            shutil.copy2(p, source / name)
    shutil.copy2(ROOT / "macos/bootstrap_feed_sandbox.py", resources / "bootstrap.py")
    shutil.copy2(ROOT / "macos/mac_selftest.py", source / "mac_selftest.py")
    # Never write Python bytecode inside the signed bundle during tests/use.
    bootstrap = resources / "bootstrap.py"
    text = bootstrap.read_text()
    text = text.replace(
        "import traceback", "import traceback\nsys.dont_write_bytecode = True"
    )
    bootstrap.write_text(text)
    manifest = prepare(app, cache)
    for arch in ("arm64", "x86_64"):
        packages = resources / "python-packages" / arch
        font_source = (packages / "matplotlib/font_manager.py").read_text()
        if 'SPFontsDataType"], timeout=5)' not in font_source:
            patch_font_discovery(packages)
    plist = app / "Contents/Info.plist"
    info = plistlib.loads(plist.read_bytes())
    info.update(
        CFBundleIdentifier="com.facilitystudio.engineering.sandbox",
        CFBundleName="工程驗證沙盒",
        CFBundleDisplayName="Facility Studio 工程驗證沙盒",
        CFBundleShortVersionString="5.6.1",
        CFBundleVersion="5.6.1.2",
        LSMinimumSystemVersion="12.0",
    )
    plist.write_bytes(plistlib.dumps(info))
    (source / "FEED_RUNTIME_NOTICES.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    sign(app, evidence / "codesign.txt")
    env = {**os.environ, "FACILITY_STUDIO_SANDBOX_DATA": str(output / "test-data")}
    launcher = app / "Contents/MacOS/FacilityStudio"
    command(
        [launcher, "--sandbox-self-test", evidence / "Sandbox_Acceptance.json"],
        evidence / "sandbox-native.txt",
        env,
    )
    command([launcher, "--self-test"], evidence / "full-native.txt", env, timeout=360)
    acceptance = json.loads((output / "test-data/Mac_Acceptance.json").read_text())
    if not acceptance["passed"]:
        raise ValueError("原生完整自測未通過。")
    shutil.copy2(
        output / "test-data/Mac_Acceptance.json", evidence / "Mac_Acceptance.json"
    )
    command(
        ["/usr/bin/codesign", "--verify", "--deep", "--strict", app],
        evidence / "codesign-after-tests.txt",
    )
    payload = output / "installer"
    payload.mkdir()
    command(
        ["/usr/bin/ditto", app, payload / APP_NAME], evidence / "installer-copy.txt"
    )
    os.symlink("/Applications", payload / "應用程式")
    (payload / "開始使用.txt").write_text(
        "Facility Studio 整合測試版 5.6.1（建置 2）\n\n主畫面的設計檢核中心可直接使用 AHU 核對、水管物性與壓損、九類工程單位換算。\n冷熱水頁可帶入目前條件；AHU 視窗按獨立核對與報告。\n\n請將同名 App 複製到獨立位置，避免替換正式版。\n測試版使用獨立偏好、日誌與暫存。\n此沙盒採 ad-hoc 完整性簽章，未取得 Developer ID 與 Apple 公證。\n本機測試與工程合格判定分開；請閱讀各頁採用條件。\n"
    )
    dmg = output / (PACKAGE + ".dmg")
    zip_path = output / (PACKAGE + ".zip")
    command(
        [
            "/usr/bin/hdiutil",
            "create",
            "-volname",
            "Facility Studio 工程驗證沙盒",
            "-srcfolder",
            payload,
            "-format",
            "UDZO",
            dmg,
        ],
        evidence / "dmg-build.txt",
    )
    command(["/usr/bin/hdiutil", "verify", dmg], evidence / "dmg-verify.txt")
    command(
        [
            "/usr/bin/ditto",
            "-c",
            "-k",
            "--sequesterRsrc",
            "--keepParent",
            app,
            zip_path,
        ],
        evidence / "zip-build.txt",
    )
    hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (dmg, zip_path)
    }
    (output / "SHA256SUMS.txt").write_text(
        "".join(f"{v}  {k}\n" for k, v in hashes.items())
    )
    (evidence / "release-gates.json").write_text(
        json.dumps(
            {
                "software_tests_passed": True,
                "developer_id_signed": False,
                "apple_notarized": False,
                "engineering_approval": False,
                "three_platform_review": False,
                "release_published": False,
            },
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {"app": str(app), "artifacts": hashes, "passed": True}, ensure_ascii=False
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
