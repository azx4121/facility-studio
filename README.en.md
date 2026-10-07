# Facility Studio — HVAC & MEP Engineering Calculators

[繁體中文](README.md) · [Worked examples](docs/guides/README.md) · [Downloads](https://github.com/azx4121/facility-studio/releases) · [Report a problem](https://github.com/azx4121/facility-studio/issues)

Facility Studio by **azx4121 / Andy Huang** is a Traditional Chinese desktop application for preliminary HVAC, electrical and facility utility calculations. The calculators can be used independently; a complete workbench supports project comparisons and seasonal AHU stage calculations. This repository is unrelated to other products or businesses with the same name.

**V5.5.4 public test release.** Windows **win.1** and macOS **mac.2** bundle their runtime. After downloading, normal calculations require neither a separately installed Python nor an internet connection.

## Download and run

| Platform | Download | Start |
| --- | --- | --- |
| Windows standalone | [Offline EXE](https://github.com/azx4121/facility-studio/releases/download/v5.5.4-win.1/Facility_Studio_V5_5_4_Windows_Offline.exe) | Double-click; target: Windows 10/11 on Intel/AMD x64 |
| Windows complete package | [Offline ZIP](https://github.com/azx4121/facility-studio/releases/download/v5.5.4-win.1/Facility_Studio_V5_5_4_Windows_Offline_OneClick.zip) | Extract completely, then run the EXE; includes source, templates and diagnostics |
| macOS | [mac.2 DMG](https://github.com/azx4121/facility-studio/releases/download/v5.5.4-mac.2/Facility_Studio_V5_5_4_macOS_mac2.dmg) | Drag Facility Studio into Applications; Apple Silicon and Intel |
| macOS complete package | [mac.2 ZIP](https://github.com/azx4121/facility-studio/releases/download/v5.5.4-mac.2/Facility_Studio_V5_5_4_macOS_mac2_OneClick.zip) | Includes application, source, equipment templates and diagnostics |

The interface and exported reports currently use Traditional Chinese. An English interface is not included. See the [Chinese installation guide](README.md#安裝與開啟) for startup and security prompts. The Windows executable has no commercial Authenticode signature; the macOS app uses ad-hoc integrity signing, without Developer ID or notarization.

## What it calculates

| Need | Inputs and outputs | Example |
| --- | --- | --- |
| Electrical load and cable candidates | Input kW, single/three-phase supply, PF and operating conditions → current, NFB AT, conductor candidate and voltage drop | [10 kW, 380 V](docs/guides/electrical.md#case-01) |
| Rectangular and round duct sizing | Airflow and maximum velocity → both sizes and actual velocities; a known route permits a static-pressure budget check | [3,000 CMH](docs/guides/duct.md#case-03) |
| CDA / nitrogen pipe sizing | Standard flow, gauge pressure and velocity limit → actual volume flow and reference inner diameter | [800 SLPM, 6 bar(g)](docs/guides/gas-vacuum.md#case-05) |
| Process vacuum | Standard flow and absolute pressure → actual volume flow and a velocity-based cross section | [150 Torr(abs)](docs/guides/gas-vacuum.md#case-07) |
| Average illuminance and lamp count | Area or volume plus height, fixture lumens, utilization and maintenance factors → average lux or number of fixtures | [90 m³ room](docs/guides/lighting.md#case-08) |
| Cooling/heating water | Flow or kW and supply/return ΔT → capacity, flow and velocity-based pipe candidate | [100 kW, ΔT 5 K](docs/guides/water.md#case-11) |
| Psychrometrics and live chart | Dry-bulb temperature, RH and atmospheric pressure → humidity ratio, enthalpy, dew point, wet bulb and plotted point | [35°C, 70% RH](docs/guides/psychrometrics.md#case-12) |
| Engineering unit conversion | Airflow, liquid flow, pressure, thermal power, length, temperature, temperature difference and Kv/Cv | [CFM / CMH](docs/guides/units.md#case-14) |
| Equipment schedules | Excel/CSV input for electricity, PCW, CDA, N2, EXHAUST, DI and PV → separate demand groups | [Batch analysis](docs/guides/equipment.md) |
| AHU / MAU stages | Seasonal preheat, precool, water-wash humidification, recool and reheat; hot-water/electric heating and separate steam humidification options | [Capacity comparison](docs/guides/ahu.md#case-18) |

Static pressure alone does not uniquely size a duct. Pipe pressure and velocity alone do not size a gas line without flow. Electrical kW means **electrical input**, not motor shaft output. The worked examples state the adopted defaults and distinguish calculation requirements from verified installed equipment performance.

This is not a BIM/CAD authoring package, a complete pipe-network solver, or short-circuit/protection-coordination software. Manufacturer coil/fan/pump curves, safety requirements and applicable design rules require separate review.

## Verification and source

The repository retains numerical and report regression evidence. Windows win.1 was also tested natively on Windows Server 2022 and 2025; mac.2 was tested on Apple Silicon and Intel macOS 15. These hosted checks do not establish compatibility with every end-user device or enterprise policy. See [Windows evidence](docs/2026-10-07-windows-offline.md) and [macOS evidence](docs/2026-10-06-macos-repair.md).

The [20 worked scenarios](docs/guides/README.md) include 18 applicable calculations and two out-of-scope controls. The example verifier runs both source distributions on the current test host; it is distinct from native OS acceptance and from search discoverability tests.

Application source is in [windows](windows/) and [macos](macos/). Launch `Facility_Studio_V5_5.py` with its sibling package and resource files. Python is needed only for source development, not for running the bundled downloads.

## License

This is **source-available**, licensed under [PolyForm Noncommercial 1.0.0 plus the Internal Business Use Additional Permission](LICENSE). Normal internal company engineering work and paid engineering projects with delivered reports are permitted. Selling, renting, paid bundling or paid hosted access to the software requires separate written permission. See [LICENSE_GUIDE.md](LICENSE_GUIDE.md) for examples and the exact English license for terms.

This is not MIT or an OSI-approved open-source license. Historical MIT releases retain their original rights, documented in [LICENSE_LEGACY_MIT](LICENSE_LEGACY_MIT). Third-party packages keep their own licenses.
