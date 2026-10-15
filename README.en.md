# Facility Studio | Facility engineering estimates and HVAC calculations

[繁體中文](README.md) · [User guides](docs/guides/README.en.md) · [FAQ](docs/faq.en.md) · [Report a problem](https://github.com/azx4121/facility-studio/issues)

**Turn equipment power, airflow, water flow and room conditions into engineering demands you can compare.**

Facility Studio is a desktop tool for facility, electrical and HVAC engineers. Use an independent calculator for a single question, import Excel/CSV schedules for multiple devices, or use the full workbench for HVAC schemes, AHU stages and reports.

**Windows / macOS · Traditional Chinese / English · Offline calculations · No separate Python installation**

<a id="installation-and-first-launch"></a>
## Download and run

Current version: **V5.6.0 public test release**, Windows **win.3** / macOS **mac.5**, published 2026-10-13 (Taipei time).

Automatic water sizing extends to **24 inches**; **all seven calculators are direct sidebar buttons**; the gas calculator and workbench share **50 factory gases plus custom mixtures**. Added gases with demand require an entered design velocity. Zero-demand workbench rows retain unused drafts without blocking the whole project. Native acceptance also runs **100 distinct scenarios, repeated 20 times each**. [Features, dimension sources and scope](docs/2026-10-12-v5.6-expansion.md#english) · [Windows delivery and SHA256](docs/2026-10-13-v5.6-audit-stress.md#english) · [Mac mac.5 fixes and delivery](docs/2026-10-13-mac-diagnostics.md#english)

| Platform | Download | Start |
| --- | --- | --- |
| Windows 10/11, Intel/AMD x64 | [**Download Windows EXE**](https://github.com/azx4121/facility-studio/releases/download/v5.6.0-win.3/Facility_Studio_V5_6_0_Windows_Offline.exe) | Save and double-click; allow time for the bundled environment to unpack on first launch |
| macOS, Apple Silicon / Intel | [**Download macOS DMG**](https://github.com/azx4121/facility-studio/releases/download/v5.6.0-mac.5/Facility_Studio_V5_6_0_macOS_mac5.dmg) | Open the DMG, drag Facility Studio into Applications, then launch it there |

Download one file for your platform. Help and equipment templates are bundled. [Versions and SHA256](https://github.com/azx4121/facility-studio/releases) · [Compatibility and first launch](docs/faq.en.md#compatibility)

The Windows EXE has no official publisher signature; the Mac app has no Developer ID or Apple notarization. First launch may show a security prompt. Check the download source and follow the [security-prompt guide](docs/signing.en.md).

<a id="current-source-revision"></a>
## Current source revision

The repository now includes an engineering/dashboard revision with **ten quick tools**, including Cleanroom airflow, Heat load estimate and Chilled-water pump. It adds explicit MAU/FFU airflow topology and ACH basis, nominal FFU module/coverage checks, separate pump shaft/electrical power, and an upstream-import chain from room airflow through heat load, water, pump and electrical demand. Imported electrical totals use explicit device inputs; chiller cooling is converted only with COP or an entered electrical input. Reports begin with calculated-demand and suggested-selection summaries, with KPI cards and HTML tables.

Existing schema 11 projects migrate to schema 12 while retaining independent FFU circulation, direct MAU room supply and the original gap-orifice leakage method. A plenum path and its ACH basis must be selected explicitly; OA is not automatically added to every historical FFU calculation. Reference leakage ACH, 30 CMH per person in the quick tool and the 85% ceiling allowance are preliminary project assumptions, not universal ASHRAE/ISO requirements.

These are **source changes**, separate from the published win.3 / mac.5 binaries and native-acceptance records linked above. Existing release versions, download assets and screenshots remain unchanged. A new packaged release needs its own native build and acceptance. See the [engineering and dashboard audit](docs/2026-10-15-engineering-dashboard-audit.md), and the current-source sections in the [workbench](docs/guides/workbench.en.md#source-revision), [electrical](docs/guides/electrical.en.md#source-revision), [water/pump](docs/guides/water.en.md#source-revision) and [AHU](docs/guides/ahu.en.md#source-revision) guides.

## What can you use it for?

| Your task | What you get | Tool / example |
| --- | --- | --- |
| Estimate supply requirements for new equipment | Current, circuit-breaker and conductor candidates, preliminary voltage drop | [Electrical sizing](docs/guides/electrical.en.md) |
| Compare round and rectangular ducts for a known airflow | Dimensions and actual velocity; preliminary pressure loss when a route is supplied | [Duct sizing](docs/guides/duct.en.md) |
| Estimate CDA / nitrogen / process-gas piping from flow and pressure | Actual volume flow and reference pipe diameter | [CDA / gas piping](docs/guides/gas-vacuum.en.md) |
| Check room and thermal requirements | Average lux / lamp count, water flow / capacity, air states and unit conversions | [Lighting](docs/guides/lighting.en.md) / [Water](docs/guides/water.en.md) / [Psychrometrics](docs/guides/psychrometrics.en.md) / [Units](docs/guides/units.en.md) |
| Consolidate an Excel/CSV equipment schedule | Grouped electricity, PCW, CDA, N2, EXHAUST, DI and PV demand | [Equipment schedules](docs/guides/equipment.en.md) |
| Compare HVAC schemes and AHU stage configurations | Summer/winter heat and moisture demand, preheat / precool / humidification / recool / reheat, capacity checks and reports | [Full workbench](docs/guides/workbench.en.md) / [Standalone AHU](docs/guides/ahu.en.md) |

Each quick tool works independently. Adopted conditions and defaults appear on screen and in reports, so you can review the assumptions and compare demand after a change.

![Facility Studio V5.6.0 Windows win.3 electrical-sizing interface in English](docs/images/v560-win3-electrical-en.png)

*Actual V5.6.0 win.3 native-acceptance screen: all seven calculators are directly available on the left, with calculation and export below.*

## Try one small calculation first

1. Launch the app and choose **English** or **Traditional Chinese** at the top right.
2. Select a tool and enter your values and units. Review the displayed assumptions.
3. Click **Calculate**, then copy the result or export TXT. **This tool's guide** opens the relevant instructions and formulas.

Try **10 kW, three-phase 380 V, general load** with the electrical tool's defaults: expect approximately **17.87 A, a 20 AT breaker candidate and 5.5 mm² per phase**. [Complete assumptions and check](docs/guides/electrical.en.md#case-01)

For a project report, open **Full workbench → Beginner tutorial** and follow the [first six walkthrough sections](docs/guides/workbench.en.md). **Open practice copy** directly loads the MAU example with a staged AHU for the next exercise.

## Before using the results

- **Scope:** preliminary engineering estimates, scheme comparison and demand summaries. Complete equipment selection, regulatory review, fault/protection studies, pipe networks and BIM drawings need separate work.
- **Data:** calculations, saved projects and schedule imports are processed locally. User-entered names and notes retain their original language.
- **License:** internal company engineering work, paid engineering projects and delivered calculation reports are permitted. Software resale, paid bundling or paid hosted software services require separate written permission. [Full terms](LICENSE) · [License examples](LICENSE_GUIDE.en.md)

The published files passed native acceptance on Windows Server 2022/2025 x64 and Apple Silicon/Intel macOS 15. Windows 10/11 and macOS 11+ are support/packaging targets; other OS versions, devices and enterprise policies need individual confirmation. [Windows verification](docs/2026-10-13-v5.6-audit-stress.md) · [Mac mac.5 verification](docs/2026-10-13-mac-diagnostics.md#english)

## Help and feedback

[Tool and formula guides](docs/guides/README.en.md) · [FAQ](docs/faq.en.md) · [Documentation](docs/README.en.md) · [Development and tests](docs/development.md#english) · [Historical records](docs/history/README.md#english)

Use [GitHub Issues](https://github.com/azx4121/facility-studio/issues) to report a problem. Include app/OS versions, steps, all values and units, and expected/actual results. Use synthetic data and remove client secrets.

**DESIGNED BY ANDY HUANG ©** · Maintainer [azx4121](https://github.com/azx4121) · [Third-party components](THIRD_PARTY_NOTICES.md)
