# CDA / N2 / process vacuum: standard flow, actual flow and pressure

[繁體中文](gas-vacuum.md) · [All guides](README.en.md) · [Downloads](../../README.en.md#download-and-run)

Pipe size needs **flow, pressure and a velocity limit**. Pressure and velocity without flow cannot determine a diameter. **CDA / gas piping** supports CDA, N2 and Ar; use the full workbench for other gases and PV. This is a velocity-based cross-section estimate, not a full compressible pipe-loss solver.

SLPM, SCFM and Sm³/h are standard-volume units; ALPM is actual pipe volume flow. Default reference: 25°C and 101.325 kPa absolute. Default pipe temperature and local atmospheric pressure are also 25°C and 101.325 kPa. Check the equipment's reference conditions and adjust them if needed.

`P_absolute = P_gauge + P_local_atmosphere`

`Q_actual = Q_standard × P_standard/P_absolute × T_pipe[K]/T_standard[K]`

The examples use ideal-gas Z ratio 1. Nominal size is not actual inner diameter; material and wall thickness require confirmation.

<a id="case-05"></a>
## Case 05: CDA 800 SLPM, 6 bar(g), maximum 15 m/s

| Result | Value |
| --- | --- |
| Absolute pipe pressure | 701.325 kPa(abs) |
| Actual flow | 115.581 ALPM |
| Minimum theoretical ID | 12.787 mm |
| Table candidate | 1/2 in (15A), reference ID 16.1 mm |
| Actual velocity | 9.462 m/s |

`D_inner[mm] = √(4 × ALPM / 60000 / π / v_limit) × 1000`.

<a id="case-06"></a>
## Case 06: N2 100 Sm³/h, 600 kPa(g), maximum 12 m/s

100 Sm³/h = 1,666.667 SLPM; 600 kPa(g) = 6 bar(g). Actual flow is 240.794 ALPM, minimum ID 20.635 mm. Candidate: 3/4 in (20A), reference ID 21.4 mm, actual velocity 11.158 m/s.

<a id="case-07"></a>
## Case 07: PV 2,000 SLPM, 150 Torr(abs)

In **Full workbench**, open the gas/PV section and enter 2,000 SLPM and 150 Torr absolute. Use maximum velocity 18 m/s, pipe/reference temperature 25°C and Z ratio 1.

150 Torr(abs) = 19.9984 kPa(abs) = 199.984 mbar(abs).
`Q_actual = 2000 × 760/150 = 10,133.333 ALPM`.
Minimum ID is 109.300 mm. The reference table selects 6 in (150A), ID 160.3 mm, velocity 8.368 m/s. Its 4 in candidate has ID 108.3 mm and is too small.

This is a **process-vacuum volume-flow estimate**, not high-vacuum performance, conductance, evacuation time or pump selection. Obtain pump curves, conductance, leaks/outgassing and external-pressure collapse data separately. Torr/kPa/mbar conversion retains the absolute-pressure basis. Supply and remote minimum pressures must satisfy the full workbench's pressure bounds.

Inputs: [05](../examples/05-gas.json), [06](../examples/06-gas.json), [PV scenario 07](../examples/scenarios.json). [Original results](../examples/calculation-results-windows.json).
