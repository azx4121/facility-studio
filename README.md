# Facility Studio｜廠務工程初估工具

繁體中文的通用廠務工具，適合快速估算、方案比較及設備需求彙整。目前為 **V5.5.4 公開測試版**；Windows 請下載 **win.1 離線直接執行版**，macOS 請下載 **mac.2 修正版**。兩者皆包含目前安全與授權維護；既有 Release 與歷史提交保留。

## 下載

| 平台 | 懶人包 | 使用條件 |
| --- | --- | --- |
| Windows（完整包） | [下載 win.1 離線懶人包](https://github.com/azx4121/facility-studio/releases/download/v5.5.4-win.1/Facility_Studio_V5_5_4_Windows_Offline_OneClick.zip) | 目標 Windows 10／11、Intel／AMD x64；解壓縮後直接開啟 EXE，不需另裝 Python／套件、不需連網 |
| Windows（單檔） | [直接下載 win.1 EXE](https://github.com/azx4121/facility-studio/releases/download/v5.5.4-win.1/Facility_Studio_V5_5_4_Windows_Offline.exe) | 已內含執行環境；可單獨執行，不需安裝流程 |
| macOS（建議） | [下載 mac.2 DMG](https://github.com/azx4121/facility-studio/releases/download/v5.5.4-mac.2/Facility_Studio_V5_5_4_macOS_mac2.dmg) | 拖到「應用程式」安裝；已含執行環境，Apple Silicon／Intel 原生驗證 |
| macOS（完整包） | [下載 mac.2 ZIP 懶人包](https://github.com/azx4121/facility-studio/releases/download/v5.5.4-mac.2/Facility_Studio_V5_5_4_macOS_mac2_OneClick.zip) | 另含原始碼、設備表範本與診斷腳本 |

也可以到 [Releases 發布頁](https://github.com/azx4121/facility-studio/releases) 選擇版本。

## 安裝與開啟

### Windows

1. 完整解壓縮 **win.1 離線懶人包**。
2. 雙擊 `Facility_Studio_V5_5_4_Windows_Offline.exe`。
3. 不需另裝 Python、不需安裝套件、不需連網；首次啟動請等候內建套件展開。

也可直接下載單檔 EXE 使用；ZIP 另含原始碼、設備需求範本、授權與診斷腳本。
不需管理員權限。若啟動失敗，可執行 `Verify_on_Windows.cmd`，記錄位於 `%LOCALAPPDATA%\Facility_Studio_V5_5\Logs`。
本版尚無商用程式碼簽章，Windows 安全性或公司政策可能攔下；請確認官方下載來源與 SHA256，勿關閉防毒。
舊 `v5.5.4-beta.1` 的 `Setup.exe` 線上安裝方式完整保留，新版不使用它。

### macOS

1. 下載並打開 **mac.2 DMG**。
2. 把 `Facility Studio` 拖到旁邊的 `Applications／應用程式`。
3. 從「應用程式」開啟；不需另裝 Python 或 Homebrew。
4. 首次若提示開發者無法驗證，先嘗試開啟，再到「系統設定 → 隱私權與安全性 → 仍要打開」，依 [Apple 官方指引](https://support.apple.com/en-us/102445) 確認。

本版通過 Apple 原生完整性簽章檢查，但使用 ad-hoc 簽章，沒有 Developer ID／Apple 公證。企業管理的 Mac 可能需要 IT 允許。
ZIP 也可完整解壓縮後直接開啟 App，或執行 `Install_on_Mac.command` 安裝到使用者應用程式資料夾。請先關閉舊版；更新不會刪除專案與復原資料。
舊 mac.1 原始包在 Apple 原生檢查中失敗，請改用 mac.2；[修正與驗證紀錄](docs/2026-10-06-macos-repair.md) 保留重現證據。

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

已完成數值情境、報告反算及 Linux 的實際 Tk 介面回歸測試，以及 Windows 安裝器檔案檢查。

mac.2 發布須通過 **Apple Silicon 與 Intel macOS 15 原生雲端驗證**：Apple 深度簽章、Tk Aqua、七種獨立工具、設備表匯入、完整工作台與 Matplotlib 繪圖。實際交付 ZIP 重新解壓縮、DMG 掛載後再次驗證。

Windows win.1 發布須通過 Windows Server 2022／2025 x64 原生雲端驗證：同一份 EXE 與解壓縮 ZIP，外部 Python 移出 PATH、EXE 對外連線被防火牆封鎖後，仍完成七種工具、設備表、原生 Tk 與完整工作台驗收。Windows10／11 為支援目標，使用者實機、企業政策與實體數字鍵盤仍須個別確認。

封裝目標為 macOS 11 以上；macOS 11～14、macOS 27 Beta、Finder 下載隔離提示、企業管理政策、實體鍵盤／觸控板及 Retina 視覺仍須使用者電腦確認。
macOS ZIP 包含 `Verify_on_Mac.command`，可產生本機驗收與錯誤記錄；不會上傳資料或更動既有工程專案。

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

## 原始碼與授權

Windows 原始碼位於 [windows](windows/)；macOS 原始碼位於 [macos](macos/)。
各平台的啟動檔為 `Facility_Studio_V5_5.py`，請保留同層的 `facility_studio` 資料夾與資源檔。
測試與驗證紀錄分別保留於各平台的 `tests/` 與 `evidence/`；Windows 安裝器位於 `windows/installer/`，macOS 封裝腳本位於 `macos/macos/`。

目前原始碼採 [PolyForm Noncommercial 1.0.0＋公司內部使用附加許可](LICENSE)，保留 Andy Huang 及貢獻者版權標示。
**允許公司用於正常工程工作、收費案件及交付計算書；軟體轉售、付費包裝、綁售及付費線上軟體服務須另行取得書面授權。**
非商業測試與免費分享仍可進行；完整範圍及案例見 [授權說明](LICENSE_GUIDE.md)。此為公開原始碼的限制性授權，不能稱為 MIT 或 OSI 開源授權。
先前已按 MIT 發布的版本（含 `f8e92ea`）仍保有原授權；歷史條文見 [LICENSE_LEGACY_MIT](LICENSE_LEGACY_MIT)。
第三方執行環境及套件保留各自的原有授權文件，詳 [第三方元件說明](THIRD_PARTY_NOTICES.md)。

本次維護修正低溫露點反算、大氣壓防呆與工程資料表驗證，詳 [測試與修正紀錄](docs/2026-10-06-review.md)。mac.2 與 Windows win.1 包含這些修正。歷史 Release、資產與標籤保留。

### 執行數值回歸測試

在專案根目錄使用已安裝的 Python 3：

```sh
python windows/tests/regression.py
python windows/tests/v55_features.py
python windows/tests/v552_core.py
python windows/tests/simple_features.py
python windows/tests/v554_features.py
python windows/tests/maintenance_checks.py
python windows/tests/security_checks.py
```

macOS 原始碼測試將路徑中的 `windows/` 改為 `macos/`；若系統指令名稱為 `python3`，請使用 `python3`。
測試會更新各平台 `evidence/` 內的驗證紀錄。介面回歸另需可用的 Tk 顯示服務及測試用 Pillow／Matplotlib；數值測試無需先開啟 GUI。

安全與授權維護：XML 於解析器層阻擋 DTD／實體；JSON 限制檔案大小、64 層深度，拒絕重複欄位與非有限數值。測試記錄見 [維護紀錄](docs/2026-10-06-security-license.md)。
