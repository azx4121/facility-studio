# V5.5.5 修訂 2：新手教學與簡易工具署名

[新手教學](guides/workbench.md) · [English walkthrough](guides/workbench.en.md) · [離線懶人包](tutorial/Facility_Studio_Beginner_Tutorial.zip) · [下載頁](../README.md#下載)

本修訂補上簡易工具左下角「DESIGNED BY ANDY HUANG ©」，七種工具切換時持續保留。原完整工作台署名與 FY 圖示保留，沒有變更工程公式或現有專案格式。

簡易工具、完整工作台及分段空調箱新增「新手教學」入口，開啟隨軟體附帶的本機 HTML；不依賴網路。工作台入口直接到第一份練習，空調箱入口直接到分段教學。

教學採十個短章節，第一輪只需前六節；另含兩份能由主工作台「開啟」的合成整案、中文／英文對照報告及操作位置示意圖。說明主案保存、報告與驗算 JSON 的差別，以及潛熱、獨立／連動水量、簡易壓損、MAU 連動限制和回傳取代行為。

教學資源以內容雜湊分開存放於本機教學資料夾；重開不覆寫已有練習檔。離線 ZIP 亦可直接下載，較早 V5.5.5 版可立即閱讀 HTML。

教學以目前中英文設定開啟。原生驗收的練習載入會還原原先已儲存／未儲存狀態；自動測試收尾明確回答測試專案的未儲存提示，日常操作仍保留原有儲存詢問。

## 驗證與發布狀態

| 檢查 | 結果 |
| --- | --- |
| Windows 原始碼教學條件 | 20 種、85 項通過 |
| macOS 原始碼教學條件 | 20 種、85 項通過 |
| 中英既有資料、匯入及報告回歸 | 隨本次修訂執行，原生流程再次檢查 |
| 署名、教學入口及實際練習載入 | 由原生 Windows／macOS 建置驗收；發布完成後補紀錄 |
| 新 Windows EXE／ZIP | 目標 `v5.5.5-win.2`，原生驗收通過後由既有流程發布 |
| 新 macOS App／DMG／ZIP | 目標 `v5.5.5-mac.2`，Apple Silicon／Intel 驗收通過後發布 |

在新版發布與下載核對完成前，首頁現有下載保持 win.1／mac.1。舊檔不會因 GitHub 原始碼更新而自動出現新按鈕或署名。所有既有提交、標籤、Release 及授權條款保留。

新增原生檢查直接測試簡易工具署名在最小 780×560 視窗的可見性、教學只開本機檔案、兩份練習隨包完整、第一案載入實際 Tk 工作台後重算，以及第九個設計報告頁可見。教學數值測試不代替原生 UI 驗收。

## English

Revision 2 restores persistent **DESIGNED BY ANDY HUANG ©** credit to the simple tools and adds bundled offline tutorial buttons to the simple home, full workbench and AHU window. Two synthetic reopenable practice workspaces and bilingual reference reports explain the actual ownership and interlock behavior.

Each source platform passes 20 practice conditions and 85 assertions. New native checks cover minimum-window credit visibility, local tutorial entries, bundled practice files, actual workbench loading/recalculation and the ninth report page. New Windows/macOS releases publish only after the existing native gates pass. Current win.1/mac.1 downloads remain valid until the new deliveries are verified. Existing releases, commits and licensing terms are preserved.
