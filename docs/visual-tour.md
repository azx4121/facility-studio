# Facility Studio 圖解導覽

[English](visual-tour.en.md) · [首頁](../README.md) · [安裝與起步](getting-started.md) · [工具索引](guides/README.md)

以下三張圖解對照 5.7.3 文件與來源提交 `01e0a3239e1dc962e76d8c23a91a2f623eaebe95`，於 2026-11-08 編製。它們是操作與模型示意，不是實際介面截圖，不代表其他候選包、原生成品或 FEED 已完成驗收。原生平台與公開下載狀態仍以[對應 Release](https://github.com/azx4121/facility-studio/releases)為準。

## 1. 依問題選入口

![四種工作範圍：單點快算、整案工作台、設備與容量、設計資料審查](images/diagrams/overview.zh.svg)

- **只解一個問題：**選電力、風管、氣體／PV、水路、照明、空氣狀態或單位等直接工具。
- **整理整個空間：**使用完整工作台整理氣候、空間、熱負荷、流路與整案報告。
- **比較設備與擴充：**在分段 AHU 檢查夏冬需求；在容量計畫比較現況、擴充與 N−1 初篩。
- **整理交付依據：**設計審查記錄來源、採用條件與缺件，仍需專業覆核。

各工作範圍的保存動作不同，完整工作台的「儲存整案」不會代替獨立容量計畫或設計審查的保存。看[資料保存](faq.md#saving)。

<a id="workflow"></a>
## 2. 第一份報告怎麼完成

![確認版本、另存副本、填條件、重算、讀工程狀態、保存及匯出](images/diagrams/workflow.zh.svg)

先從[第一個合成練習案](guides/workbench.md#first-case)開始。重算後讀「待補資料」和「未達條件」，不要為了消除警告填入未確認數字。改上游後明確重新帶入下游，並再次核對採用條件。

整案 JSON 用於重開繼續工作；TXT／HTML／PDF 用於閱讀。完整驗算資料 JSON、直接照度結果 JSON 不等同可重開的整案。逐步操作見[工作台六步教學](guides/workbench.md#start)。

<a id="ahu"></a>
## 3. AHU 圖上的目標，不等於設備已能達到

![分季入口依序經 H1、C1、加濕、C2、H2，需求與已配置能力分開檢查](images/diagrams/ahu-boundary.zh.svg)

這是分段空調箱的處理順序概念，不是每個專案都必須採用的配置，也不是完整 FFU／DCC 回風管網。每段入口承接上一段；實際未使用段落應選旁通。夏冬各自核對風量基準、熱濕收支、已配置容量及原廠同工況資料。

H1 容量不足不能拿 H2 餘量直接抵銷。較低冰水溫度或 BF／ADP 風量搜尋也不保證可行。詳細見[分段 AHU 指南](guides/ahu.md)。

<a id="screenshots"></a>
## 4. 真實介面：5.7.3 v22 r3 macOS ARM64

以下為 **5.7.3／build 5.7.3.2、v22 r3 UNVALIDATED-COMPILE-ONLY 候選包**在 macOS 27.3 ARM64 上的原生視窗截圖，電力與工作台圖為繁中，PV 圖為透過介面切換後的英文。使用內建範例與測試輸入。原始 JPEG 均為 2880 × 1716，未裁切、未重繪或更改版本標題；不是 mac.8 舊圖。

### 電力配線

![5.7.3 v22 r3 繁中電力頁，保留自動配線選型暫停與非正式 FEED 警告](images/facs-5.7.3-v22-macos-arm64-electrical-zh-Hant.jpg)

本候選包的電力頁保留輸入電功率、運轉及設計電流；**自動配線選型已暫停**。導線、NFB、有效載流量、壓降及 PE 須另行工程核實，不能把圖中初估數值當成正式選型。

### 完整工程工作台

![5.7.3 v22 r3 繁中工作台，內建範例與未達條件狀態](images/facs-5.7.3-v22-macos-arm64-workbench-zh-Hant.jpg)

畫面保留範例工況與「工程評估：未達條件」狀態。能開啟工作台不代表該範例或所有計算已驗收。

### English：PV 真空

![5.7.3 v22 r3 真實英文 PV 畫面，100 SLPM 測試輸入與未達條件狀態](images/facs-5.7.3-v22-macos-arm64-vacuum-en.jpg)

這是透過介面切換的真實英文畫面，不是翻譯覆蓋圖。100 SLPM 為測試輸入；側欄較長的英文標籤在此原生尺寸下有截斷，保留原貌。原生檢視亦觀察到 AHU 管理視窗預設高度下的底部按鈕文字裁切，尚未完成縮放覆核。

本輪已確認原生啟動、About 5.7.3、部分工具切換、工作台與英文報告頁開啟；另外完成單一 PV 案例核對、英文 TXT 匯出、取消後重開匯出、工作區 JSON 保存及內建 MAU/AHU 練習案載入。這些是局部檢查，不是全功能、全部數值、英文排版、完整匯出或正式 FEED 驗收。工作區重新開啟及單機 AHU 細測尚未完成。候選來源 inventory 有雜湊，但尚無已核對的 Git commit 對應，不能以 main 的 CI 代替此成品驗收，也不宣稱跨平台一致或公開發布。

[精確成品身份、存檔時間及原圖 SHA256](images/README.md#v573-v22-r3)。mac.8／win.10 等[歷史原圖與來源](images/README.md#historical-screenshots)繼續保留原版本身分，不再用於本節的新版展示。

[圖片與圖解來源](images/README.md) · [驗收證據格式](verification/5.7.3-release-acceptance.md)

**DESIGNED BY ANDY HUANG ©**
