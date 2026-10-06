# Facility Studio｜廠務工程初估工具

繁體中文的通用廠務工具，適合快速估算、方案比較及設備需求彙整。目前發布版本為 **V5.5.4 公開測試版**。

## 下載

| 平台 | 懶人包 | 使用條件 |
| --- | --- | --- |
| Windows | [下載 Windows 懶人包](https://github.com/azx4121/facility-studio/releases/download/v5.5.4-beta.1/Facility_Studio_V5_5_4_OneClick.zip) | 目標 Windows 10／11、Intel／AMD x64；首次安裝需要連網 |
| macOS | [下載 macOS 懶人包](https://github.com/azx4121/facility-studio/releases/download/v5.5.4-beta.1/Facility_Studio_V5_5_4_macOS_OneClick.zip) | 目標 macOS 11 以上、Apple Silicon 與 Intel；已內含 Python 執行環境 |

也可以到 [Releases 發布頁](https://github.com/azx4121/facility-studio/releases) 選擇版本。

## 安裝與開啟

### Windows

1. 完整解壓縮 Windows 懶人包。
2. 執行 `Facility_Studio_V5_5_4_Setup.exe`。
3. 首次安裝保持連網，安裝器會下載所需執行環境與套件，並在 Windows 建立應用程式。
4. 完成後從桌面捷徑開啟；日常計算可離線使用。

### macOS

1. 完整解壓縮 macOS 懶人包。
2. 開啟 `Facility Studio.app`，不需另裝 Python 或 Homebrew。
3. 想安裝至使用者應用程式資料夾，可執行 `Install_on_Mac.command`。
4. 本版尚未完成 Apple Developer ID 簽署與公證；首次若被系統攔下，依 [Apple 官方開啟指引](https://support.apple.com/en-us/102445) 處理。

## 可以做什麼

| 功能 | 輸入與結果 |
| --- | --- |
| 電力配線 | 設備 kW、電壓與使用條件 → 電流、NFB 與線徑候選 |
| 方管／圓管 | 風量與流速條件 → 尺寸與實際風速；已知路徑時可進一步檢查壓損 |
| CDA／特氣 | 流量、管內壓力與流速 → 實際流量與參考管徑 |
| 照明照度 | 空間面積或體積、燈具資料 → 平均照度，或反算所需盞數 |
| 冷熱水 | 水量、熱量與溫差換算，以及管徑初估 |
| 空氣狀態 | 溫濕度 → 焓、含濕比、露點、濕球與即時空氣線圖 |
| 單位換算 | 常用工程單位，包含溫度與溫度差的分別換算 |
| 設備表匯入 | Excel／CSV 分析電力、PCW、CDA、N2、EXHAUST、DI、PV 的設備需求 |
| 完整工程工作台 | 主案與多台空調箱；夏冬逐段預熱、預冷、水洗加濕、再冷、再熱，以及熱源配置 |

各工具可獨立使用。進階條件與採用的預設值可查看、調整；報告包含條件、結果及公式。
設備範本內的示例預設未啟用，要納入計算的設備請將「啟用(1/0)」設為 1。

## 測試狀態與適用範圍

已完成數值情境、報告反算及 Linux 的實際 Tk 介面回歸測試；另外完成 Windows 安裝器檔案檢查與 macOS 封裝靜態檢查。

**Windows／Mac 的完整實機安裝與操作驗收仍待完成。上述檢查不代表已在兩種作業系統的實機全部通過。**
macOS 懶人包包含 `Verify_on_Mac.command`，可在 Mac 上產生本機驗收記錄。

工程結果用於初估與方案比較。電氣短路與保護協調、完整管網、真空導通、設備性能選型及正式工程設計，仍需依現場條件、設備資料與適用規範覆核。
詳細驗證與限制請查看懶人包內說明及原始碼驗證資料。

## 回報問題

請到 [Issues 問題回報](https://github.com/azx4121/facility-studio/issues)，按 **New issue**。
為了重現問題，請提供：

- 軟體版本、作業系統版本與 CPU 架構。
- 使用哪一個工具，以及操作步驟。
- 完整輸入數值與單位。
- 預期結果、實際結果或錯誤訊息。
- 必要的畫面截圖；工程計算問題請附上反算方式。

回報範例請使用測試資料，移除業主或現場的機密資訊。

## 原始碼與授權進度

完整原始碼與測試紀錄已隨懶人包提供，請解壓縮其中的原始碼 ZIP 查閱。
GitHub 的 Code 原始碼上架與專案 LICENSE 尚待補齊；在明確授權完成前，不應把此專案視為已授予開源授權。
第三方執行環境及套件保留各自的原有授權文件。
