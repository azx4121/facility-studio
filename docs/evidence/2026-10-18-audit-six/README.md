# Windows win.7 驗證資料

[完整修正與原生驗收](../../2026-10-18-windows-audit-six.md)

| 檔案 | 範圍 |
| --- | --- |
| [native-release-verification.json](native-release-verification.json) | 受測提交、兩套原生 Windows、來源 CI、Artifact ZIP 完整性、公開重新下載與舊 Release 資產身分 |
| [windows-2022/summary.json](windows-2022/summary.json)／[windows-2025/summary.json](windows-2025/summary.json) | 每套主機三個啟動路徑的核心／延伸操作、離線條件、壓力測試摘要與原始報告雜湊 |
| [numeric-assertions.json](numeric-assertions.json) | 六次封裝執行核對為相同的 2,182 個獨立數值斷言，只保存一份清單 |
| [restoration-cases.json](restoration-cases.json) | win.6 與 win.7 相同輸入的來源復原重現與實際結果 |
| [format-compatibility.json](format-compatibility.json) | Windows 讀舊 ledger v1、mac.6 來源拒絕新 v2 整案；非 macOS 原生執行證明 |
| [source-local.json](source-local.json) | Linux／Tk 上 Windows 來源的本機預檢，與原生 EXE 證據分開 |
| [independent-source-summaries.json](independent-source-summaries.json) | 本次 Server 2022 的 4,432 項獨立公式與 6,977 項全欄位／報告回歸摘要，含原始檔雜湊 |
| [windows-use-cases.json](windows-use-cases.json) | 本次 Server 2022 來源 Python 的 18 個計算案例＋2 個範圍對照，共 121 項；非封裝 EXE 測試 |
| [capture-observations.json](capture-observations.json) | 兩套主機實際截圖的人工觀察；未結案的實機重繪驗證與正常介面擷取分開 |
| [screenshot-identity.json](screenshot-identity.json) | 首頁原生圖片的 Artifact 來源、檔案身分及未修改標記 |

發布檔只公開 EXE 與 SHA256SUMS。內部 ZIP 供交付路徑驗收，沒有移除原始驗收報告。歷史 win.6／win.5／win.4／mac.6 的資產 ID、大小與 digest 另列於發布核對檔。

English: source checks, delivered EXE execution and visual observations have separate scopes. The two native hosts repeat the same inputs across three delivery paths; these are not six new sets of independent design scenarios. See the report for legacy W/kVA recovery, ledger v2/Mac incompatibility and the cloud end-of-suite capture limitation.
