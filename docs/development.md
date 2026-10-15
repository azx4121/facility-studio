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

## 工程儀表板的跨平台來源驗證

新增的工程與報表檢查共用同一份腳本，以 `--platform` 選擇來源目錄；每個平台請分開啟動 Python 程序。這個選項只決定匯入哪一份來源，執行主機仍是實際的 Windows、macOS 或 Linux。JSON 紀錄會分別寫出 `source_platform`、`host_os`、Python 版本與專案 schema 版本。

```sh
python tools/verify_engineering_dashboard.py --platform windows --output work/checks/windows-boundaries.json
python tools/verify_dashboard_reports.py --platform windows --output work/checks/windows-reports.json --artifacts-dir work/checks/windows-html
python tools/verify_engineering_dashboard.py --platform macos --output work/checks/macos-boundaries.json
python tools/verify_dashboard_reports.py --platform macos --output work/checks/macos-reports.json --artifacts-dir work/checks/macos-html
```

`--output` 與 `--artifacts-dir` 都是選填；未指定時，兩支腳本只輸出檢查摘要。另有使用真實 Tk 視窗的來源 smoke；需使用含 Tk 的 Python 與可用顯示服務，每次只跑一個平台：

```sh
python tools/verify_dashboard_gui.py --platform windows --output work/checks/windows-gui-source.json
python tools/verify_dashboard_gui.py --platform macos --output work/checks/macos-gui-source.json
# Linux CI／開發主機另需 Xvfb、xauth 及 CJK 字型；下列仍是 Linux 上的來源測試。
xvfb-run -a -s "-screen 0 1920x1440x24" python tools/verify_dashboard_gui.py --platform windows --output work/checks/linux-windows-source-gui.json
```

GUI smoke 檢查實際欄位顯示／停用狀態、十種工具的 KPI 與表格、上游帶入及過期阻擋、行內錯誤、Enter 重算、寬窄版面、Tk 125%／150% 邏輯縮放與 SCADA 縮放。測試不修改 OS DPI，未擷取螢幕，也不使用 Pillow；其 JSON 明確標示 `native_binary_acceptance: false`，不能代替 Windows EXE 或 macOS App 原生驗收。工程檢查獨立重建零壓差、洩漏平方根關係、FFU 氣流路徑、MAU/DCC 熱量分工、泵軸功率與輸入電力、效率電流、風管當量直徑及粗糙度單位；並核對上游帶入、重複設備來源與歷史專案移轉。報表檢查涵蓋七大設備總覽、千分位、缺值保留、不完整主案拒絕匯出、中英數字一致、HTML 動態內容跳脫與計算結果不被改寫。產生的 HTML 是檢查樣例，沒有宣稱已完成瀏覽器視覺或原生列印驗收。

[Engineering dashboard source checks](../.github/workflows/engineering-dashboard-checks.yml) 在 Linux / Python 3.13 上以兩個獨立工作分別載入 Windows 與 macOS 來源，執行上述兩支腳本，以及既有 `simple_features`、`regression`、`v560_features`、`v557_inactive`、`v558_review`、`v559_resilience`、`bilingual` 和 `security_checks`。Windows 來源工作另執行 `installer_integrity_checks.py` 的 21 組歷史安裝程式內容／破壞案例；這是跨平台可重現的檔案完整性檢查，不會啟動 Windows 安裝程式。工作只讀取倉庫、執行來源檢查及保留本次 JSON／HTML／逐項日誌，不建置或發布 EXE／DMG。工程與報表腳本不建立視窗，另外的 Tk smoke 在 Xvfb 與 Noto CJK 字型環境執行；來源測試不需要額外的 pip 套件。兩份既有 requirements 鎖檔使用平台專屬 wheel 雜湊，保留給原生建置，不能直接當成 Linux 依賴清單。

### schema 12 與歷史資料

工程儀表板修訂沿用應用程式版本 `5.6.0`，主案儲存 schema 為 **12**。完整的舊版 schema 11 專案經 `migrate_project()` 建立新副本，保留原輸入與來源紀錄；預設延續「獨立 FFU 循環、MAU 直接入室」與門縫孔口洩漏計算，不把原有 ACH 默默改成另加 OA。只有明確選擇 MAU 入靜壓箱拓樸後，才依「總送風已含 OA」或「室內基本循環另加 OA」分配 FFU 與 DCC 風量。缺欄位或來源不完整的舊案應明確拒絕移轉，不能自動補成一份看似完整的工程案。

`windows/installer/payload/`、相關 manifest 與已交付的安裝程式均保留原樣，不能假設目前 payload 與每個歷史 EXE 是同一版。V5.5.4 安裝程式完整性測試使用固定歷史 tag `v5.5.4-win.1`／不可變提交 `6ada894438805a00c8c795f63451916b1d759a84` 對應的離線 [fixture ZIP 與雜湊紀錄](../windows/tests/fixtures/README.md)，核對該版二進位內的全部 62 個成員，並保留原本 21 組完整性／破壞測試。預期資料取自該提交，沒有從受測 EXE 反推；共用 loader 固定核對 fixture 與二進位 SHA256，不從網路即時下載內容，也不改寫目前 payload 或二進位。修改目前來源時不要同步覆蓋該快照，也不要把當前來源測試通過當成舊 EXE 已經更新。現行 Windows 原生建置從 `windows/facility_studio/` 取來源；製作新安裝包時，須一併核對 build／verifier／publisher／workflow 的新資產命名，打包目前的 `Default_Project.json`，並重新執行移轉、工程、GUI 與原生驗收。不要對歷史 V5.5.4 快照執行 `windows/build_release.py` 的 `stage_payload`，除非另外建立新的 installer 修訂並保存原快照。舊 winrelease BUILDING 中的「七種工具」是原 win.3 驗收範圍，目前來源的十種工具應另外驗證。新的原生安裝包應沿用各平台建置與原生驗證流程，以新的資產身分交付。工程取捨與這次實際執行紀錄見[工程與儀表板審核](2026-10-15-engineering-dashboard-audit.md)。

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

The engineering dashboard adds two shared source-test commands: `tools/verify_engineering_dashboard.py --platform windows|macos` and `tools/verify_dashboard_reports.py --platform windows|macos`. Replace the platform placeholder with one concrete value and use a separate Python process per source tree. Both accept an optional `--output` JSON path; the report checker also accepts `--artifacts-dir` for reproducible HTML examples. Evidence records the selected source tree separately from the actual host OS. These source checks use the standard library; importing existing desktop modules additionally requires Tk, without opening a GUI. Native build requirements remain platform-specific and their wheel hashes are not a Linux requirements set.

For a real-widget source smoke, run `python tools/verify_dashboard_gui.py --platform windows --output work/checks/windows-gui-source.json`, then use a separate process with `--platform macos`. It requires a Tk-enabled Python and an available display. On Linux use `xvfb-run -a -s "-screen 0 1920x1440x24"` before that command and install Xvfb, xauth and CJK fonts. The smoke covers actual equipment-field visibility, the ten tool dashboards, transfers and stale-result blocking, inline errors, Enter calculation, responsive layout, logical Tk scaling and SCADA resizing. It uses no Pillow or screenshots, changes no OS DPI setting, and records `native_binary_acceptance: false`.

The new [source-check workflow](../.github/workflows/engineering-dashboard-checks.yml) runs both source trees on Linux / Python 3.13, including the engineering / report checks, eight established regression suites, and the Tk source smoke under Xvfb with Noto CJK fonts. The Windows source job additionally runs the 21 historical installer integrity / corruption cases without executing an installer. Its artifacts contain fresh JSON, HTML examples and per-suite logs. It neither publishes software nor substitutes for native Windows or macOS execution, DPI, keyboard, printing or distribution checks.

The application remains version `5.6.0`; the main-project storage schema is **12**. Migration copies complete schema 11 projects without mutating the original and preserves independent FFU recirculation with MAU air supplied directly to the room, plus the existing opening-based leakage method. The plenum topology and its total-versus-recirculation airflow basis require explicit selection. Incomplete historical projects remain rejected. Preserve the existing `windows/installer/payload/`, manifest and delivered binaries; do not assume that the current payload matches every historical EXE. V5.5.4 installer checks use an [offline fixture ZIP and pinned hashes](../windows/tests/fixtures/README.md) from historical tag `v5.5.4-win.1` / immutable commit `6ada894438805a00c8c795f63451916b1d759a84`, reconstructing its 62 members for the original 21 integrity / corruption cases. Expected bytes come from that commit, not the executable under test; the shared loader verifies both archive and binary SHA256. The test downloads nothing and does not rewrite the current payload or binary. The current Windows native builder reads `windows/facility_studio/`. A new release must review build / verifier / publisher / workflow asset names, package the current `Default_Project.json`, and rerun migration, engineering, GUI and native acceptance. Do not run `windows/build_release.py` staging against the historical V5.5.4 payload unless creating a separate installer revision while retaining its prior snapshot. The seven-tool scope in historical win.3 build instructions is distinct from the ten current source tools. New native packages require their own build and acceptance evidence. See the [engineering dashboard audit](2026-10-15-engineering-dashboard-audit.md).

Current [delivery evidence](2026-10-13-v5.6-audit-stress.md) identifies tested commits and binary SHA256. Source checks are separate from native acceptance. Publish a new tested revision without replacing released binaries, moving tags or rewriting history. Documentation and release-body edits preserve binary identity and release status.

Retain **DESIGNED BY ANDY HUANG ©**, current licensing and third-party notices. Earlier MIT grants remain valid for those historical editions.
