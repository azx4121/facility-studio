# 冷熱水計算器：PCW／CHW 水量、kW、RT、ΔT 與管徑

[English](water.en.md) · [回到工具指南](README.md) · [下載](../../README.md#下載)

**Cooling-water / chilled-water flow and heat calculator.** 開啟「其他常用快算 → 冷熱水快算」，選「已知水量」或「已知熱量」。基本採清水密度1,000 kg/m³、比熱4.1868 kJ/(kg·K)、水速上限1.5 m/s；流量可用LPM、US GPM或m³/h。

公式：`Q[kW]=LPM/60000×ρ×cp×ΔT[K]`。US RT採3.51685284 kW/RT；ΔT是供回水溫差，不是其中一個水溫。乙二醇或其他液體應改用適用物性；快算清水值不能直接套用。

<a id="case-10"></a>
## 案例10：PCW 100 LPM、ΔT 5 K

選「已知水量」填100 LPM及5 K。
`100/60000×1000×4.1868×5=34.89 kW≈9.921 US RT`。
按1.5 m/s上限定寸，候選40A（1-1/2英吋）、參考內徑40.9 mm，水速1.269 m/s。

<a id="case-11"></a>
## 案例11：CHW 100 kW、ΔT 5 K

選「已知熱量」填100 kW及5 K。
`LPM=100×60000/(1000×4.1868×5)=286.615 LPM`。
候選65A（2-1/2英吋）、參考內徑67.9 mm、水速1.319 m/s。

候選僅符合指定水速；沒有代表整個水系統已合格。水泵揚程、換熱器／盤管壓降、完整供回水路徑、膨脹槽、靜壓及NPSH另核。

案例輸入：[10](../examples/10-water.json)、[11](../examples/11-water.json)。[反算記錄](../examples/calculation-results-windows.json)。

