"""Execute the same delivered installer/EXE/ZIP on genuine Windows runners."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile

os.environ["FACILITY_STUDIO_SANDBOX"] = "1"
from winrelease.build_sandbox import EXE_NAME, SETUP_NAME, ZIP_NAME, PACKAGE, sha
from winrelease.verify import check_exe, firewall


def smoke(exe, evidence, label, data_root=None):
    target = evidence / (label + "-Sandbox_Acceptance.json")
    with tempfile.TemporaryDirectory(prefix="FacilitySandbox-") as d:
        work = Path(d)
        data = Path(data_root) if data_root else work / "使用者資料"
        data.mkdir(parents=True, exist_ok=True)
        env = {
            **os.environ,
            "LOCALAPPDATA": str(data),
            "FACILITY_STUDIO_SANDBOX_DATA": str(data),
            "FACILITY_TEST_BLOCK_NETWORK": "1",
        }
        for key in tuple(env):
            if key.upper().startswith(("PYTHON", "PYI_")):
                env.pop(key)
        win = Path(os.environ["SystemRoot"])
        env["PATH"] = os.pathsep.join(
            map(str, [win / "System32", win, win / "System32/WindowsPowerShell/v1.0"])
        )
        rule = "FacilitySandbox-" + uuid.uuid4().hex
        firewall(exe, rule, True)
        try:
            r = subprocess.run(
                [str(exe), "--sandbox-self-test", str(target)],
                cwd=work,
                env=env,
                timeout=180,
            )
            if r.returncode:
                print(
                    target.read_text(encoding="utf-8", errors="replace")
                    if target.exists()
                    else "沒有產生沙盒驗收報告",
                    flush=True,
                )
                raise RuntimeError(f"沙盒 EXE 退出碼 {r.returncode}")
            report = json.loads(target.read_text(encoding="utf-8"))
            if (
                not report["passed"]
                or not report["frozen"]
                or not report["offline_network_audit"]
            ):
                raise RuntimeError("實際封裝／離線沙盒驗收未通過")
        finally:
            firewall(exe, rule, False)
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--assets", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if sys.platform != "win32":
        raise RuntimeError("必須在原生 Windows 執行驗收。")
    assets = a.assets.resolve()
    out = a.output.resolve()
    if out.exists():
        raise ValueError("請使用新的驗收目錄。")
    out.mkdir(parents=True)
    sums = {
        line.split()[1]: line.split()[0]
        for line in (assets / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    }
    for name in (EXE_NAME, SETUP_NAME, ZIP_NAME):
        if sums.get(name) != sha(assets / name):
            raise RuntimeError("交付 SHA-256 不符：" + name)
    standalone = smoke(assets / EXE_NAME, out, "standalone")
    records = []
    with tempfile.TemporaryDirectory(prefix="FacilitySandboxInstall-", dir=out) as d:
        base = Path(d)
        occupied = base / "既有資料"
        occupied.mkdir()
        marker = occupied / "保留資料.txt"
        marker.write_text("preserve-existing", encoding="utf-8")
        blocked = subprocess.run(
            [str(assets / SETUP_NAME), "/S", "/D=" + str(occupied)], timeout=60
        )
        if (
            blocked.returncode == 0
            or marker.read_text(encoding="utf-8") != "preserve-existing"
            or (occupied / EXE_NAME).exists()
        ):
            raise RuntimeError("安裝程式沒有拒絕覆寫既有資料。")
        records.append(
            {
                "name": "拒絕覆寫非空目錄",
                "passed": True,
                "exit_code": blocked.returncode,
            }
        )
        installed = base / "中文 安裝位置"
        r = subprocess.run(
            [str(assets / SETUP_NAME), "/S", "/D=" + str(installed)], timeout=180
        )
        exe = installed / EXE_NAME
        if r.returncode or not exe.is_file() or sha(exe) != sums[EXE_NAME]:
            raise RuntimeError("實際安裝或 EXE 雜湊不符。")
        records.append(
            {
                "name": "中文路徑實際離線安裝與雜湊",
                "passed": True,
                "exit_code": r.returncode,
            }
        )
        try:
            profile = base / "設定與專案資料"
            profile.mkdir()
            profile_marker = profile / "保留專案.txt"
            profile_marker.write_text("keep-project-and-settings", encoding="utf-8")
            installed_smoke = smoke(exe, out, "installed", profile)
            # Full existing frozen GUI/audit/report/CLI acceptance, not just imports.
            check_exe(exe, out, "installed-full-offline")
            extra = installed / "使用者另存資料.txt"
            extra.write_text("keep-user-file", encoding="utf-8")
            subprocess.run(
                [str(installed / "Uninstall.exe"), "/S"], timeout=90, check=True
            )
            deadline = time.monotonic() + 60
            while exe.exists() and time.monotonic() < deadline:
                time.sleep(0.25)
            if (
                exe.exists()
                or not extra.is_file()
                or extra.read_text(encoding="utf-8") != "keep-user-file"
                or profile_marker.read_text(encoding="utf-8")
                != "keep-project-and-settings"
            ):
                raise RuntimeError("移除測試程式未保留使用者檔案。")
            records.append(
                {"name": "移除程式保留使用者檔案", "passed": True, "exit_code": 0}
            )
        finally:
            # Cleanup is restricted to this temporary test installation.
            uninstaller = installed / "Uninstall.exe"
            if uninstaller.exists():
                subprocess.run([str(uninstaller), "/S"], timeout=90, check=False)
        extracted = base / "免安裝 中文目錄"
        extracted.mkdir()
        with zipfile.ZipFile(assets / ZIP_NAME) as archive:
            for item in archive.infolist():
                if not (extracted / item.filename).resolve().is_relative_to(extracted):
                    raise RuntimeError("ZIP 路徑不安全。")
            archive.extractall(extracted)
        portable = extracted / PACKAGE / EXE_NAME
        if sha(portable) != sums[EXE_NAME]:
            raise RuntimeError("ZIP 中的 EXE 與實測檔案不同。")
        portable_smoke = smoke(portable, out, "portable")
        records.append(
            {"name": "免安裝 ZIP 相同 EXE 與中文路徑", "passed": True, "exit_code": 0}
        )
    summary = {
        "passed": True,
        "platform": sys.platform,
        "exe_sha256": sums[EXE_NAME],
        "sandbox_checks": {
            "standalone": len(standalone["checks"]),
            "installed": len(installed_smoke["checks"]),
            "portable": len(portable_smoke["checks"]),
        },
        "installer_checks": records,
        "full_acceptance": "installed-full-offline/Delivery_Check.json",
        "authenticode_signed": False,
        "safety_controls_disabled": False,
    }
    (out / "Windows_Sandbox_Delivery_Check.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
