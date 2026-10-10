# Facility Studio guides: 20 questions, inputs and formulas

[繁體中文](README.md) · [English home](../../README.en.md) · [Downloads](../../README.en.md#download-and-run)

Choose a tool for your question, then review its inputs, formulas and result. These **18 calculation cases and two scope controls** use synthetic data and can be followed in the V5.5.8 Chinese or English interface.

## Start with the full-workbench walkthrough

The [beginner guide](workbench.en.md) starts with two reopenable practice projects and explains essential inputs, reports, latent load, water flow, pressure losses and AHU links. The [offline tutorial](https://github.com/azx4121/facility-studio/raw/refs/heads/main/docs/tutorial/Facility_Studio_Beginner_Tutorial.zip) works in a browser on Windows or macOS.

## Choose your calculation

| Case | Question and tool | Scope |
| --- | --- | --- |
| 01 | [Three-phase kW, current, NFB and conductor](electrical.en.md#case-01) | Preliminary sizing |
| 02 | [Single-phase continuous load and voltage drop](electrical.en.md#case-02) | Preliminary sizing |
| 03 | [Airflow to rectangular and round ducts](duct.en.md#case-03) | Preliminary sizing |
| 04 | [Duct route loss and available static pressure](duct.en.md#case-04) | Preliminary route check |
| 05 | [CDA standard flow, pressure and velocity](gas-vacuum.en.md#case-05) | Velocity-based sizing |
| 06 | [N2 flow and pressure units](gas-vacuum.en.md#case-06) | Velocity-based sizing |
| 07 | [PV actual volume flow](gas-vacuum.en.md#case-07) | Pump curve not assessed |
| 08 | [Room volume to lighting area and lux](lighting.en.md#case-08) | Average illuminance |
| 09 | [Luminaire count for target lux](lighting.en.md#case-09) | Average illuminance |
| 10 | [PCW flow and temperature difference to kW](water.en.md#case-10) | Clean-water estimate |
| 11 | [CHW kW to water flow](water.en.md#case-11) | Clean-water estimate |
| 12 | [Dry bulb, RH and live psychrometric point](psychrometrics.en.md#case-12) | Air-state calculation |
| 13 | [Air state at lower atmospheric pressure](psychrometrics.en.md#case-13) | Air-state calculation |
| 14 | [CFM to CMH](units.en.md#case-14) | Unit conversion |
| 15 | [Celsius and Fahrenheit temperature differences](units.en.md#case-15) | Unit conversion |
| 16 | [Excel electrical equipment demand](equipment.en.md#case-16) | Demand aggregation |
| 17 | [Six utility equipment schedules](equipment.en.md#case-17) | Demand aggregation |
| 18 | [AHU preheat, precool, water wash, recool and reheat](ahu.en.md#case-18) | Demand and capacity comparison |
| 19 | [Short-circuit current and protection coordination](electrical.en.md#case-19) | Outside the solver's scope |
| 20 | [BIM drawings and clash detection](#case-20) | Outside the solver's scope |

## Five examples to try

- **Electrical:** 10 kW, three-phase 380 V, PF 0.85, general load, 30 m one-way → 17.875 A, NFB 20 AT, 5.5 mm² per phase, one set.
- **Duct:** 3,000 CMH, maximum 8 m/s, aspect-ratio limit 2 → 350 × 300 mm rectangular or Ø406.4 mm round. Without a route, 200 Pa is not assessed as sufficient.
- **CDA:** 800 SLPM, 6 bar(g), 25°C, maximum 15 m/s → 115.581 ALPM, reference 1/2 in pipe, 16.1 mm ID.
- **Lighting:** 90 m³, 3 m clear height, 40 W × 10 luminaires, estimated 100 lm/W, U 0.6, M 0.8 → 640 lux.
- **Psychrometrics:** 35°C, 70% RH, 101.325 kPa(abs) → 99.771 kJ/kg dry air enthalpy, 28.701°C dew point; the chart point updates live.

Read the relevant guide for defaults, units and limitations. A candidate size is not approval of an installed system.

## Reproducible inputs and results

<details>
<summary>Developers: command-line examples and original test results</summary>

[scenarios.json](../examples/scenarios.json) contains the 20 scenarios. Fourteen quick-tool cases also have minimal JSON inputs. Developers can reproduce them from the repository root:

```sh
python windows/Facility_Studio_V5_5.py --language en --tool electrical --tool-input docs/examples/01-electrical.json --report electrical-example.txt
python windows/Facility_Studio_V5_5.py --language en --tool air --tool-input docs/examples/12-air.json --report air-example.txt
```

For macOS source, replace `windows/` with `macos/` and use `python3` if required. Bundled EXE/App users can enter the same data in the GUI without these development commands.

Each source distribution originally passed 121 example checks: numerical inverses, reports, equipment groups, AHU heat/moisture conservation and insufficient-capacity detection. Original results: [Windows](../examples/calculation-results-windows.json), [macOS](../examples/calculation-results-macos.json). They are the same 18 applicable cases and two out-of-scope controls, not 40 different questions. Native release acceptance and the separate 20 bilingual parity cases are documented independently.

</details>

<a id="case-20"></a>
## Case 20: BIM / Revit drawings and clash detection

Facility Studio does not provide BIM modeling, full 3D clash detection or automatic construction drawings. It is not a complete solution to this request. [Case 19](electrical.en.md#case-19) likewise requires a fault-current and protection-curve model.

## Use and feedback

See the [licensing examples](../../LICENSE_GUIDE.en.md) for permitted use. Report a case number, version, every value/unit and expected/actual result in [Issues](https://github.com/azx4121/facility-studio/issues). Remove client secrets.

[FAQ](../faq.en.md) · [Native acceptance](../2026-10-10-v5.5.8-native.md) · [Historical records](../history/README.md#english)
