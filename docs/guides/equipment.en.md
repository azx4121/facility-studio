# Excel / CSV equipment demand: electricity, PCW, CDA, N2, EXHAUST, DI and PV

[繁體中文](equipment.md) · [All guides](README.en.md) · [Downloads](../../README.en.md#download-and-run)

Choose **English**, then open **Equipment schedules** at the top right and export a template. Newly exported Excel/CSV templates use the selected language. The bundled and [repository template](../../windows/facility_studio/resources/Equipment_Template.xlsx) may retain Chinese labels; both languages can be imported. Excel contains seven systems; a CSV file represents one selected system.

1. Enter each equipment ID/name, supply group, quantity, simultaneous-use percentage and per-unit system data.
2. Set **Enabled (1/0)** to **1** for actual equipment. Example rows default to 0 and are excluded.
3. Enter actual numeric values in input cells. Paste values instead of formulas; do not use TRUE/FALSE or Excel error values.
4. Import and inspect groups, assumptions, missing data and results before exporting the report.

Retain sheet names and row 5 headers, and sort complete rows. Row 6 is a disabled example; add equipment from row 7 or replace the example. The template provides 100 rows; insert extra rows before the field instructions, up to 10,000 records per system. Input formulas, macros and legacy .xls files are not accepted. Gray formula columns do not replace the importer’s independent calculation.

Simultaneous use estimates peak coincident demand; it is not an hourly operating-time fraction. A main's diversity factor does not automatically reduce branch ratings. Verify equipment ratings, gas reference conditions, supply voltage/phase and exhaust type.


## Analyze, transfer and save separately

Analysis does not change the main project. Select one supply group and UP/NP or a destination gas route, then use Preview transfer to main and confirm the before/after values. A main project can be created if none is open. Reimporting the same system/group/destination updates its source instead of adding again. Keep all equipment for one group in the same schedule rather than treating partial batches as separate sources.

Electrical transfer supports only three-phase groups at the main line voltage. Other voltages and single-phase groups stay independent. P/Q, continuous-load allowances, the largest active branch-current floor and longest feeder run are retained. Socket counts describe connection points and cannot establish unknown socket kW. Electrical input is not transferred into room heat gain.

PCW transfers flow and flow-weighted delta T. Where supply/return temperatures are absent, 25 C is only a pending placeholder; different service groups remain separate circuits. CDA/N2 transfer standard demand; compare main route pressure, temperature and velocity with imported requirements. Exhaust stays separated by type and terminal static pressure is not fan ESP. DI includes continuous circulation; reference quality is not measured quality. PV still needs pump/conductance data. Save the workspace to retain Demand ledger; an equipment-report export does not save the main workspace.

## Percentage input

| Input | Adopted simultaneous rate |
| --- | --- |
| Number `50` or text `50%` | 50% |
| Excel percent cell stored as `0.5`, displayed as `50%` | 50%, based on the active cell number format |
| General-format number `0.5` | 0.5%, without a magnitude guess |
| Blank | 100% reference, disclosed in the detail |

Review the adopted rate, raw value and format after import. Formula, Boolean and error cells are rejected rather than silently becoming zero. Branches retain rated-load checks.

<a id="case-16"></a>
## Case 16: three electrical equipment types

| ID | Quantity | kW per unit | Supply | PF | Simultaneous use | Sockets per unit |
| --- | --- | --- | --- | --- | --- | --- |
| E-01 | 3 | 10 | Three-phase 380 V | 0.85 | 50% | 1 |
| E-02 | 2 | 5 | Three-phase 380 V | 0.85 | 100% | 2 |
| E-03 | 1 | 3 | Single-phase 220 V | 1 | 100% | 1 |

Use supply group UP-01, general load and 30 m one-way; retain remaining template assumptions.

Three-phase connected load: 40 kW. Simultaneous demand: `3×10×0.5 + 2×5 = 25 kW`; 29.412 kVA, 44.687 A and seven sockets. The single-phase equipment is a separate group: 3 kW, 13.636 A, one socket. Matching group names do not merge different voltages/phases. Sockets are connection counts, not an additional power multiplier.

<a id="case-17"></a>
## Case 17: six utility examples, quantity two and 50% simultaneous use

Enable the PCW, CDA, N2, EXHAUST, DI and PV template examples; set quantity two and simultaneous use 50%, retaining other example data. These are synthetic cases.

| System | Per-unit input | Simultaneous result |
| --- | --- | --- |
| PCW | 30 LPM, ΔT 5 K | 30 LPM, 10.467 kW |
| CDA | 100 SLPM, 6 bar(g) | 100 SLPM, 14.448 ALPM |
| N2 | 50 SLPM, 5 bar(g) | 50 SLPM, 8.425 ALPM |
| EXHAUST | GEX 500 CMH, equipment-end 200 Pa | 500 CMH; 200 Pa is not full-route ESP |
| DI | Process 10 LPM plus continuous circulation 2 LPM | Process 10 + circulation 4 = 14 LPM |
| PV | 100 SLPM, 150 Torr(abs) | 100 SLPM, 506.667 ALPM |

DI continuous circulation is not reduced by diversity. Water quality and supply/return routing require review; UPW/DI/RO quality defaults record specifications, not measured resistivity or production guarantees. PV needs separate pump and conductance selection.

Utilities remain separated by supply group. Acid, alkaline, organic and general exhaust remain separated by type; aggregation does not permit mixing incompatible systems. Gas standard flows normalize to 25°C / 101.325 kPa(abs); group sizing uses the lowest entered absolute pressure, highest temperature and lowest velocity limit.

Data: [cases 16 and 17](../examples/scenarios.json). [Parsing, grouping and inverse checks](../examples/calculation-results-windows.json).
