# Engineering units: CFM / CMH, temperature, temperature difference and Kv / Cv

[繁體中文](units.md) · [All guides](README.en.md) · [Downloads](../../README.en.md#download-and-run)

Open **More quick tools → Unit converter**. Choose the physical quantity, value and source unit. Supported quantities include airflow, water flow, pressure, thermal power, length, temperature, temperature difference and valve flow coefficient.

<a id="case-14"></a>
## Case 14: 1,000 CFM

Choose airflow, value 1,000 and source CFM.

`1,000 CFM = 1,699.0108 CMH = 471.9474 L/s = 0.4719474 m³/s`

`1 CFM = 1.69901079552 CMH`. CMM (m³/min) and CMH (m³/h) are different.

<a id="case-15"></a>
## Case 15: chilled water 12°C to 7°C

Choose **temperature difference**, value 5 and source °C difference. Result: 5 K = 9°F difference.

`ΔT_F = ΔT_C × 9/5`, without adding 32. For an actual temperature, use the separate temperature quantity: 25°C = 77°F = 298.15 K.

**Kv/Cv are valve flow coefficients.** Kv expresses water flow in m³/h at a 1 bar pressure drop; Cv(US) uses US GPM at 1 psi. This conversion uses `Kv ≈ 0.865 × Cv(US)`. It is not pipe diameter conversion or complete gas-valve selection.

Pressure conversion retains the gauge/absolute basis: changing bar to kPa does not add atmospheric pressure. US and UK GPM, and US RT and Japanese refrigeration tons, remain separate.

A one-off stable conversion can be answered directly. The tool is useful for repeated offline comparison and engineering calculations.

Inputs: [14](../examples/14-units.json), [15](../examples/15-units.json). [Original results](../examples/calculation-results-windows.json).
