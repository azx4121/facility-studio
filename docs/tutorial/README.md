# 離線新手教學與可開啟練習案

[中文跟做教學](../guides/workbench.md) · [English walkthrough](../guides/workbench.en.md) · [離線包](Facility_Studio_Beginner_Tutorial.zip)

一般使用者只需下載 ZIP、完整解壓縮、雙擊 `START_HERE.html`。教學不需 Python、套件或連網。HTML 可中英切換、逐步導覽、勾選學習進度或列印；讀取外部 GitHub 連結時才需網路。進度儲存在瀏覽器本機，未提供回傳或分析服務。

先**複製改名**練習 JSON，再由 Facility Studio「完整工程工作台 → 開啟」選擇複製檔；儲存整案會寫回目前開啟檔案。

| 檔案 | 用途 |
| --- | --- |
| `START_HERE.html` | 自包含中英逐步操作教學；示意圖已內嵌 |
| `01_Practice_AHU.json` | 96 m² 混風 AHU 一般作業區，先跟這份 |
| `02_Practice_MAU_and_AHU.json` | 同面積全外氣 MAU／FFU／DCC 主案，含一台分段空調箱 |
| `01_Expected_Report.txt`／`.en.txt` | 第一案的中文／英文原模型報告 |
| `02_Expected_AHU_Report.txt`／`.en.txt` | 第二案單機分段校核對照報告 |
| `expected-results.json` | 未取整的摘要值及回傳預覽欄位 |
| `LICENSE` 等 | 現有授權條款，未因教學改變 |

`workbench-map.svg`／`.en.svg` 是按程式控制項整理的**操作位置示意圖，不是 GUI 截圖**。教學不是新安裝器，也沒有修改既有工程模型；程式內署名及教學入口從 V5.5.5 win.2／mac.2 修訂起提供。

## 數值及報告重現

以下指令僅供開發者；一般使用者不需執行。

```sh
python docs/tutorial/verify_tutorial.py --platform windows --output tutorial-windows.json
python3 docs/tutorial/verify_tutorial.py --platform macos --output tutorial-macos.json
```

Windows 與 macOS 原始碼各通過 20 種條件、85 項檢查，包括面積／淨高／人數、照明、顯熱、三種製程水氣模式、CDA 最低壓力、PV 三單位、停用需求、連動／獨立水量、ΔT、水側路徑及設備壓差、MAU 主案連動、單機守恆、容量不足與結構化錯誤欄位。中文／英文對照報告也重新比對。

[Windows 驗證](verification-windows.json) · [macOS 驗證](verification-macos.json)。數值檢查在目前主機執行；新增入口、最小視窗署名及實際練習案載入另在兩平台原生交付流程驗收，見[修訂記錄](../2026-10-07-beginner-tutorial.md)。本例「待補資料」是刻意保留未知設備條件，不是正式設計合格證明。

## English

Extract the ZIP and open `START_HERE.html` in a browser. Copy and rename a practice workspace before opening it in the application's Full workbench. The guide is offline; only external GitHub links need internet. Progress stays in local browser storage.

The source-platform verifier checks 20 operation-related conditions and 85 assertions per platform. Native delivery checks separately exercise the tutorial buttons, visible author credit at minimum window size and actual workbench practice loading. Synthetic examples leave missing manufacturer/site data pending.
