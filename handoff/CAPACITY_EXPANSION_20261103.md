# Current, expansion and alternative capacity source candidate

This records the initial capacity candidate. Later integration hardening, schema-2 demand completeness, and final combined verification are recorded in [Capacity integration review](CAPACITY_INTEGRATION_REVIEW_20261103.md).

Base: `692fa047`. Isolated branch: `feat/feed-expansion-capacity`. All work was performed in the cloud source worktree. No Mac-host files, remote repository, published release, installer or packaged App was changed.

## Delivered source scope

- New `capacity_planning.py` model for electricity kW, CHW/PCW LPM and exhaust actual CMH; explicit current/expansion phases, per-case demands, source margins, one additional margin, and named alternatives.
- Normal capacity and largest-single-unit N−1 arithmetic; headroom and deficits for every simultaneous case. Separate season peaks are not incorrectly added. Water equivalent kW is an alternative representation of the same flow, never an extra demand.
- Exact supply-boundary and physical-condition grouping, independent source identities, duplicate rejection and stable-ID replacement. Missing values remain unknown, missing capacity is not zero, and partial schedules cannot be treated as a complete plant register.
- `design_workflow` now captures the existing `contributions` ledger once. It deliberately excludes already-adopted main totals and non-imported baseline loads. It preserves pending conditions, source revisions, original-source hashes and AHU stale warnings; it does not claim the pre-existing ledger or A/B functions were absent.
- Editable independent desktop capacity-plan window, JSON save/load, explicit alternative selections, recalculated text reports, source-change invalidation, unsaved-draft protection and CLI `--capacity-plan` / `--capacity-workspace`.
- Actual AHU change events invalidate capacity previews through the receipt refresh path. Export recomputes again after a modal destination dialog so intervening source changes cannot export a previously adequate cached result. Saving likewise rereads the form after the dialog.
- Windows/macOS product source and English mappings synchronized. Existing historical installer payloads are untouched.

## Synthetic examples and evidence

`tools/verify_capacity_planning.py` writes deterministic plans, reports, results and independently stated expectations. Cases include:

1. `(100 + 60) × 1.1 = 176 kW`; `3 × 100 × 0.9 = 270 kW` normal and `2 × 100 × 0.9 = 180 kW` N−1.
2. Coincident CHW totals `100 + 60 = 160` and `50 + 100 = 150 LPM`; peak is 160, not 200.
3. PCW `4 × 80 × 0.75 = 240 LPM`; `240 / 60000 × 1000 × 4.1868 × 5 = 83.736 kW`. No extra 83.736 is added to 240.
4. Exhaust at identical actual temperature, pressure and static duty: `(1000 + 600) × 1.1 = 1760 CMH`.

All examples are explicitly synthetic. No real factory/office/expansion dataset, owner design basis, manufacturer rating approval or engineering acceptance was supplied or inferred.

## Verification boundaries

- Focused capacity/model/controller suite on each platform's source: 62 passed. Two real-Tk tests are collected but skipped locally because the executor has no display.
- Independent model review: 54/54 checks passed. Independent adversarial review found and verified fixes for long ledger IDs/names, malformed exhaust values, AHU-change invalidation, and export modal-dialog race.
- Existing related regression scripts passed: 52 scenarios / 1,247 independent checks, v5.5.2 core 510 checks, v5.5.6 54 scenarios, panel demand 46 checks, fluid adoption 28, fluid selection history 33 and AHU boundaries 5.
- English parity: 20 scenarios / 7,129 checks passed before the final single informational source-scope sentence. Final static translation scan and focused tests cover that sentence.
- Broader numeric integration: 257 passed. Exact candidate hash and logs are recorded with the external evidence bundle.
- Actual desktop rendering, minimum-window behavior on Windows/macOS, packaged App/EXE, offline migration and installer acceptance were **not run**. Native Tk tests are added to source CI with `FACILITY_REQUIRE_DISPLAY=1`, which makes missing display a failure rather than a silent skip in that job. No CI or remote publication was triggered here.

This is a reviewable source feature, not a release or complete FEED certification. N−1 only models loss of one capacity unit and assumes remaining units can supply concurrently; network bottlenecks, common-cause failures, switching, kVA/reactive/starting demand, protection and field evidence remain outside its scope.

User guide: `docs/planning/capacity-expansion.md`.
