# Lighting calculator: m² / m³, lumens, lux and luminaire count

[繁體中文](lighting.md) · [All guides](README.en.md) · [Downloads](../../README.en.md#download-and-run)

Open **Lighting** and choose illuminance estimation or luminaire-count calculation. Space input can be m², Taiwan ping, length × width or m³. For volume, enter the clear height of **the same room**: `illuminated area = volume / clear height`. Enter volume, not area, in the m³ field.

Luminaire output is **lumens (lm)**; illuminance is **lux = lm/m²**. Watts alone do not determine lux. Use manufacturer lumens when known; an LED-watts estimate must retain its assumed efficacy.

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

Inputs: [08](../examples/08-lighting.json), [09](../examples/09-lighting.json). [Original inverse-check results](../examples/calculation-results-windows.json).
