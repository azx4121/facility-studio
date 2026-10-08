# Facility Studio 工具指南：20個問題、操作條件與公式

[繁體中文首頁](../../README.md) · [English guides](README.en.md) · [文件中心](../README.md) · [下載](../../README.md#下載)

這些案例使用合成資料，先判斷問題能否解，再選工具。**目前 V5.5.6 支援繁體中文／英文**，右上角可選 English；兩平台內含執行環境，可離線運作。原 V5.5.4 案例已用目前模型再驗算；V5.5.6 另釐清來源回傳、迴路分組及待重算互鎖。詳[本版操作與交付驗證](../2026-10-07-v5.5.6-usability.md)。

## 完整工作台先從這裡開始

[新手跟做教學](workbench.md)以兩份可開啟的專案，教您從基本條件到報告，並說明潛熱、水量、壓損及空調箱連動。[離線教學懶人包](https://github.com/azx4121/facility-studio/raw/refs/heads/main/docs/tutorial/Facility_Studio_Beginner_Tutorial.zip)可在 Windows／macOS 瀏覽器閱讀。

## 快速操作案例

| 情境 | 問題與操作 | 適用性 |
| --- | --- | --- |
| 01 | [三相設備 kW、NFB 與線徑初估](electrical.md#case-01) | 適用於初估 |
| 02 | [單相連續負載與壓降](electrical.md#case-02) | 適用於初估 |
| 03 | [風量換算方管與圓管](duct.md#case-03) | 適用於初估 |
| 04 | [排風路徑壓損與靜壓預算](duct.md#case-04) | 適用於初估 |
| 05 | [CDA 標準流量、壓力及流速定寸](gas-vacuum.md#case-05) | 適用於初估 |
| 06 | [N2 不同流量與壓力單位](gas-vacuum.md#case-06) | 適用於初估 |
| 07 | [PV 真空實際體積流量初估](gas-vacuum.md#case-07) | 適用於初估，未核泵曲線 |
| 08 | [空間體積反算照明面積及 Lux](lighting.md#case-08) | 適用於平均照度初估 |
| 09 | [目標照度反算燈具盞數](lighting.md#case-09) | 適用於平均照度初估 |
| 10 | [PCW 水量與溫差換算熱量](water.md#case-10) | 適用於清水初估 |
| 11 | [CHW 冷量反算冰水流量](water.md#case-11) | 適用於清水初估 |
| 12 | [外氣乾球、RH 與空氣線圖](psychrometrics.md#case-12) | 適用 |
| 13 | [較低大氣壓的空氣狀態](psychrometrics.md#case-13) | 適用 |
| 14 | [CFM 與 CMH 單位換算](units.md#case-14) | 適用；一次換算也可直接解答 |
| 15 | [攝氏溫差與華氏溫差](units.md#case-15) | 適用；一次換算也可直接解答 |
| 16 | [Excel 設備表彙總電力需求](equipment.md#case-16) | 適用於需求彙整 |
| 17 | [廠務多系統設備需求彙整](equipment.md#case-17) | 適用於需求彙整 |
| 18 | [AHU 預熱、預冷、水洗、再冷與再熱](ahu.md#case-18) | 適用於需求及方案比較 |
| 19 | [短路電流與保護協調](electrical.md#case-19) | 不適用於此解題需求 |
| 20 | [BIM 出圖與完整碰撞檢查](#case-20) | 不適用於此解題需求 |

## 五個可以立即試的例子

- **電力**：10 kW、三相380 V、PF0.85、一般設備、單程30 m → 17.875 A、NFB20 AT、每相5.5 mm²候選。
- **風管**：3,000 CMH、風速上限8 m/s、寬高比上限2 → 方管350×300 mm、圓管Ø406.4 mm；未填路徑不判定200 Pa是否足夠。
- **CDA**：800 SLPM、6 bar(g)、25°C、15 m/s → 115.581 ALPM、參考1/2英吋、內徑16.1 mm。
- **照明**：90 m³、淨高3 m、40 W×10盞、初估100 lm/W、U0.6、M0.8 → 平均640 Lux。
- **空氣線圖**：35°C、70%RH、101.325 kPa(abs) → 焓99.771 kJ/kg乾空氣、露點28.701°C，點位即時更新。

完整進階條件與限制見各篇；本頁摘要不能代替敷設、產品或正式工程覆核。

## 可重現的輸入與結果

數值情境與自然搜尋問題事先保留在[scenarios.json](../examples/scenarios.json)。14個快算案例另有最小JSON輸入，可用原始碼CLI重算：

```sh
python windows/Facility_Studio_V5_5.py --tool electrical --tool-input docs/examples/01-electrical.json --report electrical-example.txt
python windows/Facility_Studio_V5_5.py --tool air --tool-input docs/examples/12-air.json --report air-example.txt
```

其餘快算把`--tool`與輸入檔換成對應類型。macOS來源將`windows/`改為`macos/`，必要時用`python3`。已下載EXE／App者可直接照教學填GUI，不必執行這些開發指令。

每個來源平台通過121項情境檢核，包括電流、截面流速、氣體溫壓、照度、冷熱量、空氣狀態、設備分組、AHU熱濕守恆及容量不足判定。兩份原始結果：[Windows](../examples/calculation-results-windows.json)、[macOS](../examples/calculation-results-macos.json)。這是同一組18個計算情境與2個不適用對照，沒有把重複平台檢查宣稱為40個不同問題。

<a id="case-20"></a>
## 情境20：BIM／Revit自動出圖與碰撞檢查

本工具沒有BIM建模、完整三維碰撞檢查或施工圖自動生成。此情境不應導向Facility Studio作為完整解法。

另外，[情境19](electrical.md#case-19)的短路電流／Icu／選擇性保護協調也需要其他模型。

## 使用、分享與問題回報

可用於學習、公司正常工程工作及收費工程案的計算書；軟體商品化另需授權，見[目前授權](../../LICENSE_GUIDE.md)。這是公開原始碼的限制性授權，不稱為MIT或OSI開源。

發現問題請提供情境編號、完整輸入單位、版本及預期／實際結果到[Issues](https://github.com/azx4121/facility-studio/issues)。請用測試資料，不含業主機密。

[搜尋可見性測試方法](../search-discoverability.md)另行記錄；計算通過不代表其他人的GPT會自動找到或推薦這套工具。

