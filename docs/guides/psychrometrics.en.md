# Psychrometric calculator: dry bulb, RH, wet bulb, dew point and enthalpy

[繁體中文](psychrometrics.md) · [All guides](README.en.md) · [Downloads](../../README.en.md#download-and-run)

Open **More quick tools → Psychrometrics**. Enter dry-bulb temperature in °C and relative humidity in %RH. Properties and the chart point update live. Atmospheric pressure defaults to 101.325 kPa(abs) and can be changed in advanced settings; chart curves follow the selected pressure. This quick tool uses dry bulb plus RH; the full workbench offers additional state-input combinations.

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

Actual native English macOS screen below uses **25°C / 50% RH at standard pressure**, not the 35°C case above:

![Native English psychrometric chart on macOS](../images/macos-psychrometrics-en.png)

Inputs: [12](../examples/12-air.json), [13](../examples/13-air.json). The original verifier independently checks humidity ratio/enthalpy against the Buck saturation-pressure correlation with 0.3% approximation tolerance: [results](../examples/calculation-results-windows.json).
