# Electrical calculator: kW, current, NFB and conductor candidates

[繁體中文](electrical.md) · [All guides](README.en.md) · [Downloads](../../README.en.md#download-and-run)

Select **English** at the top right, then open **Electrical sizing**. Enter equipment input power, supply and use type. **kW means electrical input power**; convert motor shaft kW or HP using efficiency before using this quick tool.

Under **Adjust defaults / advanced settings**, check PF, one-way cable length, ambient temperature, loaded conductors and terminal temperature. The example defaults are PF 0.85, copper XLPE, 30 m one-way, 35°C ambient, 60°C terminals, three conductors in conduit and 3% maximum voltage drop. These are reference assumptions, not universal installation rules.

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
