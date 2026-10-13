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
python windows/tests/v559_resilience.py
python windows/tests/v5510_keypad.py
python windows/tests/v560_features.py
python windows/tests/maintenance_checks.py
python windows/tests/security_checks.py
python windows/tests/bilingual.py
python docs/tutorial/verify_tutorial.py --platform windows --output tutorial-windows.json
python tools/verify_use_cases.py --platform windows --output use-cases-windows.json
```

macOS 來源把 `windows/` 改為 `macos/`，兩個 `--platform` 改為 `macos`；需要時使用 `python3`。測試會更新來源平台 `evidence/` 的紀錄。部分測試匯入 Tk；實際 GUI 測試另需可用的顯示服務與建置文件指定的套件。

案例輸入及命令列例子見[工具指南的重現段落](guides/README.md#可重現的輸入與結果)。來源通過不能代替 EXE／App 的原生驗收。

完整報告 `report()` 需要完整主案結果；部分空調結果會回傳 `ValidationError(code="incomplete_result")`。C1 超飽和使用 `code="supersaturated_air"` 與對應的 `field_name`，可供介面定位。

要重現 100 組無塵室的物理輸入與夏冬壓力測試，可使用下列命令。保留的原始案例與重新產生的文件需分開識別：產生器沿用原來 100 組物理條件，版本資訊及預期錯誤欄位按目前來源更新，所以整份 JSON 雜湊不等於歷史文件。V5.6 來源紀錄使用保留的原始案例，移轉後再進行停用欄位突變與重複計算；見[本版擴充與來源證據](2026-10-12-v5.6-expansion.md#驗證紀錄)。這些來源紀錄不能代替已發布 EXE／DMG 的原生驗收，也不能代表本次重新執行的結果。

```sh
python tools/cleanroom100_stress.py --source . --platform windows --manifest cleanroom100.json --generate
python tools/cleanroom100_stress.py --source . --platform windows --manifest cleanroom100.json --output cleanroom100-windows.json --repeat 20
python tools/cleanroom100_stress.py --source . --platform macos --manifest cleanroom100.json --output cleanroom100-macos.json --repeat 20
```

## 維護與發布原則

以[本版交付紀錄](2026-10-13-v5.6-audit-stress.md)核對測試的提交、公開檔名與 SHA256。新程式修訂必須通過原生流程再發布；不要覆寫已發布的二進位檔、移動既有 tag 或強制推送覆蓋歷史。

文件與 Release 敘述可以獨立修正。Release 文案維護只更新文字，不重新打包，並核對原有 tag、版本狀態與資產身分。歷史數字及截圖仍按原版本保存。

保留 **DESIGNED BY ANDY HUANG ©**、[現行 LICENSE](../LICENSE) 及[第三方授權](../THIRD_PARTY_NOTICES.md)。現行授權為 PolyForm Noncommercial 加公司內部使用附加許可；[歷史 MIT](../LICENSE_LEGACY_MIT) 權利保留。

<a id="english"></a>
## English

This page is for source development, reproducible calculations and packaging. Bundled EXE/DMG users do not need these commands.

Source lives in `windows/` and `macos/`, with platform-specific navigation, scrolling, fonts and launch behavior. Retain those differences. Launch `Facility_Studio_V5_5.py` with its sibling package/resources. Follow the linked platform BUILDING documents for Python, dependencies and native packaging.

Run the commands above from the repository root. For macOS source, change `windows/` to `macos/` and both `--platform windows` options to `--platform macos`; use `python3` if required. Tests can update evidence files. GUI tests additionally require a display and the documented dependencies.

The full-report API requires a complete main-project result and rejects isolated HVAC results with `incomplete_result`. C1 supersaturation uses `supersaturated_air` and the relevant input field. The cleanroom generator retains the 100 original physical inputs; generated metadata and expected error fields reflect the current source, so its complete JSON hash differs from historical input files. The recorded V5.6 source stress checks migrate the retained original projects before inactive-field mutations and repeated calculations; see the [feature and source evidence](2026-10-12-v5.6-expansion.md#english). Historical source evidence is separate from a fresh rerun and from native acceptance of published binaries. Run v5510_keypad.py for key identity and insertion behavior, and v560_features.py for large pipes, gas choices and direct navigation; native self-tests additionally exercise delivered widgets and Windows OS messages.

Current [delivery evidence](2026-10-13-v5.6-audit-stress.md) identifies tested commits and binary SHA256. Source checks are separate from native acceptance. Publish a new tested revision without replacing released binaries, moving tags or rewriting history. Documentation and release-body edits preserve binary identity and release status.

Retain **DESIGNED BY ANDY HUANG ©**, current licensing and third-party notices. Earlier MIT grants remain valid for those historical editions.
