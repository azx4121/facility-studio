# FAQ | Facility Studio 5.7.3

[繁體中文](faq.md) · [Download/status](../README.en.md#download-and-run) · [Guides](guides/README.en.md)

**Native acceptance and platform publication status are determined by CI records and Release evidence for the exact source commit. A platform download is valid only when its matching Release provides the package and SHA256.** Historical passes do not validate new binaries.

## Do I need Python or internet access?

Packaged builds include the runtime. Calculations, projects and bundled help work locally. GitHub, external references and updates need internet access.

<a id="compatibility"></a>
## Platforms and installation

- Windows x64: Windows 10/11 are support targets; the final packages require Windows Server 2022/2025 acceptance. Windows ARM and 32-bit are not claimed tested.
- Installer: select a new empty directory. It creates application/uninstall entries, must not overwrite an occupied directory, and uninstall should remove only manifest-listed installed files, preserving later user files.
- Portable: extract the entire ZIP and run its EXE; do not copy the EXE alone. Portable does not imply that all data is beside the executable.
- Mac: this delivery targets Apple Silicon ARM64 ZIP containing `Facility Studio 5.7.3.app`, not Universal, Intel or DMG. Final tested macOS hosts/minimum support must be stated in the [acceptance record](verification/5.7.3-release-acceptance.md) and Release; old macOS 11+/Intel claims do not transfer.

Enterprise policies and other physical systems need individual confirmation.

<a id="v560-tools"></a><a id="pv"></a>
## Where are PV and liquid tools?

The 12 direct tools are electrical, ducts, CDA/process gases, PV vacuum, lighting, water/heat, liquid/pure-water piping, psychrometrics, units, cleanroom airflow, heat-load estimate and chilled-water pumps. PV is independent, not a positive-pressure gas option, and does not require opening the full workbench.

Pipe tables and gas/property data have defined limits. Unknown liquids must not silently use water properties; additional gases need a design velocity. See [water](guides/water.en.md) and [gas/vacuum](guides/gas-vacuum.en.md).

<a id="results"></a>
## Does a successful calculation approve the design?

No. Calculation complete means a numeric result exists; data required means missing vendor/site/property/review inputs; conditions not met means a known capacity/condition fails; stale/recalculation required means the result no longer represents current inputs. Recalculate upstream and explicitly reimport downstream. Export success does not remove warnings.

AHU required states differ from achievable supply. Known subtotals are not complete capacity demand. “Documents complete, ready for engineering review” does not verify identities, signatures or engineering compliance. See [design review](guides/design-review.en.md).

The tool assists selected FEED calculations and document preparation within scope; it does not certify FEED, regulatory compliance or vendor performance. Complete networks, protection coordination, construction drawings and field acceptance remain separate.

<a id="saving"></a>
## Data, logs, upgrades and rollback

The formal default is `~/Facility Studio Data-5.7.3` under the user's home directory (`%USERPROFILE%` normally on Windows). Startup output is in `啟動與驗收記錄.log` there. Advanced environment configuration can override the data root; mention overrides in bug reports. Old LOCALAPPDATA/Library paths are not this release's default.

- Workbench JSON, standalone AHU, capacity plans and design reviews have separate save flows. Saving a workbench project does not save an independent capacity plan.
- TXT/HTML reports and direct-lighting result JSON are not reopenable full projects.
- Transfer an entire design-review folder including its evidence snapshots.
- Back up before upgrading. Old release/preview data is not automatically migrated or overwritten. Import a copy, recalculate and verify it.
- Roll back with the older application and its original backup, not by overwriting a new-format project with an old application.

<a id="security"></a>
## Security prompts

Windows trusted-publisher signing and Mac Developer ID/Apple notarization require verification evidence for the exact artifact; do not infer them from the version name. Mac ad-hoc integrity checks are not publisher authentication. Check the source and published version/SHA256, follow IT policy, and do not disable antivirus, Gatekeeper or system protection. [Security guide](signing.en.md)

<a id="decimal"></a>
## Keypad or window problems

Check the version, editable state, Num Lock and input method. Report keyboard, window, scaling and expected/actual action. [Historical keypad fixes](2026-10-11-v5.5.10-keypad.md) are not a new-machine acceptance result.

<a id="first-project"></a><a id="equipment"></a>
## Starting a project or equipment import

Start with [one tool or the walkthrough](guides/workbench.en.md). Export the equipment template, enable required rows and use its `.xlsx`/`.csv` structure; paste formula values. Arbitrary `.xls`/macro workbooks are not supported. Preview and confirm before import. [Equipment guide](guides/equipment.en.md)

<a id="license"></a>
## Company and paid engineering work

See [LICENSE](../LICENSE) and [examples](../LICENSE_GUIDE.en.md) for permitted work and resale/service restrictions. A formal version name does not change licensing.

<a id="support"></a>
## Reporting issues

Use [Issues](https://github.com/azx4121/facility-studio/issues) with version, OS/CPU, steps, inputs/units, expected/actual results and relevant logs. Remove secrets, personal paths and customer data.

Historical win.6+ ledger v2 incompatibility with mac.6 describes those releases only; 5.7.3 cross-platform round trips still require same-version acceptance.

正式入口在內部設定專屬資料變數 `FACILITY_STUDIO_DATA`，不改寫系統 `LOCALAPPDATA`；這不是使用者預先設定該變數即可覆寫預設路徑的承諾。 / The entry sets the dedicated `FACILITY_STUDIO_DATA` variable internally without rewriting system `LOCALAPPDATA`; this does not promise that presetting that variable overrides the default.
