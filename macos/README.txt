Facility Studio V5.5.8 source revision

This source fixes standalone AHU draft save/reopen and adds defensive bypass-state validation.
Public binaries remain V5.5.7 until V5.5.8 native Actions and publication succeed.
Use the root README for currently published downloads; older notes below are retained as history.

--- Historical notes ---

Facility Studio V5.5.6｜macOS 中英雙語版 mac.1

V5.5.6 操作修訂
• 完整工作台預設聚焦空調與熱負荷；各個小工具可獨立使用。
• 「開啟練習新案」建立可修改副本；「另存新檔」與「複製為新方案」用途分開。
• 已採用的預設條件與隱藏的自訂值會顯示摘要；修改或錯誤時保留待重算結果，不能匯出。
• 單機空調箱與設備表採需求清單回傳：相同來源更新，不同來源累加，移除可還原。
• 水側按相容迴路彙整夏季／冬季需求；可用各迴路獨立物性，不能把不同水溫迴路硬加。
• 電力按各盤功率因數彙整有功／無功需求，保留設計電流下限；不把不同供電併成同一盤。
• Excel 百分比依儲存格格式辨識：50、50% 或顯示 50% 的數值都是 50%；一般格式的 0.5 是 0.5%。
• CDA／特氣可切換標準與管內實際流量，維持同一物理需求；風管定寸模式不用填靜壓。
• 離線中英教學分成六個必要步驟及選讀工具，從程式內按教學直接到目前工具。

English: V5.5.6 adds a focused workbench, practice copies, explicit Save as / Duplicate actions,
source-based demand transfers, seasonal water circuits, per-panel PF, Excel percentage-format
handling, standard/actual gas flow switching, and clearly marked stale results with export locks.
The built-in bilingual tutorial is offline. The FY icon and ANDY HUANG author credit are retained.

建議使用 DMG：三個步驟
1. 打開 Facility_Studio_V5_5_6_macOS_mac1.dmg。
2. 把「Facility Studio」拖到旁邊的「Applications／應用程式」。
3. 從「應用程式」打開 Facility Studio。安裝完成後可退出磁碟映像檔。

不需要另外安裝 Python、Homebrew 或套件；日常使用可離線操作。
請先關閉舊版 App。專案與復原資料不會因更換 App 被刪除。
DMG 的程式已包含完整授權及第三方元件文件。

首次開啟：若 macOS 提示開發者無法驗證
本包已使用 Apple codesign 進行 ad-hoc 完整性簽署，但沒有 Apple Developer ID
與 Apple 公證。第一次先嘗試開啟 App，再到：
「系統設定 → 隱私權與安全性 → 仍要打開」，依畫面完成確認。
公司管理的 Mac 可能需要 IT 允許。
Apple 官方操作：https://support.apple.com/en-us/102445
若顯示「已損毀」、架構不相容或開啟後無視窗，請下載本修正版 ZIP，
執行下述 Verify_on_Mac.command，保留錯誤記錄。
本包不關閉 Gatekeeper，不移除隔離標記，不改動全域安全設定。

完整 ZIP 懶人包：選用
1. 用 Mac Finder 完整解壓縮 Facility_Studio_V5_5_6_macOS_mac1_OneClick.zip。
2. 可直接開啟資料夾中的 Facility Studio.app。
3. 或雙擊 Install_on_Mac.command，安裝至：
   ~/Applications/Facility Studio V5.5.6.app。
   原同名安裝會保留為 Backup；安裝過程不需管理員密碼。
ZIP 另含 Source_and_Verification.zip、設備表範本、簽章及原生驗證記錄。
若 command 被系統攔下，也可直接把 App 拖到「應用程式」，再按上述允許流程。

本次新增
• 主畫面右上選繁體中文／English；欄位、選項、說明、驗證提示與報告同步切換。
• 英文模式可匯出七系統英文 Excel／CSV 範本；舊中文版設備表仍可讀取。
• 切換時保留數值、計算與舊專案；下次開啟沿用語言偏好。

保留的 macOS 修復
• 修正 Tcl/Tk 設定腳本未納入資源封印，導致 Apple 原生檢查及安裝失敗。
• 所有 Mach-O、內層 framework、外層 framework 及 App 由 Apple 原生工具簽署。
• Matplotlib 查詢系統字型的外部指令加上 5 秒時限，逾時改用原有目錄搜尋。
• 安裝及診斷失敗時清楚顯示記錄位置，保留完整錯誤訊息。
• 包含主分支的 XML／JSON 匯入安全檢查、工程資料表與低溫露點修訂。
詳細執行環境修改及雜湊見 MAC_RUNTIME_PATCHES.md、Verification/。

保留的功能
• 獨立工具：電力／NFB／線徑、方圓風管、CDA／特氣、照明照度。
• 冷熱水、空氣狀態與即時空氣線圖、單位換算。
• Excel／CSV 設備表：電力、PCW、CDA、N2、EXHAUST、DI、PV。
• 工程工作台、多台空調箱各段條件、預冷／預熱／再冷／再熱／加濕與熱源配置。
• 專案儲存／讀取／復原、進階條件、互鎖檢核、報告及圖形匯出。
• FY 圖示、通用版名稱、Mac 中文字型及 Command-S／Command-O 等快捷鍵。

設備表範本
Facility_Studio_Equipment_Template.xlsx 含七個系統工作表與填寫說明。
黃色欄位填設備資料；範例預設未啟用，要計算請將「啟用(1/0)」設為 1。
不同電壓、相別及排氣種類會分開彙整；插座數是點位數，設備 kW 不再乘插座數。
本程式不會自動上傳您的專案或診斷資料。

驗證與支援範圍
App 為 Universal：Apple Silicon（M 系列）及 Intel x86_64；封裝最低版本為 macOS 11。
發布流程先在 Apple Silicon 執行七種命令列工具，再於兩種 CPU 的 macOS 15
原生環境檢查 Apple 深度簽章、Tk Aqua、七種工具介面、Matplotlib 繪圖、
設備匯入及完整工程工作台。
實際交付 ZIP 重新解壓縮後、DMG 掛載後也會再次簽章檢查與介面驗證。
只有兩種 CPU 的交付驗證皆通過，才會建立本修訂的新 Release。
macOS 11～14、macOS 27 Beta、Finder 下載隔離提示、企業管理政策、實體數字
鍵盤／觸控板、Retina 視覺與 Excel for Mac 填表未納入這次雲端驗收。
不能以雲端測試通過取代使用者電腦的確認。

本機診斷：有問題才執行
從完整 ZIP 解壓縮資料夾雙擊 Verify_on_Mac.command。
結果存於 ~/Library/Logs/Facility_Studio_V5_5/：
Mac_Acceptance.json、Mac_Signature_Check.txt、Mac_SelfTest_Console.txt。
若驗證失敗，提供上述記錄及 macOS 版本、CPU 類型即可繼續定位。
診斷使用暫存測試資料，不更動既有工程專案。

使用者資料
專案復原：~/Library/Application Support/Facility_Studio_V5_5/Recovery/
介面錯誤：~/Library/Application Support/Facility_Studio_V5_5/error.log
啟動記錄：~/Library/Logs/Facility_Studio_V5_5/startup.log
啟動失敗：~/Library/Logs/Facility_Studio_V5_5/startup-error.log
安裝記錄：~/Library/Logs/Facility_Studio_V5_5/Install_on_Mac.log
繪圖快取：~/Library/Caches/Facility_Studio_V5_5/matplotlib/

授權
允許公司內部正常工程工作、收費工程案件及計算書交付；軟體轉售、付費包裝、
綁售或付費線上軟體服務需另行取得書面授權。完整條款以 LICENSE 為準。
已按 MIT 發布的歷史版本權利保留；第三方元件沿用各自原授權。
工程結果用於初估與方案比較，依現場／原廠資料完成正式設計覆核。

維護者：建置方式見 macos/BUILDING.md。
版本與問題回報：https://github.com/azx4121/facility-studio

V5.5.6: Select Traditional Chinese / English at the top right. Inputs and results remain unchanged; your language preference is saved.
No separate Python installation is needed. Open the DMG and drag Facility Studio into Applications.
English mode also exports English equipment templates. Both languages remain compatible.

English quick start
1. Open the DMG and drag Facility Studio to Applications.
2. Launch Facility Studio, then choose English in the top-right selector.
3. Use each calculator independently; no Python installation or internet is needed.
4. In Equipment schedules, export the English template, enter actual equipment and set Enabled (1/0) to 1 before importing.
If macOS blocks the first launch, follow Apple Settings > Privacy & Security > Open Anyway. The app is ad-hoc signed; it is not Developer ID notarized.

