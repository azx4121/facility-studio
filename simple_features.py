"""Independent equations and published-report round trips for the short forms."""

from pathlib import Path
import json
import math
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from facility_studio.data import PIPE_DB, WIRE_DB
from facility_studio.errors import ValidationError
from facility_studio.simple_engines import calculate_tool
from facility_studio.simple_reports import tool_report
from facility_studio.simple_schema import defaults

checks, cases = [], []
EVIDENCE = ROOT / "evidence/Simple_Reports"
EVIDENCE.mkdir(exist_ok=True)


def check(name, passed):
    checks.append({"name": name, "passed": bool(passed)})
    assert passed, name


def close(name, actual, expected, tolerance=1e-9):
    check(name, math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance))


def published(text, label):
    match = re.search(r"(?m)^\s*" + re.escape(label) + r"：([-+]?[\d,.]+)", text)
    assert match, label
    return float(match.group(1).replace(",", ""))


def saturation_pa(t):
    k = t + 273.15
    if t <= 0.01:
        coefficients = [-5674.5359 / k, 6.3925247, -.009677843*k,
                        6.2215701e-7*k*k, 2.0747825e-9*k**3,
                        -9.484024e-13*k**4, 4.1635019*math.log(k)]
    else:
        coefficients = [-5800.2206/k, 1.3914993, -.048640239*k,
                        4.1764768e-5*k*k, -1.4452093e-8*k**3,
                        6.5459673*math.log(k)]
    return math.exp(sum(coefficients))


def case(tool, **changes):
    values = defaults(tool)
    values.update({key: str(value) for key, value in changes.items()})
    result = calculate_tool(tool, values)
    text = tool_report(result, values)
    ident = f"S{len(cases)+1:02d}"
    cases.append({"id": ident, "tool": tool, "inputs": values, "result": result})
    (EVIDENCE / (ident + ".txt")).write_text(text, encoding="utf-8")
    check(ident + "_finite_export", bool(json.dumps(result, allow_nan=False)))
    check(ident + "_report_scope", "公式" in text and "採用範圍" in text and "HVAC" not in text)

    if tool == "electrical":
        voltage = float(values["supply"].split()[1][:-1])
        three = values["supply"].startswith("三相")
        pf, kw = float(values["pf"]), float(values["power"])
        current = kw*1000 / ((math.sqrt(3) if three else 1)*voltage*pf)
        close(ident + "_current", result["current_a"], current)
        design = current * (1 if values["kind"] == "一般設備" else 1.25)
        close(ident + "_design", result["design_a"], design)
        wire = result["selected"]
        if kw == 0:
            check(ident + "_no_hardware", wire is None and "無需求" in text)
            return
        check(ident + "_protection", design <= wire["nfb_a"] <= wire["ampacity_a"] + 1e-8)
        check(ident + "_parallel_minimum", wire["runs"] == 1 or wire["size_mm2"] >= 50)
        row = next(w for w in WIRE_DB if w["size_mm2"] == wire["size_mm2"])
        temperature = 90 if values["insulation"] == "XLPE" else 60
        terminal = int(values["terminal"])
        base = row["XLPE_A"] if temperature == 90 else row["PVC_A"]
        terminal_amp = row["PVC_A"] if terminal < 90 else base
        close(ident + "_derating", wire["ampacity_a"], wire["runs"] * min(base*result["dt"]*result["dp"], terminal_amp))
        copper = .017241*(1+.00393*(min(temperature, terminal)-20))*1000/wire["size_mm2"]
        drop = (math.sqrt(3) if three else 2)*current*(copper*pf+.08*math.sqrt(1-pf*pf))*float(values["length"])/1000/wire["runs"]
        close(ident + "_drop", wire["drop_v"], drop)
        check(ident + "_drop_limit", 100*drop/voltage <= float(values["drop_limit"]) + 1e-8)
        displayed = published(text, "運轉電流")
        check(ident + "_published_reverse_kw", abs(displayed*(math.sqrt(3) if three else 1)*voltage*pf/1000-kw) <= .0051*voltage*pf*math.sqrt(3)/1000)
    elif tool == "duct":
        flow = float(values["flow"])*{"CMH": 1, "CFM": 1.69901079552, "L/s": 3.6}[values["flow_unit"]]
        close(ident + "_flow", result["flow_cmh"], flow)
        pressure = float(values["pressure"])*{"Pa": 1, "mmAq": 9.80665, "kPa": 1000}[values["pressure_unit"]]
        close(ident + "_pressure", result["pressure_pa"], pressure)
        for kind in ("rectangle", "round"):
            duct = result[kind]
            if not flow:
                close(ident + "_zero_" + kind, duct["velocity_mps"], 0)
                continue
            area = duct["w_mm"]*duct["h_mm"]/1e6 if kind == "rectangle" else math.pi*(duct["round_in"]*.0254)**2/4
            diameter = 2*duct["w_mm"]*duct["h_mm"]/(duct["w_mm"]+duct["h_mm"])/1000 if kind == "rectangle" else duct["round_in"]*.0254
            velocity = flow/3600/area
            close(ident + "_real_area_" + kind, duct["area_m2"], area)
            close(ident + "_velocity_" + kind, duct["velocity_mps"], velocity)
            check(ident + "_velocity_limit_" + kind, velocity <= float(values["velocity"]) + 1e-8)
            if result["path_checked"]:
                reynolds = 1.2*velocity*diameter/.0000181
                if reynolds < 2300:
                    friction = 64/reynolds
                else:
                    friction = .02
                    for _ in range(80):
                        friction = (-2*math.log10(.00009/diameter/3.7+2.51/(reynolds*math.sqrt(friction))))**-2
                loss = (friction*float(values["length"])/diameter+float(values["k_sum"]))*1.2*velocity*velocity/2+float(values["equipment"])
                close(ident + "_independent_loss_" + kind, duct["loss_pa"], loss, 1e-7)
                check(ident + "_budget_" + kind, duct["budget_sufficient"] == (pressure >= loss))
        check(ident + "_static_not_size", result["path_checked"] or "待" not in text or "未核" in text)
        if flow:
            match = re.search(r"方管：([\d,]+) × ([\d,]+) mm", text)
            w, h = [float(v.replace(",", "")) for v in match.groups()]
            close(ident + "_published_area", w*h/1e6, result["rectangle"]["area_m2"])
    elif tool == "gas":
        standard = float(values["flow"])*{"SLPM": 1, "SCFM": 28.316846592, "Sm³/h": 1000/60}[values["flow_unit"]]
        gauge = float(values["pressure"])*{"bar(g)": 100, "kPa(g)": 1, "kgf/cm²(g)": 98.0665, "MPa(g)": 1000}[values["pressure_unit"]]
        absolute = gauge+float(values["atmosphere"])
        actual = standard*float(values["reference_p"])/absolute*(float(values["temperature"])+273.15)/(float(values["reference_t"])+273.15)
        close(ident + "_absolute_pressure", result["absolute_kpa"], absolute)
        close(ident + "_actual_flow", result["actual_lpm"], actual)
        if standard:
            diameter = result["pipe"]["id"]/1000
            velocity = actual/60000/(math.pi*diameter**2/4)
            close(ident + "_real_velocity", result["velocity_mps"], velocity)
            check(ident + "_velocity_limit", velocity <= float(values["velocity"]))
            check(ident + "_smallest_reference_pipe", all(p["id"] < result["minimum_id_mm"] for p in PIPE_DB if p["id"] < result["pipe"]["id"]))
        displayed = published(text, "實際流量")
        reverse = displayed*absolute/float(values["reference_p"])*(float(values["reference_t"])+273.15)/(float(values["temperature"])+273.15)
        check(ident + "_published_reverse_flow", abs(reverse-standard) <= .0051*absolute/float(values["reference_p"])*(float(values["reference_t"])+273.15)/(float(values["temperature"])+273.15))
    elif tool == "lighting":
        area = float(values["length"])*float(values["width"]) if values["area_mode"] == "長×寬" else float(values["area"])
        if values["area_mode"] == "體積 m³":
            area /= float(values["height"])
        if values["area_mode"] == "面積 坪":
            area *= 400/121
        lumens = float(values["lumens"]) if values["lumen_mode"] == "燈具型錄流明" else float(values["watts"])*float(values["efficacy"])
        um = float(values["utilization"])*float(values["maintenance"])
        quantity = math.ceil(float(values["target"])*area/lumens/um-1e-12) if values["mode"] == "反算燈數" else int(values["quantity"])
        close(ident + "_area", result["area_m2"], area)
        check(ident + "_quantity", result["quantity"] == quantity)
        close(ident + "_illuminance", result["illuminance_lux"], quantity*lumens*um/area)
        close(ident + "_lighting_kw", result["total_kw"], quantity*float(values["watts"])/1000)
        if values["mode"] == "反算燈數":
            check(ident + "_minimal_count", result["illuminance_lux"] >= float(values["target"]) and (quantity == 0 or (quantity-1)*lumens*um/area < float(values["target"])))
        lux = published(text, "平均照度")
        check(ident + "_published_lux", abs(lux-result["illuminance_lux"]) <= .05001)
    elif tool == "water":
        thermal = result["thermal"]
        if values["mode"] == "已知水量":
            lpm = float(values["flow"])*{"LPM": 1, "US GPM": 3.785411784, "m³/h": 1000/60}[values["flow_unit"]]
            kw = lpm/60000*1000*4.1868*float(values["delta"])
        else:
            kw = float(values["power"])*{"kW": 1, "US RT": 3.5168528420667}[values["power_unit"]]
            lpm = kw*60000/(1000*4.1868*float(values["delta"]))
        close(ident + "_water_kw", thermal["kw"], kw)
        close(ident + "_water_lpm", thermal["lpm"], lpm)
        pipe = result["pipe"]
        if lpm:
            velocity = lpm/60000/pipe["runs"]/(math.pi*(pipe["id_mm"]/1000)**2/4)
            close(ident + "_water_speed", pipe["velocity_mps"], velocity)
            check(ident + "_water_limit", velocity <= float(values["velocity"]) + 1e-9)
        printed_kw = published(text, "冷熱容量")
        check(ident + "_published_kw", abs(printed_kw-kw) <= .0051)
    elif tool == "air":
        state = result["state"]
        temperature, rh, pressure = map(float, (values["temperature"], values["rh"], values["atmosphere"]))
        pw = saturation_pa(temperature)*rh/100
        w = .621945*pw/(pressure*1000-pw)
        close(ident + "_humidity_ratio", state["w"], w)
        close(ident + "_enthalpy", state["h"], 1.006*temperature+w*(2501+1.86*temperature))
        check(ident + "_wetbulb_order", state["wetbulb_c"] <= temperature + 1e-5)
        if rh:
            check(ident + "_dewpoint_order", state["dewpoint_c"] <= state["wetbulb_c"]+1e-5)
            close(ident + "_dewpoint_pressure", saturation_pa(state["dewpoint_c"]), pw, 1e-7)
        else:
            check(ident + "_dry_dewpoint", state["dewpoint_c"] is None and "無有限露點" in text)
        check(ident + "_published_enthalpy", abs(published(text, "空氣焓值")-state["h"]) <= .0051)
    else:
        if values["category"] == "溫度":
            close(ident + "_freezing_c", result["values"]["°C"], 0)
            close(ident + "_freezing_k", result["values"]["K"], 273.15)
        else:
            close(ident + "_cfm", result["values"]["CFM"], float(values["value"])/1.69901079552)


for changes in [{}, {"power": 5, "supply": "單相 220V"},
                {"power": 1, "supply": "單相 110V"}, {"power": 25, "kind": "連續運轉"},
                {"power": 100, "supply": "三相 480V", "length": 75},
                {"power": 12, "pf": 1}, {"power": 30, "pf": .6},
                {"power": 0}, {"power": 30, "ambient": 55, "loaded": 12},
                {"power": 300, "terminal": 90, "kind": "馬達"}]:
    case("electrical", **changes)
for changes in [{}, {"flow": 0}, {"flow": 750, "flow_unit": "CFM"},
                {"flow": 100, "velocity": 4}, {"flow": 50000, "velocity": 6, "ratio": 4},
                {"check_path": 1, "pressure": 1000}, {"check_path": 1, "pressure": 50}]:
    case("duct", **changes)
for changes in [{}, {"pressure": 0, "flow": 1000}, {"reference_t": 0},
                {"flow": 100, "flow_unit": "SCFM"},
                {"pressure": 600, "pressure_unit": "kPa(g)"}, {"flow": 0}]:
    case("gas", **changes)
for changes in [{}, {"mode": "反算燈數"}, {"lumen_mode": "燈具型錄流明", "lumens": 2000},
                {"area_mode": "體積 m³", "area": 90, "height": 3},
                {"area_mode": "面積 坪", "area": 9.075},
                {"area_mode": "長×寬", "length": 10, "width": 5},
                {"quantity": 0}, {"mode": "反算燈數", "target": 640}]:
    case("lighting", **changes)
for changes in [{}, {"mode": "已知熱量"}, {"mode": "已知熱量", "power": 10, "power_unit": "US RT"},
                {"flow": 100, "flow_unit": "US GPM"}, {"flow": 0}]:
    case("water", **changes)
for changes in [{}, {"temperature": -5, "rh": 80}, {"temperature": 35, "rh": 70}, {"rh": 0}]:
    case("air", **changes)
case("units")
case("units", category="溫度", value=32, unit="°F")

for tool, fields, key in [
    ("electrical", {"power": "nan"}, "power"), ("electrical", {"pf": 0}, "pf"),
    ("electrical", {"power": ""}, "power"), ("electrical", {"length": -1}, "length"),
    ("duct", {"flow": -1}, "flow"), ("duct", {"check_path": "yes"}, "check_path"),
    ("gas", {"pressure": 301}, "pressure"), ("gas", {"velocity": 0}, "velocity"),
    ("lighting", {"quantity": 1.5}, "quantity"),
    ("lighting", {"area_mode": "體積 m³", "height": 0}, "height"),
    ("lighting", {"mode": "反算燈數", "watts": 0}, "watts"),
    ("water", {"delta": 0}, "delta"), ("air", {"rh": 101}, "rh"),
    ("air", {"atmosphere": 59}, "atmosphere"),
    ("units", {"category": "溫度", "unit": "K", "value": -1}, "value"),
]:
    inputs = defaults(tool)
    inputs.update({k: str(v) for k, v in fields.items()})
    try:
        calculate_tool(tool, inputs)
    except ValidationError as error:
        check("reject_"+tool+"_"+key+"_"+str(len(checks)), error.field_name == key)
    else:
        check("reject_"+tool+"_"+key, False)

for tool, changes in [
    ("duct", {"length": "", "k_sum": "bad", "equipment": "nan"}),
    ("lighting", {"target": "", "lumens": "bad", "height": ""}),
    ("lighting", {"mode": "反算燈數", "quantity": "bad"}),
    ("water", {"power": "bad"}),
]:
    values = defaults(tool)
    values.update(changes)
    check("inactive_"+tool+"_"+str(len(checks)), calculate_tool(tool, values)["tool"] == tool)

(ROOT / "evidence/Simple_Numeric_Checks.json").write_text(
    json.dumps({"version": "5.5.4", "cases": cases, "checks": checks}, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print(f"{len(cases)} independent-tool scenarios, {len(checks)} numerical/report checks passed")
