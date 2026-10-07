# V5.5.5 GitHub 文件同步｜Documentation review

[文件中心](README.md) · [English documentation](README.en.md) · [目前下載](../README.md#下載)

2026-10-07 核對主分支 `769b779d1553c28065fbfc2566b015cb4c10b39d` 的對外說明及已公開 Release。此次為文件更新，工程引擎、LICENSE 條文與公開安裝檔位元組保持原樣。

| 問題 | 修正 |
| --- | --- |
| 工具指南仍稱只有中文、沒有英文介面 | 改為 V5.5.5 雙語狀態；加入中英文文件中心及九類工具的完整英文指南 |
| 英文首頁連到中文案例／安裝說明 | 英文案例改連對應英文篇；補齊 Windows／macOS 首次開啟、診斷與回報步驟 |
| 平台 README 仍有 V5.5.4 檔名／尚未原生驗收 | 更新 Windows／macOS 使用說明；最初 Mac 說明完整保存在歷史區 |
| 平台授權指南仍稱新安全／授權包尚未發布 | 更新目前發布版本；補英文授權摘要，條款本身不變 |
| Mac 建置案例仍用 V5.5.4 mac.2 名稱 | 改為 V5.5.5 的實際輸出檔名，說明後續發行須同步更新版本與封裝名稱 |
| 舊 MIT、Mac 修復、Windows 離線及搜尋紀錄容易被誤認為最新狀態 | 加歷史版本提示與最新文件入口，保留原始數字、雜湊與限制 |

## 本次確認

- 原始碼與案例資料共 228 個檔案與當前 GitHub 主分支 SHA 完全一致，沒有用較舊副本代跑案例。
- 兩份來源各重跑 20 個公開操作情境（18 個適用計算、2 個不適用對照），各通過 121 項檢核；這是目前測試主機的計算／報告重算，未冒稱重做 Windows／Mac 原生驗收。
- 實際執行新版英文 CLI 電力與空氣狀態範例，成功輸出英文報告，電流／NFB／線徑及空氣性質符合指南。
- 文件檢查涵蓋相對路徑、章節定位、圖片、表格欄數、中英文互連、案例定位與目前下載資產名稱；結果見[文件檢核摘要](evidence/v5.5.5-documentation.json)。相對路徑以完整 GitHub tree 核對，並非要求所有檔案都複製到文件資料夾。
- `v5.5.5-win.1`／`v5.5.5-mac.1` 都已公開為測試版；資產與 SHA-256 和先前完整下載驗證一致。[當前安裝檔驗證](2026-10-07-bilingual.md)。
- 倉庫 `has_pages=false`：目前網站內容是 GitHub README／文件／Releases，沒有另外的 GitHub Pages 部署。

## English summary

This documentation update aligns public guidance with V5.5.5 bilingual releases. It adds English guides for all nine tool topics, a documentation index, full English installation/reporting steps and a licensing summary. Earlier records keep their original evidence and gain historical-version notices. Current release assets and engineering/license terms are retained.

The current-main source and example files matched 228 Git blob hashes. Both source distributions reran the same 18 numerical scenarios and two out-of-scope controls, passing 121 checks each on the current test host. Two English CLI examples produced the documented results. Documentation links/anchors/images, table columns, language counterparts and current asset names were checked. These host-side/documentation checks do not replace the native acceptance recorded for the already published binaries.
