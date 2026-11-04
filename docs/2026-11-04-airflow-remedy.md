# Airflow remedy: do not promise an unverified water-temperature cure

## Confirmed defect and physical cause

A schema-valid mixed-air AHU at room 22°C/95%RH, no occupants or room moisture generation, C2 water 20°C and approach 1 K returns airflow inflation 11.5222059665. The old quality text nevertheless advised water at or below 20.14°C, although the current water was already colder. The same result remains at water 19.06°C and 7°C. Room 22°C/90%RH is another case, with 5.6370714532 inflation that persists from water 19°C to 18°C.

With zero room moisture, supply humidity equals room humidity. Under positive sensible cooling, supply temperature increases monotonically with airflow and must not be below that humidity's dew point. At 95%RH the dew point is 21.16179536°C, leaving only about 0.8382 K of supply temperature difference. Changing water alone cannot remove this room-balance and saturation constraint.

## Conservative correction

- No unverified numeric chilled-water remedy is published. `chw_needed_c` remains a compatible result key but is now `None`; `chw_remedy_verified` is false.
- Failed airflow quality gates now request a full recalculation of room targets, supply dew point, coil ADP/BF and reheat. They do not promise that lowering water alone clears the gate and do not generically recommend increasing room RH.
- A stronger water-only impossibility warning is limited to the analytically provable case: exactly zero room moisture, positive sensible load, and supply below room dew point even at the maximum airflow permitted by the existing inflation threshold. No such proof is extended to positive, even very small, room moisture generation.
- When the actual searched point is at this saturation boundary and that boundary is above the water ADP floor, the governing label identifies supply saturation / room dew point. The existing engine still overrides this label when the full C2 solver was the active search constraint.

This deliberately withdraws numerical advice that was not validated against the complete model, including cases where the previous moisture formula happened to work. It does not implement a new automatic design optimizer. Future numerical advice requires a demonstrated feasible remedy, not merely a necessary analytic bound.

## Unchanged behavior

The main engine, C2 solver, search bounds, tolerances, physical rejection rules, airflow, loads, capacities and quality pass/fail limits are unchanged. The dry-versus-wet specific-heat metadata issue was not changed in this patch. Physical existence errors continue to give their existing necessary water/dew-point boundary; this patch concerns remedies attached to calculated but impractical designs.

## Tests and provenance

`integration/test_airflow_remedy.py` covers the exact 95% and 90% cases, independent saturation/room-balance limits, lower-RH boundaries, positive-moisture qualification, Chinese/English text, ordinary design and a truly impossible humidity case. The historical airflow scan retains its calculation and gate assertions, replacing only the obsolete numeric-advice guarantee with explicit conservative-warning assertions.

This is a separate increment after `bf-airflow-search.patch`, whose identity is unchanged. The copied baseline also includes the separately verified two-file BF test-oracle update from the integration task. That test-only update is not duplicated in this increment. Native macOS/Windows GUI or binary validation is not implied by source-level tests.
