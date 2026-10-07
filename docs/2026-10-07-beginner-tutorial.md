# V5.5.5 修訂 2：新手教學與簡易工具署名

[新手教學](guides/workbench.md) · [English walkthrough](guides/workbench.en.md) · [離線教學懶人包](https://github.com/azx4121/facility-studio/raw/refs/heads/main/docs/tutorial/Facility_Studio_Beginner_Tutorial.zip) · [目前下載](../README.md#下載)

**Windows `v5.5.5-win.2` 與 macOS `v5.5.5-mac.2` 已通過原生交付驗收並公開發布。** 首頁下載入口已更新；所有既有提交、標籤、Release 及授權條款保留。舊的下載檔不會自動增加新功能，請關閉舊版後下載本次修訂。

簡易工具原本沒有建立作者署名元件，只有完整工作台顯示。本修訂補上左下角 **DESIGNED BY ANDY HUANG ©**，七種工具切換時保留；原完整工作台署名與 FY 圖示也保留。工程公式及現有專案格式沒有變更。

## 新手教學

簡易工具、完整工作台及分段空調箱新增「新手教學」入口，開啟隨軟體附帶的本機 HTML，並採用目前中英文設定；不依賴網路。工作台入口直接到第一份練習，空調箱入口直接到分段教學。

教學採十個短章節，第一輪只需前六節。附兩份可由工作台「開啟」的合成整案、中英文對照報告及操作位置示意圖。示意圖不是軟體截圖；教學說明主案保存、報告與驗算 JSON 的差別，以及潛熱、獨立／連動水量、簡易壓損、MAU 連動限制和回傳取代行為。

完整 Windows／macOS ZIP 都包含 `Beginner_Tutorial` 資料夾。也可單獨下載教學 ZIP，完整解壓縮後開啟 `START_HERE.html`；較早 V5.5.5 可直接閱讀。軟體中的教學資源依內容雜湊分開存放於本機，重開不覆寫已有練習檔。

練習案的結果刻意保留「待補資料」及缺少的設備條件；不將尚未完成選型的初估案標成合格。

## 已完成的驗收

| 檢查 | 結果 |
| --- | --- |
| Windows 原始碼教學條件 | 20 種、85 項通過 |
| macOS 原始碼教學條件 | 20 種、85 項通過 |
| 中英資料、匯入及保存回歸 | 每平台 20 種、3,509 項通過 |
| 既有公開操作案例 | 每平台 18 個計算＋2 個不適用對照、121 項通過 |
| Windows Server 2022 x64 | 單檔 EXE、ZIP 解壓縮、中文 EXE 路徑各 92 項通過 |
| Windows Server 2025 x64 | 同一批交付檔，以上三種方式各 92 項通過 |
| macOS 15 Apple Silicon | 84 項通過，另驗證 Launch Services、交付 DMG 與 Apple 原生簽章 |
| macOS 15 Intel | 同一 ZIP／DMG，84 項通過及 Apple 原生簽章驗證 |

原生檢查直接測試最小 780×560 視窗的署名與教學入口、教學只開本機檔案並跟隨語言、兩份練習隨包完整、第一案載入實際 Tk 工作台後重算，以及第九個設計報告頁可見。測試亦確認練習載入後還原原先已儲存／未儲存狀態。正常操作仍保留關閉前的儲存詢問。

Windows 的單檔及 ZIP 測試移除外部 Python PATH、使用空工作目錄，並同時封鎖 EXE 對外連線及 socket 連線；額外中文 EXE 路徑使用 socket audit，沒有宣稱該額外路徑也套用防火牆。Mac 的 ZIP 重新解壓縮與 DMG 掛載後驗證，發布檔雜湊與原生交付檔一致。

- [Windows 原生工作流程](https://github.com/azx4121/facility-studio/actions/runs/37608078452)
- [macOS 原生工作流程](https://github.com/azx4121/facility-studio/actions/runs/37607419210)
- [交付驗證摘要及公開檔案 SHA256](tutorial/native-delivery-verification.json)
- [Windows 教學 20 種條件](tutorial/verification-windows.json)／[macOS 教學 20 種條件](tutorial/verification-macos.json)

重複執行同一原生檢查不算新增不同工程條件。教學的前後步、語言、進度保存／重設及列印入口另做 14 項 JavaScript 事件檢查，使用最小 DOM 模擬，不能代替實際瀏覽器的畫面驗收。

## 公開交付檔

| 檔案 | 大小（bytes） | SHA256 |
| --- | ---: | --- |
| `Facility_Studio_V5_5_5_Windows_Offline.exe` | 40408194 | `df8fbab8ddc7a7f1b482e554376453e2ca37d989ffb7fea8e4a2b30da8cf6384` |
| `Facility_Studio_V5_5_5_Windows_Offline_OneClick.zip` | 40605913 | `cb700470602ef7eaeb02e3a83fd6469d6c1c9397c9255314db81f996ccb04d0b` |
| `Facility_Studio_V5_5_5_macOS_mac2.dmg` | 146875182 | `c70c8c55492c5911ef925d2293f814fe206b88ee541307bc9b0467201cbb3c52` |
| `Facility_Studio_V5_5_5_macOS_mac2_OneClick.zip` | 94617627 | `0a8e20471697d6e831883f23c0e5ba6542be7e030e0cec20514cceacf6a03e98` |

Windows 發布提交：`d3824c66157081d0e159342e55f82aee85ffbdc4`。macOS 發布提交：`dc508ec6d48c4343ebd613b5c62fe1b29a863c02`。兩者均為原生驗收通過的原始碼；後續首頁／文件更新不會替換已公開的二進位檔。

本次未變更授權。Windows 尚無商用程式碼簽章；macOS 使用 ad-hoc 完整性簽章，沒有 Developer ID／Apple 公證。Windows 10／11 是支援目標；macOS 11 以上是封裝目標，本次原生環境為上述 Server／macOS 15，並未宣稱每部使用者實機、企業政策、鍵盤或 Retina 畫面皆完成驗收。

## English

**Revision 2 is published as `v5.5.5-win.2` and `v5.5.5-mac.2`.** It restores persistent **DESIGNED BY ANDY HUANG ©** credit to the simple tools and adds bundled offline tutorial buttons to the simple home, full workbench and AHU window. The local guide follows the selected language and contains two synthetic reopenable practice workspaces with bilingual reference reports. Existing engineering formulas, project formats, licensing terms, commits and releases are preserved.

Each source platform passed 20 tutorial conditions / 85 assertions, 20 language-parity conditions / 3,509 checks, and 121 public-example checks. Native Windows Server 2022 and 2025 each passed 92 checks for the standalone EXE, extracted ZIP and Unicode-path execution. Apple Silicon and Intel macOS 15 each passed 84 native GUI checks; the delivered ZIP, DMG, Launch Services and Apple integrity signatures were also verified.

The published asset digests match the tested deliveries and are recorded above. HTML controls passed 14 JavaScript event checks using a minimal DOM mock; that check is not a rendered-browser acceptance. Packaging targets, signing limitations and individual-device checks remain as described in the download instructions. Earlier binaries do not update automatically: download this revision, or use the standalone offline tutorial with an earlier V5.5.5 installation.
