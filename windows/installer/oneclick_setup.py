"""V5.5.4 Windows preparation/build launcher. Does not alter calculation code."""

from __future__ import annotations

import datetime
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
import uuid

PACKAGE = Path(__file__).resolve().parent


def verify_payload(root: Path):
    entries = json.loads((root / "payload_sha256.json").read_text(encoding="utf-8"))
    required = {
        "LICENSE",
        "LICENSE_GUIDE.md",
        "LICENSE_LEGACY_MIT",
        "THIRD_PARTY_NOTICES.md",
        "Facility_Studio_V5_5.py",
        "facility_studio/ahu_schema.py",
        "facility_studio/simple_desktop.py",
        "facility_studio/simple_engines.py",
        "facility_studio/air_chart.py",
        "facility_studio/equipment_schema.py",
        "facility_studio/equipment_io.py",
        "facility_studio/json_io.py",
        "facility_studio/equipment_analysis.py",
        "facility_studio/equipment_view.py",
        "facility_studio/resources/Equipment_Template.xlsx",
        "facility_studio/resources/app.ico",
        "facility_studio/resources/engineering_tables.json",
    }
    required.update(
        "facility_studio/resources/equipment_csv/" + system + ".csv"
        for system in ("電力", "PCW", "CDA", "N2", "EXHAUST", "DI", "PV")
    )
    if not isinstance(entries, dict) or not required.issubset(entries):
        raise RuntimeError("The payload manifest is incomplete.")
    for relative, digest in entries.items():
        if (
            not isinstance(relative, str)
            or "\\" in relative
            or ".." in Path(relative).parts
            or Path(relative).is_absolute()
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            raise RuntimeError("Invalid payload manifest entry.")
        path = root / "payload" / relative
        if not path.resolve().is_relative_to((root / "payload").resolve()):
            raise RuntimeError("Invalid payload path.")
        if (
            not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            raise RuntimeError("Missing or changed package file: " + relative)
    actual = {
        path.relative_to(root / "payload").as_posix()
        for path in (root / "payload").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    if actual != set(entries):
        raise RuntimeError("The payload contains unexpected or missing files.")
    return entries


def run(args, log, **kwargs):
    # A list and shell=False preserve spaces, Chinese names and CMD metacharacters.
    log.write("\nCOMMAND: " + repr([str(x) for x in args]) + "\n")
    log.flush()
    subprocess.run(
        [str(x) for x in args],
        stdout=log,
        stderr=subprocess.STDOUT,
        check=True,
        **kwargs,
    )


def check_output(exe, project, directory, log):
    report = directory / "Installation_Check.txt"
    audit = directory / "Installation_Check.json"
    if report.exists() or audit.exists():
        raise RuntimeError("Smoke-check output must be new.")
    run(
        [exe, "--project", project, "--report", report, "--result", audit],
        log,
        timeout=180,
    )
    if not report.is_file() or report.stat().st_size < 100:
        raise RuntimeError("The generated EXE did not write a valid report.")
    result = json.loads(audit.read_text(encoding="utf-8"))
    if not isinstance(result, dict) or not result.get("hash"):
        raise RuntimeError("The generated EXE did not write a valid audit.")
    simple_audit = directory / "Simple_Tool_Check.json"
    run(
        [
            exe,
            "--tool",
            "electrical",
            "--result",
            simple_audit,
            "--report",
            directory / "Simple_Tool_Check.txt",
        ],
        log,
        timeout=180,
    )
    simple = json.loads(simple_audit.read_text(encoding="utf-8"))
    if simple.get("tool") != "electrical" or not simple.get("selected"):
        raise RuntimeError(
            "The generated EXE failed the independent electrical tool check."
        )
    template = directory / "Equipment_Template.xlsx"
    run([exe, "--export-equipment-template", template], log, timeout=180)
    expected_template = (
        PACKAGE / "payload/facility_studio/resources/Equipment_Template.xlsx"
    )
    if (
        not template.is_file()
        or template.read_bytes() != expected_template.read_bytes()
    ):
        raise RuntimeError(
            "The generated EXE failed the Excel template resource check."
        )
    for system in ("電力", "PCW", "CDA", "N2", "EXHAUST", "DI", "PV"):
        source = (
            PACKAGE
            / "payload/facility_studio/resources/equipment_csv"
            / (system + ".csv")
        )
        with source.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        rows[1][0] = "1"
        fixture = directory / ("Equipment_Check_" + system + ".csv")
        with fixture.open("w", encoding="utf-8-sig", newline="") as stream:
            csv.writer(stream).writerows(rows)
        audit = directory / ("Equipment_Check_" + system + ".json")
        run(
            [
                exe,
                "--equipment",
                fixture,
                "--equipment-system",
                system,
                "--result",
                audit,
                "--report",
                directory / ("Equipment_Check_" + system + ".txt"),
            ],
            log,
            timeout=180,
        )
        schedule = json.loads(audit.read_text(encoding="utf-8"))
        if schedule.get("version") != "5.5.4" or len(schedule.get("groups", [])) != 1:
            raise RuntimeError(
                "The generated EXE failed an equipment system check: " + system
            )
    run([exe, "--gui-smoke"], log, timeout=180)


def main():
    if sys.platform != "win32":
        raise RuntimeError("Please run START.cmd on Windows 10/11 x64.")
    import tkinter  # Fail clearly before any installation if Tcl/Tk is missing.
    import struct

    if sys.version_info[:2] != (3, 13) or struct.calcsize("P") != 8:
        raise RuntimeError("Python 3.13 x64 is required by this package launcher.")
    verify_payload(PACKAGE)
    base = Path(os.environ["LOCALAPPDATA"]) / "Facility_Studio_V5_5"
    base.mkdir(parents=True, exist_ok=True)
    log_path = base / "Setup.log"
    stamp = (
        datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    )
    release = base / "releases" / stamp
    release.mkdir(parents=True)
    build_dir = release / "build"
    build_dir.mkdir()
    venv_dir = base / "build_environment"
    python = venv_dir / "Scripts" / "python.exe"
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        try:
            print("[1/5] Preparing a separate build environment...", flush=True)
            run([sys.executable, "-m", "venv", venv_dir], log, timeout=180)
            print(
                "[2/5] Downloading build and chart packages. Please wait...", flush=True
            )
            run(
                [
                    python,
                    "-m",
                    "pip",
                    "--disable-pip-version-check",
                    "install",
                    "pyinstaller>=6,<7",
                    "matplotlib>=3.8,<4",
                ],
                log,
                timeout=1800,
            )
            run([python, "-m", "pip", "freeze"], log, timeout=60)
            run(
                [
                    python,
                    "-c",
                    "import tkinter; import matplotlib.backends.backend_tkagg; "
                    "r=tkinter.Tk(); r.withdraw(); r.update(); r.destroy()",
                ],
                log,
                timeout=60,
            )
            print(
                "[3/5] Building Facility_Studio_V5_5_4.exe. This can take several minutes...",
                flush=True,
            )
            run(
                [
                    python,
                    "-m",
                    "PyInstaller",
                    "--noconfirm",
                    "--clean",
                    "--onefile",
                    "--windowed",
                    "--icon",
                    PACKAGE / "payload/facility_studio/resources/app.ico",
                    "--add-data",
                    str(PACKAGE / "payload/LICENSE") + ":.",
                    "--add-data",
                    str(PACKAGE / "payload/LICENSE_GUIDE.md") + ":.",
                    "--add-data",
                    str(PACKAGE / "payload/LICENSE_LEGACY_MIT") + ":.",
                    "--add-data",
                    str(PACKAGE / "payload/THIRD_PARTY_NOTICES.md") + ":.",
                    "--add-data",
                    str(PACKAGE / "payload/facility_studio/resources")
                    + ":"
                    + "facility_studio/resources",
                    "--name",
                    "Facility_Studio_V5_5_4",
                    "--hidden-import",
                    "matplotlib.backends.backend_tkagg",
                    "--distpath",
                    release,
                    "--paths",
                    PACKAGE / "payload",
                    "--collect-submodules",
                    "facility_studio",
                    "--workpath",
                    build_dir / "work",
                    "--specpath",
                    build_dir,
                    PACKAGE / "payload" / "Facility_Studio_V5_5.py",
                ],
                log,
                cwd=build_dir,
                timeout=1800,
            )
            exe = release / "Facility_Studio_V5_5_4.exe"
            if not exe.is_file() or exe.stat().st_size < 100000:
                raise RuntimeError("EXE build did not complete.")
            for name in ("LICENSE", "LICENSE_GUIDE.md", "LICENSE_LEGACY_MIT", "THIRD_PARTY_NOTICES.md"):
                shutil.copy2(PACKAGE / "payload" / name, release / name)
            print("[4/5] Checking the EXE by generating a design report...", flush=True)
            check_output(
                exe, PACKAGE / "payload" / "Default_Project.json", release, log
            )
            examples = base / "Examples"
            examples.mkdir(exist_ok=True)
            for source in (PACKAGE / "payload").iterdir():
                if source.suffix in (".json", ".md", ".txt"):
                    destination = examples / source.name
                    if not destination.exists():
                        shutil.copy2(source, destination)
            projects = base / "Projects"
            projects.mkdir(exist_ok=True)
            print("[5/5] Creating a desktop shortcut...", flush=True)
            env = dict(os.environ, HVAC_EXE=str(exe), HVAC_PROJECTS=str(projects))
            command = (
                "$ErrorActionPreference='Stop'; "
                "$w=New-Object -ComObject WScript.Shell; "
                "$d=[Environment]::GetFolderPath('Desktop'); "
                "$s=$w.CreateShortcut((Join-Path $d 'Facility Studio V5.5.lnk')); "
                "$s.TargetPath=$env:HVAC_EXE; $s.WorkingDirectory=$env:HVAC_PROJECTS; "
                "$s.IconLocation=$env:HVAC_EXE+',0'; $s.Description='Facility Studio V5.5.4'; $s.Save()"
            )
            shortcut_ok = True
            try:
                run(
                    [
                        "powershell.exe",
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        command,
                    ],
                    log,
                    env=env,
                    timeout=60,
                )
            except (subprocess.SubprocessError, OSError):
                shortcut_ok = False
                log.write("\nShortcut could not be created. EXE is ready.\n")
            print("\nSUCCESS: " + str(exe), flush=True)
            print("Examples: " + str(examples), flush=True)
            print("Log: " + str(log_path), flush=True)
            if not shortcut_ok:
                print(
                    "Desktop shortcut unavailable; opening the EXE folder instead.",
                    flush=True,
                )
                os.startfile(str(release))
            (base / "Installed_Path.txt").write_text(str(exe), encoding="utf-8")
            subprocess.Popen([str(exe)], cwd=projects)
            return 0
        except Exception:
            traceback.print_exc(file=log)
            print(
                "\nSETUP FAILED. Your project files were not overwritten.", flush=True
            )
            print(
                "Please send this log for troubleshooting: " + str(log_path), flush=True
            )
            return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("SETUP ERROR: " + str(error))
        raise SystemExit(1)
