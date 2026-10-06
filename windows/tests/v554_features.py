"""Independent schedule back-calculations, typed imports and chart geometry."""

from pathlib import Path
from types import SimpleNamespace
import csv
import io
import json
import math
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from facility_studio.air_chart import chart_data
from facility_studio.equipment_analysis import analyze_equipment, equipment_report
from facility_studio.equipment_io import Cell, EquipmentImportError, load_equipment
from facility_studio.equipment_schema import SCHEMAS, SCHEMA_ID, SYSTEMS, example
from facility_studio.simple_engines import calculate_tool
from facility_studio.simple_schema import defaults
from facility_studio.ui_common import is_keypad_decimal
from facility_studio.utils import sat_pa

checks, cases = [], []


def check(name, condition):
    checks.append(dict(name=name, passed=bool(condition)))
    assert condition, name


def close(name, actual, expected, tolerance=1e-10):
    check(name, math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance))


def row(system, **changes):
    data = example(system)
    data.update({"enabled": 1, **changes})
    return dict(system=system, cells={key: Cell(value) for key, value in data.items()})


def imported(*rows):
    return dict(
        schema_id=SCHEMA_ID,
        source_name="反算案例.xlsx",
        systems=SYSTEMS,
        records=[dict(record, row=i) for i, record in enumerate(rows, 6)],
    )


def case(name, *records):
    result = analyze_equipment(imported(*records))
    text = equipment_report(result)
    cases.append(
        dict(name=name, active=result["active_records"], groups=len(result["groups"]))
    )
    check(
        name + "_finite_json",
        "NaN" not in json.dumps(result, ensure_ascii=False, allow_nan=False),
    )
    check(
        name + "_report_inputs",
        "輸入：" in text and "條件：" in text and "公式：" in text,
    )
    # Reverse the published, rounded demand values for every group in the report.
    for group in result["groups"]:
        if group["system"] == "電力":
            token = f"{group['demand_kw']:,.3f}kW / {group['demand_kva']:,.3f}kVA"
            check(name + "_printed_kw_kva", token in text)
            actual_kw = float(token.split("kW")[0].replace(",", ""))
            close(name + "_rounded_power", actual_kw, group["demand_kw"], 0.00051)
        elif group["system"] in ("CDA", "N2", "PV"):
            canonical = group["demand_standard_lpm"]
            match = f"{group['actual_lpm']:,.3f}ALPM"
            check(name + "_printed_alpm", match in text)
            displayed = float(match[:-4].replace(",", ""))
            reverse = (
                displayed
                * group["absolute_kpa"]
                / 101.325
                * 298.15
                / (group["temperature_c"] + 273.15)
            )
            error = (
                0.00051
                * group["absolute_kpa"]
                / 101.325
                * 298.15
                / (group["temperature_c"] + 273.15)
            )
            check(
                name + "_printed_reverse_standard",
                abs(reverse - canonical) <= error + 1e-9,
            )
        elif group["system"] in ("PCW", "DI"):
            check(name + "_printed_water", f"{group['demand_lpm']:,.3f}LPM" in text)
        else:
            check(name + "_printed_exhaust", f"{group['demand_cmh']:,.3f}CMH" in text)
    return result, text


def reject(name, records, expected):
    try:
        analyze_equipment(imported(*records))
    except EquipmentImportError as error:
        check(name, expected in str(error))
    else:
        check(name, False)


r, report = case(
    "01_socket_points_not_power",
    row("電力", power=10, pf=1, quantity=3, usage=50, sockets=4),
)
g = r["groups"][0]
close("01_connected", g["connected_kw"], 30)
close("01_demand", g["demand_kw"], 15)
check("01_points", g["sockets"] == 12)
close("01_current", g["current_a"], 15000 / math.sqrt(3) / 380)
close("01_branch_undiscounted", r["rows"][0]["per_device_branch"]["power_kw"], 10)

r, _ = case(
    "02_mixed_pf", row("電力", power=4, pf=1), row("電力", id="EQ-002", power=3, pf=0.6)
)
g = r["groups"][0]
close("02_Q", g["demand_kvar"], 4)
close("02_S", g["demand_kva"], math.sqrt(65))
check("02_no_kva_scalar_sum", not math.isclose(g["demand_kva"], 9))

r, _ = case(
    "03_continuous_and_general",
    row("電力", power=4, pf=1, kind="連續運轉"),
    row("電力", id="EQ-002", power=3, pf=0.6),
)
close(
    "03_design",
    r["groups"][0]["design_current_a"],
    math.sqrt(80) * 1000 / math.sqrt(3) / 380,
)

r, _ = case(
    "04_motor_largest_only",
    row("電力", power=10, pf=0.8, quantity=2, kind="馬達"),
    row("電力", id="EQ-002", power=5, pf=0.8, quantity=3, kind="馬達"),
)
close(
    "04_design",
    r["groups"][0]["design_current_a"],
    37.5 / 0.8 * 1000 / math.sqrt(3) / 380,
)
check("04_motor_pending", any("FLC" in v for v in r["groups"][0]["warnings"]))
r, _ = case(
    "05_motor_partial_demand",
    row("電力", power=10, pf=0.8, quantity=2, usage=50, kind="馬達"),
)
close(
    "05_design",
    r["groups"][0]["design_current_a"],
    12.5 / 0.8 * 1000 / math.sqrt(3) / 380,
)

r, _ = case(
    "06_mixed_voltage_panel",
    row("電力", power=5, voltage=220, phases="1", pf=1),
    row("電力", id="EQ-002", power=10, voltage=380, phases="3"),
)
check(
    "06_separate",
    len(r["groups"]) == 2 and any("未合併電流" in s for s in r["warnings"]),
)
close(
    "06_single_phase",
    next(g for g in r["groups"] if g["phases"] == 1)["current_a"],
    5000 / 220,
)
r, _ = case("07_single_110", row("電力", power=1, voltage=110, phases="1", pf=1))
close("07_single_I", r["groups"][0]["current_a"], 1000 / 110)
r, _ = case("08_zero_electric", row("電力", power=0, usage=0))
close("08_zero", r["groups"][0]["current_a"], 0)
check("08_no_fake_nfb", r["groups"][0]["candidate"]["selected"] is None)
r, _ = case("09_zero_usage_branch_still_rated", row("電力", power=5, usage=0, pf=1))
close("09_no_feeder_demand", r["totals"]["demand_kw"], 0)
close("09_branch", r["rows"][0]["per_device_branch"]["power_kw"], 5)
r, _ = case(
    "10_distinct_panels",
    row("電力", power=4, group="UP-01"),
    row("電力", id="EQ-002", power=6, group="UP-02"),
)
check("10_group_counts", len(r["groups"]) == 2 and not r["warnings"])

r, _ = case(
    "11_pcw_mixed_units_and_delta",
    row("PCW", flow=30, quantity=2, usage=50, delta=5),
    row("PCW", id="EQ-002", flow=10, unit="US GPM", delta=8),
)
g = r["groups"][0]
close("11_water", g["demand_lpm"], 30 + 10 * 3.785411784)
close(
    "11_heat", g["thermal_kw"], (30 * 5 + 10 * 3.785411784 * 8) * 1000 * 4.1868 / 60000
)
pipe = g["pipe"]
v = g["demand_lpm"] / 60000 / pipe["runs"] / (math.pi * (pipe["id_mm"] / 1000) ** 2 / 4)
close("11_actual_pipe_velocity", pipe["velocity_mps"], v)
check("11_v_limit", v <= g["velocity_limit"])
r, _ = case("12_pcw_m3h", row("PCW", flow=6, unit="m³/h", delta=10))
close("12_water", r["groups"][0]["demand_lpm"], 100)
close("12_kw", r["groups"][0]["thermal_kw"], 100 * 1000 * 4.1868 * 10 / 60000)
r, _ = case("13_pcw_ls", row("PCW", flow=2, unit="L/s", usage=25))
close("13_water", r["groups"][0]["demand_lpm"], 30)
r, _ = case("14_zero_pcw", row("PCW", flow=0))
close("14_zero_kw", r["groups"][0]["thermal_kw"], 0)
r, _ = case(
    "15_di_circulation_continuous",
    row("DI", flow=10, quantity=3, usage=20, circulation=2),
)
close("15_total", r["groups"][0]["demand_lpm"], 12)
close("15_connected", r["groups"][0]["connected_lpm"], 36)
check("15_no_carbon_steel", r["groups"][0]["pipe"] is None)
r, _ = case("16_di_zero_process", row("DI", flow=0, quantity=4, usage=0, circulation=3))
close("16_circulation", r["groups"][0]["demand_lpm"], 12)

r, _ = case("17_cda_scfm", row("CDA", flow=10, unit="SCFM", pressure=6))
g = r["groups"][0]
close("17_standard", g["demand_standard_lpm"], 10 * 28.316846592)
close("17_actual", g["actual_lpm"], 10 * 28.316846592 * 101.325 / 701.325)
r, _ = case("18_n2_reference_zero_c", row("N2", flow=100, reference_t=0))
close("18_standard", r["groups"][0]["demand_standard_lpm"], 100 * 298.15 / 273.15)
r, _ = case(
    "19_cda_alpm",
    row("CDA", flow=60, unit="ALPM", pressure=600, pressure_unit="kPa(g)"),
)
close("19_actual_roundtrip", r["groups"][0]["actual_lpm"], 60)
close("19_standard", r["groups"][0]["demand_standard_lpm"], 60 * 701.325 / 101.325)
r, _ = case(
    "20_cda_mixed_gauge_and_atmosphere",
    row("CDA", flow=100, pressure=0, atmosphere=80),
    row("CDA", id="EQ-002", flow=100, pressure=6, temperature=50, velocity=8),
)
g = r["groups"][0]
close("20_worst_actual", g["actual_lpm"], 200 * 101.325 / 80 * 323.15 / 298.15)
check("20_pressure_note", any("級次" in s for s in g["warnings"]))
close("20_velocity_limit", g["velocity_limit"], 8)
r, _ = case(
    "21_n2_sm3h_mpa",
    row("N2", flow=6, unit="Sm³/h", pressure=0.5, pressure_unit="MPa(g)"),
)
close("21_standard", r["groups"][0]["demand_standard_lpm"], 100)
r, _ = case("22_n2_kgf", row("N2", flow=100, pressure=6, pressure_unit="kgf/cm²(g)"))
close("22_absolute", r["groups"][0]["absolute_kpa"], 6 * 98.0665 + 101.325)

pv_results = []
for name, unit, pressure in (
    ("23_pv_torr", "Torr(abs)", 150),
    ("24_pv_kpa", "kPa(abs)", 150 * 101.325 / 760),
    ("25_pv_mbar", "mbar(abs)", 150 * 101.325 / 760 * 10),
):
    r, _ = case(name, row("PV", flow=100, pressure=pressure, pressure_unit=unit))
    pv_results.append(r["groups"][0])
    close(name + "_actual", r["groups"][0]["actual_lpm"], 100 * 760 / 150)
    close(name + "_effective_pump", r["groups"][0]["effective_pumping_m3h"], 30.4)
    close(
        name + "_throughput", r["groups"][0]["throughput_pa_m3s"], 100 / 60000 * 101325
    )
check(
    "25_same_diameter_all_units",
    len({g["minimum_id_mm"].__round__(8) for g in pv_results}) == 1,
)
r, _ = case(
    "26_pv_alpm_at_pressure",
    row("PV", flow=600, unit="ALPM", pressure=150, temperature=40),
)
close("26_actual_roundtrip", r["groups"][0]["actual_lpm"], 600)
r, _ = case("27_pv_low_pressure_large_pipe", row("PV", flow=100000, pressure=1))
check(
    "27_outside_table",
    not r["groups"][0]["within_table"] and r["groups"][0]["pipe"] is None,
)

r, report = case(
    "28_exhaust_mixed_unit",
    row("EXHAUST", flow=500, quantity=2, usage=50, pressure=200),
    row("EXHAUST", id="EQ-002", flow=100, unit="CFM", pressure=300),
)
g = r["groups"][0]
close("28_total", g["demand_cmh"], 500 + 100 * 1.69901079552)
close("28_terminal_max_not_sum", g["known_terminal_pressure_pa"], 300)
check(
    "28_report_pressure_known", "最高要求300Pa" in report and "未核風機總ESP" in report
)
rect = g["rectangle"]
close(
    "28_velocity_actual_area",
    rect["velocity_mps"],
    g["demand_cmh"] / 3600 / (rect["w_mm"] * rect["h_mm"] / 1e6),
)
r, _ = case(
    "29_exhaust_types_separate",
    row("EXHAUST", exhaust_type="GEX"),
    row("EXHAUST", id="EQ-002", exhaust_type="SEX"),
)
check("29_separate_groups", len(r["groups"]) == 2)
r, _ = case("30_exhaust_unknown_pressure", row("EXHAUST", pressure=None))
check(
    "30_missing_is_not_zero",
    r["groups"][0]["known_terminal_pressure_pa"] is None
    and not r["groups"][0]["pressure_complete"],
)
r, _ = case("31_exhaust_zero", row("EXHAUST", flow=0, pressure=0))
close("31_zero_flow", r["groups"][0]["demand_cmh"], 0)
check("31_zero_known", r["groups"][0]["pressure_complete"])
r, report = case(
    "32_defaults_reported_with_values",
    row("電力", pf="", length="", usage="", sockets=""),
)
check(
    "32_defaults_values",
    "功率因數(PF)=0.85" in report and "單程配線長度(m)=30" in report,
)

for name, key, value, expected in (
    ("blank_power_not_zero", "power", "", "必填"),
    ("negative_power", "power", -1, "0"),
    ("nan_power", "power", "NaN", "NaN"),
    ("inf_power", "power", "Inf", "無限"),
    ("non_integer_qty", "quantity", 1.5, "整數"),
    ("zero_qty", "quantity", 0, "1"),
    ("usage_over_100", "usage", 101, "100"),
    ("pf_zero", "pf", 0, "0.1"),
    ("blank_enable", "enabled", "", "必填"),
    ("phase_two", "phases", "2", "可用"),
):
    rejected = row("電力")
    rejected["cells"][key] = Cell(value)
    reject(name, [rejected], expected)
rejected = row("電力")
rejected["cells"]["power"] = Cell("10", True)
reject("formula_input", [rejected], "不接受公式")
reject("duplicate_identity", [row("電力"), row("電力")], "重複")
reject("all_inactive", [row("電力", enabled=0)], "沒有啟用")
reject("pv_subrange", [row("PV", pressure=0.1)], "1~760")
reject("wrong_flow_unit", [row("PCW", unit="CMH")], "可用選項")
r, _ = case(
    "33_invalid_disabled_row_ignored", row("電力"), row("電力", enabled=0, power="bad")
)
check("33_inactive_count", r["skipped_records"] == 1)
r, _ = case("34_cross_system_same_equipment_id", row("電力"), row("CDA"))
check("34_link_same_device", r["active_records"] == 2)
r, _ = case(
    "35_natural_panel_order",
    row("電力", group="UP-10"),
    row("電力", id="EQ-002", group="UP-2"),
    row("電力", id="EQ-003", group="UP-1"),
    row("PCW"),
)
check(
    "35_panel_sort", [g["group"] for g in r["groups"][:3]] == ["UP-1", "UP-2", "UP-10"]
)
check("35_system_sort", r["groups"][-1]["system"] == "PCW")
r, report = case(
    "36_low_diversity_cannot_undersize_single_device",
    row("電力", power=100, pf=0.6, usage=1),
)
group = r["groups"][0]
close("36_demand_stays_estimate", group["demand_kw"], 1)
close("36_feeder_floor", group["design_current_a"], 100000 / 0.6 / math.sqrt(3) / 380)
check(
    "36_protection_at_least_one_device",
    group["candidate"]["selected"]["nfb_a"] >= group["design_current_a"],
)
check("36_floor_reason_published", "進線候選至少採該單台" in report)
wire = group["candidate"]["selected"]
resistance = 0.017241 * (1 + 0.00393 * (60 - 20)) * 1000 / wire["size_mm2"]
drop = (
    math.sqrt(3)
    * group["design_current_a"]
    * math.hypot(resistance, 0.08)
    * 30
    / 1000
    / wire["runs"]
)
close("36_conservative_drop", wire["drop_v"], drop)
r, _ = case(
    "37_continuous_floor", row("電力", power=20, pf=1, usage=10, kind="連續運轉")
)
close(
    "37_continuous_floor",
    r["groups"][0]["design_current_a"],
    25000 / math.sqrt(3) / 380,
)

with tempfile.TemporaryDirectory(prefix="facility554_io_") as folder:
    folder = Path(folder)
    template = ROOT / "facility_studio/resources/Equipment_Template.xlsx"
    data = load_equipment(template)
    check(
        "xlsx_all_systems",
        set(data["systems"]) == set(SYSTEMS) and len(data["records"]) == 7,
    )
    reject("template_examples_inactive", data["records"], "沒有啟用")
    # Disposable XML mutations exercise the reader; user-facing workbook authored by Artifact Tool.
    source = zipfile.ZipFile(template)
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    for name, mode in (
        ("active", "active"),
        ("input_formula", "formula"),
        ("duplicate_row", "duplicate"),
        ("negative_shared_index", "index"),
        ("broken_row_number", "row"),
        ("derived_cache_error", "derived"),
        ("input_cache_error", "input_error"),
    ):
        destination = folder / (name + ".xlsx")
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as out:
            for info in source.infolist():
                content = source.read(info.filename)
                if re.fullmatch(r"xl/worksheets/sheet[2-8]\.xml", info.filename):
                    xml = ET.fromstring(content)
                    rows = xml.find(namespace + "sheetData")
                    r6 = next(r for r in rows if r.get("r") == "6")
                    cell = next(c for c in r6 if c.get("r") == "A6")
                    cell.set("t", "n")
                    for child in list(cell):
                        cell.remove(child)
                    ET.SubElement(cell, namespace + "v").text = "1"
                    if info.filename.endswith("sheet2.xml"):
                        if mode == "formula":
                            power = next(c for c in r6 if c.get("r") == "G6")
                            ET.SubElement(power, namespace + "f").text = "5+5"
                        elif mode == "duplicate":
                            rows.append(ET.fromstring(ET.tostring(r6)))
                        elif mode == "index":
                            cell.set("t", "s")
                            cell.find(namespace + "v").text = "-1"
                        elif mode == "row":
                            r6.set("r", "not_a_row")
                        elif mode in ("derived", "input_error"):
                            changed = next(
                                c
                                for c in r6
                                if c.get("r") == ("O6" if mode == "derived" else "G6")
                            )
                            changed.set("t", "e")
                            changed.find(namespace + "v").text = "#DIV/0!"
                    content = ET.tostring(xml, encoding="utf-8", xml_declaration=True)
                out.writestr(info.filename, content)
        try:
            loaded = load_equipment(destination)
            result = analyze_equipment(loaded)
        except EquipmentImportError as error:
            expected = {
                "input_formula": "公式",
                "duplicate_row": "重複",
                "negative_shared_index": "索引",
                "broken_row_number": "列號",
                "input_cache_error": "Excel錯誤",
            }
            check(
                "xlsx_reject_" + name, name in expected and expected[name] in str(error)
            )
        else:
            check(
                "xlsx_active_seven_" + name,
                name in ("active", "derived_cache_error")
                and len(result["groups"]) == 7,
            )
            cases.append(
                dict(
                    name="real_workbook_" + name,
                    active=result["active_records"],
                    groups=7,
                )
            )
            check(
                "xlsx_formula_columns_ignored", result["totals"]["connected_kw"] == 10
            )
    source.close()
    for system in SYSTEMS:
        schema = SCHEMAS[system]
        file = folder / (system + ".csv")
        item = example(system)
        item["enabled"] = 1
        with file.open("w", encoding="utf-8-sig", newline="") as out:
            writer = csv.writer(out)
            writer.writerow([c["label"] for c in schema])
            writer.writerow([item[c["key"]] for c in schema])
        result = analyze_equipment(load_equipment(file, system))
        check("csv_" + system, result["groups"][0]["system"] == system)
    bad = folder / "wrong.csv"
    bad.write_text("啟用(1/0),設備編號,設備名稱\n1,EQ-1,名稱\n", encoding="utf-8")
    try:
        load_equipment(bad)
    except EquipmentImportError as error:
        check("missing_header", "缺少" in str(error))
    else:
        check("missing_header", False)
    too_wide = folder / "wide.csv"
    too_wide.write_text(",".join([""] * 130), encoding="utf-8")
    try:
        load_equipment(too_wide)
    except EquipmentImportError as error:
        check("csv_column_limit", "128" in str(error))
    else:
        check("csv_column_limit", False)

for name, category, value, unit, expected_key, expected in (
    ("delta_c_to_f", "溫度差（升溫／降溫）", 5, "°C差", "°F差", 9),
    ("negative_delta", "溫差", -5, "K", "°F差", -9),
    ("absolute_temperature", "溫度", 5, "°C", "°F", 41),
    ("kv_to_cv", "Kv/Cv", 5, "Kv", "Cv(US)", 5 / 0.865),
):
    data = defaults("units")
    data.update(category=category, value=str(value), unit=unit)
    result = calculate_tool("units", data)
    close(name, result["values"][expected_key], expected)
    cases.append(dict(name=name))

for i, (temperature, rh, pressure) in enumerate(
    (
        (25, 50, 101.325),
        (35, 70, 101.325),
        (-10, 80, 80),
        (0, 100, 101.325),
        (22, 0, 101.325),
        (80, 50, 101.325),
    )
):
    data = defaults("air")
    data.update(temperature=str(temperature), rh=str(rh), atmosphere=str(pressure))
    state = calculate_tool("air", data)["state"]
    chart = chart_data(state)
    pw = sat_pa(temperature) * rh / 100
    ratio = 0.621945 * pw / (pressure * 1000 - pw) * 1000
    close(f"chart_{i}_point_ratio", chart["point"][1], ratio)
    close(f"chart_{i}_point_t", chart["point"][0], temperature)
    check(
        f"chart_{i}_point_in_axes",
        chart["t_min"] <= temperature <= chart["t_max"]
        and 0 <= ratio <= chart["w_max_gkg"],
    )
    for curve in chart["curves"]:
        for t, w in curve["points"][::40]:
            pw = sat_pa(t) * curve["rh"] / 100
            close(
                f"chart_{i}_curve_{curve['rh']}_{t:.2f}",
                w,
                0.621945 * pw / (pressure * 1000 - pw) * 1000,
            )
    cases.append(
        dict(
            name=f"chart_conditions_{i}",
            temperature=temperature,
            rh=rh,
            pressure=pressure,
        )
    )

for key, code, platform, expected in (
    ("KP_Decimal", 91, "linux", True),
    ("KP_Separator", 91, "linux", True),
    ("Delete", 110, "win32", True),
    ("Delete", 46, "win32", False),
    ("period", 190, "win32", False),
    ("KP_Delete", 91, "linux", False),
):
    check(
        f"keypad_{key}_{platform}_{code}",
        is_keypad_decimal(SimpleNamespace(keysym=key, keycode=code), platform)
        == expected,
    )

evidence = dict(
    version="5.5.4",
    scenario_count=len(cases),
    cases=cases,
    checks=checks,
    windows_keyboard_hardware_tested=False,
)
(ROOT / "evidence/V554_New_Feature_Checks.json").write_text(
    json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(
    f"{len(cases)} scenarios; {len(checks)} independent calculation/import/report/chart checks passed"
)
