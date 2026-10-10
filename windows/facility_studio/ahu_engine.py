from .ahu_schema import NM_V3_KEYS
from .errors import InputError
from pathlib import Path
import copy
import json
from .json_io import read_json_file
from .ahu_schema import AHU_OPTIONAL_NUMBERS, NM_DEFAULTS, NM_FIELDS, NM_V1_KEYS
from .engine import blend, coil_record
from .quality import assess_ahu
from .utils import (
    US_RT_KW,
    choice,
    dewpoint,
    enthalpy,
    integer,
    number,
    project_hash,
    state_trh,
    state_tw,
)


def _nm_validate_base(i):
    from .field_state import ahu_inactive, effective_ahu

    if not isinstance(i, dict) or set(i) != set(NM_DEFAULTS):
        raise InputError(f"通用單機專案欄位缺漏或含未知欄位")
    inactive = ahu_inactive(i)
    for k, f in NM_FIELDS.items():
        v = i[k]
        limit = f["limit"]
        if not isinstance(v, str) or len(v) > 1000:
            raise InputError(f"請以文字保存欄位", field_name=f"{k}")
        if k in inactive:
            continue
        if isinstance(limit, list):
            choice(v, limit, k)
        elif isinstance(limit, tuple):
            if k in AHU_OPTIONAL_NUMBERS and (not v.strip()):
                continue
            number(v, k, *limit)
        elif not v.strip() or len(v) > 300:
            raise InputError(f"專案名稱不可空白或過長", field_name=f"{k}")
    for prefix in ("c1", "c2"):
        if float(i[prefix + "_out"]) <= float(i[prefix + "_in"]):
            raise InputError(f"冷卻水回水必須高於供水", field_name=f"{prefix}_out")
    if "hw_in" not in inactive and float(i["hw_in"]) <= float(i["hw_out"]):
        raise InputError(f"熱水供水必須高於回水", field_name=f"hw_out")
    integer(i["fan_qty"], "fan_qty", 1, 100)
    return i


def nm_h_sat(h, p):
    lo = -40.0
    hi = 80.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if state_trh(mid, 100, p)["h"] > h:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def nm_wash(s, eff, p):
    ts = nm_h_sat(s["h"], p)
    t = s["t"] - eff * max(0, s["t"] - ts)
    w = (s["h"] - 1.006 * t) / (2501 + 1.86 * t)
    return state_tw(t, max(s["w"], w), p)


def nm_precoil(s, i, p):
    adp = float(i["c1_in"]) + float(i["c1_adp"])
    t = min(s["t"], float(i["c1_t"]))
    if t >= s["t"] - 1e-09:
        return s
    if t < adp:
        raise InputError(f"C1 出口需求低於供水＋ADP 裕度", field_name=f"c1_t")
    a = state_trh(adp, 100, p)
    if s["w"] <= a["w"]:
        return state_tw(t, s["w"], p)
    hv = 2501 + 1.86 * t
    b = (1.006 * t + a["w"] * hv - a["h"]) / (s["h"] - a["h"] - (s["w"] - a["w"]) * hv)
    if not -1e-09 <= b <= 1 + 1e-09:
        raise InputError(f"C1 需求的旁通因子超出物理範圍")
    return blend(s, a, max(0, min(1, b)), p)


def _nm_heater_base(tag, s, target_t, m, i, p):
    target = state_tw(max(s["t"], target_t), s["w"], p)
    q = m * (target["h"] - s["h"])
    cp = 1.006 + 1.86 * s["w"]
    available = float(i[tag + "_hw_kw"]) if i["recovery"].startswith("二期") else 0.0
    order = i[tag + "_order"]
    pinch = float(i["hw_approach"])
    tin = float(i["hw_in"])
    tout = float(i["hw_out"])
    qh = 0.0
    note = ""
    if q > 1e-08 and available > 0:
        if order == "熱水 → 電熱":
            if tout >= s["t"] + pinch:
                qh = min(q, available, m * cp * max(0, tin - pinch - s["t"]))
            else:
                note = "回水端差不足，熱回收未採計"
        else:
            candidate = min(q, available)
            before = target["t"] - candidate / (m * cp)
            if target["t"] <= tin - pinch + 1e-08 and before <= tout - pinch + 1e-08:
                qh = candidate
            else:
                note = "電熱在前時不滿足指定供回水端差，熱回收未採計"
    qe = q - qh
    middle = state_tw(
        s["t"] + (qe if order == "電熱 → 熱水" else qh) / (m * cp), s["w"], p
    )
    return {
        "tag": tag.upper(),
        "inlet": s,
        "middle": middle,
        "outlet": target,
        "air_kw": q,
        "hw_kw": qh,
        "electric_air_kw": qe,
        "electric_kw": qe / float(i["heat_eta"]),
        "backup_electric_kw": q / float(i["heat_eta"]),
        "installed_kw": float(i[tag + "_kw"]),
        "water_lpm": qh * 60000 / (1000 * 4.1868 * (tin - tout)) if qh > 1e-8 else 0.0,
        "order": order,
        "note": note,
    }


def _nm_season_base(i, season):
    p = float(i["p"])
    oa = state_trh(float(i[season + "_t"]), float(i[season + "_rh"]), p)
    target = state_trh(float(i["sa_t"]), float(i["sa_rh"]), p)
    ref = target if i["flow_basis"].startswith("送風") else oa
    m = float(i["flow"]) / 3600 / ref["v_da"]
    ws = target["w"]
    eff = float(i["wash_eff"])
    need = oa["w"] < ws - 1e-10
    fanheat = float(i["fan_air_kw"])
    pre_fan_t = target["t"] - fanheat / (m * (1.006 + 1.86 * ws))
    if pre_fan_t < dewpoint(ws, p) - 1e-07:
        raise InputError(
            f"風機熱過大，所需風機前溫度低於送風露點", field_name=f"fan_air_kw"
        )
    c1in = oa
    c1out = oa
    pre = oa
    if not need and i["sequence"].startswith("C1"):
        c1out = nm_precoil(oa, i, p)
        pre = c1out
    h1target = pre["t"]
    wash_on = i["wash_mode"] == "AMC 需求持續水洗" or (
        i["wash_mode"] == "只在需要加濕時" and need
    )
    if need:
        if not wash_on:
            raise InputError(
                f"外氣水分不足而水洗停用，無法達成送風含濕量", field_name=f"wash_mode"
            )
        lo = pre["t"]
        hi = 80.0
        if nm_wash(state_tw(hi, pre["w"], p), eff, p)["w"] < ws:
            raise InputError(
                f"在 80°C 預熱範圍仍無法達到所需含濕量", field_name=f"wash_eff"
            )
        for _ in range(80):
            t = (lo + hi) / 2
            if nm_wash(state_tw(t, pre["w"], p), eff, p)["w"] >= ws:
                hi = t
            else:
                lo = t
        h1target = (lo + hi) / 2
    h1 = nm_heater("h1", pre, h1target, m, i, p)
    if i["sequence"].startswith("H1"):
        c1in = h1["outlet"]
        c1out = c1in if need else nm_precoil(c1in, i, p)
    else:
        c1in = oa
    wash_in = c1out if i["sequence"].startswith("H1") else h1["outlet"]
    washed = nm_wash(wash_in, eff, p) if wash_on else wash_in
    if washed["w"] < ws - 1e-08:
        raise InputError(f"水洗後含濕量不足，無法以再熱補水氣", field_name=f"wash_eff")
    w2 = ws if washed["w"] > ws + 1e-09 else washed["w"]
    t2 = min(washed["t"], pre_fan_t)
    if washed["w"] > ws + 1e-09:
        t2 = min(t2, dewpoint(ws, p))
    c2out = state_tw(t2, w2, p)
    adp = float(i["c2_in"]) + float(i["c2_adp"])
    c2_feasible = t2 >= adp - 1e-08 or (
        washed["t"] <= t2 + 1e-08 and washed["w"] <= w2 + 1e-10
    )
    c1 = coil_record("C1 預冷", c1in, c1out, m, 4.1868)
    c2 = coil_record("C2 再冷", washed, c2out, m, 4.1868)
    h2 = nm_heater("h2", c2out, pre_fan_t, m, i, p)
    sa = state_tw(h2["outlet"]["t"] + fanheat / (m * (1.006 + 1.86 * w2)), w2, p)
    evap = m * (washed["w"] - wash_in["w"]) * 3600
    balance = m * (sa["h"] - oa["h"]) - (
        h1["air_kw"] - c1["air_kw"] - c2["air_kw"] + h2["air_kw"] + fanheat
    )
    moisture = m * (sa["w"] - oa["w"]) * 3600 - (
        evap - (c1["condensate_kg_s"] + c2["condensate_kg_s"]) * 3600
    )
    if abs(balance) > 1e-05 or abs(moisture) > 1e-05:
        raise InputError(f"分段熱濕守恆檢核未通過")
    nodes = [("OA 外氣", oa), ("初／中效濾網", oa)]

    def add_h(h):
        first = "電熱" if h["order"].startswith("電熱") else "熱水"
        second = "熱水" if first == "電熱" else "電熱"
        nodes.extend(
            [
                (h["tag"] + " " + first, h["middle"]),
                (h["tag"] + " " + second, h["outlet"]),
            ]
        )

    if i["sequence"].startswith("H1"):
        add_h(h1)
        nodes.append(("C1 預冷", c1out))
    else:
        nodes.append(("C1 預冷", c1out))
        add_h(h1)
    nodes.extend([("水洗濕膜", washed), ("C2 再冷", c2out)])
    add_h(h2)
    nodes.extend([("EC 風機", sa), ("PTFE HEPA／送風", sa)])
    sf = 1 + float(i["sf"]) / 100
    checks = {
        "H1 電熱全載備援": h1["backup_electric_kw"] * sf <= float(i["h1_kw"]) + 1e-06,
        "H2 電熱全載備援": h2["backup_electric_kw"] * sf <= float(i["h2_kw"]) + 1e-06,
        "H1 當前熱源情境": h1["electric_kw"] * sf <= float(i["h1_kw"]) + 1e-06,
        "H2 當前熱源情境": h2["electric_kw"] * sf <= float(i["h2_kw"]) + 1e-06,
        "C1 總表候選容量": c1["water_kw"] * sf <= float(i["c1_rt"]) * US_RT_KW + 1e-06,
        "C2 總表候選容量": c2["water_kw"] * sf <= float(i["c2_rt"]) * US_RT_KW + 1e-06,
        "C2 可達 ADP": c2_feasible,
        "濕膜總表候選能力": evap * sf <= float(i["wash_rating"]) + 1e-06,
    }
    return {
        "season": season,
        "oa": oa,
        "target": target,
        "mass": m,
        "h1": h1,
        "c1": c1,
        "wash_in": wash_in,
        "wash_out": washed,
        "wash_on": wash_on,
        "evap_kg_h": max(0, evap),
        "c2": c2,
        "h2": h2,
        "sa": sa,
        "nodes": nodes,
        "checks": checks,
        "energy_residual_kw": balance,
        "moisture_residual_kg_h": moisture,
        "fan_inlet_cmh": m * h2["outlet"]["v_da"] * 3600,
    }


def _nm_calculate_base(i):
    from .field_state import effective_ahu, ahu_inactive

    raw = copy.deepcopy(nm_validate(i))
    i = effective_ahu(raw)
    summer = nm_season(i, "summer")
    winter = nm_season(i, "winter")
    n = lambda k: float(i[k])
    dp = sum(
        (
            float(i[k])
            for k in i
            if k.startswith("dp_") and k != "dp_status" and i[k].strip()
        )
    )
    fan_power = max(
        (
            s["fan_inlet_cmh"] / 3600 * dp / (1000 * n("fan_eff"))
            for s in [summer, winter]
        )
    )
    fan_installed = n("fan_qty") * n("fan_unit_kw")
    wash_selected = "水洗" in i["humidifier"]
    circ = (
        n("media_area") * n("wetting_rate")
        if wash_selected and n("media_area") and n("wetting_rate")
        else None
    )
    head = (
        sum((n(k) for k in ["spray_head", "spray_rise", "loop_loss"]))
        if wash_selected and all((i[k].strip() for k in ["spray_head", "spray_rise", "loop_loss"]))
        else None
    )
    return {
        "inputs": i,
        "raw_inputs": raw,
        "inactive_fields": ahu_inactive(raw),
        "summer": summer,
        "winter": winter,
        "circulation_lpm": circ,
        "pump_head_m": head,
        "evap_makeup_lph": max(summer["evap_kg_h"], winter["evap_kg_h"]) if wash_selected else 0.0,
        "makeup_plus_allowance_lph": (
            max(summer["evap_kg_h"], winter["evap_kg_h"]) + n("drift_lph")
            if wash_selected else 0.0
        ),
        "air_dp_pa": dp,
        "pressure_complete": i["dp_status"] == "已填完整同風量資料"
        and all((i[k].strip() for k in i if k.startswith("dp_") and k != "dp_status")),
        "fan_required_kw": fan_power,
        "fan_installed_kw": fan_installed,
        "installed_electric_kw": n("h1_kw") + n("h2_kw") + fan_installed,
        "fan_capacity_pass": fan_power <= fan_installed + 1e-08,
        "hash": project_hash(raw),
    }


def nm_draft_inputs(i):
    """Check storage shape and bounds while retaining unfinished field text."""
    if not isinstance(i, dict) or set(i) != set(NM_DEFAULTS):
        raise InputError("單機草稿欄位缺漏或含未知欄位")
    for key, value in i.items():
        if not isinstance(value, str) or len(value) > 1000:
            raise InputError("草稿必須為有長度限制的文字，不能包含執行物件", field_name=key)
    return dict(i)


def nm_validate(i):
    from .field_state import ahu_inactive

    if isinstance(i, dict) and set(i) == NM_V3_KEYS:
        i = dict(i, **{k: v for k, v in NM_DEFAULTS.items() if k not in NM_V3_KEYS})
    _nm_validate_base(i)
    inactive = ahu_inactive(i)
    if "steam_cond_min" not in inactive and float(i["steam_cond_min"]) > float(i["steam_cond_max"]):
        raise InputError(f"原廠電導率上限不得低於下限", field_name=f"steam_cond_max")
    for tag in ["h1", "h2"]:
        if tag + "_hw_in" not in inactive and i[tag + "_water_mode"] == "本段獨立設定" and float(
            i[tag + "_hw_in"]
        ) <= float(i[tag + "_hw_out"]):
            raise InputError(f"本段熱水供水必須高於回水", field_name=f"{tag}_hw_out")
        if tag + "_eta" not in inactive and 0 < float(i[tag + "_eta"]) < 0.1:
            raise InputError(f"效率限 0 沿用共同或 0.1～1", field_name=f"{tag}_eta")
    return i


def nm_read_project(path):
    if Path(path).stat().st_size > 2000000:
        raise InputError(f"檔案過大")
    doc = read_json_file(path, max_bytes=2_000_000)
    if (
        not isinstance(doc, dict)
        or not {"kind", "schema_version", "inputs"}.issubset(doc)
        or doc["kind"] not in ["nammao_mau", "ahu_stage"]
        or type(doc["schema_version"]) is not int
    ):
        raise InputError(f"請使用通用單機專案格式")
    if doc["schema_version"] == 5:
        if set(doc) != {"kind", "schema_version", "inputs", "draft"} or doc["draft"] is not True:
            raise InputError("單機草稿標記或格式不符")
        doc["inputs"] = nm_draft_inputs(doc["inputs"])
        doc["kind"] = "ahu_stage"
        return doc
    if set(doc) != {"kind", "schema_version", "inputs"}:
        raise InputError("請使用通用單機專案格式")
    if doc["schema_version"] == 1:
        if not isinstance(doc["inputs"], dict) or set(doc["inputs"]) != NM_V1_KEYS:
            raise InputError(f"舊單機專案欄位不完整")
        doc = copy.deepcopy(doc)
        doc["schema_version"] = 2
        doc["inputs"].update(
            {k: v for k, v in NM_DEFAULTS.items() if k not in NM_V1_KEYS}
        )
    if doc["schema_version"] not in [2, 3, 4]:
        raise InputError(f"不支援的單機專案版本")
    # Add new optional fields before converting the legacy zero-as-unknown values.
    if isinstance(doc["inputs"], dict) and set(doc["inputs"]) == NM_V3_KEYS:
        doc["inputs"].update(
            {k: v for k, v in NM_DEFAULTS.items() if k not in NM_V3_KEYS}
        )
    if not isinstance(doc["inputs"], dict) or set(doc["inputs"]) != set(NM_DEFAULTS):
        raise InputError("單機專案欄位缺漏或含未知欄位")
    if doc["schema_version"] < 3:
        for k in AHU_OPTIONAL_NUMBERS:
            if not str(doc["inputs"][k]).strip() or float(doc["inputs"][k]) == 0:
                doc["inputs"][k] = ""
    doc["kind"] = "ahu_stage"
    doc["schema_version"] = 4
    doc["inputs"] = nm_validate(doc["inputs"])
    return doc


def nm_heater(tag, s, target_t, m, i, p):
    source = i.get(tag + "_source", "熱水＋電熱")
    electric_enabled = source in ["電熱", "熱水＋電熱"]
    water_enabled = source in ["回收熱水", "熱水＋電熱"] and i["recovery"].startswith("二期")
    j = dict(i)
    if water_enabled and i.get(tag + "_water_mode") == "本段獨立設定":
        for suffix in ["in", "out", "approach"]:
            j["hw_" + suffix] = i[tag + "_hw_" + suffix]
    if electric_enabled and float(i.get(tag + "_eta", 0)) > 0:
        j["heat_eta"] = i[tag + "_eta"]
    if not electric_enabled:
        j["heat_eta"] = "1"
        j[tag + "_kw"] = "0"
    if not water_enabled:
        j[tag + "_hw_kw"] = "0"
    h = _nm_heater_base(tag, s, target_t, m, j, p)
    h["source"] = source
    h["unserved_kw"] = 0.0
    if source in ["回收熱水", "停用"]:
        h["unserved_kw"] = h["electric_air_kw"]
        h["electric_air_kw"] = h["electric_kw"] = 0.0
        h["backup_electric_kw"] = 0.0
    sf = 1 + float(i["sf"]) / 100
    h["source_pass"] = (
        h["unserved_kw"] < 1e-06
        and (not electric_enabled or h["electric_kw"] * sf <= float(j[tag + "_kw"]) + 1e-06)
        and (h["hw_kw"] * sf <= float(j[tag + "_hw_kw"]) + 1e-06)
    )
    h["water_enabled"] = water_enabled
    h["electric_enabled"] = electric_enabled
    h["effective_water"] = (
        {k: float(j[k]) for k in ["hw_in", "hw_out", "hw_approach"]}
        if water_enabled else None
    )
    h["effective_electric_eta"] = float(j["heat_eta"]) if electric_enabled else None
    return h


def nm_explicit_coil(s, tag, season, i, p):
    prefix = season + "_" + tag
    mode = i[prefix + "_mode"]
    t = float(i[prefix + "_t"])
    if mode == "旁通":
        return s
    if mode == "指定出口 T/RH":
        out = state_trh(t, float(i[prefix + "_rh"]), p)
    elif tag == "c1":
        j = dict(i, c1_t=str(t))
        out = nm_precoil(s, j, p)
    else:
        if t > s["t"] + 1e-08:
            raise InputError(f"冷卻段不可把空氣加熱", field_name=f"{prefix}_t")
        out = state_tw(t, min(s["w"], state_trh(t, 100, p)["w"]), p)
    if (
        out["t"] > s["t"] + 1e-07
        or out["w"] > s["w"] + 1e-09
        or out["h"] > s["h"] + 1e-07
    ):
        raise InputError(
            f"冷卻出口不得加熱或增加水氣；請檢查 T/RH", field_name=f"{prefix}_mode"
        )
    return out


def nm_steam(s, ws, m, i, p):
    g = max(0, ws - s["w"]) * m
    h = s["h"] + g / m * float(i["steam_h"])
    w = s["w"] + g / m
    t = (h - 2501 * w) / (1.006 + 1.86 * w)
    try:
        out = state_tw(t, w, p)
    except InputError as e:
        raise InputError(
            f"蒸汽注入後超飽和，需提高 H1 出口或減少注入需求", field_name=f"humidifier"
        ) from e
    power = (
        g
        * (float(i["steam_h"]) - 4.1868 * float(i["steam_feed_t"]))
        / float(i["steam_eta"])
    )
    return (
        out,
        {"kg_h": g * 3600, "air_kw": g * float(i["steam_h"]), "electric_kw": power},
    )


def nm_season(i, season):
    if i.get("target_mode") == "主案分季需求":
        i = dict(
            i,
            sa_t=i[season + "_sa_t"],
            sa_rh=i[season + "_sa_rh"],
            flow=i[season + "_flow"],
            flow_basis="送風狀態實際風量",
        )
    auto = all(
        (
            i[season + "_" + tag + "_mode"] == "自動需求"
            for tag in ["h1", "c1", "c2", "h2"]
        )
    )
    if (
        auto
        and i["humidifier"] == "循環水洗濕膜"
        and all((i[tag + "_source"] == "熱水＋電熱" for tag in ["h1", "h2"]))
    ):
        s = _nm_season_base(i, season)
        for tag in ["h1", "h2"]:
            s["checks"][tag.upper() + " 當前熱源情境"] = s[tag]["source_pass"]
        s.update(
            steam={"kg_h": 0.0, "air_kw": 0.0, "electric_kw": 0.0},
            control_basis="自動目標需求",
        )
        return s
    p = float(i["p"])
    n = lambda k: float(i[k])
    oa = state_trh(n(season + "_t"), n(season + "_rh"), p)
    target = state_trh(n("sa_t"), n("sa_rh"), p)
    ws = target["w"]
    ref = target if i["flow_basis"].startswith("送風") else oa
    m = n("flow") / 3600 / ref["v_da"]
    fanheat = n("fan_air_kw")
    pre_fan_t = target["t"] - fanheat / (m * (1.006 + 1.86 * ws))
    if pre_fan_t < dewpoint(ws, p) - 1e-07:
        raise InputError(f"所需風機前狀態低於送風露點", field_name=f"fan_air_kw")
    wet = "水洗" in i["humidifier"]
    steam_on = "蒸汽" in i["humidifier"]
    need = oa["w"] < ws - 1e-10
    wash_on = wet and (
        i["wash_mode"] == "AMC 需求持續水洗"
        or (i["wash_mode"] == "只在需要加濕時" and need)
    )

    def cooling1(s):
        mode = i[season + "_c1_mode"]
        return (
            (s if need else nm_precoil(s, i, p))
            if mode == "自動需求"
            else nm_explicit_coil(s, "c1", season, i, p)
        )

    c1in = oa
    c1out = oa
    pre = oa
    if i["sequence"].startswith("C1"):
        c1out = cooling1(oa)
        pre = c1out
    ht = pre["t"]
    mode = i[season + "_h1_mode"]
    if mode == "指定出口乾球":
        ht = n(season + "_h1_t")
        if ht < pre["t"] - 1e-07:
            raise InputError(f"H1 加熱段不可降低乾球", field_name=f"{season}_h1_t")
    elif mode == "自動需求" and need:
        if wash_on and (not steam_on):
            lo = pre["t"]
            hi = 80.0
            if nm_wash(state_tw(hi, pre["w"], p), n("wash_eff"), p)["w"] < ws:
                raise InputError(f"80°C 範圍仍無法達標", field_name=f"wash_eff")
            for _ in range(80):
                mid = (lo + hi) / 2
                if nm_wash(state_tw(mid, pre["w"], p), n("wash_eff"), p)["w"] >= ws:
                    hi = mid
                else:
                    lo = mid
            ht = (lo + hi) / 2
        elif steam_on:

            def deficit(t):
                st = state_tw(t, pre["w"], p)
                st = nm_wash(st, n("wash_eff"), p) if wash_on else st
                dw = max(0, ws - st["w"])
                hh = st["h"] + dw * n("steam_h")
                ww = st["w"] + dw
                return enthalpy(dewpoint(ww, p) + 0.2, ww) - hh

            if deficit(ht) > 0:
                lo = ht
                hi = 80.0
                if deficit(hi) > 0:
                    raise InputError(
                        f"80°C 預熱仍無法防止蒸汽過飽和", field_name=f"humidifier"
                    )
                for _ in range(80):
                    mid = (lo + hi) / 2
                    if deficit(mid) > 0:
                        lo = mid
                    else:
                        hi = mid
                ht = (lo + hi) / 2
    h1 = nm_heater("h1", pre, ht, m, i, p)
    if i["sequence"].startswith("H1"):
        c1in = h1["outlet"]
        c1out = cooling1(c1in)
    wash_in = c1out if i["sequence"].startswith("H1") else h1["outlet"]
    washed = nm_wash(wash_in, n("wash_eff"), p) if wash_on else wash_in
    steam = {"kg_h": 0.0, "air_kw": 0.0, "electric_kw": 0.0}
    c2in = washed
    if steam_on:
        c2in, steam = nm_steam(washed, ws, m, i, p)
    mode = i[season + "_c2_mode"]
    if mode == "自動需求":
        w2 = min(c2in["w"], ws)
        t2 = min(c2in["t"], pre_fan_t)
        if c2in["w"] > ws + 1e-09:
            t2 = min(t2, dewpoint(ws, p))
        c2out = state_tw(t2, w2, p)
    else:
        c2out = nm_explicit_coil(c2in, "c2", season, i, p)
    mode = i[season + "_h2_mode"]
    ht = (
        max(c2out["t"], target["t"] - fanheat / (m * (1.006 + 1.86 * c2out["w"])))
        if mode == "自動需求"
        else c2out["t"] if mode == "旁通" else n(season + "_h2_t")
    )
    if ht < c2out["t"] - 1e-07:
        raise InputError(f"H2 加熱段不可降低乾球", field_name=f"{season}_h2_t")
    h2 = nm_heater("h2", c2out, ht, m, i, p)
    sa = state_tw(ht + fanheat / (m * (1.006 + 1.86 * c2out["w"])), c2out["w"], p)
    c1 = coil_record("C1 預冷", c1in, c1out, m, 4.1868)
    c2 = coil_record("C2 再冷", c2in, c2out, m, 4.1868)
    evap = m * (washed["w"] - wash_in["w"]) * 3600
    nodes = [("OA 外氣", oa), ("初／中效濾網", oa)]

    def add_h(h):
        if h["source"] == "電熱":
            nodes.append((h["tag"] + " 電熱（需求）", h["outlet"]))
        elif h["source"] in ["回收熱水", "停用"]:
            delivered = state_tw(
                h["inlet"]["t"] + h["hw_kw"] / (m * (1.006 + 1.86 * h["inlet"]["w"])),
                h["inlet"]["w"],
                p,
            )
            nodes.append((h["tag"] + " " + h["source"], delivered))
            if h["unserved_kw"] > 1e-06:
                nodes.append((h["tag"] + " 未供應熱量（需求點）", h["outlet"]))
        else:
            first = "電熱" if h["order"].startswith("電熱") else "熱水"
            second = "熱水" if first == "電熱" else "電熱"
            nodes.extend(
                [
                    (h["tag"] + " " + first, h["middle"]),
                    (h["tag"] + " " + second, h["outlet"]),
                ]
            )

    if i["sequence"].startswith("H1"):
        add_h(h1)
        nodes.append(("C1 預冷", c1out))
    else:
        nodes.append(("C1 預冷", c1out))
        add_h(h1)
    if wet:
        nodes.append(("水洗濕膜", washed))
    if steam_on:
        nodes.append(("電極蒸汽" if "電極" in i["humidifier"] else "電熱蒸汽", c2in))
    nodes.append(("C2 再冷", c2out))
    add_h(h2)
    nodes.extend([("EC 風機", sa), ("PTFE HEPA／送風", sa)])
    sf = 1 + n("sf") / 100
    checks = {}
    for tag, h in [("h1", h1), ("h2", h2)]:
        if h["source"] in ["熱水＋電熱", "電熱"]:
            checks[tag.upper() + " 電熱全載備援"] = (
                h["backup_electric_kw"] * sf <= n(tag + "_kw") + 1e-06
            )
        checks[tag.upper() + " 當前熱源情境"] = h["source_pass"]
    for tag, c in [("c1", c1), ("c2", c2)]:
        checks[tag.upper() + " 總表候選容量"] = (
            c["water_kw"] * sf <= n(tag + "_rt") * US_RT_KW + 1e-06
        )
        adp = n(tag + "_in") + n(tag + "_adp")
        adpw = state_trh(adp, 100, p)["w"]
        checks[tag.upper() + " 可達 ADP"] = c["air_kw"] <= 1e-08 or (
            c["outlet"]["t"] >= adp - 1e-08
            and c["outlet"]["w"] >= min(c["inlet"]["w"], adpw) - 1e-09
        )
    checks["送風乾球目標"] = abs(sa["t"] - target["t"]) <= 0.05
    checks["送風含濕量目標"] = abs(sa["w"] - target["w"]) <= 1e-07
    if wet:
        checks["濕膜總表候選能力"] = evap * sf <= n("wash_rating") + 1e-06
    if steam_on:
        checks["蒸汽產量額定"] = steam["kg_h"] * sf <= n("steam_capacity") + 1e-06
        checks["蒸汽電力額定"] = steam["electric_kw"] * sf <= n("steam_kw") + 1e-06
        checks["蒸汽給水已確認"] = i["steam_water"] == "原廠確認可用"
        if "電極" in i["humidifier"]:
            checks["電極給水電導率"] = (
                i["steam_water"] == "原廠確認可用"
                and n("steam_cond_min") > 0
                and (
                    n("steam_cond_min")
                    <= n("steam_conductivity")
                    <= n("steam_cond_max")
                )
            )
    balance = m * (sa["h"] - oa["h"]) - (
        h1["air_kw"]
        - c1["air_kw"]
        + steam["air_kw"]
        - c2["air_kw"]
        + h2["air_kw"]
        + fanheat
    )
    moisture = m * (sa["w"] - oa["w"]) * 3600 - (
        evap + steam["kg_h"] - (c1["condensate_kg_s"] + c2["condensate_kg_s"]) * 3600
    )
    if abs(balance) > 1e-05 or abs(moisture) > 1e-05:
        raise InputError(f"分段熱濕守恆未通過")
    return {
        "season": season,
        "oa": oa,
        "target": target,
        "mass": m,
        "h1": h1,
        "c1": c1,
        "wash_in": wash_in,
        "wash_out": washed,
        "wash_on": wash_on,
        "evap_kg_h": evap,
        "c2": c2,
        "h2": h2,
        "sa": sa,
        "nodes": nodes,
        "checks": checks,
        "energy_residual_kw": balance,
        "moisture_residual_kg_h": moisture,
        "fan_inlet_cmh": m * h2["outlet"]["v_da"] * 3600,
        "steam": steam,
        "control_basis": "逐段指定／自動混合需求",
    }


def nm_calculate(i):
    r = _nm_calculate_base(i)
    i = r["inputs"]
    r["active_installed_electric_kw"] = (
        sum(
            (
                float(i[t + "_kw"])
                for t in ["h1", "h2"]
                if i[t + "_source"] in ["電熱", "熱水＋電熱"]
            )
        )
        + r["fan_installed_kw"]
        + (float(i["steam_kw"]) if "蒸汽" in i["humidifier"] else 0)
    )
    # Compatibility alias; both keys now describe the same selected equipment.
    r["installed_electric_kw"] = r["active_installed_electric_kw"]
    r["quality"] = assess_ahu(r)
    return r
