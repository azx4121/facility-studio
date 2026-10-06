Unicode true
!include MUI2.nsh
Name "廠務簡易工具 V5.5.4"
!ifndef FS_SETUP_OUTPUT
 !define FS_SETUP_OUTPUT "Facility_Studio_V5_5_4_Setup.exe"
!endif
OutFile "${FS_SETUP_OUTPUT}"
VIProductVersion "5.5.4.0"
VIAddVersionKey /LANG=1028 "ProductName" "廠務簡易工具"
VIAddVersionKey /LANG=1028 "FileDescription" "Facility Studio V5.5.4 Online Setup"
VIAddVersionKey /LANG=1028 "FileVersion" "5.5.4.0"
VIAddVersionKey /LANG=1028 "ProductVersion" "5.5.4"
VIAddVersionKey /LANG=1028 "LegalCopyright" "Facility Studio"
InstallDir "$LOCALAPPDATA\Facility_Studio_V5_5"
RequestExecutionLevel user
CRCCheck force
SetCompressor /SOLID lzma
Icon "facility_studio/resources/app.ico"
UninstallIcon "facility_studio/resources/app.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "廠務簡易工具 V5.5.4"
!define MUI_WELCOMEPAGE_TEXT "通用版・線上安裝程式$\r$\n$\r$\n安裝時會下載官方 Python 與繪圖套件，並在您的電腦建立程式及桌面捷徑。首次需連網，可能需數分鐘。$\r$\n$\r$\n支援 Windows 10/11 Intel/AMD 64 位元。$\r$\n本工具供工程初估；請依檢核結果補齊設計與原廠選型資料。"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "TradChinese"
Function .onInit
 System::Call 'kernel32::CreateMutexW(p 0, i 0, w "FacilityStudio55Setup") p .r0 ?e'
 Pop $1
 StrCmp $1 183 0 +3
 MessageBox MB_OK "另一個安裝程序正在執行。"
 Abort
FunctionEnd
Section "安裝"
 SetShellVarContext current
 RMDir /r "$INSTDIR\installer\payload"
 SetOutPath "$INSTDIR\installer"
 File /r /x "__pycache__" /x "*.pyc" "installer/*"
 DetailPrint "正在下載、建立程式與驗證，請保留開啟的進度視窗。"
 ClearErrors
 ExecWait '"$SYSDIR\cmd.exe" /D /C ""$INSTDIR\installer\START.cmd" /installer"' $0
 IfErrors install_failed
 StrCmp $0 0 install_ok
 install_failed:
 MessageBox MB_OK|MB_ICONSTOP "安裝未完成。請查看 $INSTDIR\Setup.log 或 bootstrap\Python_Setup.log。原有專案不會覆寫。"
 SetErrorLevel 1
 Abort
 install_ok:
 WriteUninstaller "$INSTDIR\Uninstall.exe"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FacilityStudio55" "DisplayName" "廠務簡易工具 V5.5.4"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FacilityStudio55" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FacilityStudio55" "DisplayVersion" "5.5.4"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FacilityStudio55" "DisplayIcon" "$INSTDIR\installer\payload\facility_studio\resources\app.ico"
 WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FacilityStudio55" "NoModify" 1
 WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FacilityStudio55" "NoRepair" 1
SectionEnd
Section "Uninstall"
 SetShellVarContext current
 Delete "$DESKTOP\Facility Studio V5.5.lnk"
 RMDir /r "$INSTDIR\installer"
 RMDir /r "$INSTDIR\build_environment"
 RMDir /r "$INSTDIR\releases"
 RMDir /r "$INSTDIR\bootstrap"
 Delete "$INSTDIR\Uninstall.exe"
 DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\FacilityStudio55"
 DetailPrint "保留 Projects、Examples 及記錄檔；共用 Python 不移除。"
SectionEnd
