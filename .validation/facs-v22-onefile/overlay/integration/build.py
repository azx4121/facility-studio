"""Native, isolated five-library application; never touches the installed app."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile

try:
    from .acceptance_validation import validate_acceptance, validate_embedded_manifest
    from .source_provenance import expected_source_manifest, verify_source_unchanged
except ImportError:  # Direct script invocation.
    from acceptance_validation import validate_acceptance, validate_embedded_manifest
    from source_provenance import expected_source_manifest, verify_source_unchanged

ROOT = Path(__file__).resolve().parents[1]
NAME = "Facility Studio 5.7.3"


def run(args, log, timeout=1500, env=None):
    with log.open("w", encoding="utf-8") as file:
        result = subprocess.run([str(a) for a in args], stdout=file, stderr=subprocess.STDOUT,
                                cwd=ROOT, timeout=timeout, env=env)
    if result.returncode:
        raise RuntimeError(f"Command exit {result.returncode}; evidence: {log}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-dirty", action="store_true",
                        help="Build explicitly non-release development evidence from uncommitted inputs.")
    parser.add_argument("--windows-onefile", action="store_true",
                        help="Build a Windows portable single EXE, without an installer.")
    a = parser.parse_args()
    if sys.version_info[:2] != (3, 12) or sys.platform not in ("darwin", "win32"):
        raise RuntimeError("Native macOS/Windows and supported Python 3.12 are required.")
    if sys.platform == "darwin" and platform.machine() != "arm64":
        raise RuntimeError("The current macOS distribution supports Apple Silicon arm64 only.")
    if a.windows_onefile and sys.platform != "win32":
        raise RuntimeError("The single EXE option requires native Windows.")
    build_options = {"onefile": True} if a.windows_onefile else {}
    source_platform = "macos" if sys.platform == "darwin" else "windows"
    expected_manifest = expected_source_manifest(ROOT, source_platform, allow_dirty=a.allow_dirty)
    requested = a.output.absolute()
    if os.path.lexists(requested):
        raise FileExistsError(f"Build output already exists: {requested}")
    output = requested.resolve()
    # A fresh output below the repository is itself reachable by the freezer's
    # repository import root. Build elsewhere until both source guards pass,
    # instead of excluding any repository subtree from provenance scanning.
    if output.is_relative_to(ROOT.resolve()):
        temp_parent = Path(tempfile.gettempdir()).resolve()
        if temp_parent.is_relative_to(ROOT.resolve()):
            temp_parent = ROOT.resolve().parent
        with tempfile.TemporaryDirectory(prefix="facility-studio-build-", dir=temp_parent) as temporary:
            staging = Path(temporary) / "output"
            result = _build(staging, source_platform, expected_manifest, a.allow_dirty, **build_options)
            if os.path.lexists(output):
                raise FileExistsError(f"Build output appeared during build: {output}")
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(staging), str(output))
            return result
    return _build(output, source_platform, expected_manifest, a.allow_dirty, **build_options)


def _build(output, source_platform, expected_manifest, allow_dirty, *, onefile=False):
    if onefile and (sys.platform != "win32" or source_platform != "windows"):
        raise RuntimeError("The single EXE option requires native Windows source.")
    output.mkdir(parents=True, exist_ok=False)
    evidence = output / "evidence"
    evidence.mkdir()
    source = ROOT / ("macos" if sys.platform == "darwin" else "windows")
    # Keep python-hvac's MIT process/coil implementation and CoolProp fluids.
    # The product does not use its separate Water/Ice wrappers backed by the
    # GPL iapws package. Patch only a build-local copy's eager initializer;
    # never alter the installed environment or any engineering equation.
    hvac_dist = importlib.metadata.distribution("python-hvac")
    vendor = output / "vendor"
    shutil.copytree(hvac_dist.locate_file("hvac"), vendor / "hvac",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    initializer = vendor / "hvac/fluids/__init__.py"
    original = initializer.read_text(encoding="utf-8")
    selected = original
    for line in ("from .water import Water\n", "from .ice import Ice\n"):
        if selected.count(line) != 1:
            raise RuntimeError("Pinned python-hvac initializer changed; review loading patch.")
        selected = selected.replace(line, "")
    initializer.write_text(selected, encoding="utf-8")
    manifest = dict(expected_manifest, python=platform.python_version(), platform=platform.platform(),
                    excluded_generated_evidence=["windows/evidence/**", "macos/evidence/**"])
    manifest_file = evidence / "Build_Manifest.json"
    manifest["python_hvac_loading_adapter"] = dict(
        upstream_commit="94247560a667905bfbf67e45a58965a58254fce8",
        original_initializer_sha256=hashlib.sha256(original.encode()).hexdigest(),
        selected_initializer_sha256=hashlib.sha256(selected.encode()).hexdigest(),
        excluded_unused_wrappers=["hvac.fluids.water", "hvac.fluids.ice", "iapws"],
        engineering_equations_modified=False,
    )
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    development_notice = None
    if not manifest["source_clean"]:
        development_notice = evidence / "NON_RELEASE_DEVELOPMENT.txt"
        development_notice.write_text(
            "NON-RELEASE DEVELOPMENT BUILD\n"
            "Built from uncommitted inputs. The recorded commit is the base commit, "
            "not the identity of these modified bytes. Do not publish as a release.\n"
            "See Build_Manifest.json for the actual input SHA-256 values.\n", encoding="utf-8")
    notices = []
    for dist in sorted(importlib.metadata.distributions(), key=lambda d: d.metadata["Name"]):
        if dist.metadata["Name"].lower() == "iapws":
            continue  # Not part of the delivered executable.
        for file in dist.files or ():
            path = dist.locate_file(file)
            if path.is_file() and path.stat().st_size < 2_000_000 and any(w in str(file).lower() for w in ("license", "copying", "copyright", "notice")):
                try:
                    notices.append(dist.metadata["Name"] + " " + dist.version + "\n" + path.read_text(encoding="utf-8"))
                except UnicodeError:
                    pass
    for name in ("LICENSE", "LICENSE_LEGACY_MIT", "THIRD_PARTY_NOTICES.md", "macos/macos/PsychroLib-LICENSE.txt"):
        notices.append(name + "\n" + (ROOT / name).read_text(encoding="utf-8"))
    python_license = next((p for p in (Path(sys.base_prefix) / "LICENSE.txt",
                                       Path(sys.base_prefix) / "lib/python3.12/LICENSE.txt") if p.is_file()), None)
    if python_license is None:
        raise RuntimeError("Bundled Python license was not found.")
    notices.append(python_license.read_text(encoding="utf-8"))
    notice_file = evidence / "第三方授權.txt"
    notice_file.write_text("\n\n".join(notices), encoding="utf-8")
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile" if onefile else "--onedir", "--windowed", "--noupx",
            "--name", NAME, "--paths", source, "--paths", vendor, "--collect-submodules", "facility_studio",
            "--additional-hooks-dir", ROOT / "windows/winrelease/hooks",
            "--hidden-import", "matplotlib.backends.backend_tkagg", "--hidden-import", "CoolProp.CoolProp",
            "--hidden-import", "CoolProp._constants", "--collect-data", "pint", "--collect-data", "fluids",
            "--collect-data", "hvac", "--collect-data", "scipy",
            "--add-data", str(source / "facility_studio/resources") + os.pathsep + "facility_studio/resources",
            "--add-data", str(notice_file) + os.pathsep + ".",
            "--add-data", str(manifest_file) + os.pathsep + ".",
            "--distpath", output / "dist", "--workpath", output / "work", "--specpath", output]
    if development_notice is not None:
        args += ["--add-data", str(development_notice) + os.pathsep + "."]
    if onefile:
        for guide in ("README_繁體中文.md", "README_English.md"):
            args += ["--add-data", str(ROOT / "integration" / guide) + os.pathsep + "."]
    for name in ("PsychroLib", "CoolProp", "fluids", "Pint", "python-hvac"):
        args += ["--copy-metadata", name]
    # python-hvac imports CoolProp.Plots through hvac.charts even when this
    # product only requests process calculations. Frozen execution proved that
    # Plots must remain; only unused tests/GUI are excluded.
    # Arrow is pandas' optional Parquet/Feather engine (110 MB of binaries on
    # macOS). The product uses Excel/CSV, not these formats; pandas supports
    # their absence. Retain and test openpyxl, the actual Excel dependency.
    for name in ("pyarrow", "pytest", "hypothesis", "CoolProp.tests", "CoolProp.GUI", "numpy.tests", "scipy.tests", "pandas.tests", "IPython", "iapws", "hvac.fluids.water", "hvac.fluids.ice"):
        args += ["--exclude-module", name]
    if sys.platform == "win32":
        args += ["--add-binary", str(Path(sys.base_prefix) / "python3.dll") + os.pathsep + ".",
                 "--version-file", ROOT / "integration/windows_version.txt",
                 "--icon", source / "facility_studio/resources/app.ico"]
    else:
        args += ["--osx-bundle-identifier", "com.facilitystudio.release573",
                 "--icon", source / "facility_studio/resources/app.png"]
    args += [ROOT / "integration/entry.py"]
    run(args, evidence / "PyInstaller_Build.txt")
    # Detect source edits during freezing before accepting or distributing bytes.
    verify_source_unchanged(ROOT, source_platform, expected_manifest)
    archive_index = output / "work" / NAME / "PYZ-00.toc"
    if "'iapws" in archive_index.read_text(encoding="utf-8"):
        raise RuntimeError("Unused iapws implementation entered the frozen archive.")
    if onefile:
        try:
            from .onefile_validation import verify_single_exe
        except ImportError:
            from onefile_validation import verify_single_exe
        executable = output / "dist" / (NAME + ".exe")
        verify_single_exe(executable, evidence / "single-exe", expected_manifest,
                          allow_non_release=allow_dirty)
        verify_source_unchanged(ROOT, source_platform, expected_manifest)
        artifact = output / "Facility-Studio-5.7.3-v22-Windows-x64-Portable.exe"
        shutil.copy2(executable, artifact)
        if hashlib.sha256(artifact.read_bytes()).digest() != hashlib.sha256(executable.read_bytes()).digest():
            raise RuntimeError("Single EXE delivery copy differs from the tested executable.")
        (output / "SHA256SUMS.txt").write_text(hashlib.sha256(artifact.read_bytes()).hexdigest()
                                             + "  " + artifact.name + "\n", encoding="utf-8")
        return 0
    if sys.platform == "darwin":
        app = output / "dist" / (NAME + ".app")
        shutil.copy2(ROOT / "integration/README_繁體中文.md", app / "Contents/Resources/操作說明_繁體中文.md")
        shutil.copy2(ROOT / "integration/README_English.md", app / "Contents/Resources/User_Guide_English.md")
        info = app / "Contents/Info.plist"
        values = plistlib.loads(info.read_bytes())
        values.update(CFBundleShortVersionString="5.7.3", CFBundleVersion="5.7.3.2",
                      CFBundleDisplayName=NAME, NSHighResolutionCapable=True)
        info.write_bytes(plistlib.dumps(values))
        run(["/usr/bin/codesign", "--force", "--sign", "-", "--timestamp=none", app], evidence / "Sign_App.txt")
        run(["/usr/bin/codesign", "--verify", "--deep", "--strict", app], evidence / "Signature.txt")
        executable = app / "Contents/MacOS" / NAME
    else:
        app = output / "dist" / NAME
        shutil.copy2(ROOT / "integration/README_繁體中文.md", app / "操作說明_繁體中文.md")
        shutil.copy2(ROOT / "integration/README_English.md", app / "User_Guide_English.md")
        executable = app / (NAME + ".exe")
    validate_embedded_manifest(app, manifest["commit"], expected_manifest=expected_manifest,
                               allow_non_release=allow_dirty)
    env = dict(os.environ, FACILITY_STUDIO_FUSION_DATA=str(output / "isolated-test-data"), FACILITY_TEST_BLOCK_NETWORK="1")
    run([executable, "--fusion-self-test", evidence / "Fusion_Acceptance.json"], evidence / "Fusion_Acceptance.log", env=env, timeout=180)
    run([executable, "--facilities-self-test", evidence / "Facilities_Acceptance.json"], evidence / "Facilities_Acceptance.log", env=env, timeout=180)
    validate_acceptance(evidence / "Fusion_Acceptance.json", expected_commit=manifest["commit"],
                        expected_manifest=expected_manifest, expected_suite="fusion",
                        allow_non_release=allow_dirty)
    validate_acceptance(evidence / "Facilities_Acceptance.json", expected_commit=manifest["commit"],
                        expected_manifest=expected_manifest, expected_suite="facilities",
                        allow_non_release=allow_dirty)
    if sys.platform == "win32":
        try:
            from .windows_installer import build as build_installer, verify as verify_installer
        except ImportError:
            from windows_installer import build as build_installer, verify as verify_installer
        setup = build_installer(app, output, NAME, run)
        verify_installer(setup, output, NAME, run, env, expected_commit=manifest["commit"],
                         expected_manifest=expected_manifest, allow_non_release=allow_dirty)
    verify_source_unchanged(ROOT, source_platform, expected_manifest)
    artifact = output / (("Facility-Studio-5.7.3-macOS-arm64.zip") if sys.platform == "darwin" else "Facility-Studio-5.7.3-Windows-x64-Portable.zip")
    if sys.platform == "darwin":
        run(["/usr/bin/ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", app, artifact], evidence / "Archive.txt")
    else:
        shutil.make_archive(str(artifact.with_suffix("")), "zip", app.parent, app.name)
    deliveries = [artifact] + ([setup] if sys.platform == "win32" else [])
    (output / "SHA256SUMS.txt").write_text("".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n" for p in deliveries), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
