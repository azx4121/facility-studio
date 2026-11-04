# 簽章與安全提示｜Facility Studio 5.7.3

[English](signing.en.md) · [下載與狀態](../README.md#下載)

原生驗收、Windows 可信 Authenticode 發行者簽章及 Mac Developer ID／Apple 公證狀態，以對應 commit 的 CI 與 Release 附件中對精確成品的證據為準；沒有證據即不能視為已驗證。Mac ad-hoc 僅核對完整性。正式版名稱、SHA256 相同或原生測試通過都不代表發行者身分認證或無惡意程式保證。

1. 只從本倉庫 Releases 取得成品，核對平台、版本、大小及該檔正式公布的 SHA256。該平台只有在對應 Release 提供成品與 SHA256 時才可下載核對，不自行填造雜湊。
2. portable／ARM64 ZIP 須完整解壓。ZIP 只是包裝，不能繞過安全檢查；本次沒有 Mac DMG 或 Intel／Universal 包。
3. 先看完整提示。公司政策或 Smart App Control 阻擋應交 IT 評估，不關閉保護。若列具體病毒名稱、檔案損毀或雜湊不符，停止執行並回報完整提示及檔案身分。
4. 不關閉防毒、Gatekeeper 或隔離保護，不使用全面略過指令。一般操作不應需提升權限；不預期的權限要求需先核實。

## 後續可信簽章

Windows 須由有權維護者配置簽章憑證、時間戳並對最終檔案原生驗證。Mac 須合法 Developer ID、必要 entitlements 及成功公證後才能宣稱已公證。簽章會改變 bytes，應重新算 SHA256 並重跑成品驗收。私鑰與憑證密碼不可進公開倉庫或 Release。

實際狀態按[正式驗收證據格式](verification/5.7.3-release-acceptance.md)隨對應 Release 提供，不必回寫已凍結的來源文件；不能沿用舊版簽章／測試結果。

[Microsoft 簽章與信譽說明](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation) · [Apple Developer ID](https://developer.apple.com/developer-id/)
