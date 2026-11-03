# Facility Studio 護鎖與警告驗收

本輪交付：5.7.3-preview.1，精確產品提交 `731e416011251c96c4ca622832cc99b5fc914859`。文件提交可能較新，成品與來源 ZIP 均維持上述已測產品提交。

涵蓋 12 項簡易工具、完整工作台與單機空調箱。修正已知超限／相態風險顯示、未達優先於待資料、複製與匯出成功訊息蓋掉工程警告、另存期間輸入變更仍輸出舊結果，以及圓管直徑表格。待資料用黃色，已知未達用紅色；可供工程檢討的報告保留警告，無效／過期結果禁止匯出。沒有新增無來源的通用安全流速。

驗收證據：來源 302 項測試（含 81 項針對護鎖測試）與 27 套工程回歸通過；Windows 原生 117 項與 27 套通過。Mac／Windows 各 100 情境、7,998 欄位報表檢查通過。Mac 及兩個 Windows 環境成品均通過 31 項核心與 116 項 GUI 檢查；Windows 安裝拒絕非空目錄退出 2，安裝／移除退出 0，額外使用者檔案保留。Mac 移機離線 9 命令與警告版面 12 情境通過。預期錯誤案例採用非零退出，不以一律退出 0 冒充通過。

- [來源、建置與兩環境 Windows 驗收](https://github.com/azx4121/facility-studio/actions/runs/41593248412)
- [Mac／Windows 欄位及報表驗收](https://github.com/azx4121/facility-studio/actions/runs/41593248336)
- [雲端交付](https://drive.google.com/drive/folders/1nA-Rqq2692n5ZlFSKesaPAv4s9pGRJ_h)

本機交付：`/Users/chaoi/Facility-Studio-5.7.3-交付-731e416`。證據：`/Users/chaoi/Facility-Studio-Guard-Evidence-20261103`。14 個雲端檔案讀回名稱／大小／目的資料夾，13 個本機檔案 SHA256 核對；未聲稱已下載雲端檔案逐位元核對。

Mac 在本機測試；Windows 在 GitHub Windows 2022／2025 驗證，未聲稱在使用者實體 Windows 驗證。Mac 使用 ad-hoc 簽章且未公證，Windows 無發行商簽章。53 個既有未提交檔案與舊 App／專案保留；未合併 main、未發布 Release。Claude 接管撤銷，本機千問僅進行可查證的唯讀文案審閱，未作工程認證。

這是指定護鎖與警告範圍的軟體驗收，不能證明所有可能條件無缺陷，也不是完整 FEED 工程認證。完整工程範圍與待原廠／專案資料繼續依 FEED_GAPS.md 管理。對未改動且已通過的測試不重跑。
