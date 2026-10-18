# AHU / MAU stages: preheat, precool, water wash, recool and reheat

V5.6.0 standalone AHU windows can save invalid raw inputs as an explicitly confirmed draft. Reopening still identifies invalid fields and locks export. Correct inputs and recalculate before producing design outputs; a subsequent ordinary save keeps the draft backup. Cancellation preserves the file. This is manual draft saving, without a new standalone autosave timer.

C1 supersaturation messages identify the season, entering state, ADP and leaving demand. Use **Locate issue** to inspect the automatic target or the seasonal specified outlet. Correct the conditions and recalculate before exporting the report.

[繁體中文](ahu.md) · [All guides](README.en.md) · [Downloads](../../README.en.md#download-and-run)

<a id="source-revision"></a>
## Current source: MAU, DCC, FFU and the system display

This section describes the current engineering/interface revision separately from the retained published-version cases below. Source changes do not rewrite the versions or acceptance evidence of existing EXE/DMG downloads.

The main MAU model explicitly selects airflow topology and ACH basis. Older projects retain **Independent FFU loop; MAU supplies the room directly**: FFU and circulation-following DCC both use the original recirculation flow, without adding OA. For **MAU enters the plenum and supplies through FFUs**, choose whether ACH denotes basic recirculation or total FFU supply including OA. These give `FFU=recirculation+OA` and `DCC=FFU-OA`, respectively. Negative return is retained as a failed condition. See the [workbench comparison](workbench.en.md#source-revision).

The main model determines final OA from exhaust, leakage, occupancy and dehumidification before updating FFU count, fan-to-room heat and DCC sensible load. DCC air-side capacity uses the same flow as the report and the larger summer/winter load. The independent DCC-flow option remains supported. Existing gap-orifice leakage is already zero at 0 Pa; reference ACH is an optional alternative estimate. A 15 Pa / 1 ACH reference and 85% installation ratio are not universal cleanroom code requirements.

The staged individual unit still represents outdoor-air entry, consecutive equipment stages and final supply targets; it does not include the whole FFU/DCC return loop. Convert room-reference CMH and supply-state CMH through the same dry-air mass rate before comparing them. Do not add volume flows measured at different air states directly. Main-project fields and reports distinguish DCC dry coils and FFUs rather than presenting them as FCUs.

The responsive colour flow diagram uses green for OA, cyan for cooling, orange for heating/reheat, blue for supply/FFUs and amber for exhaust. State cards show temperature, RH and enthalpy; KPI cards and structured details show demand and checks. These are still target/calculated states. When installed capacity is insufficient, the target point is not a prediction of achieved leaving air.


In **Full workbench**, open the individual AHU window. Set summer/winter conditions. Each stage supports automatic demand, bypass or specified outlet dry bulb; cooling stages also support temperature/RH targets. The preceding outlet becomes the next inlet. H1/H2 can use electric heat, recovered hot water, both or neither; hot-water conditions may be shared or separate.

Water-wash/wetted-media evaporation, electrode steam and electric steam are different devices. Evaporative media cool the air; do not assume all humidification is isothermal. Electrode steam needs the manufacturer's conductivity range; DI/UPW is not automatically suitable.

Inactive fields retain drafts but do not affect states, capacity, power, water or reports. Recovery-only/disabled H1 or H2 excludes direct-electric efficiency and ratings. Offline recovery excludes adopted hot-water conditions. Wash circulation, pump head and wash makeup are shown only for selected wash equipment; steam-only selection reports steam demand. Rated power consistently sums selected direct heaters, selected steam generators and EC fans, excluding circulation pumps and auxiliaries. It is not simultaneous operating consumption.

The main project's summer first-stage mode applies to summer only; winter C1 is bypassed. Use this AHU window's seasonal stage controls to set winter preheat, precool, recool and reheat.

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

Coil ADP/bypass, matching-condition manufacturer selection, fan/N−1 behavior, washer pump flow/head and control interlocks need supplier data. Missing data stays unverified. Other inputs retain the original V5.5.4 example defaults; V5.6.0 retains these stage balances. See [complete case 18 inputs/results](../evidence/2026-10-18-audit-six/windows-use-cases.json).

Return only units that are included in the installed design. The same unit ID updates its contribution; distinct units add. Alternatives A/B are comparisons, not two installed units. Compatible water circuits sum each season separately and use the larger seasonal flow; different temperatures, fluids and circuit IDs remain separate. Preview the selected destination before transfer. Editing the source marks its retained results stale and disables transfer until recalculation.
