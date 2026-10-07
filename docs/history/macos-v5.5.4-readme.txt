Facility Studio V5.5.4｜macOS 離線懶人包｜mac.1

先這樣開啟
1. 在 Mac 完整解壓縮 Facility_Studio_V5_5_4_macOS_OneClick.zip。
2. 雙擊其中的「Facility Studio.app」。
3. 若想安裝到使用者應用程式資料夾，雙擊 Install_on_Mac.command。
   安裝位置：~/Applications/Facility Studio V5.5.4.app。
   也可以自行把 App 拖進「應用程式」，或從解壓縮資料夾直接開啟。

不用另外安裝 Python，不用 Homebrew，不必輸入終端機指令。
程式所需的 Python、Tk、Matplotlib、NumPy、Pillow 已包含於 App。
計算、圖形、Excel／CSV 匯入與報告匯出均可離線使用。
目標：macOS 11.0 以上，Apple Silicon（M 系列）與 Intel x86_64。
同一份 App 包含兩種原生架構；這是封裝目標，尚未完成 Mac 實機驗收。

首次開啟可能需要系統允許
這份 App 使用 ad-hoc 完整性簽章，尚未取得 Apple Developer ID 與 Apple 公證。
若系統說無法驗證開發者，先嘗試開啟一次，再到：
「系統設定 → 隱私權與安全性 → 仍要打開」，確認開啟此 App。
公司管制的 Mac 可能需要 IT 允許。
若顯示檔案損毀或驗證失敗，請重新下載並執行 Verify_on_Mac.command 檢查。
本包不會自動關閉 Gatekeeper，也不會移除系統安全標記。
Apple 開啟指引：https://support.apple.com/en-us/102445

已保留 V5.5.4 的功能
• 首頁獨立工具：電力／NFB／線徑、方圓風管、CDA／特氣、照明照度。
• 更多工具：冷熱水、空氣狀態與即時空氣線圖、單位換算。
• Excel／CSV 設備表匯入：電力、PCW、CDA、N2、EXHAUST、DI、PV。
• 完整工程工作台、空調箱各段條件、預冷／預熱／再冷／再熱／加濕。
• 專案儲存／讀取／復原、進階參數、互鎖與資料檢核、報告及圖形匯出。
• 原 FY 圖示與通用版名稱。
• 已包含公開設備範本；也能在「設備表匯入」視窗直接匯出新範本。

本次 Mac 調整
• App 原生啟動器在主程序載入內含 Python，維持 Mac 的 Dock 與主執行緒。
• Python 與第三方套件依 CPU 選擇；不使用電腦原本的 Python 環境。
• 修正觸控板捲動幅度；零幅度事件不會讓頁面自行移動。
• 下拉選單的滾動不會帶動外面的表單。
• 中文介面優先使用 Mac 的 PingFang TC／Heiti TC 字體。
• 主案與單機支援 Command-S；主案支援 Command-O；Command-Return 執行計算。
• Mac 的「結束」選單走原有未儲存專案的處理流程。
• 專案復原與記錄改用 Mac 的使用者資料位置，不寫入 App 內。
• 計算公式、工程資料表、既有輸入與報告內容沿用 V5.5.4。

設備表範本
Facility_Studio_V5_5_4_Equipment_Template.xlsx 有說明與七個系統工作表。
黃色欄位填設備資料；第一列範例預設未啟用，不會算入總量。
完成後在「設備表匯入」選 Excel 或 CSV，查看總需求及各群組分析。
插座數是點位數；不要把設備 kW 再重複乘以插座數。
不同電壓與相別、不同排氣種類會分開分析。
這是初估與方案比較工具；既有報告會列出需要現場／原廠資料覆核的項目。

驗證範圍
已執行：52 組原工程情境／1247 項獨立檢查；20 組延伸數值條件／93 項；
305 項互鎖核心檢查；42 組簡易工具情境／375 項；49 組設備匯入等條件／646 項；
244 項實際 Tk 介面操作；37 項 Mac 介面與路徑相容性檢查。
Tk 介面測試在 Linux/Xvfb 執行；Mac 平台選擇條件以模擬方式測試。
封裝另檢查官方 CPython 與 PyPI 檔案 SHA256、Mach-O 架構、動態函式庫路徑、
程式簽章頁雜湊與資源封條、ZIP 內容／執行權限／相對連結。
所有可執行相依檔案均包含於 App，系統函式庫由 macOS 提供。

仍待完成：Apple 原生 codesign 驗證、Mac Finder 首次開啟、實體數字鍵盤、
觸控板、Retina 顯示，以及 Mac 版 Excel 實際填表／儲存／匯入的驗收。
無法把上述 Linux 及靜態檢查視為已在 Mac 執行成功。

選用的 Mac 實機驗證
雙擊 Verify_on_Mac.command：
先使用 Apple codesign 深度檢查 App，再執行原生 CPU、Tk Aqua、Matplotlib 線圖、
七種簡易工具、完整工作台、Excel 範本與設備匯入等測試。
結果存於 ~/Library/Logs/Facility_Studio_V5_5/：
Mac_Acceptance.json、Mac_Signature_Check.txt、Mac_SelfTest_Console.txt。
只有該 Mac 實際跑過，才會產生實機驗收紀錄。
驗證工具不會上傳您的資料，也不會更動您既有的工程專案。

資料與錯誤記錄
專案復原：~/Library/Application Support/Facility_Studio_V5_5/Recovery/
介面錯誤：~/Library/Application Support/Facility_Studio_V5_5/error.log
啟動記錄：~/Library/Logs/Facility_Studio_V5_5/startup.log
啟動失敗：~/Library/Logs/Facility_Studio_V5_5/startup-error.log
繪圖快取：~/Library/Caches/Facility_Studio_V5_5/matplotlib/
移動或更新 App 不會刪除這些使用者資料。
再次安裝時，原 App 會保留為 Backup；請先關閉正在執行的舊版。

給維護者
Source_and_Verification.zip 包含 Python 原始碼、C 啟動器、封裝／檢查程式與證據。
Python 入口為 Facility_Studio_V5_5.py，需與 facility_studio 資料夾一起使用。
macos/prepare_runtime.py 會依官方雜湊抓取並抽出 CPython framework 與指定架構套件，
並以 Zig 編譯雙架構啟動器；建置用途需 Python、Zig 0.16.0、Pillow 及 rcodesign 0.29.0。
macos/build_bundle.py 建立 App；macos/verify_bundle.py 重建頁面與資源雜湊。
詳細建置方法見 macos/BUILDING.md。一般使用者不用執行建置。
rcodesign 0.29.0 的 verify 指令對 ad-hoc 空 CMS 有已知解析警告；本次另以獨立
頁面／資源雜湊核對，Apple codesign 的真正驗證仍由 Mac 實機工具執行。

第三方授權與來源
CPython、Tcl／Tk 與各套件的原始授權文件保留在 App 相應位置。
CPython：https://www.python.org/downloads/release/python-31315/
Mac Python 說明：https://docs.python.org/3/using/mac.html
Py_BytesMain：https://docs.python.org/3.13/c-api/init.html#c.Py_BytesMain
Apple Gatekeeper：https://support.apple.com/en-us/102445
rcodesign：https://gregoryszorc.com/docs/apple-codesign/stable/apple_codesign_rcodesign_signing.html
