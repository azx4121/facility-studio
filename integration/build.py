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

ROOT = Path(__file__).resolve().parents[1]
NAME = "Facility Studio 5.7.1 測試版"


def run(args, log, timeout=1500, env=None):
    with log.open("w", encoding="utf-8") as file:
        result = subprocess.run([str(a) for a in args], stdout=file, stderr=subprocess.STDOUT,
                                cwd=ROOT, timeout=timeout, env=env)
    if result.returncode:
        raise RuntimeError(f"Command exit {result.returncode}; evidence: {log}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    a = parser.parse_args()
    if sys.version_info[:2] != (3, 12) or sys.platform not in ("darwin", "win32"):
        raise RuntimeError("Native macOS/Windows and supported Python 3.12 are required.")
    if sys.platform == "darwin" and platform.machine() != "arm64":
        raise RuntimeError("This delivery target is the user's Apple Silicon Mac.")
    output = a.output.resolve()
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
    manifest = dict(python=platform.python_version(), platform=platform.platform(),
                    commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                    build_inputs_sha256={p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                         for p in (ROOT / "integration").glob("*") if p.is_file()},
                    product_source_sha256={p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                           for p in (source / "facility_studio").rglob("*")
                                           if p.is_file() and "__pycache__" not in p.parts})
    manifest_file = evidence / "Build_Manifest.json"
    manifest["python_hvac_loading_adapter"] = dict(
        upstream_commit="94247560a667905bfbf67e45a58965a58254fce8",
        original_initializer_sha256=hashlib.sha256(original.encode()).hexdigest(),
        selected_initializer_sha256=hashlib.sha256(selected.encode()).hexdigest(),
        excluded_unused_wrappers=["hvac.fluids.water", "hvac.fluids.ice", "iapws"],
        engineering_equations_modified=False,
    )
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
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
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed", "--noupx",
            "--name", NAME, "--paths", source, "--paths", vendor, "--collect-submodules", "facility_studio",
            "--additional-hooks-dir", ROOT / "windows/winrelease/hooks",
            "--hidden-import", "matplotlib.backends.backend_tkagg", "--hidden-import", "CoolProp.CoolProp",
            "--hidden-import", "CoolProp._constants", "--collect-data", "pint", "--collect-data", "fluids",
            "--collect-data", "hvac", "--collect-data", "scipy",
            "--add-data", str(source / "facility_studio/resources") + os.pathsep + "facility_studio/resources",
            "--add-data", str(notice_file) + os.pathsep + ".",
            "--add-data", str(manifest_file) + os.pathsep + ".",
            "--distpath", output / "dist", "--workpath", output / "work", "--specpath", output]
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
        args += ["--osx-bundle-identifier", "com.facilitystudio.engineeringfusion.preview571",
                 "--icon", source / "facility_studio/resources/app.png"]
    args += [ROOT / "integration/entry.py"]
    run(args, evidence / "PyInstaller_Build.txt")
    archive_index = output / "work" / NAME / "PYZ-00.toc"
    if "'iapws" in archive_index.read_text(encoding="utf-8"):
        raise RuntimeError("Unused iapws implementation entered the frozen archive.")
    if sys.platform == "darwin":
        app = output / "dist" / (NAME + ".app")
        shutil.copy2(ROOT / "integration/README_繁體中文.md", app / "Contents/Resources/操作說明_繁體中文.md")
        info = app / "Contents/Info.plist"
        values = plistlib.loads(info.read_bytes())
        values.update(CFBundleShortVersionString="5.7.1", CFBundleVersion="5.7.1.1",
                      CFBundleDisplayName=NAME, NSHighResolutionCapable=True)
        info.write_bytes(plistlib.dumps(values))
        run(["/usr/bin/codesign", "--force", "--sign", "-", "--timestamp=none", app], evidence / "Sign_App.txt")
        run(["/usr/bin/codesign", "--verify", "--deep", "--strict", app], evidence / "Signature.txt")
        executable = app / "Contents/MacOS" / NAME
    else:
        app = output / "dist" / NAME
        shutil.copy2(ROOT / "integration/README_繁體中文.md", app / "操作說明_繁體中文.md")
        executable = app / (NAME + ".exe")
    env = dict(os.environ, FACILITY_STUDIO_FUSION_DATA=str(output / "isolated-test-data"), FACILITY_TEST_BLOCK_NETWORK="1")
    run([executable, "--fusion-self-test", evidence / "Fusion_Acceptance.json"], evidence / "Fusion_Acceptance.log", env=env, timeout=180)
    run([executable, "--facilities-self-test", evidence / "Facilities_Acceptance.json"], evidence / "Facilities_Acceptance.log", env=env, timeout=180)
    if sys.platform == "win32":
        from windows_installer import build as build_installer, verify as verify_installer
        setup = build_installer(app, output, NAME, run)
        verify_installer(setup, output, NAME, run, env)
    artifact = output / (("Facility-Studio-5.7.1-macOS-arm64.zip") if sys.platform == "darwin" else "Facility-Studio-5.7.1-Windows-x64-Portable.zip")
    if sys.platform == "darwin":
        run(["/usr/bin/ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", app, artifact], evidence / "Archive.txt")
    else:
        shutil.make_archive(str(artifact.with_suffix("")), "zip", app.parent, app.name)
    deliveries = [artifact] + ([setup] if sys.platform == "win32" else [])
    (output / "SHA256SUMS.txt").write_text("".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n" for p in deliveries), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
