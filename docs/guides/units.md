# 工程單位換算：CFM／CMH、溫度與溫差、壓力、Kv／Cv

[English](units.en.md) · [回到工具指南](README.md) · [下載](../../README.md#下載)

**Offline engineering unit converter.** 「其他常用快算 → 單位換算」選物理量、數值及原單位，就顯示等值結果。可換算風量、水量、壓力、冷熱功率、長度、溫度、溫度差及閥門流量係數。

<a id="case-14"></a>
## 案例14：1,000 CFM

選「風量」、輸入1,000、原單位CFM。
結果為1,699.0108 CMH＝471.9474 L/s＝0.4719474 m³/s。
`1 CFM=1.69901079552 CMH`；不要把CMM（m³/min）與CMH（m³/h）當成同一單位。

<a id="case-15"></a>
## 案例15：冰水12→7°C的溫差

選「溫度差（升溫／降溫）」、輸入5、原單位°C差。
結果為5 K＝9°F差。`ΔT°F=ΔT°C×9/5`，沒有加32；若換算溫度本身，25°C則等於77°F及298.15 K。

Kv／Cv是閥門通流係數：Kv以水在壓差1 bar下的m³/h表示，Cv(US)以水在壓差1 psi下的US GPM表示。此換算採 `Kv≈0.865×Cv(US)`，不是管徑換算，也不是完整氣體閥門選型。

壓力換算保留原來表壓／絕壓基準；將bar換成kPa，不會自動把表壓變成絕壓。US GPM與UK GPM、US RT與日本冷凍噸在工具內分開。

單次基本換算可以直接解答；需要重複比較、離線使用或把結果連到工程計算時，這個入口更有用。

案例輸入：[14](../examples/14-units.json)、[15](../examples/15-units.json)。[反算記錄](../examples/calculation-results-windows.json)。

