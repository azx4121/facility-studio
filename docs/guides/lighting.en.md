# Lighting calculator: m² / m³, lumens, lux and luminaire count

[繁體中文](lighting.md) · [All guides](README.en.md) · [Downloads](../../README.en.md#download-and-run)

Open **Lighting** and choose illuminance estimation or luminaire-count calculation. Space input can be m², Taiwan ping, length × width or m³. For volume, enter the clear height of **the same room**: `illuminated area = volume / clear height`. Enter volume, not area, in the m³ field.

Luminaire output is **lumens (lm)**; illuminance is **lux = lm/m²**. Watts alone do not determine lux. Use manufacturer lumens when known; an LED-watts estimate must retain its assumed efficacy.

Windows **win.5 and later (currently win.8)**: the catalogue-U/room-index action retains the current area, calculation mode and lumen source. For m², ping or volume it asks you to select length × width and enter the actual dimensions; it never adopts hidden dimension drafts. K requires actual geometry, and U still comes from the manufacturer's photometric/reflectance data. See [F07 correction and acceptance](../2026-10-18-windows-lighting-f07.md). macOS mac.6 has not received this interaction fix.

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

U, M and 100 lm/W are example assumptions. Confirm luminaire data, reflectance, installation height, cleaning and aging. This tool estimates average illuminance; it does not simulate photometric files, glare, point illuminance or uniformity.

Inputs: [08](../examples/08-lighting.json), [09](../examples/09-lighting.json). [Windows win.7 source checks](../evidence/2026-10-18-audit-six/windows-use-cases.json).

## Lighting design report (FEED estimate)

Advanced conditions now include optional project, room, luminaire model, catalogue/photometric source, and design/U/M basis fields. These identify the report and record references; they do not change calculations or import/verify a photometric file.

Lighting result export defaults to HTML. Open it and select Print / Save as PDF for the A4 portrait layout. TXT remains available, and combined HTML summaries include lighting details.

The report lists adopted geometry, average illuminance, luminaire schedule, total complete-luminaire flux, W, W/m², and W/m²/100 lx using the actual calculated average. The normalized metric is not applicable at zero illuminance. Hidden length, width and mounting-height drafts are never presented as adopted geometry.

Emin, Emax, uniformity, surface illuminance, grids, isolux contours, reflections and UGR remain explicitly uncalculated. This is not a DIALux-equivalent simulation or a compliance assessment. Point calculation needs manufacturer IES/LDT photometry, positions/orientations, room and workplane geometry, and a grid; reflection results additionally need reflectances and an appropriate solver.

## Layout / direct illuminance (second-stage candidate)

A separate workspace imports a strict supported subset of IES/LDT, accepts explicit fixture positions and file-C0 yaw, and calculates sampled horizontal-plane direct illuminance with uniformity and interpolated isolux contours. It exports HTML/CSV/JSON. It does not calculate reflections, shadows, daylight, UGR or compliance and is not DIALux-equivalent. The existing lumen method remains independent. See the [scope and validation record](../2026-11-03-direct-lighting.md).
