# 開啟安全提示與正式認證

[English](signing.en.md) · [下載](../README.md#下載)

更新：2026-10-08。目前 Windows EXE 未有正式 Authenticode 簽章；macOS App 只有 ad-hoc 完整性簽章，沒有 Developer ID／Apple 公證。原生啟動測試及 SHA256 核對不能替代作業系統的發行者認證，也不代表病毒掃描保證。

## Windows：先看提示內容

| 畫面 | 意義及處理 |
| --- | --- |
| 「Windows 已保護您的電腦」／SmartScreen／不明發行者 | 可能是新檔案或發行者信譽不足。核對本倉庫下載來源及 Release 的 SHA256，再依個人／公司政策決定是否允許。 |
| Windows 11 Smart App Control 或公司管理政策阻擋 | 可能不提供「仍要執行」。由 IT 評估允許或等待正式簽章版本，不需關閉安全功能。 |
| 防毒列出 Trojan 等具體威脅名稱 | 停止執行，回報完整偵測名稱、EXE 的 SHA256、Windows 版本及下載網址。維護者必須核對實際檔案，不能只說是誤判。 |
| 要求管理員權限的 UAC 視窗 | 日常使用此 EXE 不需要管理員權限；請確認執行檔及所採取的動作，回報完整畫面。 |

若下載的是 ZIP，解壓縮本身不會提供發行者身分驗證；因此改成 ZIP 不能保證消除警告。現版保留單檔 EXE，內含執行環境及教學。

## 正式 Windows 發行

1. 維護者以本人或合法組織身分取得受 Windows 信任的程式碼簽章憑證／簽章服務，先確認台灣及個人身分的適用資格。
2. 原生建置、工程測試後，對最終 EXE 簽章並加入可信時間戳。
3. 在原生 Windows 驗證 Authenticode 信任鏈、發行者名稱及時間戳，重新測試已簽章 EXE。
4. 對已簽章檔案計算新的 SHA256，再用新的 Release 發布。簽章後不可修改檔案，也不可沿用未簽章檔案的雜湊。

**正式簽章仍不保證新程式立即免除 SmartScreen 提示。** Microsoft 官方說明：新檔案與發行者需累積信譽；EV 憑證也不再自動略過 SmartScreen。透過 Microsoft Store 安裝是官方列出的免受此下載信譽提示方案，但上架、封裝與驗收屬於另一項工作，現版尚未上架。

參考：[Microsoft SmartScreen 開發者說明](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation)。憑證費用及資格以服務提供者確認為準，沒有在本次維護中購買憑證或付費服務。

## macOS：Developer ID 與 Apple 公證

現版 DMG 可拖到「應用程式」，但 ad-hoc 簽章只驗證封裝完整性，並沒有向系統證明發行者身分。

正式流程：

1. 維護者加入 Apple Developer Program，以本人的合法身分或合法組織申請。
2. 建立 **Developer ID Application** 憑證，對 App 內原生程式、動態函式庫、框架及外層 App 由內向外簽署，啟用 hardened runtime 並核對必要的 entitlements。
3. 驗證原生 App，建立並簽署最終 DMG，提交 Apple notarization。
4. 僅在 Apple 回傳 **Accepted** 後，將公證票證 staple 到 DMG，並驗證票證。
5. 在原生 Mac 上透過實際下載隔離條件檢查 Gatekeeper、啟動和內建工具，再計算最終 DMG 的 SHA256，以新 Release 發布。

公證可處理「無法驗證開發者」的問題；首次正常的「從網際網路下載，是否開啟」確認仍可能出現。公證不是 App Store 上架審核，也不保證工程公式、所有企業政策或未測試 OS 版本。

Apple Developer Program 官方標準費用為 **US$99／年**；所在地區金額以加入時顯示為準。現有發布流程未配置正式憑證，不能標示「已通過 Apple 公證」。

參考：[Developer ID](https://developer.apple.com/developer-id/) · [Apple 公證流程](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution) · [加入會員與費用](https://developer.apple.com/programs/enroll/)。

簽章私鑰、憑證密碼與公證金鑰不可加入公開倉庫或 Release。維護者取得資格後，應透過受控簽章服務或 GitHub Actions Secrets 配置，不需將帳號密碼傳給測試者。
