# Frequently asked questions

[繁體中文](faq.md) · [Downloads](../README.en.md#download-and-run) · [User guides](guides/README.en.md)

## Do I need Python or an internet connection?

No. The Windows EXE and macOS DMG include their runtime. Calculations, saved projects and equipment imports are processed locally. Bundled help works offline; GitHub documentation, downloads and update links need internet.

<a id="compatibility"></a>
## Can I use it on my computer? How do I launch it?

| Platform | Current download and startup | Completed native acceptance |
| --- | --- | --- |
| Windows | Windows 10/11 on Intel/AMD x64 are support targets. Download and double-click the EXE; allow time for the bundled environment to unpack on first launch. | Windows Server 2022/2025 x64 |
| macOS | Universal App for Apple Silicon / Intel, packaging target macOS 11+. Open the DMG, drag into Applications, then launch there. Eject the DMG after installation. | Apple Silicon / Intel macOS 15 |

Windows ARM, 32-bit Windows, and other Mac OS versions/devices were not included in this acceptance. Enterprise policies may also restrict execution. [Full acceptance and download hashes](2026-10-10-v5.5.8-native.md)

Close the old app before replacing the EXE/App. Saved projects and recovery data are retained.

<a id="security"></a>
## Why does Windows or macOS show an unknown-publisher prompt?

The Windows EXE has no formal Authenticode signature. The Mac app has ad-hoc integrity signing without Developer ID or Apple notarization. Native tests and matching SHA256 do not establish official publisher identity.

Check this repository's download source and SHA256, then follow the [system security-prompt guide](signing.en.md) and your company policy. Retain and report explicit antivirus threat detections, a damaged-app message, or a launch without a window.

<a id="first-project"></a>
## Do I need to fill every system before I can start?

Start with an independent calculator for your question, such as electrical sizing, ducts or water.

For a project, use the first example in **Beginner tutorial** and complete the [first six sections](guides/workbench.en.md). **Open practice copy** directly loads the second example: an outside-air MAU project with a staged AHU. Practice files use synthetic data; replace them with your site conditions later.

<a id="results"></a>
## What do calculation-complete, data-required and stale states mean?

| State | Meaning | Next step |
| --- | --- | --- |
| Calculation complete | The current inputs can be calculated | Still review capacity, assumptions and pending evidence |
| Data required | Manufacturer performance, equipment resistance or site conditions are unconfirmed | Supply actual data and review |
| Condition not met | A known capacity or operating condition fails a requirement | Read the reason, change the configuration and recalculate |
| Recalculation required | The previous valid result is retained after inputs change | Recalculate successfully before exporting or transferring current results |

Disabled fields retain their draft values for validation when re-enabled; inactive drafts do not affect that mode's calculation. Advanced fields hidden by Basic mode may still use saved settings. Review the displayed adopted assumptions.

These states do not certify a design. Fault/protection studies, complete pipe networks, equipment performance selection and BIM drawings require separate work.

<a id="saving"></a>
## How do I save projects, drafts and reports?

- **Workspace JSON:** saves the main project, AHUs, schemes and demand sources for reopening. **Save as** changes the path; **Duplicate as new scheme** creates a new project identity.
- **Standalone AHU JSON:** use **Save AHU as**. V5.5.8 can save invalid raw drafts after confirmation; correction is still required before calculation/export. Standalone AHUs have no background autosave, so save manually before leaving.
- **TXT/HTML reports:** for reading, printing or sharing. Print HTML to PDF with a browser. A report cannot be reopened as a workspace.

<a id="equipment"></a>
## How do I start with equipment Excel/CSV files?

Export a template from **Equipment schedules**, enter actual equipment, then import it for analysis. Set **Enabled (1/0)** to 1 for included equipment; template examples default to 0.

Import template-format `.xlsx` or `.csv`, rather than arbitrary spreadsheets. Legacy `.xls` and macro workbooks are not accepted; paste input formulas as values. Results can be exported, and transfers to the main project are previewed for confirmation. [Fields and grouping](guides/equipment.en.md)

<a id="license"></a>
## Can a company use it for paid engineering projects?

The current license permits internal company engineering work, paid engineering projects and delivered calculation reports. Software resale, paid packaging/bundling or paid hosted software services need separate written permission.

[LICENSE](../LICENSE) governs the complete terms; see the [licensing guide](../LICENSE_GUIDE.en.md) for examples. The current edition has a restrictive source-available license. Historical MIT editions retain their original license rights.

<a id="support"></a>
## How do I report a launch problem or a different calculation result?

Use [GitHub Issues](https://github.com/azx4121/facility-studio/issues). Include app/OS version and CPU, steps, every input and unit, expected/actual results and the error screen. For engineering questions, include your independent calculation if available.

For startup failures, you can include logs:

- Windows: `%LOCALAPPDATA%\Facility_Studio_V5_5\Logs`
- macOS startup: `~/Library/Logs/Facility_Studio_V5_5/`; UI errors: `~/Library/Application Support/Facility_Studio_V5_5/error.log`

Use synthetic data and remove client/site secrets. Native and historical evidence are available through the [documentation center](README.en.md).

**DESIGNED BY ANDY HUANG ©**
