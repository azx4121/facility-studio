# PCW / CHW / hot water: flow, kW, RT, ΔT and pipe size

[繁體中文](water.md) · [All guides](README.en.md) · [Downloads](../../README.en.md#download-and-run)

<a id="source-revision"></a>
## Current source: heat load to chilled water and pump

These features are included in Windows win.7 and macOS mac.6; the subsequent Windows-only audit corrections are described below.

Heat load estimate separates lighting, envelope, occupant sensible/latent heat, equipment room heat and FFU fan heat. Envelope 20 W/m2, FFU 0.18 kW per unit and OA enthalpy difference 50 kJ/kg are editable preliminary assumptions. Keep the enthalpy endpoint and control volume consistent:

| OA enthalpy basis | Preliminary total chiller cooling |
| --- | --- |
| Outdoor air to room reference | Room sensible + occupant latent + MAU total cooling; neutral-supply approximation assigns room sensible heat to DCC |
| Outdoor air to actual leaving dew-point state | DCC sensible + MAU total cooling; do not add occupant latent heat again when the leaving state already removes it |

Actual-dew-point mode can subtract an explicitly entered **MAU room sensible cooling credit** from DCC demand. Also enter the room-minus-MAU-supply temperature difference. Credit cannot exceed the conservative air-side bound `1.2 x OA/3600 x 1.006 x temperature difference`. No credit gives an uncredited upper-bound cooling load. Zero OA with occupant latent heat is rejected. This quick tool does not solve the full humidity, reheat and equipment-feasibility problem; use the main heat/moisture balance for final dry-coil demand.

After calculating heat load, use **Import upstream** in Water / heat load, then confirm water delta T. Advanced inputs include critical route length, sum K and equipment/terminal pressure loss. Default roughness is 0.045 mm. Convert both bore and roughness to metres for dimensionless epsilon/D. Parallel pipes use flow per branch. Zero equipment loss means it has not been included, not that the equipment has no resistance.

In Chilled-water pump, import flow and included route head. Enter only terminal losses absent from the piping calculation. `H=(route loss+additional terminal loss) x (1+allowance/100)+open-system static head`. Enter zero static head for closed loops; do not add building height.

| Power | Clean-water definition | Use |
| --- | --- | --- |
| Hydraulic | Q(m3/h) x H(m) x 9.81/3600 | Power delivered to the fluid |
| Shaft | Hydraulic / pump efficiency | Required mechanical motor output |
| Motor electrical input | Shaft / motor efficiency | Electrical-demand import |
| Recommended motor nameplate | Shaft x 1.15, rounded up to a standard size | Rated mechanical output kW, not electrical input |

Above the 75 kW reference catalogue, select a larger rating separately. Verify the pump curve, NPSH, terminal equipment and actual circuit. Without equipment losses, pump head remains a piping subtotal. Chiller cooling is not chiller electrical input; see the [electrical import scope](electrical.en.md#source-revision).


Open **Water / heat load in the sidebar**. Choose **Known water flow** or **Known heat load**. Example defaults: clean-water density 1,000 kg/m³, specific heat 4.1868 kJ/(kg·K), maximum water velocity 1.5 m/s. Flow units include LPM, US GPM and m³/h.

V5.6 extends automatic references to 30 inches, choosing one pipe within the velocity limit before parallel circuits. Added 14-30 inch carbon-steel STD references use 9.5 mm walls; enter the actual ID in the workbench when supplied dimensions differ. Examples: 7,000 LPM / 1 m/s → one 16-inch pipe, ID 387.4 mm; 30,000 LPM / 2 m/s → one 24-inch pipe, ID 590.6 mm. [Dimension sources and verification](../2026-10-12-v5.6-expansion.md)

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

Inputs: [10](../examples/10-water.json), [11](../examples/11-water.json). [Windows win.7 source checks](../evidence/2026-10-18-audit-six/windows-use-cases.json).


2026-10-16: STD reference bores at 26/28/30 inches are 641.4/692.2/743.0 mm (OD minus two 9.5 mm walls), checked against the [supplier table](https://www.snyi.com.tw/product-femco01.html). Confirm supplied material and wall thickness.

## Windows win.7: K reports and pump units

Water TXT/HTML reports show the actual adopted ΣK. Local loss remains `Δp=ΣK×ρ×v²/2`; it is not added twice. Pump-unit switching preserves physical flow: 100 LPM = 6 m³/h ≈ 26.4172 US GPM. With unchanged head and efficiencies, shaft/input power and motor selection remain unchanged. These fixes began in win.6 and are retained in win.7; mac.6 has not received them. [Independent checks](../2026-10-18-windows-audit-six.md#english).
