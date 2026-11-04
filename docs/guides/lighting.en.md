# Lighting calculator: m² / m³, lumens, lux and luminaire count

**5.7.3 version guide: native acceptance and publication status are established by CI records and Release attachments for the corresponding commit; this guide does not assert a pass.** Older version-labelled examples, screenshots and pass counts below are historical evidence, not a fresh 5.7.3 run. [Release status](../verification/5.7.3-release-acceptance.md).

U is an adopted catalogue utilization factor; K supports lookup, not a universal U(K) function. Supported IES/LDT layouts calculate direct illuminance, not complete room reflections or UGR. Retain photometric files, orientation, work-plane and unit evidence; numeric results do not certify a complete lighting design.

[繁體中文](lighting.md) · [All guides](README.en.md) · [Downloads](../../README.en.md#download-and-run)

Open **Lighting** and choose illuminance estimation or luminaire-count calculation. Space input can be m², Taiwan ping, length × width or m³. For volume, enter the clear height of **the same room**: `illuminated area = volume / clear height`. Enter volume, not area, in the m³ field.

Luminaire output is **lumens (lm)**; illuminance is **lux = lm/m²**. Watts alone do not determine lux. Use manufacturer lumens when known; an LED-watts estimate must retain its assumed efficacy.

This guide follows the **Facility Studio 5.7.3**, with matching Windows/macOS source. Older downloads may differ. Catalogue-U/room-index checks preserve area, calculation mode and lumen source. Select length × width and enter actual dimensions when geometry is needed. Hidden drafts are not adopted; K supports catalogue lookup and does not generate U.

<a id="case-08"></a>
## Case 08: 90 m³, 3 m height, 40 W × 10 luminaires

Select volume and enter 90 m³ and 3 m. Use 40 W per luminaire, count 10, estimated efficacy 100 lm/W, utilization U 0.6 and maintenance factor M 0.8.

`Area = 90/3 = 30 m²`

`Lumens per luminaire = 40 × 100 = 4000 lm`

`Average lux = 10 × 4000 × 0.6 × 0.8 / 30 = 640 lux`

Lighting power is 0.4 kW.

<a id="case-09"></a>
## Case 09: 30 m² and target 500 lux

Choose count calculation, area 30 m², target 500 lux, manufacturer output 4,000 lm per luminaire, 40 W each, U 0.6 and M 0.8.

`N = ceil(500 × 30 / (4000 × 0.6 × 0.8)) = 8`

The rounded-up count gives 512 lux and 0.32 kW. Seven luminaires give only 448 lux.

U, M and 100 lm/W are example assumptions. Confirm luminaire data, reflectance, installation height, cleaning and aging. The lumen method estimates average illuminance without point illuminance or uniformity. Use the separate Layout / direct illuminance workspace for sampled direct light. Neither method establishes glare or regulatory compliance.

Inputs: [08](../examples/08-lighting.json), [09](../examples/09-lighting.json). [Windows win.7 source checks](../evidence/2026-10-18-audit-six/windows-use-cases.json).

## Lighting design report (FEED estimate)

Advanced conditions now include optional project, room, luminaire model, catalogue/photometric source, and design/U/M basis fields. These identify the report and record references; they do not change calculations or import/verify a photometric file.

Lighting result export defaults to HTML. Open it and select Print / Save as PDF for the A4 portrait layout. TXT remains available, and combined HTML summaries include lighting details.

The report lists adopted geometry, average illuminance, luminaire schedule, total complete-luminaire flux, W, W/m², and W/m²/100 lx using the actual calculated average. The normalized metric is not applicable at zero illuminance. Hidden length, width and mounting-height drafts are never presented as adopted geometry.

In the **lumen-method report**, Emin, Emax, uniformity, surface illuminance, grids, isolux contours, reflections and UGR remain explicitly uncalculated. This is not a DIALux-equivalent simulation or a compliance assessment. Point calculation needs manufacturer IES/LDT photometry, positions/orientations, room and workplane geometry, and a grid; reflection results additionally need reflectances and an appropriate solver.

## Layout / direct illuminance (second-stage candidate)

A separate workspace imports a strict supported subset of IES/LDT, accepts explicit fixture positions and file-C0 yaw, and calculates sampled horizontal-plane direct illuminance with uniformity and interpolated isolux contours. It exports HTML/CSV/JSON. It does not calculate reflections, shadows, daylight, UGR or compliance and is not DIALux-equivalent. The existing lumen method remains independent. See the [scope and validation record](../2026-11-03-direct-lighting.md).


Beginner sequence: import a source → enter room/workplane/grid/maintenance → select source ID and rows/columns, then generate an editable layout or fill `ID,x,y,z,yaw,scale` → check orientation → calculate → export HTML/CSV/JSON. Generating a layout replaces the schedule. Maintenance defaults to 1; lumen-method U/M are not inherited. Changed sources, conditions or layout require recalculation, including changes during a save dialog.

ID means photometry source ID. The origin is lower left, +X right, +Y up and z above floor; every luminaire faces down with no tilt. At yaw=0, file C0 points along +X and C90 along +Y. Positive yaw is counterclockwise from above. Confirm the manufacturer's file axes rather than guessing the housing front.

**Saving:** imports are snapshots; reimport changed files explicitly. CSV/JSON preserve results and traceability but this version cannot reopen a direct-lighting project. Retain sources, inputs and layout before closing. Refine the grid to check convergence; sampled extrema are not continuous extrema. Reflections, shadows, daylight and UGR are excluded, and light-output scale is not an electrical-power multiplier.
