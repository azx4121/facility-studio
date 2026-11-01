Unicode true
!include MUI2.nsh
Name "Facility Studio 工程驗證沙盒 5.6.1"
OutFile "${FEED_OUT}"
InstallDir "$LOCALAPPDATA\Facility Studio FEED Sandbox\Application-5.6.1.1"
RequestExecutionLevel user
CRCCheck force
SetCompress off
VIProductVersion "5.6.1.1"
VIAddVersionKey /LANG=1028 "ProductName" "Facility Studio 工程驗證沙盒"
VIAddVersionKey /LANG=1028 "FileDescription" "繁體中文離線安裝程式"
VIAddVersionKey /LANG=1028 "FileVersion" "5.6.1.1"
VIAddVersionKey /LANG=1028 "ProductVersion" "5.6.1-win-sandbox.1"
VIAddVersionKey /LANG=1028 "LegalCopyright" "Andy Huang and contributors"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Facility Studio 工程驗證沙盒"
!define MUI_WELCOMEPAGE_TEXT "繁體中文離線測試版。$\r$\n$\r$\n內含執行環境，不需另裝 Python 或連網。$\r$\n使用獨立安裝與資料目錄，不替換正式版。$\r$\n$\r$\n請選擇新的空目錄。工程驗證與實際設計簽核分開。"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "TradChinese"
Function GuardDestination
 IfFileExists "$INSTDIR\*" destination_used destination_ok
 destination_used:
 IfSilent destination_abort
 MessageBox MB_OK|MB_ICONSTOP "安裝位置已有檔案。為保留既有資料，請選擇新的空目錄。"
 destination_abort:
 SetErrorLevel 2
 Abort
 destination_ok:
FunctionEnd
Section "安裝"
 Call GuardDestination
 SetShellVarContext current
 SetOutPath "$INSTDIR"
 File "${FEED_EXE}"
 File "${FEED_ASSETS}\README_Windows_繁體中文.txt"
 File "${FEED_ASSETS}\LICENSE"
 File "${FEED_ASSETS}\LICENSE_GUIDE.md"
 File "${FEED_ASSETS}\LICENSE_LEGACY_MIT"
 File "${FEED_ASSETS}\THIRD_PARTY_NOTICES.md"
 File "${FEED_ASSETS}\THIRD_PARTY_LICENSES.txt"
 CreateDirectory "$SMPROGRAMS\Facility Studio 工程驗證沙盒"
 CreateShortcut "$SMPROGRAMS\Facility Studio 工程驗證沙盒\5.6.1.lnk" "$INSTDIR\Facility_Studio_FEED_Sandbox_5_6_1.exe"
 WriteUninstaller "$INSTDIR\Uninstall.exe"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FacilityStudioFeedSandbox561" "DisplayName" "Facility Studio 工程驗證沙盒 5.6.1"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FacilityStudioFeedSandbox561" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FacilityStudioFeedSandbox561" "InstallLocation" "$INSTDIR"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FacilityStudioFeedSandbox561" "DisplayVersion" "5.6.1.1"
 WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FacilityStudioFeedSandbox561" "NoModify" 1
 WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FacilityStudioFeedSandbox561" "NoRepair" 1
SectionEnd
Section "Uninstall"
 SetShellVarContext current
 Delete "$INSTDIR\Facility_Studio_FEED_Sandbox_5_6_1.exe"
 Delete "$INSTDIR\README_Windows_繁體中文.txt"
 Delete "$INSTDIR\LICENSE"
 Delete "$INSTDIR\LICENSE_GUIDE.md"
 Delete "$INSTDIR\LICENSE_LEGACY_MIT"
 Delete "$INSTDIR\THIRD_PARTY_NOTICES.md"
 Delete "$INSTDIR\THIRD_PARTY_LICENSES.txt"
 Delete "$INSTDIR\Uninstall.exe"
 Delete "$SMPROGRAMS\Facility Studio 工程驗證沙盒\5.6.1.lnk"
 RMDir "$SMPROGRAMS\Facility Studio 工程驗證沙盒"
 RMDir "$INSTDIR"
 DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FacilityStudioFeedSandbox561"
 DetailPrint "已移除本測試程式；保留使用者資料與正式版。"
SectionEnd
