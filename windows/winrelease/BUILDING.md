# Windows V5.6.0 離線發行

[目前下載與英文安裝](../../README.en.md#download-and-run) · [工程覆核與原生驗收](../../docs/2026-10-16-gemini-integration-review.md)

Developer build only: the V5.6.0 EXE bundles Python; publication requires both native jobs to pass. Normal users do not run pip or these build commands. ZIPs are built for native acceptance and developer diagnostics. The publisher uploads only the native-tested EXE and filtered public SHA256SUMS without changing internal acceptance files. The current publisher targets v5.6.0-win.6 and refuses to overwrite an existing published release. For a future release, update the builder, verifier, publisher and workflow version/output names together. See [distribution signing](../../docs/signing.en.md).

## win.6 修訂與封裝

win.6 修正 F01–F06：水管報告 ΣK、同迴路斷路器與線徑一致、W／kVA 來源帶入、夏冬 RCU／FCU 容量、泵浦單位切換、換算溢位與絕對零度邊界。`tests/audit_regressions.py --gui` 與封裝 EXE 的 `winrelease.selftest` 執行相同獨立數值及中英文操作驗證；舊版已錯存的電力來源顯示未達條件，需移除並用原始資料重新帶入。只有主案而無來源記錄的舊檔仍須自行核對原始 W／kVA。win.5 的照明 F07 回歸持續執行。

獨立快算共十項，包含新增的 `cleanroom`、`heat_loads`、`pumps`。CLI、GUI、雙語與原生 self-test 均涵蓋十項；設備表仍是原有七個系統。照明採型錄 U 與實際室指數 K，水管參考延伸至30吋。

使用當前 `windows/facility_studio`、資源與 `Default_Project.json`，驗證 schema 11 專案可移轉至 schema 12 且保留原氣流路徑及採用值，再執行來源工程、雙語、GUI 及兩個 Windows 環境的原生驗收。既有 win.3 資產與驗收紀錄保留。

當前線上 Setup 的 `windows/installer/payload`、`payload_sha256.json` 與 binary 須由 `windows/build_release.py` 成套更新，通過完整解壓與逐檔一致性檢查；這不等於離線 EXE 原生驗收。V5.5.4 歷史安裝器的固定 fixture 位於 `windows/tests/fixtures`，不可改寫。離線流程直接封裝當前來源。

win.6 covers ten independent calculators and seven equipment systems. Build current sources/resources/defaults, verify schema migration and all ten tools, then complete native acceptance. Preserve published releases and frozen historical installer fixtures. See the [engineering audit and release status](../../docs/2026-10-16-gemini-integration-review.md).

`entry.py` 為單檔 EXE 的視窗模式入口；日常使用不執行 pip、不尋找外部 Python、不下載元件。
主應用程式與完整計算邏輯仍使用 `windows/facility_studio`；不是另一套精簡計算版本。

在原生 Windows x64 使用官方 CPython 3.13.15，執行：

```powershell
python -m pip install --require-hashes --only-binary=:all: -r windows/winrelease/requirements.lock.txt
cd windows
python -m winrelease.build --output C:\FacilityStudioBuild
python -m winrelease.verify --assets C:\FacilityStudioBuild --output C:\FacilityStudioEvidence
```

連網只發生於開發者建置套件取得時。封裝17個套件版本及下載SHA256鎖定；
原始 CPython、第三方套件授權與專案現行／歷史授權資料一併保留。
發行輸出含獨立 EXE、完整 ZIP、SHA256SUMS；FY 圖示、版本資訊與設備範本均包含。

驗收腳本由開發者 Python 控制，啟動的 EXE 本身只使用內建執行環境。
驗收時 EXE 的 PATH 移除外部 Python，工作目錄為空白資料夾；
僅針對該 EXE 建立暫時對外封鎖防火牆規則，完成即刪除。
另使用 Python audit hook 禁止 socket 連線，檢查封裝資源、原生 Tk、
十種工具、七種設備分析、完整工作台八頁、原生繪圖、CLI報告與模板輸出。
相同檔案另在第二個 Windows runner 重複驗證，成功才允許 main 發布新 Release。
另在中文與空格的 EXE 路徑驗收；該額外路徑測試使用 socket audit hook，
不與 Windows 防火牆的程式路徑正規化混為一談。防火牆規則使用展開短路徑別名後的完整路徑。

本機一般使用者診斷 `Verify_on_Windows.cmd` 不需系統管理員、不更動防火牆、
不會上傳資料、不覆寫原有專案。CI防火牆設定只是開發者驗收。

原生runner為 Windows Server 2022／2025；不冒稱 Windows10／11實體電腦已完成驗收。
未取得商用程式碼簽章；Windows安全性、SmartScreen與企業管制需現場確認。
舊線上安裝器與歷史Release保留；它們不屬於新版離線啟動流程。



V5.6.0 win.6 / 十項快算、氣流路徑、工程帶入與設備總覽
簡易工具左下角持續顯示 DESIGNED BY ANDY HUANG ©。
簡易工具、完整工程工作台及單台空調箱的「新手教學」可開啟離線中英逐步教學。
完整 ZIP 的 Beginner_Tutorial/START_HERE.html 也可直接閱讀。
V5.6.0 可由完整工作台「開啟練習新案」建立副本；原廠選型與設備阻力等待補資料仍需補。
V5.6.0 retains author credit, offline walkthroughs, keypad checks, factory gases and retained velocity when reselecting the same gas. win.6 additionally validates airflow topology, upstream electrical units, manual photometric U and equipment summaries.
No additional Python installation or internet is needed for the tutorial.


Zero-demand gas velocity remains an inactive retained draft. The delivered EXE executes100 physically distinct,20-repeat calculation/persistence stress recipes. Source CI separately runs the independent100-cleanroom matrix. Publication requires both native Windows environments to pass.

win.6 splits core acceptance and the extended audit into separate EXE invocations (`--self-test` and `--audit-self-test`). Both retain the 210-second process budget and five-second GUI heartbeat. Every launch path must pass both: 318 core checks, 120 audit entry/UI checks and 2,073 independent numeric checks. `Delivery_Check.json` records both counts; raw reports are `Windows_Acceptance.json` and `Windows_Audit_Acceptance.json`. A timed-out test terminates only its own complete process tree before profile cleanup.
