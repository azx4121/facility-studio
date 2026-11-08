# 離線教學與練習專案

[首頁與下載](../../README.md) · [中文跟做教學](../guides/workbench.md) · [English](#english)

**Facility Studio 5.7.3 成品內建教學，日常使用不必另外下載教學包。此版本的原生驗收與各平台發布狀態，以對應 commit 的 CI 紀錄及 Release 附件為準；只有對應 Release 已提供平台成品及 SHA256 時，該平台下載才有效。**

本次修訂對照 5.7.3 來源操作，新增完整空氣線圖、直接照度配置、容量／擴建規劃，以及輸入變更後的重算／匯出規則。Windows 與 macOS 來源使用相同章節；本教學不代表舊下載檔已具備候選功能，也不代表原生交付已驗收。

簡易工具按「本工具教學」可看目前工具；完整工作台按「新手教學」可跟做第一份報告。教學左側附練習檔案，先完成前六步，其餘章節按需要閱讀。

## 先看操作流程

![先確認版本、另存練習、填條件、重算、讀狀態、保存匯出](../images/diagrams/workflow.zh.svg)

本圖是操作示意，不是新成品截圖。詳細說明見[圖解導覽](../visual-tour.md)及[安裝與起步](../getting-started.md)。現有離線 ZIP 的內容與雜湊保持不變；本次新增圖解供 GitHub 文件閱讀。

## 不開軟體，也可以先看教學

[Windows 5.7.3 教學包](Facility_Studio_Beginner_Tutorial_Windows.zip)／[macOS ARM64 5.7.3 教學包](Facility_Studio_Beginner_Tutorial_macOS.zip)。完整解壓縮後用瀏覽器開啟 `START_HERE.html`。新增液體／純水與保溫、PV 真空及潔淨室 ACH／MAU 章節。不需 Python 或套件；只有外部連結需要網路。

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

本版對照報告：Windows 的[第一案](windows/01_Expected_Report.txt)／[第二案空調箱](windows/02_Expected_AHU_Report.txt)，macOS 的[第一案](macos/01_Expected_Report.txt)／[第二案空調箱](macos/02_Expected_AHU_Report.txt)。各平台 ZIP 使用對應的新報告；教學根目錄舊報告及通用 ZIP 保留作歷史資料。

案例是合成練習配置，刻意保留未知原廠性能與現場條件。「待補資料」需要補真實資料，計算完成不代表正式選型合格。舊 `workbench-map.svg`／`.en.svg` 保留作歷史位置示意，不是本候選版 GUI 截圖；現行教學以按鈕名稱與操作表定位。

## 驗證與原始資料

[歷史交付狀態（731e416，不是本候選版驗收）](../../handoff/STATUS.json) 僅記錄先前提交與交付；其中的完成標示、路徑及 CI 不適用於本次整合候選版。現行驗收須核對本次分支的實際提交與成品，不能沿用舊狀態判定完成。其他歷史紀錄：[Windows 教學檢查](verification-windows.json) · [macOS 教學檢查](verification-macos.json) · [Windows win.8 原生交付](../2026-10-18-windows-report-audit.md) · [mac.6 原生交付](../2026-10-16-gemini-integration-review.md)。

<details>
<summary>開發者：重現教學數值與報告</summary>

```sh
python docs/tutorial/verify_tutorial.py --platform windows --output tutorial-windows.json
python3 docs/tutorial/verify_tutorial.py --platform macos --output tutorial-macos.json
```

教學驗證各平台包含20情境／93檢查：工作台條件、設備與水路、空調箱守恆及容量，並完整比對中文／英文報告與內建ZIP修訂。實際執行結果以本候選版驗收證據為準；數值檢查與原生介面驗收分開記錄。

</details>

<a id="english"></a>
## English

[Visual workflow](../visual-tour.en.md#workflow) · [Installation and first run](../getting-started.en.md). The illustration above is a documentation diagram, not a new binary screenshot. Existing offline ZIP contents and hashes are unchanged; these new diagrams are for the GitHub documentation.

Facility Studio 5.7.3 includes updated offline help. Native acceptance and platform publication status are determined by CI records and Release evidence for the exact source commit. A platform download is valid only when its matching Release provides the package and SHA256. Full psychrometric charts, direct-lighting layouts, capacity/expansion plans and stale-result handling are covered in both languages. This does not establish that older downloads include the features or that native delivery has passed acceptance. Use **This tool's guide** in a calculator or **Full workbench → Beginner tutorial** for a first report. Complete the first six sections; additional chapters are optional.

To read without launching the app, download the Windows or macOS ARM64 tutorial package above, extract it, and open `START_HERE.html` in a browser. No Python is needed. Progress records reading in local browser storage; only external links need internet.

The [historical delivery status for 731e416](../../handoff/STATUS.json) is not acceptance of this candidate. Its completion flag, paths and CI describe the earlier delivery; verify the actual current candidate commit and artifacts separately.

Start with `01_Practice_AHU.json`, available from the tutorial sidebar, and save your own copy. **Open practice copy** directly loads the second MAU/staged-AHU example with a new project identity. All examples are synthetic and leave unconfirmed manufacturer/site conditions pending. Platform ZIPs use their corresponding rebuilt reports. The old generic ZIP and root-level reports remain historical material, not current package evidence.

**DESIGNED BY ANDY HUANG ©**
