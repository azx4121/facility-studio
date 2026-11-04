# 常見問題｜Facility Studio 5.7.3

[English](faq.en.md) · [下載與發布狀態](../README.md#下載) · [指南](guides/README.md)

**此版本的原生驗收與各平台發布狀態，以對應 commit 的 CI 紀錄及 Release 附件為準；只有對應 Release 已提供平台成品及 SHA256 時，該平台下載才有效。** 舊版通過紀錄不能套用到新包。

## 需要 Python 或網路嗎？

成品包含執行環境，不需另裝 Python。計算、專案及內建教學在本機使用；GitHub、外部參考資料及更新需要網路。

<a id="compatibility"></a>
## 支援哪些電腦？怎麼安裝？

- Windows x64：Windows 10／11 為支援目標；正式包須在 Windows Server 2022／2025 重驗。結果見對應 commit 的 CI 與 Release 附件，不宣稱 Windows ARM 或 32 位元已驗。
- Windows 安裝版：選新的空目錄，建立程式入口及卸載資訊。不可用它覆蓋已有資料的目錄。卸載按安裝清單處理，不應刪除使用者後建檔案。
- Windows portable：完整解壓後執行內部 EXE，不能只複製 EXE。portable 不表示所有資料都保存在程式旁。
- Mac：本版平台範圍只包含 Apple Silicon ARM64 ZIP，完整解壓後開啟 `Facility Studio 5.7.3.app`；不是 Universal、Intel 或 DMG。最終原生驗收、實測 macOS 與最低支援版本以[驗收頁](verification/5.7.3-release-acceptance.md)及最終 Release 為準，不沿用舊版 macOS 11+／Intel 宣稱。

企業政策及其他實機仍需個別確認。

<a id="v560-tools"></a><a id="pv"></a>
## PV、液體與其他工具在哪裡？

左側 12 項快算：電力配線、風管尺寸、CDA／特氣管徑、PV 真空、照明照度、冷熱水、液體／純水管路、空氣狀態／線圖、單位換算、潔淨室風量、熱負荷、冰水泵浦。PV 有獨立入口，不是正壓氣體選單選項，也不必先進完整工作台。

水管參考尺寸與氣體資料均有適用範圍；未知材料／物性不可直接沿用水，新增氣體需確認設計流速。見[水路](guides/water.md)與[氣體／真空](guides/gas-vacuum.md)。

<a id="results"></a>
## 計算成功就是設計通過嗎？

- 計算完成：可得到數值，仍要看容量及採用條件。
- 待補資料：原廠性能、物性、現場條件或覆核未完成。
- 未達條件：已知工況或容量不符合，需改條件並重算。
- 待重算／來源過期：結果不代表目前輸入；重算上游並明確重新帶入。

複製／匯出成功不會解除警告。AHU 需求點不等於實際供應；容量的已知小計不等於完整需求。設計審查的「文件齊備，可送工程審查」不驗證人員身分、簽章或工程合格。[設計審查指南](guides/design-review.md)

本工具可協助範圍內 FEED 初期計算及文件準備，不是 FEED、法規或設備性能認證。完整管網、保護協調、施工圖及現場驗收另行完成。

<a id="saving"></a>
## 資料、記錄、升級與回退

正式預設資料目錄：`~/Facility Studio Data-5.7.3`（Windows 的 `~` 為使用者家目錄，通常是 `%USERPROFILE%`）。啟動記錄位於該目錄的 `啟動與驗收記錄.log`；進階環境設定可改變資料根目錄，回報時說明是否有自訂。不要再依舊版 LOCALAPPDATA／Library 路徑尋找本次預設記錄。

- 整案 JSON、單機 AHU、容量計畫和設計審查有各自保存流程；工作台儲存整案不會保存獨立容量計畫。
- TXT／HTML 報告及直接照度結果 JSON 不是可重開的整案專案。
- 設計審查移機時帶走整個資料夾及 evidence 附件快照。
- 升級前備份並保留舊程式；新版本不自動搬移／覆寫舊資料。明確匯入副本、重算及核對再使用。
- 回退使用舊程式和其原備份，不假設舊版本可讀新格式；勿用舊版覆寫新版專案。

<a id="security"></a>
## 為何有安全提示？

Windows 可信發行者簽章或 Mac Developer ID／Apple 公證須有對應成品的驗證證據，不能由版本名稱推定。Mac ad-hoc 完整性檢查不是發行者認證。核對來源、版本及正式公布的 SHA256，依公司政策處理；不要關閉防毒、Gatekeeper 或系統保護。[安全提示](signing.md)

<a id="decimal"></a>
## 鍵盤小數點或視窗異常怎麼辦？

確認版本、欄位是否可編輯、Num Lock 與輸入法。回報鍵盤型號、視窗、縮放、預期及實際動作。歷史小數點修正見[舊版記錄](2026-10-11-v5.5.10-keypad.md)，不代表本次每一台電腦已驗。

<a id="first-project"></a><a id="equipment"></a>
## 第一次使用／設備表匯入

先做[單一工具或跟做案](guides/workbench.md)。設備表先匯出範本，將要納入的列設為啟用；使用指定 `.xlsx`／`.csv` 結構，公式先貼上值，不接受任意 `.xls`／巨集檔。帶入前預覽並確認。[設備指南](guides/equipment.md)

<a id="license"></a>
## 公司與收費工程案

以 [LICENSE](../LICENSE) 為準；允許範圍與軟體轉售／服務限制見[授權案例](../LICENSE_GUIDE.md)。正式版名稱不改變授權。

<a id="support"></a>
## 問題回報

到 [Issues](https://github.com/azx4121/facility-studio/issues) 提供版本、OS／CPU、步驟、輸入／單位、預期與實際結果及必要記錄。先移除機密、個人路徑與客戶資料。

歷史 win.6+ ledger v2 與 mac.6 的不相容僅屬舊版紀錄；不能據此判斷 5.7.3 跨平台資料相容性，仍需同版本讀回驗收。

正式入口在內部設定專屬資料變數 `FACILITY_STUDIO_DATA`，不改寫系統 `LOCALAPPDATA`；這不是使用者預先設定該變數即可覆寫預設路徑的承諾。 / The entry sets the dedicated `FACILITY_STUDIO_DATA` variable internally without rewriting system `LOCALAPPDATA`; this does not promise that presetting that variable overrides the default.
