# 離線教學與練習專案

[首頁與下載](../../README.md) · [中文跟做教學](../guides/workbench.md) · [English](#english)

**V5.5.8 已內建教學，日常使用不必另外下載教學包。**

簡易工具按「本工具教學」可看目前工具；完整工作台按「新手教學」可跟做第一份報告。教學左側附練習檔案，先完成前六步，其餘章節按需要閱讀。

## 不開軟體，也可以先看教學

[下載離線教學包](https://github.com/azx4121/facility-studio/raw/refs/heads/main/docs/tutorial/Facility_Studio_Beginner_Tutorial.zip)，完整解壓縮後用瀏覽器開啟 `START_HERE.html`。不需 Python 或套件；只有外部 GitHub 連結需要網路。

可切換中英文、逐步閱讀或列印。勾選進度只代表已閱讀，存在本機瀏覽器，不代表工程驗證通過。

## 練習檔怎麼選？

| 檔案 | 用途 |
| --- | --- |
| `01_Practice_AHU.json` | 96 m² 混風 AHU 一般作業區，先跟這份完成第一份報告 |
| `02_Practice_MAU_and_AHU.json` | 同面積全外氣 MAU／FFU／DCC 主案，含一台分段空調箱 |
| `01_Expected_Report.txt`／`.en.txt` | 第一案的中英文對照報告 |
| `02_Expected_AHU_Report.txt`／`.en.txt` | 第二案單機的中英文對照報告 |
| `expected-results.json` | 對照用摘要值與回傳預覽 |
| `LICENSE` 等 | 現有授權條款 |

第一案可從教學左側下載，再用工作台「開啟」及「另存新檔」保存自己的副本。「開啟練習新案」則直接載入**第二案**，建立新的案件身分；修改後用「儲存整案」保存。

案例是合成練習配置，刻意保留未知原廠性能與現場條件。「待補資料」需要補真實資料，計算完成不代表正式選型合格。`workbench-map.svg`／`.en.svg` 是控制項位置示意圖，並非 GUI 截圖。

## 驗證與原始資料

[Windows 教學檢查](verification-windows.json) · [macOS 教學檢查](verification-macos.json) · [V5.5.8 原生交付](../2026-10-10-v5.5.8-native.md)

<details>
<summary>開發者：重現教學數值與報告</summary>

```sh
python docs/tutorial/verify_tutorial.py --platform windows --output tutorial-windows.json
python3 docs/tutorial/verify_tutorial.py --platform macos --output tutorial-macos.json
```

每個來源平台各有 20 情境／87 檢查，包含工作台條件、設備與水路、空調箱守恆及容量檢核；中文／英文報告另完整比對。來源數值檢查與原生按鈕、署名及練習載入驗收分開記錄。

</details>

<a id="english"></a>
## English

V5.5.8 includes offline help. Use **This tool's guide** in a calculator or **Full workbench → Beginner tutorial** for a first report. Complete the first six sections; additional chapters are optional.

To read without launching the app, download the tutorial package above, extract it, and open `START_HERE.html` in a browser. No Python is needed. Progress records reading in local browser storage; only external links need internet.

Start with `01_Practice_AHU.json`, available from the tutorial sidebar, and save your own copy. **Open practice copy** directly loads the second MAU/staged-AHU example with a new project identity. All examples are synthetic and leave unconfirmed manufacturer/site conditions pending.

**DESIGNED BY ANDY HUANG ©**
