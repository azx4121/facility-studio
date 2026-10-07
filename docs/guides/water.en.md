# PCW / CHW / hot water: flow, kW, RT, ΔT and pipe size

[繁體中文](water.md) · [All guides](README.en.md) · [Downloads](../../README.en.md#download-and-run)

Open **More quick tools → Water / heat load**. Choose **Known water flow** or **Known heat load**. Example defaults: clean-water density 1,000 kg/m³, specific heat 4.1868 kJ/(kg·K), maximum water velocity 1.5 m/s. Flow units include LPM, US GPM and m³/h.

`Q[kW] = LPM/60000 × ρ × cp × ΔT[K]`

US RT uses 3.51685284 kW/RT. ΔT is the supply/return **temperature difference**, not either water temperature. Glycol and other liquids need their applicable properties; do not use the clean-water defaults unchanged.

<a id="case-10"></a>
## Case 10: PCW 100 LPM, ΔT 5 K

`100/60000 × 1000 × 4.1868 × 5 = 34.89 kW ≈ 9.921 US RT`

At maximum velocity 1.5 m/s, candidate 40A (1-1/2 in), reference ID 40.9 mm, actual velocity 1.269 m/s.

<a id="case-11"></a>
## Case 11: CHW 100 kW, ΔT 5 K

`LPM = 100 × 60000 / (1000 × 4.1868 × 5) = 286.615 LPM`

Candidate 65A (2-1/2 in), reference ID 67.9 mm, velocity 1.319 m/s.

The candidate satisfies the chosen velocity limit only. Pump head, coil/heat-exchanger loss, complete supply/return routes, expansion vessel, static pressure and NPSH need separate checks.

Inputs: [10](../examples/10-water.json), [11](../examples/11-water.json). [Original inverse-check results](../examples/calculation-results-windows.json).
