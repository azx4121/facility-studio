"""Build a real, self-contained Windows executable before distribution."""

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parent
EXE_NAME = "Facility_Studio_V5_5_4_Windows_Offline.exe"
ZIP_NAME = "Facility_Studio_V5_5_4_Windows_Offline_OneClick.zip"
NOTICE_NAMES = ("LICENSE", "LICENSE_GUIDE.md", "LICENSE_LEGACY_MIT", "THIRD_PARTY_NOTICES.md")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def collect_notices(destination):
    notices = []
    for distribution in sorted(importlib.metadata.distributions(), key=lambda item: item.metadata["Name"].lower()):
        collected = []
        for file in distribution.files or ():
            if any(word in str(file).lower() for word in ("license", "copying", "copyright", "notice")):
                path = distribution.locate_file(file)
                if path.is_file() and path.stat().st_size < 2_000_000:
                    try:
                        collected.append(str(file) + "\n" + path.read_text(encoding="utf-8"))
                    except UnicodeError:
                        continue
        if collected:
            notices.append(distribution.metadata["Name"] + " " + distribution.version + "\n" + "\n\n".join(collected))
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise RuntimeError("Official Python license is missing")
    notices.insert(0, "CPython " + platform.python_version() + "\n" + python_license.read_text(encoding="utf-8"))
    destination.write_text("Third-party components retain their original licenses.\n\n" + "\n\n".join(notices), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "win32" or platform.machine().upper() not in ("AMD64", "X86_64"):
        raise RuntimeError("The offline EXE must be built on native x64 Windows")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    evidence = output / "evidence"
    evidence.mkdir(exist_ok=True)
    work = output / "build"
    work.mkdir(exist_ok=True)
    notices = output / "THIRD_PARTY_LICENSES.txt"
    collect_notices(notices)
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed", "--noupx",
               "--name", EXE_NAME[:-4], "--icon", str(ROOT / "facility_studio/resources/app.ico"),
               "--version-file", str(ROOT / "winrelease/version.txt"),
               "--paths", str(ROOT), "--collect-submodules", "facility_studio",
               "--hidden-import", "winrelease.selftest", "--hidden-import", "matplotlib.backends.backend_tkagg",
               "--copy-metadata", "matplotlib", "--copy-metadata", "numpy", "--copy-metadata", "Pillow",
               "--add-data", str(ROOT / "facility_studio/resources") + ":facility_studio/resources",
               "--add-data", str(notices) + ":.", "--distpath", str(output),
               "--workpath", str(work / "work"), "--specpath", str(work)]
    for name in NOTICE_NAMES:
        command.extend(["--add-data", str(REPOSITORY / name) + ":."])
    command.append(str(ROOT / "winrelease/entry.py"))
    with (evidence / "PyInstaller_Build.txt").open("w", encoding="utf-8") as log:
        subprocess.run(command, cwd=ROOT, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=1200)
    exe = output / EXE_NAME
    if not exe.is_file() or exe.stat().st_size < 10_000_000:
        raise RuntimeError("Bundled EXE was not created")
    versions = {item.metadata["Name"]: item.version for item in importlib.metadata.distributions()}
    (evidence / "Build_Manifest.json").write_text(json.dumps({
        "revision": "5.5.4-win.1", "source_commit": os.environ.get("GITHUB_SHA"),
        "python": sys.version, "platform": platform.platform(), "packages": versions,
        "exe_sha256": sha(exe), "exe_bytes": exe.stat().st_size,
        "build_only_internet": True, "runtime_requires_python_installation": False,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    package = output / "Facility_Studio_V5_5_4_Windows_Offline"
    package.mkdir(exist_ok=True)
    shutil.copy2(exe, package / EXE_NAME)
    shutil.copy2(ROOT / "winrelease/README_Offline.txt", package / "README_先看我.txt")
    shutil.copy2(ROOT / "winrelease/Verify_on_Windows.cmd", package / "Verify_on_Windows.cmd")
    shutil.copy2(ROOT / "facility_studio/resources/Equipment_Template.xlsx", package / "設備需求範本.xlsx")
    for name in NOTICE_NAMES:
        shutil.copy2(REPOSITORY / name, package / name)
    shutil.copy2(notices, package / notices.name)
    source = package / "Source"
    shutil.copytree(ROOT / "facility_studio", source / "facility_studio", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("Facility_Studio_V5_5.py", "Default_Project.json"):
        shutil.copy2(ROOT / name, source / name)
    with zipfile.ZipFile(output / ZIP_NAME, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(output).as_posix())
    (output / "SHA256SUMS.txt").write_text("".join(sha(output / name) + "  " + name + "\n" for name in (EXE_NAME, ZIP_NAME)), encoding="utf-8")
    print("Built standalone EXE and full offline ZIP; native delivery acceptance still required.")


if __name__ == "__main__":
    main()
