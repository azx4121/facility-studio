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

[Engineering dashboard source checks](../.github/workflows/engineering-dashboard-checks.yml) 在 Linux / Python 3.13 上以兩個獨立工作分別載入 Windows 與 macOS 來源，執行上述兩支腳本，以及既有 `simple_features`、`regression`、`v560_features`、`v557_inactive`、`v558_review`、`v559_resilience`、`bilingual` 和 `security_checks`。Windows 來源工作另執行 `installer_integrity_checks.py` 的 22 項歷史及當前完整性案例；這是跨平台可重現的檔案完整性檢查，不會啟動 Windows 安裝程式。工作只讀取倉庫、執行來源檢查及保留本次 JSON／HTML／逐項日誌，不建置或發布 EXE／DMG。工程與報表腳本不建立視窗，另外的 Tk smoke 在 Xvfb 與 Noto CJK 字型環境執行；來源測試不需要額外的 pip 套件。兩份既有 requirements 鎖檔使用平台專屬 wheel 雜湊，保留給原生建置，不能直接當成 Linux 依賴清單。

### schema 12 與歷史資料

工程儀表板修訂沿用應用程式版本 `5.6.0`，主案儲存 schema 為 **12**。完整的舊版 schema 11 專案經 `migrate_project()` 建立新副本，保留原輸入與來源紀錄；預設延續「獨立 FFU 循環、MAU 直接入室」與門縫孔口洩漏計算，不把原有 ACH 默默改成另加 OA。只有明確選擇 MAU 入靜壓箱拓樸後，才依「總送風已含 OA」或「室內基本循環另加 OA」分配 FFU 與 DCC 風量。缺欄位或來源不完整的舊案應明確拒絕移轉，不能自動補成一份看似完整的工程案。

當前線上 Setup 的 `windows/installer/payload/`、manifest 與 binary 由 `windows/build_release.py` 成套產生，完整解出全部成員並逐檔核對。V5.5.4 歷史安裝器另外使用固定 tag `v5.5.4-win.1`／不可變提交 `6ada894438805a00c8c795f63451916b1d759a84` 的 [fixture ZIP 與雜湊紀錄](../windows/tests/fixtures/README.md)，其62個成員與歷史測試不可改寫。完整性測試共22項，包含21項原歷史內容／破壞檢查及新增當前完整payload檢查。預期歷史資料取自固定提交，沒有從受測EXE反推；測試不下載、補檔或重建來源。現行離線建置直接使用 `windows/facility_studio/`，包含十項 CLI／GUI 快算、當前資源與 `Default_Project.json`。新修訂須完成來源工程、移轉、GUI及原生驗收，不能用線上Setup的CRC／解壓通過代替離線EXE執行。工程取捨與實測見[本次覆核](2026-10-16-gemini-integration-review.md)。

## 維護與發布原則

以[本版交付紀錄](2026-10-16-gemini-integration-review.md)核對測試的提交、公開檔名與 SHA256。新程式修訂必須通過原生流程再發布；不要覆寫已發布的二進位檔、移動既有 tag 或強制推送覆蓋歷史。

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

The new [source-check workflow](../.github/workflows/engineering-dashboard-checks.yml) runs both source trees on Linux / Python 3.13, including the engineering / report checks, eight established regression suites, and the Tk source smoke under Xvfb with Noto CJK fonts. The Windows source job additionally runs the 22 historical/current installer integrity and corruption cases without executing an installer. Its artifacts contain fresh JSON, HTML examples and per-suite logs. It neither publishes software nor substitutes for native Windows or macOS execution, DPI, keyboard, printing or distribution checks.

The application remains version `5.6.0`; the main-project schema is **12**. Migration copies complete schema11 projects and retains independent FFU recirculation, direct MAU room supply and opening-based leakage. Plenum topology and its airflow basis require explicit selection. Incomplete historical projects remain rejected. Current online Setup staging, manifest and binary are regenerated together by `windows/build_release.py` and checked by full extraction and per-file hashes. The separate [V5.5.4 fixture ZIP and pinned hashes](../windows/tests/fixtures/README.md) from tag `v5.5.4-win.1` / commit `6ada894438805a00c8c795f63451916b1d759a84` preserve the62 historical members. The22 integrity checks include21 original historical content/corruption guards and the full current payload. Tests download and repair nothing. The offline builder reads current sources, resources and defaults and validates all ten tools. A new revision requires migration, engineering, GUI and native execution; online archive integrity is not offline executable acceptance. See the [integration review](2026-10-16-gemini-integration-review.md).

Current [delivery evidence](2026-10-16-gemini-integration-review.md) identifies tested commits and binary SHA256. Source checks are separate from native acceptance. Publish a new tested revision without replacing released binaries, moving tags or rewriting history. Documentation and release-body edits preserve binary identity and release status.

Retain **DESIGNED BY ANDY HUANG ©**, current licensing and third-party notices. Earlier MIT grants remain valid for those historical editions.


## 2026-10-16 整合覆核重現

先執行前述既有回歸，再分開檢查兩份來源：

```sh
python tools/verify_gemini_review.py --platform windows --output independent-windows.json
python tools/verify_engineering_dashboard.py --platform windows --output boundaries-windows.json
python tools/verify_dashboard_reports.py --platform windows --output reports-windows.json
python tools/verify_100x_all_fields_and_reports.py --platform windows --iterations 100 --output fields-windows.json
xvfb-run -a python tools/verify_dashboard_gui.py --platform windows --output gui-windows.json
python tools/test_public_downloads.py
```

macOS 來源將 `--platform windows` 改為 `--platform macos`。原生平台直接執行 GUI 指令，不使用 Xvfb。100 種潔淨室參考式涵蓋 schema 12 的顯式 FFU 路徑；凍結案例可直接使用 `docs/evidence/2026-10-16-gemini-review/cleanroom100-inputs.json.gz`，重算 20 次，不覆寫清單。

照明改為型錄 U 配合實際幾何 K；不以 `K/(K+0.59)` 當光度模擬。舊候選 schema 12 自動 U 模式會移轉到型錄模式並保留手填 U 草稿，須重新確認。電力工具的 kW/W 為輸入、HP/PS 為軸輸出；上游帶入一律明填 kW。管路參考至 30 吋。[完整覆核](2026-10-16-gemini-integration-review.md)

Installer manifests compare exact bytes. Repository attributes preserve authored line endings on every OS; keep Windows CMD files in CRLF and do not normalize an existing frozen payload after generating its SHA256 manifest.

## Windows win.7：工程稽核與來源復原回歸

```sh
python windows/tests/audit_regressions.py --output audit-numeric.json
python windows/tests/audit_regressions.py --gui --output audit-source-ui.json
```

數值 2,182 項；真實 Tk 中英文操作 140 項，合計 2,322。涵蓋 F01–F06、功率單位／逐盤 PF 與效率快照、夏冬末端容量、轉換溢位、手動數值／單位成組保留、多次帶入與移除、存檔重開及舊 v2 空彙整記錄。F07 另有 2,500 數值與 71 來源 GUI 檢查。

封裝 EXE 分開執行 `--self-test` 與 `--audit-self-test`，各維持 210 秒程序上限與五秒 GUI 心跳；每個啟動路徑須通過 318 核心、140 延伸入口／介面及 2,182 獨立數值檢查。逾時僅終止該測試程序樹，不放寬限制。每個原生 Windows 主機重驗獨立 EXE、ZIP 解壓及中文空格路徑，發布須兩主機全通過。詳見[當前驗收](2026-10-18-windows-audit-six.md)。macOS 應用來源未改；其 ledger v1 讀取器無法讀 Windows 新整案的 ledger v2，不能僅憑主案 schema 12 宣稱雙向相容。

English: audit regression acceptance has 2,182 numeric assertions and 140 real-widget source checks (2,322 total). Frozen acceptance runs 318 core checks and 140 extended entry/UI checks in separate bounded processes, plus the same 2,182 assertions. Both native hosts must pass all three launch paths before publication. Source success and online Setup extraction do not substitute for delivered EXE execution. mac.6's ledger v1 reader cannot open v2 workspaces; its application source is unchanged.
