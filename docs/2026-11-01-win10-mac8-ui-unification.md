# win.10／mac.8：兩平台畫面一致（2026-11-01）

起因：用戶回報開啟 mac.7 的畫面與 GitHub 說明圖片（win.8 原生圖）不同，並要求網頁圖片等於實際開啟的畫面、Windows 與 macOS 的介面一致，且以 macOS 畫面為準。

## 比對方法與結果

用 `tools/capture_native_ui.py`（工作流程 `capture-native-ui.yml`）在原生桌面啟動**已發布**的 win.9 EXE 與 mac.7 DMG（Windows Server 2022、macOS 15；只預先寫入語言偏好檔），擷取視窗，中英文各一張（[run 41272257213](https://github.com/azx4121/facility-studio/actions/runs/41272257213)）。並排比對：

| 項目 | win.9 | mac.7 |
| --- | --- | --- |
| 文字大小（同一視窗） | 較大（1 pt＝1.33 px；10 pt 行高 17 px） | 較小（1 pt＝1 px；10 pt 行高 13 px） |
| 首頁可見內容 | 較少：「調整預設值」核取框落在可視範圍外、儀表卡片被截 | 較多 |
| 完整工作台導覽 | tk 按鈕、自動換行 | ttk 樣式、選取粗體 |
| 字型／視窗外框 | Microsoft JhengHei UI／Consolas，Windows 外框 | PingFang TC／Menlo，macOS 外框 |

程式碼層面：兩平台共用同一份簡易工具與 `clam` 主題；差異來自 Tk 點數換算與完整工作台導覽元件。

## 修正

- `platform_support.normalize_tk_scaling`：所有平台採用 macOS 的換算，再乘以系統回報的顯示縮放（dpi／96，最小 1），每個 Tk 直譯器只套用一次。
- `uses_ttk_navigation` 在所有平台為真，完整工作台導覽兩平台相同。
- 新增 `ui_scaling_checks`（72／96／144 dpi 的 10 pt 文字尺寸、重複呼叫不變）；macOS 樹新增 `text_clipping_checks`（90/90，Linux Tk 版面尺寸）。

## 驗證與限制

- 分支原生驗收：Windows（[run 41272844846](https://github.com/azx4121/facility-studio/actions/runs/41272844846)）通過；macOS（[run 41272847017](https://github.com/azx4121/facility-studio/actions/runs/41272847017)）Apple Silicon 建置通過，Intel 第一次因 UI 互動效能預算 5.04 秒對 5 秒失敗，未放寬門檻、重跑通過。
- 兩平台的字型與視窗外框由系統提供，不會逐像素相同；「一致」指文字大小、版面、導覽元件與顏色。
- 實體 Windows 在 125 %／150 % 縮放下的外觀、實體 Mac 均未確認。
- Windows 的文字比 win.9 小，是為了符合用戶要求（以 macOS 畫面為準）。
- `windows/tests/v552_interactions.py` 在 main 上本來就失敗（風機數量提示斷言，不在 CI 清單），與本次修改無關。
