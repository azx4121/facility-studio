"""Additive numerical verification; production design equations stay unchanged."""

from functools import lru_cache
import hashlib
import html
import json
import math
from importlib.metadata import version

from .ahu_engine import nm_calculate, nm_read_project
from .ahu_schema import NM_DEFAULTS

BUILD = "5.6.1-sandbox.1"
# Internal software/model-comparison limits, NOT a FEED design standard.
LIMITS = {
    "psychrolib_w": {"relative": 0.0002, "absolute": 1e-8},
    "psychrolib_h": {"relative": 0.0002, "absolute": 0.001},
    "coolprop_w": {"relative": 0.01, "absolute": 1e-6},
    "coolprop_h": {"relative": 0.01, "absolute": 0.15},
}
UNIT_GROUPS = {
    "體積流量": {
        "CMH": "meter**3/hour",
        "CFM": "foot**3/minute",
        "LPM": "liter/minute",
        "US GPM": "gallon/minute",
        "L/s": "liter/second",
    },
    "熱功率": {
        "kW": "kilowatt",
        "W": "watt",
        "美制冷凍噸": "refrigeration_ton",
        "BTU/h": "Btu/hour",
    },
    "壓力": {
        "Pa": "pascal",
        "kPa": "kilopascal",
        "bar": "bar",
        "psi": "psi",
        "mmH₂O": "millimeter_H2O",
    },
    "長度": {"m": "meter", "mm": "millimeter", "inch": "inch", "foot": "foot"},
    "溫度": {"°C": "degC", "°F": "degF", "K": "kelvin"},
    "質量流量": {
        "kg/h": "kilogram/hour",
        "kg/s": "kilogram/second",
        "lb/h": "pound/hour",
    },
    "能量": {"kWh": "kilowatt_hour", "kJ": "kilojoule", "MJ": "megajoule"},
    "密度": {"kg/m³": "kilogram/meter**3", "lb/ft³": "pound/foot**3"},
    "動力黏度": {
        "Pa·s": "pascal*second",
        "mPa·s": "millipascal*second",
        "cP": "centipoise",
    },
}


@lru_cache(maxsize=1)
def registry():
    from pint import UnitRegistry

    return UnitRegistry()


def finite(value, label, low=-1e12, high=1e12):
    if isinstance(value, bool):
        raise ValueError(label + "不得使用布林值。")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(label + "請填數值。") from None
    if not math.isfinite(number) or not low <= number <= high:
        raise ValueError(f"{label}須介於 {low:g}～{high:g}，且為有限數值。")
    return number


def convert_units(value, group, source):
    if group not in UNIT_GROUPS or source not in UNIT_GROUPS[group]:
        raise ValueError("請選擇同一物理量的已支援單位。")
    number = finite(value, "原數值")
    u = registry()
    q = u.Quantity(number, UNIT_GROUPS[group][source])
    if group == "溫度" and q.to("kelvin").magnitude < 0:
        raise ValueError("溫度不得低於絕對零度。")
    return {name: q.to(unit).magnitude for name, unit in UNIT_GROUPS[group].items()}


def metadata():
    return {
        name: version(name) for name in ("PsychroLib", "CoolProp", "Pint", "fluids")
    }


def difference(actual, reference, key):
    lim = LIMITS[key]
    delta = actual - reference
    limit = lim["absolute"] + lim["relative"] * abs(reference)
    return {"delta": delta, "limit": limit, "within_limit": abs(delta) <= limit}


def compare_inputs(inputs, case="原版預設合成案例"):
    import psychrolib
    from CoolProp.HumidAirProp import HAPropsSI

    psychrolib.SetUnitSystem(psychrolib.SI)
    result = nm_calculate(dict(inputs))
    pressure = float(result["inputs"]["p"]) * 1000
    rows = []
    balances = []
    for season in ("summer", "winter"):
        block = result[season]

        def reference_state(point):
            w_ref = psychrolib.GetHumRatioFromRelHum(
                point["t"], point["rh"] / 100, pressure
            )
            h_ref = psychrolib.GetMoistAirEnthalpy(point["t"], w_ref) / 1000
            return w_ref, h_ref

        basis = (
            block["target"]
            if result["inputs"]["flow_basis"].startswith("送風")
            else block["oa"]
        )
        basis_w, _ = reference_state(basis)
        volume = psychrolib.GetMoistAirVolume(basis["t"], basis_w, pressure)
        reference_mass = float(result["inputs"]["flow"]) / 3600 / volume
        wa, ha = reference_state(block["oa"])
        ws, hs = reference_state(block["sa"])
        net_air_heat = (
            block["h1"]["air_kw"]
            - block["c1"]["air_kw"]
            + block["steam"]["air_kw"]
            - block["c2"]["air_kw"]
            + block["h2"]["air_kw"]
            + float(result["inputs"]["fan_air_kw"])
        )
        net_water = (
            block["evap_kg_h"]
            + block["steam"]["kg_h"]
            - (block["c1"]["condensate_kg_s"] + block["c2"]["condensate_kg_s"]) * 3600
        )
        balances.append(
            {
                "season": season,
                "engine_mass_kg_s": block["mass"],
                "psychrolib_mass_kg_s": reference_mass,
                "reference_energy_residual_kw": reference_mass * (hs - ha)
                - net_air_heat,
                "reference_moisture_residual_kg_h": reference_mass * (ws - wa) * 3600
                - net_water,
            }
        )
        for label, point in block["nodes"]:
            t, rh = point["t"], point["rh"] / 100
            # Recompute W from T/RH, rather than reuse the engine's W for H.
            w = psychrolib.GetHumRatioFromRelHum(t, rh, pressure)
            h = psychrolib.GetMoistAirEnthalpy(t, w) / 1000
            cw = HAPropsSI("W", "T", t + 273.15, "P", pressure, "R", rh)
            ch = HAPropsSI("H", "T", t + 273.15, "P", pressure, "R", rh) / 1000
            rows.append(
                {
                    "season": season,
                    "node": label,
                    "temperature_c": t,
                    "relative_humidity_pct": rh * 100,
                    "engine_w": point["w"],
                    "psychrolib_w": w,
                    "coolprop_w": cw,
                    "engine_h": point["h"],
                    "psychrolib_h": h,
                    "coolprop_h": ch,
                    "checks": {
                        key: difference(
                            point["w"] if key.endswith("_w") else point["h"], ref, key
                        )
                        for key, ref in [
                            ("psychrolib_w", w),
                            ("psychrolib_h", h),
                            ("coolprop_w", cw),
                            ("coolprop_h", ch),
                        ]
                    },
                }
            )
        for tag in ("c1", "c2", "h1", "h2"):
            stage = block[tag]

            def enthalpy(p):
                sw = psychrolib.GetHumRatioFromRelHum(p["t"], p["rh"] / 100, pressure)
                return psychrolib.GetMoistAirEnthalpy(p["t"], sw) / 1000

            sign = 1 if tag.startswith("c") else -1
            ref = (
                sign
                * reference_mass
                * (enthalpy(stage["inlet"]) - enthalpy(stage["outlet"]))
            )
            rows.append(
                {
                    "season": season,
                    "stage": tag.upper(),
                    "engine_air_kw": stage["air_kw"],
                    "psychrolib_air_kw": ref,
                    "reference_mass_kg_s": reference_mass,
                }
            )
    checks = [c for row in rows if "checks" in row for c in row["checks"].values()]
    return {
        "build": BUILD,
        "kind": "ahu_comparison",
        "case": case,
        "project_hash": result["hash"],
        "inputs": result["inputs"],
        "pressure_pa": pressure,
        "model_quality": result["quality"],
        "reference_balances": balances,
        "comparison": rows,
        "numerical_summary": {
            "checks": len(checks),
            "within_limit": sum(c["within_limit"] for c in checks),
            "outside_limit": sum(not c["within_limit"] for c in checks),
        },
        "limits": LIMITS,
        "versions": metadata(),
        "scope": "內部數值對照；容許差是軟體回歸門檻，不是 FEED 工程驗收標準。乾空氣流量以相同設計風量基準及 PsychroLib 重算；平衡使用原段落熱量與加除濕量核對，不驗證實際設備性能。",
    }


def compare_file(path):
    project = nm_read_project(path)
    if project.get("draft"):
        raise ValueError("草稿資料不完整；請先修正並儲存正式 AHU 單機專案。")
    return compare_inputs(project["inputs"], "選取的 AHU 單機專案")


def compare_defaults():
    return compare_inputs(NM_DEFAULTS)


def pipe_calculate(inputs):
    from CoolProp.CoolProp import PropsSI, PhaseSI
    from fluids import Reynolds
    from fluids.friction import friction_factor
    from .utils import darcy_factor

    q = finite(inputs.get("flow_lpm"), "水量 LPM", 0, 1e7) / 60000
    d = finite(inputs.get("id_mm"), "內徑 mm", 0.1, 3000) / 1000
    length = finite(inputs.get("length_m"), "直管長度 m", 0, 100000)
    rough = finite(inputs.get("roughness_mm"), "粗糙度 mm", 0, 5) / 1000
    if rough >= d:
        raise ValueError("粗糙度必須小於內徑。")
    k = finite(inputs.get("sum_k"), "管件 K 加總", 0, 1e6)
    eq = finite(inputs.get("equipment_pa"), "設備壓降 Pa", 0, 1e8)
    t = finite(inputs.get("temperature_c"), "水溫 °C", 1, 95)
    p = finite(inputs.get("pressure_kpa"), "水絕對壓力 kPa", 5, 2000) * 1000
    mode = inputs.get("boundary", "閉式循環")
    if mode not in ("閉式循環", "開式系統"):
        raise ValueError("請選擇閉式循環或開式系統。")
    z = finite(inputs.get("static_m", 0), "開式靜揚程 m", 0, 10000)
    if mode == "閉式循環" and z:
        raise ValueError("閉式循環不直接加入樓高；靜揚程請填 0。")
    phase = PhaseSI("T", t + 273.15, "P", p, "Water")
    if phase != "liquid":
        raise ValueError("指定水溫與絕對壓力不是單相液態水；請修正條件。")
    rho = PropsSI("D", "T", t + 273.15, "P", p, "Water")
    mu = PropsSI("V", "T", t + 273.15, "P", p, "Water")
    cp = PropsSI("C", "T", t + 273.15, "P", p, "Water")
    run_count = finite(inputs.get("runs", 1), "等流量並聯支數", 1, 32)
    if run_count != int(run_count):
        raise ValueError("等流量並聯支數必須是整數。")
    runs = int(run_count)
    branch_q = q / runs
    velocity = branch_q / (math.pi * d * d / 4)
    re = Reynolds(V=velocity, D=d, rho=rho, mu=mu) if q else 0
    transitional = 2040 <= re < 4000
    f = friction_factor(Re=re, eD=rough / d, Darcy=True) if q else 0
    dynamic = rho * velocity**2 / 2
    straight = f * length / d * dynamic
    local = k * dynamic
    equipment = eq if q else 0
    static = rho * 9.80665 * z
    total = straight + local + equipment + static
    # Compare the old correlation with exactly the same material properties.
    legacy_f = darcy_factor(re, rough / d) if q else 0
    legacy = legacy_f * length / d * dynamic + local + equipment + static
    return {
        "build": BUILD,
        "kind": "liquid_pipe",
        "inputs": dict(inputs),
        "rho_kg_m3": rho,
        "mu_pa_s": mu,
        "cp_j_kg_k": cp,
        "flow_m3s": q,
        "runs": runs,
        "branch_flow_m3s": branch_q,
        "velocity_m_s": velocity,
        "reynolds": re,
        "darcy_factor": f,
        "legacy_darcy_factor": legacy_f,
        "legacy_same_properties_pa": legacy,
        "straight_pa": straight,
        "local_pa": local,
        "equipment_pa": equipment,
        "static_pa": static,
        "total_pa": total,
        "head_m": total / (rho * 9.80665),
        "regime": "零流量"
        if not q
        else "過渡流：需覆核"
        if transitional
        else "層流"
        if re < 2040
        else "紊流",
        "versions": metadata(),
        "scope": "單相純水、圓管、單一路徑或同徑等流量並聯。壓差為單支路徑壓差，不乘並聯支數。直管採 Darcy–Weisbach／fluids，水物性採 CoolProp；K 與設備壓降為使用者輸入。過渡流不判合格。未涵蓋氣體可壓縮流、混合液或網路平衡。",
    }


def pipe_from_water_tool(data):
    from .simple_engines import water

    r = water(data)
    if not r["pipe"]["id_mm"]:
        raise ValueError("原水管工具目前沒有管徑需求，請在本頁明填內徑。")
    return {
        "flow_lpm": str(r["flow_lpm"]),
        "runs": str(r["pipe"]["runs"]),
        "id_mm": str(r["pipe"]["id_mm"]),
        "length_m": str(data["length"]),
        "sum_k": str(data["k_sum"]),
        "equipment_pa": str(data["equipment_pa"]),
        "roughness_mm": str(data["roughness_mm"]),
    }


def report_text(result):
    lines = [f"Facility Studio 工程驗證沙盒 {BUILD}", result.get("scope", ""), ""]
    if result["kind"] == "ahu_comparison":
        q = result["model_quality"]
        n = result["numerical_summary"]
        lines += [
            "資料：" + result["case"],
            "輸入雜湊：" + result["project_hash"],
            f"原模型工程狀態：{q['status']}；未達 {q['failed']}，待資料 {q['pending']}。",
            f"數值對照：{n['within_limit']}/{n['checks']} 在內部門檻內，超限 {n['outside_limit']}。",
            "",
            "工程品質明細：",
        ]
        lines += [
            f"• {x['status']}｜{x['name']}：{x['detail']}"
            + (f"（欄位 {x['field']}）" if x["field"] else "")
            for x in q["items"]
        ]
        lines += [
            "",
            "數值門檻（絕對值＋相對值×參考值）：",
            json.dumps(LIMITS, ensure_ascii=False),
            "",
            "狀態與段落對照：",
        ]
        for balance in result["reference_balances"]:
            season = "夏季" if balance["season"] == "summer" else "冬季"
            lines.append(
                f"{season} PsychroLib 重算：乾空氣 {balance['psychrolib_mass_kg_s']:.8f} kg/s；空氣側熱平衡殘差 {balance['reference_energy_residual_kw']:.8g} kW；水量殘差 {balance['reference_moisture_residual_kg_h']:.8g} kg/h。"
            )
        for x in result["comparison"]:
            season = "夏季" if x["season"] == "summer" else "冬季"
            if "node" in x:
                lines += [
                    f"{season} {x['node']}｜{x['temperature_c']:.2f} °C／{x['relative_humidity_pct']:.2f} %RH",
                    f"  含濕比 kg/kg 乾空氣：原 {x['engine_w']:.8f}／PsychroLib {x['psychrolib_w']:.8f}／CoolProp {x['coolprop_w']:.8f}",
                    f"  焓 kJ/kg 乾空氣：原 {x['engine_h']:.5f}／PsychroLib {x['psychrolib_h']:.5f}／CoolProp {x['coolprop_h']:.5f}",
                ]
                for key, c in x["checks"].items():
                    if not c["within_limit"]:
                        lines.append(
                            f"  超限：{key}，差 {c['delta']:+.8g}，門檻 {c['limit']:.8g}"
                        )
            else:
                lines.append(
                    f"{season} {x['stage']} 空氣側 kW：原 {x['engine_air_kw']:.5f}／PsychroLib {x['psychrolib_air_kw']:.5f}；PsychroLib 乾空氣流量 {x['reference_mass_kg_s']:.5f} kg/s。"
                )
    elif result["kind"] == "liquid_pipe":
        labels = [
            ("regime", "流況"),
            ("runs", "等流量並聯支數"),
            ("flow_m3s", "總水量 m³/s"),
            ("branch_flow_m3s", "每支水量 m³/s"),
            ("rho_kg_m3", "水密度 kg/m³"),
            ("mu_pa_s", "動力黏度 Pa·s"),
            ("cp_j_kg_k", "比熱 J/(kg·K)"),
            ("velocity_m_s", "流速 m/s"),
            ("reynolds", "Reynolds 數"),
            ("darcy_factor", "Darcy 摩擦因子"),
            ("straight_pa", "直管壓降 Pa"),
            ("local_pa", "管件壓降 Pa"),
            ("equipment_pa", "設備壓降 Pa"),
            ("static_pa", "靜壓 Pa"),
            ("total_pa", "總壓差 Pa"),
            ("head_m", "揚程 m"),
            ("legacy_same_properties_pa", "原關聯式同物性壓差 Pa"),
        ]
        lines += [
            f"{label}：{result[key]:.8g}"
            if isinstance(result[key], (float, int))
            else f"{label}：{result[key]}"
            for key, label in labels
        ]
        lines += [
            "",
            "採用輸入：",
            json.dumps(result["inputs"], ensure_ascii=False, indent=2),
        ]
    else:
        lines += [f"{k}：{v:.10g}" for k, v in result["values"].items()]
    lines += [
        "",
        "套件版本："
        + json.dumps(result.get("versions", metadata()), ensure_ascii=False),
    ]
    return "\n".join(lines)


def export_report(result, path):
    from pathlib import Path
    from .utils import atomic_text

    path = Path(path)
    # Prevent accidentally replacing a source project, including a non-json suffix.
    if path.exists():
        raise ValueError("為保留既有檔案，請使用新的報告檔名。")
    if path.suffix.lower() == ".json":
        body = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
    elif path.suffix.lower() == ".html":
        body = (
            '<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><title>工程驗證報告</title><style>body{font:16px sans-serif;max-width:1100px;margin:32px auto;padding:0 20px}pre{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.6}</style><h1>工程驗證報告</h1><pre>'
            + html.escape(report_text(result))
            + "</pre></html>"
        )
    elif path.suffix.lower() == ".txt":
        body = report_text(result)
    else:
        raise ValueError("報告副檔名請使用 .txt、.html 或 .json。")
    atomic_text(path, body)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()
