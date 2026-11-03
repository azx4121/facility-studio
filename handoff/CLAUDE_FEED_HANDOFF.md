# Facility Studio：最新 FEED 續作

本文件與 `STATUS.json` 優先於已封存的 5.7.1 交付狀態；原版成功交付不表示完整 FEED 已完成。

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
