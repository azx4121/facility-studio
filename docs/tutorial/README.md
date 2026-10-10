# 離線新手教學與可開啟練習案

[中文跟做教學](../guides/workbench.md) · [English walkthrough](../guides/workbench.en.md) · [離線包](https://github.com/azx4121/facility-studio/raw/refs/heads/main/docs/tutorial/Facility_Studio_Beginner_Tutorial.zip)

一般使用者只需下載 ZIP、完整解壓縮、雙擊 `START_HERE.html`。教學不需 Python、套件或連網。HTML 可中英切換、逐步導覽、勾選學習進度或列印；讀取外部 GitHub 連結時才需網路。進度儲存在瀏覽器本機，未提供回傳或分析服務。

V5.5.7 建議從程式「完整工程工作台 → 開啟練習新案」選擇練習，程式會建立新案。修改後按「儲存整案」選擇自己的檔名。若使用舊版，先複製改名練習 JSON，再開啟副本。

必要教學只有六步：選工具、認識介面、開啟第一案、填條件、閱讀結果、儲存及匯出。空調箱、設備匯入、迴路彙總及各小工具是選讀章節；勾選進度代表您已閱讀，不代表工程驗證通過。

| 檔案 | 用途 |
| --- | --- |
| `START_HERE.html` | 自包含中英逐步操作教學；示意圖已內嵌 |
| `01_Practice_AHU.json` | 96 m² 混風 AHU 一般作業區，先跟這份 |
| `02_Practice_MAU_and_AHU.json` | 同面積全外氣 MAU／FFU／DCC 主案，含一台分段空調箱 |
| `01_Expected_Report.txt`／`.en.txt` | 第一案的中文／英文原模型報告 |
| `02_Expected_AHU_Report.txt`／`.en.txt` | 第二案單機分段校核對照報告 |
| `expected-results.json` | 未取整的摘要值及回傳預覽欄位 |
| `LICENSE` 等 | 現有授權條款，未因教學改變 |

`workbench-map.svg`／`.en.svg` 是按程式控制項整理的**操作位置示意圖，不是 GUI 截圖**。教學不是安裝器。V5.5.7 的來源彙總、互鎖及新手操作同步見[修訂與測試記錄](../2026-10-07-v5.5.6-usability.md)；V5.5.5 win.2／mac.2 的署名及教學入口歷史驗證仍保留。

## 數值及報告重現

以下指令僅供開發者；一般使用者不需執行。

```sh
python docs/tutorial/verify_tutorial.py --platform windows --output tutorial-windows.json
python3 docs/tutorial/verify_tutorial.py --platform macos --output tutorial-macos.json
```

Windows 與 macOS 原始碼各通過 20 種條件、87 項檢查，包括面積／淨高／人數、照明、顯熱、三種製程水氣模式、CDA 最低壓力、PV 三單位、停用需求、連動／獨立水量、ΔT、水側路徑及設備壓差、MAU 主案連動、單機守恆、容量不足與結構化錯誤欄位。中文／英文對照報告也重新比對。

[Windows 驗證](verification-windows.json) · [macOS 驗證](verification-macos.json)。數值檢查在目前主機執行；新增入口、最小視窗署名及實際練習案載入另在兩平台原生交付流程驗收，本版見[V5.5.7 修訂與驗收](../2026-10-07-v5.5.6-usability.md)，舊版見[教學入口修訂記錄](../2026-10-07-beginner-tutorial.md)。本例「待補資料」是刻意保留未知設備條件，不是正式設計合格證明。

## English

Extract the ZIP and open `START_HERE.html` in a browser. In V5.5.7 use Full workbench → Open practice copy, then Save workspace under your own file name. On older versions, copy and rename the practice workspace before opening it. The guide is offline; only external GitHub links need internet. Progress stays in local browser storage.

The source-platform verifier checks 20 operation-related conditions and 87 assertions per platform. Native delivery checks separately exercise the tutorial buttons, visible author credit at minimum window size and actual workbench practice loading. Synthetic examples leave missing manufacturer/site data pending.
