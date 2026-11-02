"""Build a genuine native x64 Windows sandbox; no release publication."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import zipfile

os.environ["FACILITY_STUDIO_SANDBOX"] = "1"
from winrelease.build import collect_notices, NOTICE_NAMES

ROOT = Path(__file__).resolve().parents[1]
EXE_NAME = "Facility_Studio_FEED_Sandbox_5_6_1.exe"
SETUP_NAME = "Facility_Studio_FEED_Sandbox_5_6_1_Setup.exe"
ZIP_NAME = "Facility_Studio_FEED_Sandbox_5_6_1_Portable.zip"
PACKAGE = "Facility_Studio_FEED_Sandbox_5_6_1"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(args, log, timeout=1200):
    with log.open("w", encoding="utf-8") as file:
        r = subprocess.run(
            [str(x) for x in args],
            cwd=ROOT,
            stdout=file,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    if r.returncode:
        print(log.read_text(encoding="utf-8", errors="replace")[-20000:], flush=True)
        raise RuntimeError(f"建置失敗，退出碼 {r.returncode}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "win32" or platform.machine().upper() not in ("AMD64", "X86_64"):
        raise RuntimeError("必須在原生 Windows x64 建置。")
    output = args.output.resolve()
    if output.exists():
        raise ValueError("請使用新的輸出資料夾，保留既有檔案。")
    output.mkdir(parents=True)
    evidence = output / "evidence"
    evidence.mkdir()
    (output / "build").mkdir()
    notices = output / "THIRD_PARTY_LICENSES.txt"
    collect_notices(notices)
    # The published PsychroLib sdist omits its license text; include the
    # retained upstream MIT notice already audited for the Mac sandbox.
    with notices.open("a", encoding="utf-8") as file:
        file.write(
            "\nPsychroLib 2.5.0\n"
            + (ROOT.parent / "macos/macos/PsychroLib-LICENSE.txt").read_text()
        )
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--noupx",
        "--name",
        EXE_NAME[:-4],
        "--icon",
        ROOT / "facility_studio/resources/app.ico",
        "--version-file",
        ROOT / "winrelease/sandbox_version.txt",
        "--paths",
        ROOT,
        "--additional-hooks-dir",
        ROOT / "winrelease/hooks",
        "--collect-submodules",
        "facility_studio",
        "--hidden-import",
        "winrelease.selftest",
        "--hidden-import",
        "matplotlib.backends.backend_tkagg",
        "--collect-all",
        "CoolProp",
        "--collect-data",
        "pint",
        "--collect-data",
        "fluids",
        "--collect-data",
        "scipy",
        "--exclude-module",
        "pytest",
        "--exclude-module",
        "hypothesis",
        "--add-data",
        str(ROOT / "facility_studio/resources")
        + os.pathsep
        + "facility_studio/resources",
        "--add-data",
        str(notices) + os.pathsep + ".",
        "--distpath",
        output,
        "--workpath",
        output / "build/work",
        "--specpath",
        output / "build",
    ]
    # The official CoolProp wheel uses the stable ABI via python3.dll.
    # Retain that shim even if dependency discovery considers it a system DLL.
    stable_abi = Path(sys.base_prefix) / "python3.dll"
    if not stable_abi.is_file():
        raise RuntimeError("官方 Python 執行環境缺少穩定 ABI DLL。")
    args += ["--add-binary", str(stable_abi) + os.pathsep + "."]
    for name in (
        "matplotlib",
        "numpy",
        "Pillow",
        "PsychroLib",
        "CoolProp",
        "Pint",
        "fluids",
        "scipy",
        "flexcache",
        "flexparser",
        "platformdirs",
        "typing_extensions",
    ):
        args += ["--copy-metadata", name]
    for name in NOTICE_NAMES:
        args += ["--add-data", str(ROOT.parent / name) + os.pathsep + "."]
    args += [ROOT / "winrelease/sandbox_entry.py"]
    command(args, evidence / "PyInstaller_Build.txt")
    exe = output / EXE_NAME
    if not exe.is_file() or exe.stat().st_size < 10_000_000:
        raise RuntimeError("未建立實際 Windows 執行檔。")
    from importlib.util import find_spec
    from PyInstaller.archive.readers import CArchiveReader

    coolprop = Path(find_spec("CoolProp").origin).parent
    sidecars = list((coolprop.parent / "coolprop.libs").glob("*.dll"))
    if not sidecars:
        raise RuntimeError("官方 CoolProp wheel 未含預期原生依賴。")
    archive = CArchiveReader(str(exe))
    bundled = {name.replace("\\", "/").lower() for name in archive.toc}
    required = {"python3.dll", "coolprop/coolprop.pyd"}
    required.update("coolprop.libs/" + p.name.lower() for p in sidecars)
    missing = sorted(required - bundled)
    if missing:
        raise RuntimeError("封裝缺少原生 DLL／擴充模組：" + ", ".join(missing))
    (evidence / "Native_DLL_Manifest.json").write_text(
        json.dumps({"required": sorted(required), "missing": missing,
                    "official_sidecar_sha256": {p.name: sha(p) for p in sidecars}},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    readme = output / "README_Windows_繁體中文.txt"
    readme.write_text(
        """Facility Studio 整合測試版 5.6.1（建置 2；Windows x64）

安裝：執行 Facility_Studio_FEED_Sandbox_5_6_1_Setup.exe，依繁中畫面安裝。
免安裝：解壓縮 Portable.zip 後，開啟 Facility_Studio_FEED_Sandbox_5_6_1.exe。
內含 Python、Tk 與計算套件；使用時不需另外安裝 Python 或連網。

主畫面「設計檢核中心」可直接使用 AHU 獨立核對、水管物性與壓損、九類單位換算。
冷熱水頁可帶入物性與壓損分析；每個 AHU 視窗按「獨立核對與報告」讀取目前輸入。
提供 AHU 目前輸入對照、完整品質原因、純水管路壓損、九類單位換算及 TXT/HTML/JSON 匯出。
水管可帶入原快算條件；並聯依支數分流。請確認水溫、絕對壓力與系統邊界。
輸入變更後必須重新計算；報告不覆寫既有檔案。

正式版與測試版使用不同安裝位置及捷徑。
預設資料：%LOCALAPPDATA%\\Facility Studio FEED Sandbox\\Data
移除程式時會保留專案、偏好與日誌。既有正式版與原專案不替換。
安裝程式拒絕寫入非空目錄，避免覆蓋其他檔案。

本版是合成案例軟體驗證與工程初估工具；工程品質、內部數值門檻及設計驗收分開。
原模型未達條件／待資料會如實顯示；不能把數值對照通過當成設備性能或 FEED 簽核。
本版未取得 Windows Authenticode 商業簽章；不要求關閉防毒或安全機制。
第三方套件授權見隨附 LICENSE 與 THIRD_PARTY_LICENSES.txt。
""",
        encoding="utf-8-sig",
    )
    package = output / PACKAGE
    package.mkdir()
    for path in (exe, readme, notices):
        shutil.copy2(path, package / path.name)
    for name in NOTICE_NAMES:
        shutil.copy2(ROOT.parent / name, output / name)
        shutil.copy2(ROOT.parent / name, package / name)
    template = ROOT / "facility_studio/resources/Equipment_Template.xlsx"
    shutil.copy2(template, package / "設備需求範本.xlsx")
    compiler = shutil.which("makensis") or str(
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
        / "NSIS/makensis.exe"
    )
    if not Path(compiler).is_file():
        raise RuntimeError("建置環境缺少官方 NSIS 編譯器。")
    setup = output / SETUP_NAME
    command(
        [
            compiler,
            "/V3",
            "/DFEED_EXE=" + str(exe),
            "/DFEED_OUT=" + str(setup),
            "/DFEED_ASSETS=" + str(output),
            ROOT / "winrelease/sandbox_installer.nsi",
        ],
        evidence / "NSIS_Build.txt",
    )
    with zipfile.ZipFile(
        output / ZIP_NAME, "w", zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(output).as_posix())
    names = (EXE_NAME, SETUP_NAME, ZIP_NAME)
    (output / "SHA256SUMS.txt").write_text(
        "".join(f"{sha(output / name)}  {name}\n" for name in names), encoding="utf-8"
    )
    manifest = {
        "build": "5.6.1-win-sandbox.2",
        "source_commit": os.environ.get(
            "FACILITY_SOURCE_COMMIT", os.environ.get("GITHUB_SHA")
        ),
        "python": sys.version,
        "platform": platform.platform(),
        "artifacts": {
            n: {"sha256": sha(output / n), "bytes": (output / n).stat().st_size}
            for n in names
        },
        "source_sha256": {
            p.relative_to(ROOT).as_posix(): sha(p)
            for p in (ROOT / "facility_studio").rglob("*.py")
            if "__pycache__" not in p.parts
        },
        "authenticode_signed": False,
        "release_published": False,
    }
    (evidence / "Build_Manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest["artifacts"]), flush=True)


if __name__ == "__main__":
    main()
