# 2026-10-08：下載入口與發行者認證

依維護者要求，目前推薦版本只提供兩種程式下載：Windows EXE 與 macOS DMG。中英文首頁及安裝教學同步，設備範本與離線教學仍能從程式內使用。原始碼、授權及開發者診斷留在 GitHub 倉庫。

## 本次限定範圍

| Release | 移除的完整 ZIP | 保留的程式 |
| --- | --- | --- |
| v5.5.6-win.3 | Facility_Studio_V5_5_6_Windows_Offline_OneClick.zip | Facility_Studio_V5_5_6_Windows_Offline.exe |
| v5.5.6-mac.2 | Facility_Studio_V5_5_6_macOS_mac2_OneClick.zip | Facility_Studio_V5_5_6_macOS_mac2.dmg |

Release、標籤、提交紀錄及其他歷史版本維持不變。SHA256SUMS 同步為僅列出保留程式的雜湊；不修改 EXE／DMG。

| 保留檔案 | SHA256 |
| --- | --- |
| Windows EXE | fcfa8a672095aac7cb6f2b5664c6d1124d75d678b3a1404a8d22b1fc929e0765 |
| macOS DMG | 117c38cb7700f219869b889fd1af015b291d6ec29c65f854b3cc0ab471e2fd59 |

歷史驗收包含 ZIP，記錄保留當時原始結果，不能把資產移除寫成未曾驗收。開發者建置仍可產生 ZIP 做跨主機驗收；公開發布程式只上傳 EXE／DMG 及與其一致的 SHA256SUMS。

## 執行與保護

維護腳本使用明確的兩個 Release ID、ZIP 資產 ID、檔名、大小及 SHA256。先核對兩個 Release、保留檔案及檢查碼，全部符合才開始變更。先上傳並驗證新的檢查碼，再替換舊檢查碼；重跑可接續處理中斷狀態。正式程式的 ID、大小與雜湊都必須維持原樣。

維護工作僅由 main 的專用 GitHub Actions 工作執行，不對 PR 執行、不重建原生程式，也不改工程公式。工作證據保存變更前後的公開資產中繼資料及檢查碼。完成狀態以 Actions 成功紀錄及 Release 再讀回核對為準。

發布與刪除保護測試：`python tools/test_public_downloads.py` 通過 31 項，包含兩平台、檔案身分與雜湊被改、範圍錯誤、意外新增資產、上傳檢查碼失敗、中途中斷後接續、重跑不重複變更，以及內部驗收檔不被改寫。GitHub 工作在正式變更前會重跑此測試。

## 認證狀態

此次更新不是正式簽章發布。Windows EXE 仍未簽章；macOS 仍為 ad-hoc 完整性簽章，沒有 Developer ID／Apple 公證。[中文認證規劃](signing.md)與[英文說明](signing.en.md)區分 SmartScreen、Smart App Control、防毒偵測及 Gatekeeper，並列出正式流程及所需資格。

## English summary

Only the complete ZIP assets of the two currently recommended releases are retired. The standalone EXE and DMG retain their original IDs, sizes and hashes. Release bodies, current download instructions and public checksums are synchronized. Historical releases, tags, commits, engineering formulas and acceptance evidence are preserved. Developer ZIPs may still be used internally for native acceptance, but public publishers only upload the executable/DMG and matching checksums. This update does not claim trusted publisher signing or notarization.
