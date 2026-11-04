# Facility Studio 5.7.3

Version 5.7.3 operating guide. Native acceptance and platform publication status are determined by CI records and Release evidence for the exact source commit. A platform download is valid only when its matching Release provides the package and SHA256. Preview test results do not validate final packages. Check https://github.com/azx4121/facility-studio/releases for the evidence accompanying your package.

## Start and preserve your data

Windows x64: use the installer with a new empty directory, or extract the entire portable folder and run its EXE. Mac: extract the Apple Silicon ARM64 ZIP and open Facility Studio 5.7.3.app. This is not a Universal/Intel/DMG delivery. No separate Python is required for packaged builds.

The formal default data folder is `Facility Studio Data-5.7.3` in your home directory. Startup output is in `啟動與驗收記錄.log` there; advanced environment settings may override the root. Old release/preview data is not automatically migrated or overwritten. Back up first and import/recalculate copies. Roll back using the older application and its original backup, not by overwriting a new project.

Traditional Chinese is the initial language; select English in the interface. Verify the version and published artifact hash before use. Formal naming does not establish trusted publisher signing or Apple notarization. Do not disable system security to run the application.

## Tools and workflow

1. The sidebar has 12 quick tools, including independent **PV vacuum** and **Liquid/pure-water piping**. PV converts standard gas flow and absolute pressure to actual pipe flow; unit changes preserve the physical value. A necessary pump-speed check is not a complete pump-curve/conductance solution.
2. Select liquid medium, material and flow explicitly. Importing water-tool flow does not replace your material/property choices. Unknown chemicals or mixtures require density, heat capacity, dynamic viscosity and a reliable source. Temperature, pressure or concentration changes invalidate prior property evidence.
3. Pump suction checks require surface absolute pressure, minimum liquid level, total suction-side losses and same-condition vendor NPSHr/margin. Main-route loss is not automatically suction loss. Mixture bubble pressure requires reliable same-condition evidence. Missing inputs, flashing or inadequate margin cannot pass.
4. Insulation uses pipe outside diameter, liquid/ambient conditions, conductivity, surface heat transfer, heat-loss limit and contractual minimum. Do not substitute bore for outside diameter.
5. Recalculate edited upstream data and explicitly reimport linked results. Stale inputs, invalid values or changes during a save dialog can block export. Copy/export success does not turn failed or pending engineering conditions green.
6. AHU required states are not achievable supply. Check seasonal flow, capacity, BF/ADP and infeasible C2 conditions together. Explicitly detach linked sources before an independent calculation. A suggested water temperature is not a feasibility guarantee.
7. Cleanroom ACH basis and MAU/FFU topology must be explicit. Reports distinguish required pressure-relief/exhaust; no pressure guarantee exists without a discharge path. Duct thickness references still require project pressure, reinforcement, joints, materials and contract review.
8. Lighting U is an adopted catalogue value, not a generic function of K. IES/LDT direct illuminance does not include full reflections or UGR. Air charts need valid pressure/states and do not replace equipment feasibility.
9. DI continuous circulation remains at zero process duty. Different PCW supply groups must not be merged. Thermal CHW demand, pump shaft power and equipment electrical input are different quantities.
10. Capacity plans separately record current/expansion demand, supply boundaries and normal/N−1 scenarios. Known subtotals do not establish complete demand. Save the independent capacity plan separately from the workbench project.

## Design basis and delivery review

Create an independent review project; enter design conditions, criteria and specifications as **name | edition | clause | applicable scope | source**. Attach documents explicitly. Attachments are snapshots: source updates require a new attachment and review. Transfer the whole project folder including evidence.

The reviewer must differ from the preparer. Changes to basis/register/evidence invalidate old review. Save/export to new files and retain earlier revisions. “Documents complete, ready for engineering review” checks recorded documents and human review only; it does not authenticate identity, signatures or engineering compliance.

Workbench JSON, standalone AHU, capacity plans and design review have different save scopes. Reports and direct-lighting result JSON are not reopenable full projects. Use the bundled guide for a synthetic practice project before entering real project data.

## Scope and reporting

Facility Studio supports preliminary calculations, option comparison and design-demand documentation within stated scope, including selected FEED activities. Software verification does not certify FEED deliverables, regulatory compliance or vendor performance. Project inputs, same-condition vendor data, complete deliverables and professional review remain necessary. Complete networks, protection coordination, construction drawings and field acceptance require separate work.

Report problems with version, OS/CPU, steps, input units and expected/actual results. Remove customer data and personal paths. Public documentation and actual releases: https://github.com/azx4121/facility-studio

DESIGNED BY ANDY HUANG ©

正式入口在內部設定專屬資料變數 `FACILITY_STUDIO_DATA`，不改寫系統 `LOCALAPPDATA`；這不是使用者預先設定該變數即可覆寫預設路徑的承諾。 / The entry sets the dedicated `FACILITY_STUDIO_DATA` variable internally without rewriting system `LOCALAPPDATA`; this does not promise that presetting that variable overrides the default.
