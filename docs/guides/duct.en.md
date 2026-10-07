# Duct calculator: airflow, rectangular / round sizes and static pressure

[繁體中文](duct.md) · [All guides](README.en.md) · [Downloads](../../README.en.md#download-and-run)

Open **Duct sizing**. Enter CMH, CFM or L/s and available duct static pressure. Advanced settings include maximum velocity, aspect ratio and the critical route. Defaults are maximum 8 m/s and rectangular aspect-ratio limit 2; these do not suit every supply, corrosive exhaust or noise requirement.

<a id="case-03"></a>
## Case 03: 3,000 CMH, 200 Pa

Use maximum velocity 8 m/s, aspect-ratio limit 2 and no route input.

| Result | Rectangular | Round |
| --- | --- | --- |
| Candidate | 350 × 300 mm | Ø406.4 mm (16 in) |
| Actual velocity | 7.937 m/s | 6.424 m/s |
| Available static pressure | 200 Pa | 200 Pa |
| Pressure sufficiency | Route not assessed | Route not assessed |

`A = CMH / 3600 / v`; `D_round = √(4A / π)`. Discrete size increments reduce actual velocity below the limit. **Static pressure alone cannot determine size; without a route, 200 Pa is not declared sufficient.**

<a id="case-04"></a>
## Case 04: 2,000 CFM and a known 20 m route

Use 2,000 CFM, 300 Pa available pressure, enable the known-route check, and enter 20 m straight length, fitting `ΣK = 4`, equipment/terminal loss 100 Pa and maximum velocity 8 m/s. Retain other defaults.

| Result | Rectangular | Round |
| --- | --- | --- |
| Airflow | 3,398.022 CMH | Same |
| Candidate | 400 × 300 mm | Ø406.4 mm (16 in) |
| Actual velocity | 7.866 m/s | 7.277 m/s |
| Route loss | 286.912 Pa | 254.095 Pa |
| Remaining pressure | 13.088 Pa | 45.905 Pa |

`Δp = f(L/Dh)ρv²/2 + ΣKρv²/2 + equipment loss`.
For a rectangle, `Dh = 2WH/(W+H)`, but velocity uses the **actual rectangular area**. Do not recalculate velocity using a circle of diameter Dh. This example uses air density 1.2 kg/m³, viscosity 1.81 × 10⁻⁵ Pa·s and roughness 0.09 mm.

The quick route assumes constant size and flow along the route. Branch networks, changing sections, pollutant treatment, fan curves and filter final resistance need separate modeling. The maximum equipment-end static-pressure requirement is not total fan ESP.

Inputs: [03](../examples/03-duct.json), [04](../examples/04-duct.json). [Original inverse-check results](../examples/calculation-results-windows.json).
