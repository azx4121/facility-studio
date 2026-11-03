"""Write deterministic synthetic examples and independently stated hand checks."""
import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("windows", "macos"), default="windows")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / args.platform))
    from facility_studio.capacity_planning import new_plan, new_row, evaluate_plan, capacity_report
    from facility_studio.i18n import set_language
    set_language("zh-Hant", persist=False)
    args.output.mkdir(parents=True, exist_ok=True)
    checks = []
    for system in ("ELECTRIC", "CHW", "PCW", "EXHAUST"):
        plan = new_plan("合成範例 " + system)
        plan.update(synthetic=True, scope="僅本範例明列的合成服務；非真實工廠／辦公室資料", scope_confirmed=True)
        conditions = {
            "ELECTRIC": dict(voltage_v=380, phases=3, frequency_hz=60),
            "CHW": dict(fluid="water", supply_c=7, return_c=12, rho_kg_m3=1000, cp_kj_kgk=4.1868),
            "PCW": dict(fluid="water", supply_c=25, return_c=30, rho_kg_m3=1000, cp_kj_kgk=4.1868),
            "EXHAUST": dict(exhaust_type="GEX", temperature_c=25, absolute_kpa=101.325, required_static_pa=500),
        }[system]
        def row(kind, ident, summer, winter):
            r = new_row(kind, ident, system)
            r.update(boundary="SYNTHETIC-" + system, conditions=conditions.copy(),
                     values=dict(summer=summer, winter=winter),
                     source=dict(reference="Synthetic algebra fixture, no manufacturer claim", revision="R1", fingerprint=""))
            if kind == "capacity":
                r["derating"] = 1.0
            else:
                r["demand_complete"] = True
            return r
        if system in ("ELECTRIC", "EXHAUST"):
            scale = 1 if system == "ELECTRIC" else 10
            a, b, c = row("demand", "current", 100 * scale, 100 * scale), row("demand", "expansion", 60 * scale, 60 * scale), row("capacity", "three-units", 100 * scale, 100 * scale)
            b["phase"], c["quantity"], c["derating"] = "expansion", 3, .9
            plan.update(additional_margin_pct=10, margin_reason="Synthetic explicit additional 10%; not a statutory default")
            plan.update(demands=[a, b], capacities=[c])
        elif system == "CHW":
            a, b, c = row("demand", "current", 100, 50), row("demand", "expansion", 60, 100), row("capacity", "three-units", 100, 100)
            b["phase"], c["quantity"] = "expansion", 3
            plan.update(demands=[a, b], capacities=[c])
        else:
            a, c = row("demand", "four-tools", 80, 80), row("capacity", "two-units", 300, 300)
            a["quantity"], a["coincidence"], c["quantity"] = 4, .75, 2
            plan.update(demands=[a], capacities=[c])
        result = evaluate_plan(plan)
        plan = result["plan"]  # emit the adopted normalized inputs matching plan_hash
        group = result["alternatives"][0]["groups"][0]
        first = group["cases"][0]
        if system in ("ELECTRIC", "EXHAUST"):
            expected = (176, 270, 180) if system == "ELECTRIC" else (1760, 2700, 1800)
            actual = tuple(first[k] for k in ("design_demand", "normal_capacity", "n_minus_one_capacity"))
            assert all(abs(a - e) < 1e-8 for a, e in zip(actual, expected)), (system, actual)
            checks.append(dict(system=system, independent_expected=expected, actual=actual,
                               hand_calculation="(100+60)*1.1=176; 3*100*.9=270; (3-1)*100*.9=180" + ("; exhaust scale x10" if system == "EXHAUST" else "")))
        elif system == "CHW":
            actual = [x["design_demand"] for x in group["cases"]]
            assert actual == [160, 150] and group["peak_design_demand"] == 160
            checks.append(dict(system=system, independent_expected=[160, 150], actual=actual, hand_calculation="summer100+60=160; winter50+100=150; max160, not200"))
        else:
            actual = [first["design_demand"], first["equivalent_thermal_kw"]]
            assert abs(actual[0] - 240) < 1e-8 and abs(actual[1] - 83.736) < 1e-8
            checks.append(dict(system=system, independent_expected=[240, 83.736], actual=actual, hand_calculation="4*80*.75=240 LPM; 240/60000*1000*4.1868*5=83.736kW; same load, not summed"))
        stem = system.lower()
        for suffix, content in (("plan.json", plan), ("result.json", result)):
            (args.output / (stem + "-" + suffix)).write_text(json.dumps(content, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        (args.output / (stem + "-report.txt")).write_text(capacity_report(result), encoding="utf-8")
    evidence = dict(platform_source=args.platform, synthetic_only=True, not_real_project_validation=True, checks=checks)
    (args.output / "independent-expectations.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
