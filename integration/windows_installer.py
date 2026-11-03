"""Per-user NSIS package; uninstall deletes only the shipped file manifest."""
import os
from pathlib import Path
import shutil
import subprocess


def quoted(value):
    return str(value).replace("$", "$$").replace('"', '$\\"')


def build(app, output, name, runner):
    compiler = shutil.which("makensis") or str(Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "NSIS/makensis.exe")
    if not Path(compiler).is_file():
        raise RuntimeError("Native build environment is missing NSIS.")
    setup = output / "Facility-Studio-5.7.2-Windows-x64-Setup.exe"
    files = sorted(p for p in app.rglob("*") if p.is_file())
    directories = sorted({p.parent.relative_to(app) for p in files}, key=lambda p: len(p.parts), reverse=True)
    lines = ["Unicode true", "!include MUI2.nsh", 'Name "Facility Studio 5.7.2 測試版"',
             f'OutFile "{quoted(setup)}"', 'InstallDir "$LOCALAPPDATA\\Facility Studio 測試版\\Application-5.7.2.1"',
             "RequestExecutionLevel user", "CRCCheck force", 'SetCompressor /SOLID lzma',
             'VIProductVersion "5.7.2.1"',
             'VIAddVersionKey /LANG=1028 "ProductName" "Facility Studio 測試版"',
             'VIAddVersionKey /LANG=1028 "FileVersion" "5.7.2.1"',
             'VIAddVersionKey /LANG=1028 "ProductVersion" "5.7.2-preview.1"',
             '!define MUI_WELCOMEPAGE_TITLE "Facility Studio 5.7.2 測試版"',
             '!define MUI_WELCOMEPAGE_TEXT "繁體中文、離線執行，提供廠務工程計算與設計報表。$\\r$\\n$\\r$\\n請使用新的空目錄。正式版、舊專案與使用者資料不會被替換。$\\r$\\n$\\r$\\n本測試版供操作及合成案例驗證，工程採用仍須依專案設計條件覆核。"',
             "!insertmacro MUI_PAGE_WELCOME", "!insertmacro MUI_PAGE_DIRECTORY", "!insertmacro MUI_PAGE_INSTFILES",
             "!insertmacro MUI_PAGE_FINISH", "!insertmacro MUI_UNPAGE_CONFIRM", "!insertmacro MUI_UNPAGE_INSTFILES",
             '!insertmacro MUI_LANGUAGE "TradChinese"', 'Section "安裝"',
             'IfFileExists "$INSTDIR\\*" used empty', 'used:', "IfSilent stop",
             'MessageBox MB_OK|MB_ICONSTOP "目的目錄已有檔案，為保留資料已停止安裝。請選新的空目錄。"',
             "stop:", "SetErrorLevel 2", "Abort", "empty:", "SetShellVarContext current"]
    for file in files:
        rel = file.relative_to(app)
        lines.extend([f'SetOutPath "$INSTDIR\\{quoted(rel.parent)}"', f'File "{quoted(file)}"'])
    lines.extend(['CreateDirectory "$SMPROGRAMS\\Facility Studio 測試版"',
                  f'CreateShortcut "$SMPROGRAMS\\Facility Studio 測試版\\5.7.2.lnk" "$INSTDIR\\{quoted(name)}.exe"',
                  'WriteUninstaller "$INSTDIR\\Uninstall.exe"',
                  'WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\FacilityStudioPreview572" "DisplayName" "Facility Studio 5.7.2 測試版"',
                  'WriteRegStr HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\FacilityStudioPreview572" "UninstallString" \'$\\"$INSTDIR\\Uninstall.exe$\\"\'',
                  "SectionEnd", 'Section "Uninstall"', "SetShellVarContext current"])
    for file in files:
        lines.append(f'Delete "$INSTDIR\\{quoted(file.relative_to(app))}"')
    lines.extend(f'RMDir "$INSTDIR\\{quoted(directory)}"' for directory in directories)
    lines.extend(['Delete "$INSTDIR\\Uninstall.exe"',
                  'Delete "$SMPROGRAMS\\Facility Studio 測試版\\5.7.2.lnk"',
                  'RMDir "$SMPROGRAMS\\Facility Studio 測試版"', 'RMDir "$INSTDIR"',
                  'DeleteRegKey HKCU "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\FacilityStudioPreview572"',
                  'DetailPrint "只移除本版已交付檔案；保留專案、偏好與額外檔案。"', "SectionEnd"])
    script = output / "fusion-installer.nsi"
    script.write_text("\n".join(lines), encoding="utf-8-sig")
    runner([compiler, "/V3", script], output / "evidence/NSIS_Build.txt")
    return setup


def verify(setup, output, name, runner, env):
    # NSIS /D must be the last argument, unquoted even when it contains spaces.
    install = output / "installer acceptance"
    result = subprocess.run(f'"{setup}" /S /D={install}', timeout=180)
    if result.returncode:
        raise RuntimeError(f"Installer exited {result.returncode}")
    runner([install / (name + ".exe"), "--fusion-self-test", output / "evidence/Installed_Acceptance.json"],
           output / "evidence/Installed_Acceptance.log", env=env, timeout=180)
    runner([install / (name + ".exe"), "--facilities-self-test", output / "evidence/Installed_Facilities_Acceptance.json"],
           output / "evidence/Installed_Facilities_Acceptance.log", env=env, timeout=180)
    marker = install / "user-added-file.txt"
    marker.write_text("preserve", encoding="utf-8")
    retry = subprocess.run(f'"{setup}" /S /D={install}', timeout=120)
    if retry.returncode != 2 or marker.read_text(encoding="utf-8") != "preserve":
        raise RuntimeError("Nonempty destination protection failed.")
    removed = subprocess.run(f'"{install / "Uninstall.exe"}" /S _?={install}', timeout=120)
    if removed.returncode or (install / (name + ".exe")).exists() or marker.read_text(encoding="utf-8") != "preserve":
        raise RuntimeError("Manifest-only uninstall or user-file preservation failed.")
    import json
    (output / "evidence/Installer_Protection.json").write_text(json.dumps(
        dict(passed=True, installation_exit_code=result.returncode,
             nonempty_destination_exit_code=retry.returncode, marker_preserved=True,
             uninstall_exit_code=removed.returncode, shipped_executable_removed=True,
             additional_user_file_preserved=True)), encoding="utf-8")
