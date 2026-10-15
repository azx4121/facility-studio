# Electrical calculator: power, current, NFB and conductor candidates

[繁體中文](electrical.md) · [All guides](README.en.md) · [Downloads](../../README.en.md#download-and-run)

Select **English** at the top right, then open **Electrical sizing**. Enter equipment power, supply and use type. **kW/W mean electrical input power**. HP/PS mean motor shaft output, which the calculator converts to electrical input using motor efficiency.

Under **Adjust defaults / advanced settings**, check PF, one-way cable length, ambient temperature, loaded conductors and terminal temperature. The example defaults are PF 0.85, copper XLPE, 30 m one-way, 35°C ambient, 60°C terminals, three conductors in conduit and 3% maximum voltage drop. These are reference assumptions, not universal installation rules.

<a id="power-units"></a>
## Power units and motor efficiency

The unit dropdown offers kW, W, HP (mechanical horsepower) and PS (metric horsepower). This is a source revision. The published win.3/mac.5 downloads still accept only kW, so convert before entering power in those downloads.

| Input unit | Electrical input in kW |
| --- | --- |
| kW | Entered value |
| W | Entered value / 1000 |
| HP | Entered value × 0.745699871582 / motor efficiency |
| PS | Entered value × 0.73549875 / motor efficiency |

Selecting HP/PS shows **Motor efficiency**, initially 0.90. Use the equipment nameplate or manufacturer's data; efficiency and PF are different inputs. HP/PS use the motor-load estimate of 125% of operating current. kW/W follow the selected use type. Changing units converts the entered value to preserve electrical input power; changing from HP/PS to kW/W retains the motor use type.

For **10 HP, efficiency 0.90, three-phase 380 V and PF 0.85**, electrical input is approximately **8.28555 kW**, operating current **14.8101 A**, and motor design current **18.5126 A**. If electrical input kW is already known, enter kW directly without dividing by efficiency again. Reports state the unit, adopted efficiency and conversion formula. Legacy inputs without a unit remain kW.

<a id="case-01"></a>
## Case 01: 10 kW, three-phase 380 V

| Condition / result | Value |
| --- | --- |
| Electrical input / supply | 10 kW / three-phase 380 V line-to-line |
| Use / PF / one-way length | General load / 0.85 / 30 m |
| Operating and design current | 17.8746 A |
| Candidate | NFB 20 AT; 5.5 mm² per phase × 1 set |
| Effective ampacity | 25 A |
| Voltage drop | 2.903 V; 0.764% |

Formula: `I = P[kW] × 1000 / (√3 × V_line-to-line × PF)`.
Candidates must meet `design current ≤ NFB AT ≤ effective ampacity` and the configured voltage-drop limit. Sizes come from this project's reference tables; actual installation and manufacturer data need review.

<a id="case-02"></a>
## Case 02: 5 kW, single-phase 220 V, continuous load

Use PF 1 and 20 m one-way; retain other defaults. `I = 5000 / (220 × 1) = 22.7273 A`. The tool's 125% continuous-load estimate gives 28.4091 A design current. Candidate: NFB 30 AT, 8 mm² × 1 set, effective ampacity 33 A, voltage drop 1.031%. Single-phase voltage drop includes the outgoing and return conductors; enter the one-way distance.

Resistance heaters may be near PF 1. Motors and drives need their actual data. Motor breaker selection also needs FLC, starting behavior and independent overload protection. Neutral, grounding, short-circuit ratings and protective coordination require separate checks.

<a id="case-19"></a>
## Case 19: fault current, Icu and protective coordination

This request is **outside this tool's complete scope**. Load current and breaker AT are not fault current or interrupting capacity Icu/Ics. Obtain source fault level, transformer impedance, cable impedance and protection curves, then use a suitable model and engineering review.

Inputs: [01](../examples/01-electrical.json), [02](../examples/02-electrical.json). [Original inverse-check results](../examples/calculation-results-windows.json).

## Workbench largest-motor input and derating

For general loads containing listed HP motors, or the motor-load category, enter the largest motor within the listed HP total. The preliminary rule is `I_design = I_total + 0.25 × I_largest_motor`; 0 means unknown and conservatively uses `1.25 × I_total`. Continuous loads always use `1.25 × I_total`; the largest-motor draft is inactive and excluded. If loads are only kW/A, list the corresponding motor in HP before entering its largest HP. Validation identifies the relevant field.

This estimate uses shared PF/efficiency and does not replace required motor FLC tables, separate mixed continuous-load calculations or motor protection selection. Workbench ambient/grouping derating follows dropdown ranges, using the ambient upper bound. Independent tools use entered ambient and conductor counts. Reports show the adopted factors.
