"""Run shipped binaries with external Python hidden and outbound traffic blocked."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid
import zipfile

from winrelease.build import EXE_NAME, ZIP_NAME, sha


def firewall(exe, rule, add):
    # Windows temporary paths can contain 8.3 aliases. WFP rules require a
    # canonical application path; do not pass the unresolved temp alias.
    application_path = exe.resolve(strict=True)
    env = dict(
        os.environ, FACILITY_TEST_EXE=str(application_path), FACILITY_TEST_RULE=rule
    )
    if add:
        command = "$ErrorActionPreference='Stop'; New-NetFirewallRule -Name $env:FACILITY_TEST_RULE -DisplayName $env:FACILITY_TEST_RULE -Direction Outbound -Action Block -Program $env:FACILITY_TEST_EXE -Profile Any | Out-Null"
    else:
        command = "$ErrorActionPreference='Stop'; Remove-NetFirewallRule -Name $env:FACILITY_TEST_RULE"
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        env=env,
        check=True,
        timeout=60,
    )


def launch(exe, arguments, cwd, env):
    result = subprocess.run(
        [str(exe), *map(str, arguments)], cwd=cwd, env=env, timeout=150
    )
    if result.returncode:
        if "--self-test-result" in arguments:
            index = arguments.index("--self-test-result") + 1
            report = Path(arguments[index])
            if report.is_file():
                data = json.loads(report.read_text(encoding="utf-8"))
                print(json.dumps({
                    "native_selftest_failures": [
                        item for item in data["checks"] if not item["passed"]
                    ],
                    "total_checks": len(data["checks"]),
                }, ensure_ascii=False), flush=True)
            runtime_log = report.with_name("Windows_Runtime.txt")
            if runtime_log.is_file():
                print(runtime_log.read_text(
                    encoding="utf-8", errors="replace"
                )[-12000:], flush=True)
        raise RuntimeError(
            "Delivered EXE failed with exit code " + str(result.returncode)
        )


def check_exe(exe, output, label, block_firewall=True):
    evidence = output / label
    evidence.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="FacilityStudioWindows-") as directory:
        temporary = Path(directory)
        user_data = temporary / "使用者資料"
        user_data.mkdir()
        # No build interpreter, source directory or Python launcher on PATH.
        env = dict(
            os.environ, LOCALAPPDATA=str(user_data), FACILITY_TEST_BLOCK_NETWORK="1"
        )
        for name in tuple(env):
            if name.upper().startswith(("PYTHON", "PYI_")):
                env.pop(name)
        systemroot = Path(os.environ["SystemRoot"])
        env["PATH"] = os.pathsep.join(
            map(
                str,
                [
                    systemroot / "System32",
                    systemroot,
                    systemroot / "System32/WindowsPowerShell/v1.0",
                ],
            )
        )
        cwd = temporary / "空白 工作資料夾"
        cwd.mkdir()
        rule = "FacilityStudioOfflineAcceptance-" + uuid.uuid4().hex
        if block_firewall:
            firewall(exe, rule, True)
        try:
            report = evidence / "Windows_Acceptance.json"
            launch(exe, ["--self-test", "--self-test-result", report], cwd, env)
            data = json.loads(report.read_text(encoding="utf-8"))
            if (
                not data["passed"]
                or not data["frozen"]
                or not data["offline_network_audit"]
            ):
                raise RuntimeError("Frozen Windows acceptance did not pass")
            for name in (
                "electrical",
                "duct",
                "gas",
                "lighting",
                "water",
                "air",
                "units",
            ):
                result = evidence / (name + ".json")
                text = evidence / (name + ".txt")
                launch(
                    exe,
                    ["--tool", name, "--result", result, "--report", text],
                    cwd,
                    env,
                )
                if (
                    json.loads(result.read_text(encoding="utf-8"))["tool"] != name
                    or not text.read_text(encoding="utf-8").strip()
                ):
                    raise RuntimeError("Independent executable report failed: " + name)
            template = evidence / "設備 範本.xlsx"
            launch(exe, ["--export-equipment-template", template], cwd, env)
            if not template.is_file():
                raise RuntimeError("Frozen EXE template export failed")
            project = evidence / "預設專案.json"
            launch(exe, ["--write-default", project], cwd, env)
            full_result = evidence / "Full_Engineering.json"
            launch(
                exe,
                [
                    "--project",
                    project,
                    "--result",
                    full_result,
                    "--report",
                    evidence / "完整報告.txt",
                ],
                cwd,
                env,
            )
            if not isinstance(
                json.loads(full_result.read_text(encoding="utf-8")), dict
            ):
                raise RuntimeError("Frozen full engineering CLI failed")
            summary = {
                "label": label,
                "gui_checks": len(data["checks"]),
                "cli_tools": 7,
                "firewall_outbound_blocked": block_firewall,
                "network_audit_blocked": True,
                "python_on_path": False,
                "empty_working_directory": True,
                "exe_sha256": sha(exe),
                "passed": True,
            }
            (evidence / "Delivery_Check.json").write_text(
                json.dumps(summary, indent=2), encoding="utf-8"
            )
            print(json.dumps(summary), flush=True)
        finally:
            runtime_log = user_data / "Facility_Studio_V5_5/Logs/Windows_Runtime.log"
            if runtime_log.is_file():
                shutil.copy2(runtime_log, evidence / "Windows_Runtime.txt")
            if block_firewall:
                firewall(exe, rule, False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assets, output = args.assets.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    sums = {
        line.split()[1]: line.split()[0]
        for line in (assets / "SHA256SUMS.txt").read_text().splitlines()
    }
    for name in (EXE_NAME, ZIP_NAME):
        if sums.get(name) != sha(assets / name):
            raise RuntimeError("Delivered file SHA256 mismatch: " + name)
    check_exe(assets / EXE_NAME, output, "standalone")
    # Stage beneath the runner's canonical work directory. Keep a separate
    # Unicode-path execution check, independent of firewall path parsing.
    with tempfile.TemporaryDirectory(
        prefix="FacilityStudioZip-", dir=output
    ) as directory:
        extraction = Path(directory)
        with zipfile.ZipFile(assets / ZIP_NAME) as archive:
            # Only our freshly built, verified distribution is extracted.
            for member in archive.infolist():
                target = (extraction / member.filename).resolve()
                if not target.is_relative_to(extraction.resolve()):
                    raise RuntimeError("Unexpected unsafe package member")
            archive.extractall(extraction)
        exe = extraction / "Facility_Studio_V5_5_6_Windows_Offline" / EXE_NAME
        if sha(exe) != sums[EXE_NAME]:
            raise RuntimeError("ZIP contains a different executable")
        check_exe(exe, output, "zip-extracted")
        unicode_directory = extraction / "中文 解壓縮目錄"
        unicode_directory.mkdir()
        unicode_exe = unicode_directory / EXE_NAME
        shutil.copy2(exe, unicode_exe)
        check_exe(unicode_exe, output, "unicode-executable-path", block_firewall=False)
    print(
        "Both standalone EXE and extracted ZIP passed native offline Windows acceptance."
    )


if __name__ == "__main__":
    main()
