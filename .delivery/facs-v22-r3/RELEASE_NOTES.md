# FACS v22 r3：Mac Apple Silicon 完整單檔候選

下載本頁附件 **FACS-v22-r3-UNVALIDATED-COMPILE-ONLY-macOS-arm64.zip**。這是一個完整 ZIP，內含完整 .app，無須拼接或另行下載分片。

**目前是未驗收的 compile-only 候選，不是正式工程發布。** 僅完成受守衛的 Mac ARM64 編譯與靜態檢查；未完成產品啟動、GUI、frozen 或完整工程驗收。不是 FEED 核准、Developer ID 簽署或 Apple 公證版本，不能作為工程核准依據。原有 Mac fixture／完整驗收缺口及電力自動選型限制仍保留。

- 平台：macOS Apple Silicon ARM64，非 Intel／Universal。
- 完整 ZIP：78,519,839 bytes。
- SHA256：`26dcbac483b5c039486af1d88b750ba7dda5f11dbb9965e88fabc08d0236643a`
- 解壓後保留獨立候選位置，勿覆蓋既有安裝或真實公司資料。
- 包內「私人候選／尚未發布」等文字是編譯當時的原始身分紀錄。此次依擁有者要求公開下載，未更改、重建或重新簽署 ZIP，也未把未通過的驗收改為通過。
- 此 tag 的 commit 僅記錄本次檔案傳輸及發布，不代表候選的編譯來源 commit。候選原始來源身分保留於 ZIP 中的 CANDIDATE_IDENTITY.json；不是目前 main 的重新建置。

## English

Download the single complete ZIP attached to this prerelease. No manual joining or separate component downloads are required.

This is an **unvalidated compile-only Mac ARM64 candidate**, published at the owner's request. It has not passed native application launch, GUI, frozen or full engineering acceptance. It is not FEED approval, a Developer ID signed build or Apple notarization. Preserve existing installations and real project data. The ZIP is byte-for-byte unchanged from the original candidate; its embedded private/unpublished labels describe its build-time status. This tag records distribution, not a source build or a new acceptance result.

DESIGNED BY ANDY HUANG ©
