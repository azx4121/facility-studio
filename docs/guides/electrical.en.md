# Electrical calculator: kW, current, NFB and conductor candidates

[繁體中文](electrical.md) · [All guides](README.en.md) · [Downloads](../../README.en.md#download-and-run)

<a id="source-revision"></a>
## Current source: efficiency, continuous-load preselection and device import

This section describes the repository revision. Published V5.6.0 cases below retain their original conditions and results at `eta=1`. These source changes require separate packaging and native acceptance before appearing in a new download.

**Efficiency eta** defaults to 1 for electrical input kW. For motor shaft-output kW, enter the actual motor efficiency, for example 0.90; do not divide by efficiency before entry and then divide again here. Three-phase current is `I=P x 1000/(sqrt(3) x V x PF x eta)`; single phase omits sqrt(3). The full workbench retains its HP-to-electrical-input conversion.

A separate continuous-load preselection shows `1.25 x operating current` and rounds up against reference AT sizes. Read this separately from the cable/protection candidate calculated for General load, Continuous load or Motor. Displaying the extra preselection does not change the original general-load case's candidate. The 125% estimate does not establish complete motor compliance or replace starting, overload, short-circuit and coordination checks. Requirements above the reference catalogue remain unselected rather than being capped at its maximum.

Before **Import upstream**, enter the import-specific MAU electrical input, process electrical input, and chiller COP or input kW. The import combines current FFU, lighting and pump electrical inputs with these explicit entries. Explicit chiller input takes priority over COP; otherwise chiller electrical input is cooling kW divided by COP. Occupant heat, envelope heat, DCC cooling and equipment room sensible heat are not electrical loads. Missing MAU, process and chiller inputs are identified separately. Check exhaust fans, cooling towers and other auxiliaries too.

The pipeline API also accepts a named schedule of explicit device inputs. Duplicate sources are rejected, including a scheduled `Chiller` already represented by its dedicated input or COP calculation. Reimport updates the sources without adding a previous feeder total again. The full workbench reports UP/NP panel candidates separately and does not add their AT ratings as a main-breaker selection.


Select **English** at the top right, then open **Electrical sizing**. Enter equipment input power, supply and use type. **kW defaults to electrical input power** at eta=1. The current source also accepts shaft-output kW with the actual motor efficiency. Convert HP to mechanical kW first; do not enter HP as electrical input.

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

## Workbench largest-motor input and derating

For general loads containing listed HP motors, or the motor-load category, enter the largest motor within the listed HP total. The preliminary rule is `I_design = I_total + 0.25 × I_largest_motor`; 0 means unknown and conservatively uses `1.25 × I_total`. Continuous loads always use `1.25 × I_total`; the largest-motor draft is inactive and excluded. If loads are only kW/A, list the corresponding motor in HP before entering its largest HP. Validation identifies the relevant field.

This estimate uses shared PF/efficiency and does not replace required motor FLC tables, separate mixed continuous-load calculations or motor protection selection. Workbench ambient/grouping derating follows dropdown ranges, using the ambient upper bound. Independent tools use entered ambient and conductor counts. Reports show the adopted factors.
