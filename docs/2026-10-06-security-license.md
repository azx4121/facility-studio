# 安全與授權維護紀錄｜2026-10-06

> **歷史紀錄：**以下保留當時版本與提交的測試、限制及雜湊，不代表目前下載狀態。現行版本為 **V5.5.5 中英雙語版**，見[最新下載](../README.md#下載)、[雙語原生驗收](2026-10-07-bilingual.md)及[目前授權](../LICENSE_GUIDE.md)。
> Historical record; see [current English downloads](../README.en.md#download-and-run) and [V5.5.5 verification](2026-10-07-bilingual.en.md).

基準提交：`f8e92eab6f9c03262378c87591e8600ec3910e17`。本次保留功能、原有歷史、圖示、Release 與標籤，沒有變更工程公式。

## 授權範圍

維護者選擇：允許公司工作使用，限制軟體轉售及商品化。
目前完整授權採 PolyForm Noncommercial 1.0.0 原文，加上本專案內部商業使用附加許可 1.0。
公司可執行收費工程工作並交付計算結果；出售軟體或修改版、付費綁售與付費軟體服務須另取得書面授權。
這個組合含專案自訂附加許可，不是純標準 PolyForm、MIT 或 OSI 開源授權；正式法律問題應由法律專業覆核。

根目錄、Windows、macOS 與 Windows payload 的 LICENSE、中文指南及歷史 MIT 文件一致。
歷史 MIT 文字與基準提交中的 LICENSE 完全相同；既有版本的已授權權利不會因本次更新被追溯限制。
這些限制也不會改變 Python、Matplotlib 等第三方元件的原授權。

## 修正及驗證

| 項目 | 原因與修正 |
| --- | --- |
| Excel XML 宣告 | 原先只掃描原始 ASCII 位元組，UTF-16 可繞過。改用解析器的 DTD 回呼直接阻擋；讀取限制 40 MiB、深度 64、節點 1,000,000。UTF-16 及正常註解仍可讀取 |
| 深層 JSON | 原先觸發未處理的 RecursionError。改用共用有限讀取器，在解析前檢查 64 層深度；字串內括號與跳脫字元不誤判 |
| JSON 資料歧義 | 拒絕重複欄名、NaN、Infinity、數字溢位及損壞編碼，回報結構化 ValidationError |
| 匯入入口 | 套用於整案、主案、空調箱、復原檔、CLI 小工具、小工具設定及工程資料表；macOS 專用儲存位置保留 |
| Windows 封裝 | payload 同步新增安全模組及授權資料；強制驗證完整成員及 SHA256；安裝器增加完整授權頁，重建後逐檔解壓比對 |
| macOS 封裝腳本 | 未來建置 App 與 ZIP 時需帶入目前授權、說明與歷史 MIT；本次沒有重建或替換既有已封裝 App |

## 本次實測

下表為每一份平台原始碼的結果；兩份都在 Linux 實際執行。GUI 使用 Tk 8.6 與 Xvfb，不代表已在 Windows/macOS 實機驗收。

| 套件 | 每平台結果 |
| --- | --- |
| 核心回歸 | 52 情境／1,247 檢查通過；7 項預期拒絕 |
| V5.5 功能 | 20 條件／93 檢查通過 |
| V5.5.2 核心 | 305 檢查通過 |
| 簡易工具 | 42 情境／375 檢查通過 |
| 設備表與空氣圖 | 49 情境／646 檢查通過 |
| 空氣狀態與資料表維護 | 90 条件／1,129 檢查通過 |
| 安全與授權 | 55 不同條件全部通過 |
| 實際 Tk 互動 | 42＋31＋44＋58＋69＋14＝258 檢查通過，另通過 GUI smoke |

另通過 19 項 Windows 封裝檢查、21 項安裝器完整性檢查；實際解壓並逐位元比對 62 個內嵌檔案。177 個 Python 檔案完成語法解析。
執行證據：[數值與輸入測試](Security_License_Numeric_Execution.json)、[GUI 執行](Security_License_GUI_Execution.json)、各平台 `evidence/Security_Input_Checks.json`。

## 仍未完成的事項

- 既有 `v5.5.4-beta.1` Release 安裝包保留，沒有替換為本次安全及授權修訂。主分支原始碼與 repo 中 Windows Setup 已更新；下載區仍須另發布新包。
- Windows 安裝器仍未具發行者 Authenticode 簽章；Mac 仍缺 Developer ID 簽署與公證。
- Windows 線上安裝的建置套件目前仍使用版本範圍，尚未完成帶雜湊的完整依賴鎖定。
- 主分支保護、GitHub Ruleset、帳號 2FA 與私人權限設定未在本次變更中調整。
- 此測試不是完整滲透測試、第三方 CVE 清查或原生平台安裝驗收，也不構成零漏洞保證。

本次沒有改寫 Git 歷史、移動既有標籤或撤回先前授權。法律與技術上的複製、商品化風險須分別看待；公開的舊 MIT 版本仍可依其原條款使用。

