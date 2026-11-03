# 2026-11-03 FEED 能力續作

基線為 674b509，新的隔離分支 `sandbox/feed-readiness-20261103`，工作樹 `/Users/chaoi/Facility-Studio-FEED-20261103`。原 5.7.1 成品、原工作樹及其未提交資料均保留。此分支為 5.7.2-preview.1，不能套用 5.7.1 的成品驗收數字。

## 能力結論

仍不能聲稱具備完整 FEED 交付能力。已具備的熱濕、水力、電力初估及本次文件管理／局部泵浦校核，可以支援 FEED 的一部分。專案適用範圍、正式規範版本與業主／設計者簽核尚未給定；不能用軟體測試或 AI 意見補成真實工程核准。

未完成的可開發項目包括：多區壓差／多支路水力網、可壓縮氣體與完整真空網、原廠產品壓溫與相容性資料、適用風管補強／保溫規範表、電力短路與保護協調，以及 P&ID／控制 I/O／MTO 的一致資料模型。選定標準與原廠工況資料屬外部工程輸入；不能虛構。

## 本次已實作

1. 設計依據與交付審查：主畫面入口、規範登錄、十二類文件與附件快照、人工覆核、全案變更使舊覆核失效、遺失／損壞附件攔截、獨立版次與繁體中文報告、CLI 核對退出碼 0／3／2。每份報告附對應設計資料 JSON，可重現檢查。證據僅因使用者附加而讀取，不自動掃描本機資料。
2. 液體頁泵浦吸入校核：NPSHa、液槽與吸入口相態限制、原廠 NPSHr＋指定裕度；負壓、吸上高度、熱水、混合液及高流速閃蒸反例。變更工況清除舊吸入損失與泵曲線依據，重算前不允許沿用。

## 查證依據（2026-11-03）

- [DOE 前端規劃與定義成熟度](https://www.energy.gov/documents/front-end-planning-and-project-definition-rating-index-nuclear-and-non-nuclear)：FEED 成熟度涉及交付文件完整程度，不是本程式自行宣告的固定百分比。
- [DOE 專案交付要求範例](https://eere-exchange.energy.gov/FileContent.aspx?FileID=d79e747f-149f-4104-90dc-633eb09f94c6)：包括設計依據、工程圖件、設備與控制等文件；本次十二類清單是依此概念制定的通用起始清單，不宣稱適用所有業主。
- [KSB 離心泵選用資料](https://www.ksb.com/en-global/centrifugal-pump-lexicon/article/npsh-1116954)：液槽表面至泵的 NPSHa 能量式；本版採標準重力 9.80665 m/s²。大型槽表面速度假設為零，不能再額外加一次吸入管速度水頭。
- [ISO 14644-1](https://www.iso.org/standard/53394.html)：潔淨度涉及粒子濃度分級，ACH 計算不能替代現場潔淨度測試。

## 實測紀錄

證據目錄：`/Users/chaoi/Facility-Studio-FEED-Evidence-20261103`。先前 combined-r2：210 passed／1 failed；失敗為測試把「液槽低於蒸氣壓」錯推成「NPSHa 必為負」，忽略正液位靜水頭。修正測試為必須拒絕單相判定，負 NPSHa 另以吸上高度案例核對，未放寬產品相態保護。後續結果以 STATUS 與新的 XML／日誌為準。

## Claude 接續

GitHub 全欄位工作流另找到新增 NPSH 開關對非法文字未攔截；已改為僅接受 0／1，加入 pytest 與封裝內反例。其測試設定同時更新為明填合成吸入損失／泵曲線／裕度，不把缺值變成產品預設零。新增文字來源拒絕控制字元，保留空白 NPSHr／裕度的待資料語意。`fields-macos-r9.json` 已通過 100 組、7998 項欄位／報告檢查，包含 201 個簡易欄位、4790 次報告核對。

交付前新增反例發現並修正兩項資料保留缺陷：附件的隨機名稱碰撞時，原先錯誤清理可能刪到已存在的檔案；現在只清理本次成功建立而寫入失敗的副本，碰撞保持原檔完整。另限制儲存的設計 JSON 與讀取端同為 4 MiB，避免存得下卻讀不回。`counterexamples-before-r7.xml` 保存兩項真實失敗，修正後結果見 `combined-r7.xml`。碰撞反例亦已加入封裝內操作驗收。906934d 的第一次 Mac 封裝雖通過當時驗收，因這兩項新反例列為先前候選，不可作最終交付。

13:05 後先讀本分支與最新 STATUS，再決定審查／修改。不要把原 5.7.1 已交付誤認為本分支或完整 FEED 已完成，也不要直接發布未驗收分支。保留先前時間、帳號、安全與發布界線。


## Codex 接續完成本輪軟體驗收（2026-11-03）

使用者取消 Claude 接管後，只終止本任務 Claude 程序，保留其提交及所有未提交檔案。`CLAUDE_HANDOFF_REVOKED.json` 與 dispatcher 防護已提交；實測拒絕接管退出碼 3、未發生模型 API 呼叫。

產品提交 `be1b0cc7a3c52346b27bb8fba1d0e065ebd14f35`：修正四段驗收文字漏譯，以及只切換文件就誤報未存變更。保留並驗證主視窗／工作台關閉時的設計草稿保護、同視窗重用與獨立 Mac bundle identifier。反例 `navigation-before-r13.json` 顯示修正前純瀏覽使 dirty 變成 true；新增原生 GUI 及封裝驗收已通過。

同版結果：220 項 pytest、27 套完整來源回歸；Windows 原生另有 27 套回歸及 36 項 pytest。兩份來源各 100 組條件／7,998 項欄位檢查通過。Mac 與 Windows 成品各 31 項核心、52 項操作檢查；Mac 完成 9 種離線移機命令情境。Windows 2022／2025 均通過同 SHA 套件、安裝、非空資料夾拒絕覆寫及移除保留額外檔案。Mac 與 Windows 各 106 個產品來源雜湊均與實際 Build Manifest 相符。

本機 `qwen3.8:27b` 真實執行 88.26 秒、輸出 950 tokens；僅做有限範圍吸入公式複核，輸出達設定上限，不當成完整獨立工程審查，未因此修改方程式。

CI：https://github.com/azx4121/facility-studio/actions/runs/41584428775
來源檢核：https://github.com/azx4121/facility-studio/actions/runs/41584428803
本機交付：`/Users/chaoi/Facility-Studio-5.7.2-交付-be1b0cc`。雲端：https://drive.google.com/drive/folders/11meqqhIZibASCU4fnNnn6vptgBdhX2Hg 。完整證據位於 `/Users/chaoi/Facility-Studio-FEED-Evidence-20261103/Delivery_Evidence_be1b0cc`，另附交付證據 ZIP。

本輪完成的是獨立測試版的功能／UX 修正及跨平台軟體驗收。完整 FEED 的管網、多區壓差、保護協調、產品資料及跨專業工程交付仍依 `FEED_GAPS.md` 接續。沒有合併 main、公開 Release、取代正式 App，亦未把文件齊備或 AI 審閱稱為工程認證。
