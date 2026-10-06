"""Stage a complete payload and build the Windows online installer."""

from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from nsis_integrity import expected_members, verify_setup

ROOT = Path(__file__).resolve().parent


def stage_payload():
    installer = ROOT / "installer"
    for cache in installer.rglob("__pycache__"):
        shutil.rmtree(cache)
    payload = installer / "payload"
    # This directory contains generated installer inputs only.
    if payload.is_symlink():
        raise RuntimeError("The generated payload directory must not be a symlink.")
    if payload.exists():
        shutil.rmtree(payload)
    payload.mkdir(parents=True)
    shutil.copytree(
        ROOT / "facility_studio",
        payload / "facility_studio",
        ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", "*.openai-download-*", ".*"
        ),
    )
    for name in ["Facility_Studio_V5_5.py", "Default_Project.json", "README.txt"]:
        shutil.copy2(ROOT / name, payload / name)
    # Check the staged copy before allowing publication of an installer.
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; import facility_studio; "
            "from facility_studio import api; "
            "from facility_studio.simple_engines import calculate_tool, ENGINES; "
            "from facility_studio.simple_schema import defaults; "
            "from facility_studio.equipment_io import load_equipment; "
            "assert Path(facility_studio.__file__).resolve().is_relative_to(Path.cwd()); "
            "assert facility_studio.__version__ == api.VERSION == '5.5.4'; "
            "api.calculate(api.default_project()); "
            "api.nm_calculate(api.NM_DEFAULTS.copy()); "
            "assert all(calculate_tool(k, defaults(k))['tool'] == k for k in ENGINES); "
            "schedule=load_equipment(Path('facility_studio/resources/Equipment_Template.xlsx')); "
            "assert len(schedule['systems']) == len(schedule['records']) == 7; "
            "print('Staged payload imports, full defaults, seven simple tools and seven schedule tabs: PASS')",
        ],
        cwd=payload,
        check=True,
    )
    for cache in payload.rglob("__pycache__"):
        shutil.rmtree(cache)
    manifest = {
        path.relative_to(payload)
        .as_posix(): hashlib.sha256(path.read_bytes())
        .hexdigest()
        for path in sorted(payload.rglob("*"))
        if path.is_file()
    }
    (installer / "payload_sha256.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def main():
    manifest = stage_payload()
    compiler = shutil.which("makensis")
    env = dict(os.environ)
    if compiler is None:
        local = ROOT.parent / "installer_runtime/root/usr/bin/makensis"
        if not local.is_file():
            raise SystemExit(
                "Install NSIS 3.x and put makensis on PATH to rebuild Setup.exe. "
                "The staged installer/START.cmd can also build the application on Windows."
            )
        compiler = str(local)
        env["NSISDIR"] = str(ROOT.parent / "installer_runtime/root/usr/share/nsis")
    log_path = ROOT / "evidence/NSIS_Build.log"
    log_path.parent.mkdir(exist_ok=True)
    output = ROOT / "Facility_Studio_V5_5_4_Setup.exe"
    # Keep the previous output intact until the new binary is fully verified.
    with tempfile.TemporaryDirectory(prefix=".nsis-build-", dir=ROOT) as temporary:
        candidate = Path(temporary) / output.name
        with log_path.open("w", encoding="utf-8") as log:
            subprocess.run(
                [
                    compiler,
                    "-V4",
                    "-DFS_SETUP_OUTPUT=" + str(candidate),
                    str(ROOT / "installer.nsi"),
                ],
                cwd=ROOT,
                env=env,
                check=True,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        integrity = verify_setup(candidate, expected_members(ROOT / "installer"))
        os.replace(candidate, output)
    (ROOT / "evidence/Installer_Integrity.json").write_text(
        json.dumps(integrity, indent=2), encoding="utf-8"
    )
    print(
        "Setup CRC, complete decompression and embedded files: PASS;",
        integrity["embedded_files"],
        "embedded files;",
        len(manifest),
        "application payload files",
    )


if __name__ == "__main__":
    main()
