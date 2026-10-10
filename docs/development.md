# 開發、建置與測試

[首頁](../README.md) · [文件中心](README.md) · [English](#english)

本頁供閱讀原始碼、重現計算或建置套件的人使用。一般使用者直接下載 EXE／DMG，不需要執行以下指令。

## 原始碼位置

Windows 在 [windows](../windows/)，macOS 在 [macos](../macos/)。兩者各自保留平台導覽、捲動、字型與啟動實作；不要把 Windows 的整份介面檔覆蓋到 macOS。

啟動入口為各平台的 `Facility_Studio_V5_5.py`，需保留同層 `facility_studio` 與資源。原生封裝步驟與依賴以 [Windows BUILDING](../windows/winrelease/BUILDING.md) 及 [macOS BUILDING](../macos/macos/BUILDING.md) 為準。

## 重現數值檢查

在倉庫根目錄，以符合建置文件的 Python 執行：

```sh
python windows/tests/regression.py
python windows/tests/v55_features.py
python windows/tests/v552_core.py
python windows/tests/simple_features.py
python windows/tests/v554_features.py
python windows/tests/v556_features.py
python windows/tests/v557_inactive.py
python windows/tests/v558_review.py
python windows/tests/maintenance_checks.py
python windows/tests/security_checks.py
python windows/tests/bilingual.py
python docs/tutorial/verify_tutorial.py --platform windows --output tutorial-windows.json
python tools/verify_use_cases.py --platform windows --output use-cases-windows.json
```

macOS 來源把 `windows/` 改為 `macos/`，兩個 `--platform` 改為 `macos`；需要時使用 `python3`。測試會更新來源平台 `evidence/` 的紀錄。部分測試匯入 Tk；實際 GUI 測試另需可用的顯示服務與建置文件指定的套件。

案例輸入及命令列例子見[工具指南的重現段落](guides/README.md#可重現的輸入與結果)。來源通過不能代替 EXE／App 的原生驗收。

## 維護與發布原則

以[本版交付紀錄](2026-10-10-v5.5.8-native.md)核對測試的提交、公開檔名與 SHA256。新程式修訂必須通過原生流程再發布；不要覆寫已發布的二進位檔、移動既有 tag 或強制推送覆蓋歷史。

文件與 Release 敘述可以獨立修正。Release 文案維護只更新文字，不重新打包，並核對原有 tag、版本狀態與資產身分。歷史數字及截圖仍按原版本保存。

保留 **DESIGNED BY ANDY HUANG ©**、[現行 LICENSE](../LICENSE) 及[第三方授權](../THIRD_PARTY_NOTICES.md)。現行授權為 PolyForm Noncommercial 加公司內部使用附加許可；[歷史 MIT](../LICENSE_LEGACY_MIT) 權利保留。

<a id="english"></a>
## English

This page is for source development, reproducible calculations and packaging. Bundled EXE/DMG users do not need these commands.

Source lives in `windows/` and `macos/`, with platform-specific navigation, scrolling, fonts and launch behavior. Retain those differences. Launch `Facility_Studio_V5_5.py` with its sibling package/resources. Follow the linked platform BUILDING documents for Python, dependencies and native packaging.

Run the commands above from the repository root. For macOS source, change `windows/` to `macos/` and both `--platform windows` options to `--platform macos`; use `python3` if required. Tests can update evidence files. GUI tests additionally require a display and the documented dependencies.

Current [delivery evidence](2026-10-10-v5.5.8-native.md) identifies tested commits and binary SHA256. Source checks are separate from native acceptance. Publish a new tested revision without replacing released binaries, moving tags or rewriting history. Documentation and release-body edits preserve binary identity and release status.

Retain **DESIGNED BY ANDY HUANG ©**, current licensing and third-party notices. Earlier MIT grants remain valid for those historical editions.
