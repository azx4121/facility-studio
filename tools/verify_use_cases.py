"""Verify the published examples against each platform's existing engine.

No model rankings or other users' recommendations are simulated here.
"""

import argparse
import copy
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("windows", "macos"), default="windows")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / args.platform))
    from facility_studio.simple_schema import defaults
    from facility_studio.simple_engines import calculate_tool
    from facility_studio.simple_reports import tool_report
    from facility_studio.schema import default_project
    from facility_studio.engine import gas_from_inputs
    from facility_studio.ahu_schema import NM_DEFAULTS
    from facility_studio.ahu_engine import nm_calculate
    from facility_studio.equipment_io import Cell, load_equipment
    from facility_studio.equipment_analysis import analyze_equipment, equipment_report

    scenarios = json.loads((ROOT / "docs/examples/scenarios.json").read_text("utf-8"))
    assert len(scenarios) == 20
    assert len({case["id"] for case in scenarios}) == 20
    assert len({case["query"] for case in scenarios}) == 20
    evidence = []
    check_count = 0
    for case in scenarios:
        checks = []

        def check(ok, message):
            nonlocal check_count
            assert ok, f"Case {case['id']}: {message}"
            check_count += 1
            checks.append(message)

        def close(actual, expected, message, *, rel=1e-8, absolute=1e-8):
            check(
                math.isclose(actual, expected, rel_tol=rel, abs_tol=absolute), message
            )

        tool = case["tool"]
        if tool is None:
            check(case["route"] is None, "不把不適用情境指定給軟體工具")
            check(bool(case["reason"]), "保留不適用理由")
            evidence.append(
                dict(id=case["id"], status="不適用", checks=checks, result=None)
            )
            continue
        if tool in ("electrical", "duct", "gas", "lighting", "water", "air", "units"):
            inputs = defaults(tool)
            inputs.update(case["inputs"])
            result = calculate_tool(tool, inputs)
            exported = tool_report(result, inputs)
            check(bool(exported.strip()), "產生可閱讀的文字報告")
            check(bool(result.get("formula")), "計算結果包含公式")
            if tool == "electrical":
                factor = math.sqrt(3) if result["phases"] == 3 else 1
                expected = (
                    float(inputs["power"])
                    * 1000
                    / (factor * result["voltage"] * float(inputs["pf"]))
                )
                close(result["current_a"], expected, "由功率、電壓及 PF 獨立反算電流")
                multiplier = 1.25 if inputs["kind"] == "連續運轉" else 1
                close(result["design_a"], expected * multiplier, "連續負載餘裕基準")
                selected = result["selected"]
                check(
                    result["design_a"] <= selected["nfb_a"] <= selected["ampacity_a"],
                    "電流 ≤ NFB AT ≤ 有效載流",
                )
                check(
                    selected["drop_pct"] <= float(inputs["drop_limit"]),
                    "候選符合設定壓降上限",
                )
                check(
                    f"{selected['nfb_a']:g} AT" in exported, "報告 NFB 與結構化結果一致"
                )
            elif tool == "duct":
                cmh = float(inputs["flow"]) * (
                    1.69901079552 if inputs["flow_unit"] == "CFM" else 1
                )
                close(result["flow_cmh"], cmh, "CFM／CMH 基準獨立換算")
                for shape in ("rectangle", "round"):
                    row = result[shape]
                    area = (
                        row["w_mm"] * row["h_mm"] / 1e6
                        if shape == "rectangle"
                        else math.pi * row["diameter_m"] ** 2 / 4
                    )
                    close(
                        row["velocity_mps"],
                        cmh / 3600 / area,
                        f"{shape} 實際截面與速度反算",
                    )
                    check(
                        row["velocity_mps"] <= float(inputs["velocity"]) + 1e-8,
                        f"{shape} 未超設定風速",
                    )
                    if result["path_checked"]:
                        expected = (
                            row["friction_pa"]
                            + float(inputs["k_sum"])
                            * 1.2
                            * row["velocity_mps"] ** 2
                            / 2
                            + float(inputs["equipment"])
                        )
                        close(row["loss_pa"], expected, f"{shape} 總壓損量綱及組成")
                        close(
                            row["pressure_margin_pa"],
                            result["pressure_pa"] - expected,
                            f"{shape} 可用靜壓餘裕",
                        )
                        check(
                            row["budget_sufficient"]
                            == (result["pressure_pa"] >= expected),
                            f"{shape} 壓力預算判定",
                        )
                if not result["path_checked"]:
                    check("loss_pa" not in result["rectangle"], "未知路徑不虛構壓損")
            elif tool == "gas":
                std = float(inputs["flow"]) * (
                    1000 / 60 if inputs["flow_unit"] == "Sm³/h" else 1
                )
                gauge = float(inputs["pressure"]) * (
                    100 if inputs["pressure_unit"] == "bar(g)" else 1
                )
                actual = (
                    std
                    * float(inputs["reference_p"])
                    / (float(inputs["atmosphere"]) + gauge)
                    * (float(inputs["temperature"]) + 273.15)
                    / (float(inputs["reference_t"]) + 273.15)
                )
                close(result["standard_lpm"], std, "標準流量基準")
                close(result["actual_lpm"], actual, "表壓加大氣壓後換算實際流量")
                close(
                    result["minimum_id_mm"],
                    math.sqrt(4 * actual / 60000 / math.pi / float(inputs["velocity"]))
                    * 1000,
                    "流量與流速反算最小內徑",
                )
                check(
                    result["velocity_mps"] <= float(inputs["velocity"]),
                    "採用參考內徑符合速度上限",
                )
            elif tool == "lighting":
                area = (
                    float(inputs["area"]) / float(inputs["height"])
                    if inputs["area_mode"] == "體積 m³"
                    else float(inputs["area"])
                )
                close(result["area_m2"], area, "體積除同空間淨高，沒有把 m³ 當 m²")
                expected = result["quantity"] * 4000 * 0.6 * 0.8 / area
                close(result["illuminance_lux"], expected, "流明法平均照度反算")
                if result["target_lux"] is not None:
                    check(expected >= result["target_lux"], "取整盞數達目標平均照度")
                    check(
                        (result["quantity"] - 1) * 4000 * 0.6 * 0.8 / area
                        < result["target_lux"],
                        "少一盞無法達設定目標",
                    )
            elif tool == "water":
                thermal = result["thermal"]
                close(
                    thermal["kw"],
                    thermal["lpm"] / 60000 * 1000 * 4.1868 * float(inputs["delta"]),
                    "清水熱量與水量反算",
                )
                if inputs["mode"] == "已知水量":
                    close(thermal["kw"], 34.89, "100 LPM × 5 K = 34.89 kW")
                else:
                    close(
                        thermal["lpm"],
                        100 * 60000 / 1000 / 4.1868 / 5,
                        "100 kW、5 K 反算水量",
                    )
                check(
                    result["pipe"]["velocity_mps"] <= float(inputs["velocity"]),
                    "管徑候選符合水速上限",
                )
            elif tool == "air":
                state = result["state"]
                t, rh, p = (
                    float(inputs["temperature"]),
                    float(inputs["rh"]),
                    float(inputs["atmosphere"]),
                )
                # Buck (1981) over liquid water is an independent approximation;
                # the product uses the ASHRAE saturation-pressure correlation.
                pws = 0.61121 * math.exp((18.678 - t / 234.5) * t / (257.14 + t))
                pw = pws * rh / 100
                w = 0.621945 * pw / (p - pw)
                close(state["w"], w, "含濕比與 Buck 獨立關聯式對照", rel=0.003)
                close(
                    state["h"],
                    1.006 * t + w * (2501 + 1.86 * t),
                    "焓值乾空氣基準對照",
                    rel=0.003,
                )
                check(
                    state["dewpoint_c"] <= state["wetbulb_c"] <= t, "露點 ≤ 濕球 ≤ 乾球"
                )
                close(
                    state["v_da"],
                    0.287042 * (t + 273.15) * (1 + 1.607858 * state["w"]) / p,
                    "比容及當地壓力基準反算",
                    rel=0.0001,
                )
            elif tool == "units":
                if case["id"] == "14":
                    close(result["values"]["CMH"], 1699.01079552, "1000 CFM 換算 CMH")
                    close(result["values"]["L/s"], 1699.01079552 / 3.6, "CMH 換算 L/s")
                else:
                    close(result["values"]["K"], 5, "5°C 溫差 = 5 K")
                    close(result["values"]["°F差"], 9, "5°C 溫差 = 9°F差，沒有加32")
        elif tool == "pv":
            inputs = default_project()["inputs"]
            inputs.update(case["inputs"])
            inputs.update(gas1_q="0", gas2_q="0", gas3_q="0")
            result = gas_from_inputs(inputs)["4"]
            close(
                result["actual_lpm"],
                2000 * 760 / 150,
                "150 Torr 絕壓下的實際體積流量",
                rel=1e-8,
            )
            close(
                result["minimum_id_mm"],
                math.sqrt(4 * result["actual_lpm"] / 60000 / math.pi / 18) * 1000,
                "PV 流速截面反算",
            )
            check(result["selected_id_mm"] >= result["minimum_id_mm"], "候選內徑足夠")
        elif tool.startswith("equipment-"):
            template = (
                ROOT
                / args.platform
                / "facility_studio/resources/Equipment_Template.xlsx"
            )
            imported = load_equipment(template)
            check(len(imported["systems"]) == 7, "實際 XLSX 範本可解析七個系統")
            if tool == "equipment-electric":
                base = next(
                    row for row in imported["records"] if row["system"] == "電力"
                )
                records = []
                for index, values in enumerate(case["inputs"]["rows"], 6):
                    row = copy.deepcopy(base)
                    row["row"] = index
                    row["cells"].update(
                        {key: Cell(value) for key, value in values.items()}
                    )
                    row["cells"]["enabled"] = Cell(1)
                    records.append(row)
            else:
                records = [
                    copy.deepcopy(row)
                    for row in imported["records"]
                    if row["system"] != "電力"
                ]
                for row in records:
                    for key in ("quantity", "usage", "enabled"):
                        row["cells"][key] = Cell(case["inputs"][key])
            result = analyze_equipment(dict(imported, records=records))
            check(bool(equipment_report(result)), "設備結果可匯出文字報告")
            groups = result["groups"]
            if tool == "equipment-electric":
                check(len(groups) == 2, "同盤名稱、不同相數及電壓仍分組")
                three = next(group for group in groups if group["phases"] == 3)
                one = next(group for group in groups if group["phases"] == 1)
                close(three["connected_kw"], 40, "三相全開功率40 kW")
                close(three["demand_kw"], 25, "使用率後三相需求25 kW")
                check(three["sockets"] == 7, "插座僅統計點位，不重複乘 kW")
                close(one["demand_kw"], 3, "單相需求3 kW保持獨立")
            else:
                by_system = {row["system"]: row for row in groups}
                check(len(by_system) == 6, "六個公用系統分開彙總")
                close(by_system["PCW"]["demand_lpm"], 30, "PCW 台數及同時率")
                close(by_system["PCW"]["thermal_kw"], 10.467, "PCW 流量、溫差與熱量")
                close(by_system["DI"]["demand_lpm"], 14, "DI 10 LPM製程＋4 LPM持續循環")
                close(by_system["CDA"]["demand_standard_lpm"], 100, "CDA 同時標準流量")
                close(by_system["N2"]["demand_standard_lpm"], 50, "N2 同時標準流量")
                close(by_system["PV"]["actual_lpm"], 100 * 760 / 150, "PV 同時實際流量")
                close(by_system["EXHAUST"]["demand_cmh"], 500, "排氣需求與風量基準")
        elif tool == "ahu":
            inputs = dict(NM_DEFAULTS)
            inputs.update(case["inputs"])
            result = nm_calculate(inputs)
            for season in ("summer", "winter"):
                row = result[season]
                energy = row["mass"] * (row["sa"]["h"] - row["oa"]["h"])
                delivered = (
                    row["h1"]["air_kw"]
                    - row["c1"]["air_kw"]
                    + row["steam"]["air_kw"]
                    - row["c2"]["air_kw"]
                    + row["h2"]["air_kw"]
                )
                close(
                    energy,
                    delivered,
                    f"{season} 逐段能量加總與進出風焓差",
                    absolute=1e-5,
                )
                net_moisture = row["mass"] * (row["sa"]["w"] - row["oa"]["w"]) * 3600
                moisture = (
                    row["evap_kg_h"]
                    + row["steam"]["kg_h"]
                    - (row["c1"]["condensate_kg_s"] + row["c2"]["condensate_kg_s"])
                    * 3600
                )
                close(
                    net_moisture,
                    moisture,
                    f"{season} 加濕／除濕與含濕比守恆",
                    absolute=1e-5,
                )
                check(bool(row["checks"]), f"{season} 設備容量判定與需求點分開保留")
                check("電熱" in row["h1"]["source"], f"{season} H1 熱源選擇有效")
            check(
                result["winter"]["h1"]["air_kw"] > float(inputs["h1_kw"]),
                "冬季H1需求大於已配置400 kW",
            )
            check(
                result["winter"]["checks"]["H1 當前熱源情境"] is False,
                "保留容量不足，未把需求點當成實際性能",
            )
        else:
            raise AssertionError(f"Unverified tool {tool}")
        evidence.append(
            dict(id=case["id"], status="計算與反算通過", checks=checks, result=result)
        )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            dict(
                platform=args.platform,
                scope="18個適用情境的計算／報告核對，2個不適用對照；不是20個獨立GPT帳號測試",
                check_count=check_count,
                scenarios=evidence,
            ),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        + "\n",
        "utf-8",
    )
    print(
        f"{args.platform}: 18 numerical cases + 2 negative controls; {check_count} checks passed"
    )


if __name__ == "__main__":
    main()
