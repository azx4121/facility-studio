# AHU / MAU stages: preheat, precool, water wash, recool and reheat

[繁體中文](ahu.md) · [All guides](README.en.md) · [Downloads](../../README.en.md#download-and-run)

In **Full workbench**, open the individual AHU window. Set summer/winter conditions. Each stage supports automatic demand, bypass or specified outlet dry bulb; cooling stages also support temperature/RH targets. The preceding outlet becomes the next inlet. H1/H2 can use electric heat, recovered hot water, both or neither; hot-water conditions may be shared or separate.

Water-wash/wetted-media evaporation, electrode steam and electric steam are different devices. Evaporative media cool the air; do not assume all humidification is isothermal. Electrode steam needs the manufacturer's conductivity range; DI/UPW is not automatically suitable.

Start with [section 8 of the beginner walkthrough](workbench.en.md#ahu) to practice on a small MAU before the larger capacity case below.

<a id="case-18"></a>
## Case 18: 58,000 CMH with insufficient winter preheat

| Condition | Value |
| --- | --- |
| Airflow / volume reference | 58,000 CMH at supply state |
| Summer outdoor air | 35°C / 70% RH |
| Winter outdoor air | 5°C / 40% RH |
| Supply target | 22°C / 55% RH |
| H1 / H2 installed electric capacity | 400 / 200 kW |
| Water wash | Continuous for AMC control; media effectiveness 0.85 |
| C1 supply/return water / candidate | 14/19°C / 250 US RT |
| C2 supply/return water / candidate | 7/12°C / 160 US RT |
| Other settings | Automatic stages; fan-to-air heat 0; capacity margin 0%; recovered hot water off |

| Demand result | Summer | Winter |
| --- | --- | --- |
| Dry-air mass flow | 18.9921 kg/s | Same |
| H1 heat into air | 0 kW | 573.141 kW |
| C1 air-side cooling | 719.429 kW | 0 kW |
| Media evaporation | 17.011 kg/h | 472.385 kg/h |
| C2 air-side cooling | 501.289 kW | 0 kW |
| H2 heat into air | 183.509 kW | 86.499 kW |
| Installed H1 capacity sufficient | Yes | **No: 400 kW is insufficient** |

The example's 619.4 kg/h washer rating and media effectiveness are assumptions, not certified product performance. Air-side and water-side cooling can differ because of condensate energy; use water-side results for water-coil capacity comparisons.

`m_dry_air = supply CMH / 3600 / supply specific volume`

`Stage air-side kW = m_dry_air × Δh`

`Moisture kg/h = m_dry_air × Δw × 3600`

Evaporation, steam and condensation use separate balances. Include fan heat in reheat and the overall energy balance when present.

**Plotted demand points are reverse-calculated targets, not proof that a 400 kW heater can reach them.** Winter H1+H2 requires about 659.64 kW here; 600 kW total installed does not pass. Spare H2 capacity cannot simply be moved upstream to H1. After changing airflow or adding 30/24°C recovered hot water, recalculate each stage and coil capability at the same conditions.

Coil ADP/bypass, matching-condition manufacturer selection, fan/N−1 behavior, washer pump flow/head and control interlocks need supplier data. Missing data stays unverified. Other inputs retain the original V5.5.4 example defaults; V5.5.5 keeps the engineering model. See [complete case 18 inputs/results](../examples/calculation-results-windows.json).
