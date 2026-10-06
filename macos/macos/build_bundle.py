"""Build the offline universal2 macOS app from pinned, verified artifacts.

Build inputs are CPython's official framework, platform-specific PyPI wheels,
Zig-generated Mach-O launchers and rcodesign. Build never executes Mac code.
"""

import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import stat
import subprocess
import zipfile

from macho import inspect, relocate, slices, universal

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--signer", type=Path, required=True)
    args = parser.parse_args()
    runtime, output = args.runtime.resolve(), args.output.resolve()
    app = output / "Facility Studio.app"
    if app.exists():
        raise SystemExit(
            "Build output already exists; choose a fresh output directory."
        )
    contents = app / "Contents"
    frameworks, resources, executables = [
        contents / item for item in ("Frameworks", "Resources", "MacOS")
    ]
    for directory in (frameworks, resources, executables):
        directory.mkdir(parents=True, exist_ok=True)
    framework = frameworks / "Python.framework"
    shutil.copytree(runtime / "Python.framework", framework, symlinks=True)
    version = framework / "Versions" / "3.13"
    # These interpreter tools are not used by the application.
    for directory in (
        version / "Resources/Python.app",
        version / "bin",
        version / "Headers",
        version / "include",
        version / "lib/python3.13/test",
        version / "lib/python3.13/idlelib",
        version / "lib/python3.13/ensurepip",
    ):
        if directory.is_symlink():
            directory.unlink()
        elif directory.is_dir():
            shutil.rmtree(directory)
    for path in list(framework.rglob("*")):
        if path.is_file() and (
            path.name.startswith("._") or path.suffix in (".pyc", ".a", ".o")
        ):
            path.unlink()
    for path in sorted(framework.rglob("__pycache__"), reverse=True):
        shutil.rmtree(path)
    # Remove wrapper symlinks whose targets were intentionally omitted.
    for path in list(framework.rglob("*")):
        if path.is_symlink() and not path.exists():
            path.unlink()
    if (version / "bin").exists():
        raise ValueError("Unused interpreter bin directory was not removed")
    universal(
        [runtime / "launcher_x86_64", runtime / "launcher_arm64"],
        executables / "FacilityStudio",
    )
    app_source = resources / "app"
    app_source.mkdir()
    for name in ("Facility_Studio_V5_5.py", "facility_studio", "Default_Project.json"):
        source = ROOT / name
        if source.is_dir():
            shutil.copytree(
                source,
                app_source / name,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        elif source.is_file():
            shutil.copy2(source, app_source / name)
    shutil.copy2(ROOT / "macos/bootstrap.py", resources / "bootstrap.py")
    shutil.copy2(ROOT / "macos/mac_selftest.py", app_source / "mac_selftest.py")
    wheel_records = []
    for architecture in ("arm64", "x86_64"):
        packages = resources / "python-packages" / architecture
        packages.mkdir(parents=True)
        for wheel in sorted((runtime / f"wheels_{architecture}").glob("*.whl")):
            with zipfile.ZipFile(wheel) as archive:
                if archive.testzip() is not None:
                    raise ValueError("Corrupt wheel")
                for item in archive.infolist():
                    if item.is_dir():
                        continue
                    target = packages / item.filename
                    if not target.resolve().is_relative_to(packages.resolve()):
                        raise ValueError("Unsafe wheel path")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(item))
            wheel_records.append(
                {
                    "architecture": architecture,
                    "filename": wheel.name,
                    "sha256": sha(wheel),
                }
            )
    # Convert the existing multi-resolution FY icon without changing its artwork.
    with zipfile.ZipFile(runtime / "icon.icns.zip") as archive:
        (resources / "FacilityStudio.icns").write_bytes(
            archive.read("FacilityStudio.icns")
        )
    info = {
        "CFBundleName": "Facility Studio",
        "CFBundleDisplayName": "Facility Studio",
        "CFBundleIdentifier": "com.facilitystudio.desktop",
        "CFBundleExecutable": "FacilityStudio",
        "CFBundlePackageType": "APPL",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleShortVersionString": "5.5.4",
        "CFBundleVersion": "5.5.4.1",
        "CFBundleIconFile": "FacilityStudio.icns",
        "CFBundleDevelopmentRegion": "zh_TW",
        "CFBundleLocalizations": ["zh_TW", "en"],
        "LSMinimumSystemVersion": "11.0",
        "LSArchitecturePriority": ["arm64", "x86_64"],
        "NSHighResolutionCapable": True,
        "CFBundleAllowMixedLocalizations": True,
        "NSHumanReadableCopyright": "Facility Studio — 通用廠務工程工具",
    }
    with (contents / "Info.plist").open("wb") as file:
        plistlib.dump(info, file)
    (contents / "PkgInfo").write_bytes(b"APPL????")
    binaries = []
    changes = 0
    for path in sorted(app.rglob("*")):
        if path.is_file() and not path.is_symlink():
            # Official framework libraries arrive read-only; the copied build
            # must be writable while relocating and generating new signatures.
            path.chmod(path.stat().st_mode | stat.S_IWUSR)
            with path.open("rb") as file:
                magic = file.read(4)
            if magic in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf"):
                changes += relocate(path, app)
                binaries.append(path)
    # Clear stale bundle resource signatures before recursively making ad-hoc ones.
    for path in list(app.rglob("_CodeSignature")):
        if path.is_dir():
            shutil.rmtree(path)
    signature_log = output / "AdHoc_Signing.log"
    broken_before_signing = [str(path.relative_to(app)) for path in app.rglob("*") if path.is_symlink() and not path.exists()]
    if broken_before_signing:
        raise ValueError(f"Broken symlinks before signing: {broken_before_signing}")
    with signature_log.open("w", encoding="utf-8") as file:
        subprocess.run(
            [str(args.signer.resolve()), "sign", str(app)],
            stdout=file,
            stderr=subprocess.STDOUT,
            check=True,
        )
    broken_after_signing = [str(path.relative_to(app)) for path in app.rglob("*") if path.is_symlink() and not path.exists()]
    if broken_after_signing:
        raise ValueError(f"Broken symlinks after signing: {broken_after_signing}")
    manifest = {
        "version": "5.5.4-mac.1",
        "minimum_macos": "11.0",
        "architectures": ["arm64", "x86_64"],
        "runtime": {
            "python": "3.13.15",
            "pkg_sha256": sha(runtime / "python-3.13.15-macos11.pkg"),
        },
        "wheels": wheel_records,
        "relocated_commands": changes,
        "signing": "ad-hoc; no Developer ID certificate or Apple notarization",
        "mac_hardware_execution": False,
        "binaries": [
            {"path": str(path.relative_to(app)), "slices": inspect(path)}
            for path in binaries
        ],
    }
    (output / "Mac_Bundle_Manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Built {app}; {len(binaries)} Mach-O files; {changes} relocated commands.")


if __name__ == "__main__":
    main()
