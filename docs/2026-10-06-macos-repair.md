# macOS 啟動修復與原生交付驗證｜2026-10-06

適用版本：V5.5.4 mac.2。保留 V5.5.4 功能、FY 圖示、專案格式、提交紀錄及歷史 Release。
新的下載採用當前安全與授權維護原始碼。mac.1 原始資產未替換。

## 已重現的安裝問題

原始 mac.1 ZIP 的 SHA-256 與 GitHub 資產相同：
`aef324d08815257848e4b8080023611b41a4a88eb2cdd03e6ee1a71e5a983b65`。
其執行權限、雙 CPU Mach-O、相對連結及檔案雜湊可通過靜態檢查；
**Apple Silicon 與 Intel macOS 15.7.9 的 Apple 原生深度簽章檢查卻都失敗**。
Tcl/Tk 的 tclConfig.sh、tclooConfig.sh、tkConfig.sh 位於框架的版本根目錄，
跨平台簽署未正確處理 Apple 對巢狀程式及資源的規則。
原安裝器會拒絕這個簽章結果，因此僅檢查 ZIP 雜湊不能宣稱能在 Mac 安裝。

重現紀錄：[原始包原生診斷](https://github.com/azx4121/facility-studio/actions/runs/37456331721)。

## 修正

- 保留三個 Tcl/Tk 編譯用設定檔，移至框架的 Resources/BuildConfiguration，讓 Apple 將它們作為資料資源封印。執行時不需編譯擴充模組。
- 220 個 Mach-O、三個框架與外層 App 改用 Apple codesign 由內向外簽署，再要求深度、嚴格驗證通過。
- Matplotlib 外部字型查詢限制五秒，逾時改採原本的目錄字型搜尋；記錄修改前後 SHA-256 並更新 wheel RECORD。這是專案封裝副本的修訂，原版授權保留。
- 表單尺寸及捲動範圍相同時，不重複要求 Tk 重排；保留真正尺寸變更時的連動。
- 原 GUI 驗證在隱藏多個視窗後的 root.update() 等待不結束。新版改用可見視窗及正常 mainloop，以計時器驗證事件迴圈回應，加入八個工作台分頁與 callback 錯誤檢查。**不將舊測試最後一行「建立字型快取」當作已證實的唯一根因。**
- 增加標準 DMG 拖曳安裝，保留 ZIP、選用安裝／本機驗證腳本。安裝失敗保留記錄與舊 App。

資源位置依 Apple [Code Signing Tasks](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/Procedures/Procedures.html) 與 [TN2206](https://developer.apple.com/library/archive/technotes/tn2206/)；執行環境修訂及來源見 [MAC_RUNTIME_PATCHES](../macos/MAC_RUNTIME_PATCHES.md)。

## 修正版實際結果

驗證來源提交：`b47085be8fa311bf358913c359d48c60312cd953`。
[原生交付驗證工作流程](https://github.com/azx4121/facility-studio/actions/runs/37461422765)。

| 項目 | Apple Silicon macOS 15.7.9 | Intel macOS 15.7.9 |
| --- | --- | --- |
| Apple 深度、嚴格簽章檢查 | 通過 | 通過 |
| CPython 3.13.15、NumPy、Pillow 原生載入 | 通過 | 通過 |
| 七種工具、Tk Aqua、設備表、工程工作台、Matplotlib | 45 項全通過 | 45 項全通過 |
| 實際交付 ZIP 解壓縮後簽章與介面驗證 | 通過 | 同一份 ZIP 通過 |
| 實際 DMG 掛載後簽章與介面驗證 | 通過 | 同一份 DMG 通過 |
| Launch Services 開啟 App 後完成驗證 | 通過 | 此項未獨立執行 |
| 七種命令列入口 | 通過 | 新交付包以 GUI 計算驗證；此項未獨立執行 |

原始 JSON 與介面記錄保留於 [macOS 原生證據](../macos/evidence/macos-native-mac2/)。
每個執行情境各有 45 項檢查，不把多次重跑加總成更多不同測試。
新增版本的發布流程會從主分支重新建置，兩種 CPU 的交付驗證通過後才建立新 Release；
上傳資產的檔案大小與 SHA-256 必須與被驗證的成品一致。

## 仍須使用者電腦確認

此版使用 ad-hoc 完整性簽章，沒有 Apple Developer ID 或 Apple 公證。
首次瀏覽器下載後可能需依 Apple 官方「隱私權與安全性 → 仍要打開」流程允許。
沒有關閉 Gatekeeper、沒有移除隔離標記，也不修改使用者全域安全設定。

測試為 GitHub 原生 Mac 雲端環境，不是使用者的 Mac mini M2。
macOS 11～14、macOS 27 Beta、實體數字鍵盤／觸控板、Retina 視覺、公司管理政策、
Finder 隔離提示及 Excel for Mac 填表流程未包含在本次驗收。
若使用者仍無法開啟，需提供實際錯誤與 ZIP 內 Verify_on_Mac.command 的本機記錄。
