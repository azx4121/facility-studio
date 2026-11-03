> 最新指示（2026-11-03 13:21）：使用者已取消 Claude 接管，現在由 Codex 繼續；Claude 程序已依要求停止。下方接管／額度保留指示是歷史，不得再啟動 Claude。保留全部修改與驗收資料。

# Facility Studio：最新 FEED 續作

本文件與 `STATUS.json` 優先於已封存的 5.7.1 交付狀態；原版成功交付不表示完整 FEED 已完成。

## 11:17 使用量保留檢查點（最新）

使用者明確要求保留 Codex 用量供 13:05 交接，現在停止擴大功能與重複測試，已啟動的 GitHub 驗證繼續執行。最新產品提交 `85cff1f8e597f243f60d9a20fb2233f1ca2c291b`；217 項 pytest 與兩平台來源各 7998 項全欄位／報表檢查通過。Mac 候選 `/Users/chaoi/Facility-Studio-5.7.2-Review-85cff1f` 的封裝內核心 31 項、操作 37 項通過。**這不是最終交付：尚待最新移機離線、Windows 成品與以下關閉行為檢查。**

GitHub run `41571021522`（來源＋原生 Windows＋第二 Windows）及 `41571021461`（dashboard）於本檢查點仍執行中。接管時讀取結果，不能沿用前兩個已取消／失敗 run，也不要重派尚在執行的同一提交。所有先前候選與失敗證據保留。

發布前先處理兩項源碼審閱發現，尚未做反例實測：

1. `SimpleToolsApp.close()` 尚未詢問新 `DesignReviewWindow` 的未存變更，直接銷毀主視窗可能連帶丟失草稿；先寫主視窗關閉／切到完整工作台後關閉的拒絕離開反例，再串接確認。相關完整工作台關閉入口在 `session_controller.py:close_workspace`，避免同一動作重複詢問。
2. `integration/build.py` 的 macOS bundle identifier 仍是原版 `com.facilitystudio.engineeringfusion.preview571`；新候選應使用獨立識別碼，例如 `com.facilitystudio.preview572`，避免與既有 App 識別混淆。修改後才重建並測試新的成品，不覆蓋現有封裝。

若只讀 CI 或更新文件，不要重跑已過且無程式變動的測試。`windows/evidence/*` 是此次回歸產生的未提交檔案，保留；另有工作流備份 stash 與 `workflow-reviewed.patch`，不刪除、不套用覆蓋新工作流。

## 執行位置及時間

- 新工作樹 `/Users/chaoi/Facility-Studio-FEED-20261103`，分支 `sandbox/feed-readiness-20261103`，版本 `5.7.2-preview.1`。
- 新證據目錄 `/Users/chaoi/Facility-Studio-FEED-Evidence-20261103`。先讀 `FEED_PROGRESS_20261103.md`、`FEED_GAPS.md`、`STATUS.json` 及實際 Git 狀態。
- Claude 只能在 **2026-11-03 13:05 Asia/Taipei** 後透過本工作樹 `handoff/dispatch_claude.py` 啟動，不得改時間門檻。04:07 是 Codex 額度重置點，不是停止時間。
- 共用舊證據目錄的 `claude-handoff/active.lock` 防重入，新 session 證據寫入新 FEED 目錄；舊的已停止 session 不得重開。到期才唯讀核對訂閱 OAuth，不能讀取／輸出憑證。

## 本次新增

1. `design_basis.py`／`design_basis_ui.py`：主畫面設計依據與交付審查、九項依據、規範名稱／版次／條號／範圍／來源、十二類文件、附件快照及雜湊、人工覆核、設計變更使舊覆核失效、缺件／篡改阻擋、每次儲存及匯出另建版次。CLI `--dossier-check` 退出 0 文件齊備、3 待處理、2 格式錯誤。
2. `pump_suction.py`：液體頁的等溫穩態 NPSHa、液槽及吸入口閃蒸檢查、原廠工況 NPSHr 加專案裕度。液位與吸入口高程均相對原廠 NPSH 基準面。混合液需要同溫度／濃度泡點來源；工況變更清除舊吸入損失與泵曲線依據。
3. 繁體中文 UI／報告／離線教學與封裝內 `design_acceptance.py` 已接入。千問提供文案翻譯，Codex 已逐項核對並修正質量平衡漏譯等內容，不把本機模型當作工程審核。

## 待繼續完成

完整 FEED 仍缺多區壓差／完整支路水力網、完整氣體／真空網、原廠產品尺寸及壓溫／相容性資料、適用風管補強與保溫規範、電力短路及保護協調、P&ID／控制 I/O／MTO 的一致資料模型。設計文件登錄不會產出或驗證這些內容。

先核對 STATUS 中新來源、Mac 成品及 Windows CI 的真實結果，再獨立審查新功能與反例。只補失敗或受變動影響的驗收，不重跑未變更且已通過的項目。使用者要求持續實作，不只交清單。缺原廠／標準資料時，完成可配置模型與合成測試並保留待資料，不能虛構規範值。

專案 Design Basis、適用規範、業主及具資格工程簽核不是軟體可以捏造的輸入。「文件齊備，可送工程審查」不是工程核准，人工姓名不是經驗證的電子簽章；不得給無依據完成百分比。

## 保護及發布

原 5.7.1 工作樹、未提交資料、正式 App、Hub 及舊交付全部保留。不得 reset／clean／force push／合併 main，不覆蓋 tag 或成品。不得使用 Gemini、付費 API 或安全／權限 bypass。全繁體中文；對外只叫 Facility Studio，不展示後端套件品牌及版本清單，必要授權獨立保留。

使用者已授權由 Claude 在全部驗收後檢查草稿 Release 並正式發布新資產，但不可把限定功能發布描述成完整 FEED 工程核准。任何程式修改都要有對應反例、原生操作與新封裝驗收；不能把舊版本數字套到新版。記錄 session、提交、命令退出碼、缺陷及發布網址；啟動／排程不等於已接管或已完成。

Python：`/Users/chaoi/Facility-Studio-Fusion-Env-20261102/bin/python`。新增測試 `integration/test_design_basis.py`、`test_design_basis_gui.py`、`test_pump_suction.py`；封裝內 `--facilities-self-test` 已加入新操作驗收。原完整要求及歷史交付存於 `CLAUDE_HANDOFF_5.7.1_ARCHIVE.md`／`STATUS_5.7.1_ARCHIVE.json`。
