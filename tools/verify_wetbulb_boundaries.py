"""Check wet-bulb trial states without widening public psychrometric limits."""

import argparse
import itertools
import json
import math
import platform
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("windows", "macos"), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / args.platform))

    import psychrolib
    from facility_studio.engine import wetbulb
    from facility_studio.errors import ValidationError
    from facility_studio.quick_tools import psychrometric
    from facility_studio.utils import MW_RATIO, dewpoint, sat_pa, state_trh, state_tw

    psychrolib.SetUnitSystem(psychrolib.SI)
    checks = []
    cases = []

    def check(name, passed):
        checks.append({"name": name, "passed": bool(passed)})
        assert passed, name

    def reject(name, operation, field=None):
        try:
            operation()
        except ValidationError as error:
            check(name, field is None or error.field_name == field)
        else:
            check(name, False)

    # Exact reported regression and supported high-humidity states. The
    # saturation state at a trial wet-bulb temperature may exceed w=1.
    high_cases = (
        (75, .99, 60), (75, 1, 60), (80, .99, 60), (85, .99, 60),
        (90, .99, 60), (85, .99, 80), (90, .99, 80), (90, .99, 101.325),
    )
    check("reported_saturation_exceeds_public_humidity_limit",
          MW_RATIO * sat_pa(75) / (60000 - sat_pa(75)) > 1)
    for t, w, p in high_cases:
        name = f"high_{t}_{w}_{p}"
        original = state_tw(t, w, p)
        actual = psychrometric("乾球＋RH", t, original["rh"], p)
        reference = psychrolib.GetTWetBulbFromHumRatio(t, w, p * 1000)
        check(name + "_reference", abs(actual["wetbulb_c"] - reference) <= .002)
        recovered = psychrolib.GetHumRatioFromTWetBulb(t, actual["wetbulb_c"], p * 1000)
        check(name + "_balance", abs(recovered - w) <= 1e-10)
        inverse = psychrometric("乾球＋濕球", t, actual["wetbulb_c"], p)
        check(name + "_wetbulb_roundtrip", abs(inverse["w"] - w) <= 1e-10)
        check(name + "_inverse_preserves_limit", 0 <= inverse["w"] <= 1)
        # Dew-point inputs retain their own supported range and guards.
        if w < 1:  # Avoid testing unrelated exact-boundary RH roundoff.
            from_dew = psychrometric("乾球＋露點", t, dewpoint(w, p), p)
            check(name + "_dewpoint_roundtrip", abs(from_dew["w"] - w) <= 1e-10)
        cases.append({"dry_bulb_c": t, "humidity_ratio": w, "pressure_kpa": p,
                      "rh_percent": original["rh"], "wetbulb_c": actual["wetbulb_c"],
                      "reference_wetbulb_c": reference})

    # Hot, low-pressure states that really need w > 1 must still fail. A
    # bounded inverse bracket must not return the nearest permitted state.
    for t, p in ((75, 60), (90, 60), (90, 80), (90, 101.325)):
        for w in (1.0001, 1.01):
            pw = p * 1000 * w / (MW_RATIO + w)
            rh = pw / sat_pa(t) * 100
            twb = psychrolib.GetTWetBulbFromHumRatio(t, w, p * 1000)
            reject(f"out_of_range_rh_{t}_{p}_{w}",
                   lambda t=t, rh=rh, p=p: psychrometric("乾球＋RH", t, rh, p))
            reject(f"out_of_range_wetbulb_{t}_{p}_{w}",
                   lambda t=t, twb=twb, p=p: psychrometric("乾球＋濕球", t, twb, p), "second")
    reject("public_humidity_limit", lambda: state_tw(75, 1.000001, 60))
    reject("public_temperature_limit", lambda: wetbulb(90.001, 20, 60))
    reject("public_pressure_limit", lambda: wetbulb(75, 20, 59.999))
    reject("public_rh_limit", lambda: wetbulb(75, 100.001, 60))
    reject("supersaturated_state", lambda: state_tw(25, .1, 101.325))
    reject("invalid_vapor_pressure", lambda: wetbulb(90, 100, 60))
    reject("wetbulb_above_drybulb", lambda: psychrometric("乾球＋濕球", 25, 25.01, 101.325))
    reject("wetbulb_below_dry_limit", lambda: psychrometric("乾球＋濕球", 25, -60, 101.325))
    reject("enthalpy_mode_limit_unchanged", lambda: psychrometric("焓＋含濕比", 2689.545, 990, 60))

    sweep_count = 0
    skipped = 0
    max_reference_error = 0.0
    for t, rh, p in itertools.product(
        (-60, -50, -20, -1, 0, .01, 1, 15, 22, 35, 45, 60, 70, 75, 80, 85, 90),
        (0, 1, 10, 50, 70, 99, 100), (60, 80, 101.325, 120),
    ):
        try:
            state = state_trh(t, rh, p)
        except ValidationError:
            skipped += 1
            continue
        name = f"sweep_{t}_{rh}_{p}"
        actual = psychrometric("乾球＋RH", t, rh, p)
        twb = actual["wetbulb_c"]
        check(name + "_finite", math.isfinite(twb) and twb <= t + 1e-10)
        if state["w"] >= psychrolib.MIN_HUM_RATIO:
            expected = psychrolib.GetTWetBulbFromHumRatio(t, state["w"], p * 1000)
            error = abs(expected - twb)
            max_reference_error = max(max_reference_error, error)
            check(name + "_reference", error <= .002)
        inverse = psychrometric("乾球＋濕球", t, twb, p)
        check(name + "_inverse_valid", 0 <= inverse["w"] <= 1)
        check(name + "_wetbulb_roundtrip", abs(inverse["wetbulb_c"] - twb) <= 1e-7)
        # The ice/water formula is discontinuous at 0 C. An exact zero can
        # represent a range of W; elsewhere verify the humidity round trip.
        if abs(twb) > 1e-7:
            check(name + "_humidity_roundtrip", abs(inverse["w"] - state["w"]) <= 1e-10)
        sweep_count += 1

    output = {
        "source_platform": args.platform,
        "host_os": platform.system(),
        "python": platform.python_version(),
        "native_binary_acceptance": False,
        "reference": "PsychroLib 2.5.0 SI wet-bulb inverse / humidity balance",
        "reference_source": "https://psychrometrics.github.io/psychrolib/_modules/psychrolib.html",
        "high_humidity_cases": cases,
        "valid_sweep_states": sweep_count,
        "unsupported_sweep_states_skipped": skipped,
        "max_reference_wetbulb_error_c": max_reference_error,
        "checks": checks,
        "failed": sum(not item["passed"] for item in checks),
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{args.platform}: {len(checks)} checks passed; {sweep_count} supported sweep states")


if __name__ == "__main__":
    main()
