# Psychrometric calculator: dry bulb, RH, wet bulb, dew point and enthalpy

**5.7.3 version guide: native acceptance and publication status are established by CI records and Release attachments for the corresponding commit; this guide does not assert a pass.** Older version-labelled examples, screenshots and pass counts below are historical evidence, not a fresh 5.7.3 run. [Release status](../verification/5.7.3-release-acceptance.md).

Confirm local absolute atmospheric pressure and valid A/B states before opening the full chart, zooming or saving snapshots. Wet-bulb and enthalpy lines differ; wet-bulb boundaries must remain within model validity, and RH=0 does not produce an invented finite dew point. Recalculate changed inputs before chart export. Charts do not replace coil heat/moisture and capacity checks.

[繁體中文](psychrometrics.md) · [All guides](README.en.md) · [Downloads](../../README.en.md#download-and-run)

This guide follows the **Facility Studio 5.7.3**. Open Psychrometrics and enter A dry bulb °C/RH. Enable the second state for B and choose whether B represents the room or coil leaving/supply air. Valid results update both points and differences. Advanced local atmospheric pressure is kPa(abs), default 101.325, shared by both states; do not enter gauge pressure.

<a id="case-12"></a>
## Case 12: 35°C, 70% RH, 101.325 kPa(abs)

| Property | Result |
| --- | --- |
| Humidity ratio | 25.159 g/kg dry air |
| Enthalpy | 99.771 kJ/kg dry air |
| Dew point | 28.701°C |
| Wet bulb | 30.059°C |
| Specific volume | 0.90827 m³/kg dry air |

`Pw = RH/100 × Pws(T)`

`w = 0.621945 × Pw/(P − Pw)`

`h = 1.006T + w(2501 + 1.86T)`

P and Pw must use the same pressure unit. In the enthalpy equation, w is kg/kg dry air, not g/kg.

<a id="case-13"></a>
## Case 13: 25°C, 50% RH, 80 kPa(abs)

Change atmospheric pressure to 80 kPa. Results: 12.568 g/kg dry air, enthalpy 57.167 kJ/kg dry air, dew point 13.864°C, wet bulb 17.332°C, specific volume 1.09139 m³/kg dry air. At the same dry bulb and RH, vapor partial pressure is unchanged, but humidity ratio and specific volume depend on total pressure.

At RH 0%, no finite dew point exists; the software does not invent one. Coil loads require dry-air mass flow and inlet/outlet states; a single plotted point does not determine an HVAC load.


Inputs: [12](../examples/12-air.json), [13](../examples/13-air.json). The original verifier independently checks humidity ratio/enthalpy against the Buck saturation-pressure correlation with 0.3% approximation tolerance: [results](../evidence/2026-10-18-audit-six/windows-use-cases.json).

## Full chart and snapshots

1. Obtain a valid result and open Enlarge psychrometric chart. Dry-bulb/humidity grids, 10–100% RH, enthalpy, wet-bulb and specific-volume families follow the current pressure.
2. Read dry bulb °C horizontally and g/kg dry air on the right. The outer green scale is h; brown WB is wet bulb; purple v is specific volume. Enthalpy and wet bulb are different scales.
3. Use zoom buttons or the wheel, drag to pan, and Fit / reset or double-click to restore the full chart. Maximize enlarges the window; Esc or Close exits.
4. The enlarged window is an **opening-time snapshot**, not live. After A/B or pressure edits, obtain a valid main-page result, close the old chart and reopen it.

The A/B connection compares endpoints, not an actual equipment process. Coil loads also require airflow, dry-air mass flow and the appropriate state basis; a plotted line does not certify equipment performance.
