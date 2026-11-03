# Wet-bulb trial-state boundary correction

## Reproduction and engineering interpretation

Base source: `731e416011251c96c4ca622832cc99b5fc914859`.

The state **75°C dry bulb, 60 kPa(abs), w = 0.99 kg/kg dry air** is admissible under the existing model bounds: dry bulb −60…90°C, pressure 60…120 kPa, humidity ratio 0…1 kg/kg, and no supersaturation. It has:

- Vapor pressure: 36.849892521 kPa, below the 60 kPa total pressure.
- Relative humidity: 95.484949424%, below saturation.
- Saturation humidity ratio at the dry bulb: 1.121203460 kg/kg.
- Corrected model wet bulb: **73.912065355°C**.
- PsychroLib 2.5.0 reference wet bulb: 73.911866250°C. The 0.000199105°C difference is inside its 0.001°C bisection tolerance and this project's established 0.002°C comparison tolerance.

Before this correction, `state_tw(75, .99, 60)` succeeded but the public psychrometric calculator raised “不可大於 1” while calculating the wet bulb. It incorrectly validated an internal saturated trial as though it were the user's final air state. This is a false rejection, not evidence that the final state is supersaturated or that previously returned ordinary HVAC results were unsafe.

These high-moisture cases are atypical of comfort HVAC. Passing these checks establishes implementation consistency with the existing psychrometric equations and supported ranges, not independent high-temperature process-design certification.

## Scoped changes

- The wet-bulb solver validates its requested final state as before. It computes trial saturation humidity directly, without imposing the user's w ≤ 1 bound on the trial. A trial reaching total vapor pressure narrows the bracket instead of dividing by zero or using a negative humidity ratio.
- The dry-bulb + wet-bulb inverse solver narrows trial RH values that would imply w > 1 or vapor pressure at/above total pressure. It validates the final state and its wet-bulb residual, so an out-of-range request is rejected rather than silently clipped to w = 1.
- The inverse solver preserves its normal midpoint result, falling back to the validated lower bracket only when the final midpoint is outside the supported domain.
- Added an English translation for the explicit inverse out-of-range error.
- The product's public temperature, pressure, RH, humidity-ratio, supersaturation and mode-specific limits are unchanged. In particular, enthalpy + humidity-ratio mode still has its narrower 500 g/kg input limit.
- Windows and macOS source changes are identical. No installer payload, historical evidence, release binary or native computer is modified by the patch.

## Repeatable verification

```sh
python tools/verify_wetbulb_boundaries.py --platform windows --output wetbulb-windows.json
python tools/verify_wetbulb_boundaries.py --platform macos --output wetbulb-macos.json
python tools/verify_platform_sync.py
python windows/tests/reference_psychrometrics.py
python macos/tests/reference_psychrometrics.py
python windows/tests/v554_features.py
python macos/tests/v554_features.py
python windows/tests/simple_features.py
python windows/tests/regression.py
python windows/tests/bilingual.py
python macos/tests/bilingual.py
```

The new checker covers 2,290 checks per source tree, including eight high-humidity states, forward/reference and inverse round trips, 460 supported sweep states, and actual invalid final states. Sixteen unsupported sweep combinations are classified by the unchanged public validator, not silently accepted. Maximum wet-bulb reference difference in the sweep is 0.000480523°C.

Existing checks passed in the isolated Linux workspace: 1,320 reference checks per tree, 646 calculation/import/report/chart checks per tree, 6,636 localization/import/persistence checks per tree, 375 short-form checks and 1,247 general regression checks. Source synchronization, compilation and the new checker's Ruff check passed. These are source checks, not Windows EXE or macOS App native acceptance; no GUI/native build is claimed.

An additional comparison against the base commit checked 616 ordinary forward/inverse state results. The largest absolute difference in any returned numeric quantity was 2.274×10⁻¹³ (dew-point temperature); the largest wet-bulb difference was 2.843×10⁻¹⁴°C. The solver correction therefore preserves ordinary results to floating-point precision.

## Separate pre-existing precision corner

This patch deliberately does not loosen the public humidity cap. At an exact mathematical w = 1 boundary, converting through floating-point RH can produce 1.0000000000000002, for example at 85°C/80 kPa. The unchanged strict validator can reject that round trip. The reported w = 0.99 case is not this precision issue. Any later boundary-normalization change should be separately reviewed and tested without admitting genuinely out-of-range humidity.

## Formula reference

[PsychroLib's wet-bulb and humidity-ratio implementation](https://psychrometrics.github.io/psychrolib/_modules/psychrolib.html) cites ASHRAE Handbook—Fundamentals (2017), chapter 1, equations 33 and 35. The test uses its independently implemented wet-bulb solver and humidity-balance inverse, not values generated by the corrected application solver itself.
