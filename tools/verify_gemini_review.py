#!/usr/bin/env python3
"""Independent specifications for the 2026-10-16 Gemini integration review.

Runs both source trees in separate processes. No checked-in evidence is read as
an oracle. Electrical watts, room geometry, air balance and heat balances are
reconstructed from physical inputs and explicit conversion constants.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import platform
import random
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(source):
    sys.path.insert(0, str(ROOT / source))
    from facility_studio.engine import calculate, migrate_project, validate_project
    from facility_studio.errors import ValidationError
    from facility_studio.reports import executive_summary
    from facility_studio.schema import default_project
    from facility_studio.services import electrical_device_loads, transfer_upstream, calculate_pipeline
    from facility_studio.simple_engines import calculate_tool, ENGINES
    from facility_studio.simple_schema import defaults
    from facility_studio.simple_reports import tool_report

    checks = 0
    rng = random.Random(20261016)
    examples = []

    def check(condition, name):
        nonlocal checks
        if not condition:
            raise AssertionError(name)
        checks += 1

    def near(value, expected, name):
        check(math.isclose(value, expected, rel_tol=1e-10, abs_tol=1e-8),
              f"{name}: {value!r} != {expected!r}")

    def rejected(callback, field, name):
        try:
            callback()
        except ValidationError as error:
            check(error.field_name == field, name + ": field")
        else:
            raise AssertionError(name + ": accepted invalid input")

    def tool(name, **updates):
        return calculate_tool(name, dict(defaults(name), **{k: str(v) for k, v in updates.items()}))

    for index in range(100):
        kw = rng.uniform(.05, 75)
        pf = rng.uniform(.5, 1)
        efficiency = rng.uniform(.65, .97)
        supply, phases, voltage = [
            ("三相 380V", 3, 380), ("三相 220V", 3, 220),
            ("單相 220V", 1, 220), ("單相 110V", 1, 110),
        ][index % 4]
        expected_a = kw * 1000 / ((math.sqrt(3) if phases == 3 else 1) * voltage * pf)
        values = {"kW": kw, "W": kw * 1000, "HP": kw * efficiency / .745699871582,
                  "PS": kw * efficiency / .73549875, "A": expected_a, "kVA": kw / pf}
        baseline = None
        for unit, value in values.items():
            result = tool("electrical", power=value, power_unit=unit, pf=pf,
                          supply=supply, motor_efficiency=efficiency, kind="馬達", length=0)
            near(result["electrical_input_kw"], kw, f"case {index} {unit} input kW")
            near(result["power_kw"], kw, f"case {index} {unit} compatible API input kW")
            near(result["current_a"], expected_a, f"case {index} {unit} current")
            near(result["design_a"], expected_a * 1.25, f"case {index} {unit} design current")
            if baseline is None:
                baseline = result["selected"]
            else:
                check(result["selected"] == baseline, f"case {index} {unit} identical cable/protection")

        length, width, mounting = rng.uniform(5, 90), rng.uniform(5, 40), rng.uniform(3, 8)
        u, maintenance = rng.uniform(.35, .8), rng.uniform(.6, .9)
        lumens, lux = rng.uniform(1500, 15000), rng.uniform(100, 1000)
        lighting = tool("lighting", mode="反算燈數", area_mode="長×寬", length=length, width=width,
                        u_mode="型錄 U＋室指數 K 檢核", mount_h=mounting, work_h=.8,
                        utilization=u, maintenance=maintenance, lumen_mode="燈具型錄流明",
                        lumens=lumens, target=lux)
        near(lighting["utilization"], u, "U must remain the supplied photometric input")
        near(lighting["room_index_k"], length * width / ((mounting - .8) * (length + width)), "room index")
        check(lighting["quantity"] == math.ceil(lux * length * width / (lumens * u * maintenance)), "independent lumen count")

        flow, head, pump_eff, motor_eff = rng.uniform(1, 4000), rng.uniform(1, 100), .72, .91
        pump = tool("pumps", flow=flow, head_m=head, eta_pump=pump_eff, eta_motor=motor_eff)
        near(pump["motor_input_kw"], flow / 60000 * 1000 * 9.81 * head / pump_eff / motor_eff / 1000,
             "pump electric power from Q rho g H")
        pipeline = calculate_pipeline({"cleanroom": {"area": str(100 + index)},
                                       "electrical": {"power_unit": list(values)[index % 6], "chiller_cop": "4"}})
        near(pipeline["electrical"]["power_kw"], sum(row["power_kw"] for row in pipeline["electrical_loads"]),
             "pipeline device sum")
        check(pipeline["adopted_inputs"]["electrical"]["power_unit"] == "kW", "pipeline forces adopted kW")
        if index < 3:
            examples.append({"case": index, "input_kw": kw, "current_a": expected_a,
                             "lighting_qty": lighting["quantity"], "pump_input_kw": pump["motor_input_kw"]})

        project = default_project()
        project["inputs"].update(sys_type="MAU+FFU+DCC (全外氣/無塵室)",
                                 en_L_A="20", en_W_A="20", en_H_A="3", en_L_B="0", en_W_B="0",
                                 en_ach_A=str(40 + index), eq_kw=str(1000 + index * 10),
                                 en_manual_oa=str(10000 + 400 * index),
                                 ffu_topology="MAU入靜壓箱經FFU送風", ffu_airflow_basis="室內基本循環（另加OA）")
        original = copy.deepcopy(project)
        main = calculate(project)
        near(main["ffu_total_cmh"], 1200 * (40 + index) + main["oa_room_cmh"], "FFU plenum air balance")
        near(main["dcc_return_cmh"], 1200 * (40 + index), "DCC return flow")
        check(main["ffu_count"] == math.ceil(main["ffu_total_cmh"] / float(project["inputs"]["ffu_cmh"])), "FFU round up")
        near(main["parts"]["fan"], float(project["inputs"]["fan_room_kw"]) + main["ffu_count"] * float(project["inputs"]["ffu_w"]) / 1000,
             "final FFU fan heat")
        near(main["oa_mass"] * (main["room"]["w"] - main["summer"]["supply"]["w"]), main["moisture"], "room moisture balance")
        near(main["q_total_kw"], sum(main["water"][key]["load_kw"] for key in ("MCHW", "CHW", "DCCW")) / main["sf"],
             "chiller capacity envelope matches the separately sized temperature loops")
        summary = executive_summary(main)[1]
        check("外氣入口基準冷量" not in summary["selection"], "volume reference must not rescale cooling kW")
        inlet_volume = main["oa_mass"] * main["oa"]["v_da"] * 3600
        check(f"{inlet_volume:,.2f}".rstrip("0").rstrip(".") in summary["selection"], "report actual inlet volume")
        check(project == original, "calculations preserve source documents")

    for unit in ("US RT", "kcal/h", "BTU/h"):
        rejected(lambda: tool("electrical", power_unit=unit), "power_unit", "thermal capacity is not electricity")
    rejected(lambda: tool("lighting", u_mode="型錄 U＋室指數 K 檢核", area_mode="面積 m²"),
             "area_mode", "K requires actual dimensions")
    for unit in ("kW", "W", "HP", "PS", "A", "kVA"):
        adopted = transfer_upstream("electrical", {"pumps": {"motor_input_kw": 10}},
                                    dict(defaults("electrical"), power_unit=unit))
        check(adopted["power_unit"] == "kW", "adopt kW for every prior unit")
        near(calculate_tool("electrical", adopted)["power_kw"], 10, "10 kW pump remains 10 kW")
    near(sum(x["power_kw"] for x in electrical_device_loads({}, {"chiller_input_kw": 5, "chiller_cop": "draft"})),
         5, "inactive COP draft cannot block explicit input")
    empty = default_project()
    empty["inputs"].update(sys_type="MAU+FFU+DCC (全外氣/無塵室)", en_L_A="0", en_W_A="0", en_L_B="0", en_W_B="0",
                           ppl_A="0", ppl_B="0", en_manual_oa="58000", eq_kw="1000")
    rejected(lambda: calculate(empty), "en_L_A", "zero floor area is a field error")
    draft = default_project()
    draft["inputs"]["light_u_mode"] = "室指數 K 自動（DIALux 基準）"
    original = copy.deepcopy(draft)
    migrated = migrate_project(draft)
    check(migrated["inputs"]["light_u_mode"] == "型錄 U＋室指數 K 檢核", "legacy automatic U draft migrates")
    check(migrated["inputs"]["light_u"] == draft["inputs"]["light_u"] and draft == original, "migration preserves manual U and source")
    for name in ENGINES:
        check(calculate_tool(name, defaults(name))["tool"] == name, "staged engine identity: " + name)
    for language in ("zh-Hant", "en"):
        value = tool("electrical", power=10)
        legacy = defaults("electrical")
        del legacy["power_unit"], legacy["motor_efficiency"]
        check("10 kW" in tool_report(value, legacy, language=language), "legacy report defaults")
    return {"passed": True, "source_platform": source, "host_os": platform.system(),
            "python": platform.python_version(), "scenarios": 100, "checks": checks, "examples": examples}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("windows", "macos"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.platform)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "examples"}))
