"""One set of activation rules for the forms and the engineering validators.

Inactive drafts stay in saved inputs. Only the calculation copy receives safe
placeholders; mode logic must never consume an inactive engineering parameter.
"""
from .schema import DEFAULTS, FIELDS, PD_DEFAULTS
from .ahu_schema import NM_DEFAULTS, NM_FIELDS


def main_inactive(i):
    off = {}

    def disable(keys, reason):
        off.update({k: reason for k in keys})

    system = i.get("sys_type", "")
    if not system.startswith("MAU"):
        disable("mau_supply_t en_dcc_rt ffu_cmh ffu_w dccw_in dccw_dp_margin dcc_airflow_mode dcc_airflow_cmh dcc_air_approach".split(), "本模式不使用 MAU／DCC／FFU")
    elif i.get("dcc_airflow_mode") != "獨立 DCC 循環":
        disable(["dcc_airflow_cmh"], "沿用 FFU 循環風量")
    if not system.startswith("FCU"):
        disable(["en_fcu_cmh", "fcu_rt"], "本模式不使用 FCU")
    if not system.startswith("RCU"):
        disable(["en_rcu_rt"], "本模式不使用 RCU")
    if i.get("pre_mode") == "停用／旁通":
        disable(["chw1_in", "adp_approach", "pre_t", "pre_rh"], "一段旁通，保留備用設定")
    elif i.get("pre_mode") != "指定出口（需求檢核）":
        disable(["pre_rh"], "出口濕度由盤管過程計算")
    for zone in "AB":
        keys = ["face_" + zone, "coverage_" + zone] if i.get("mode_" + zone) == "ACH" else ["en_ach_" + zone]
        disable(keys, "未採用的循環風量計算方式")
    for prefix, flow, unit in WATER_ROWS:
        if i.get(prefix + "_link") == "連動負荷":
            disable([flow, unit], "採用負荷反算水量，手填值僅保留")
        if i.get(prefix + "_fluid_mode") != "本迴路獨立物性":
            disable([prefix + "_" + prop for prop in ("fluid_name", "rho", "cp", "mu")],
                    "本迴路採共用參考物性，獨立值只保留為草稿")
    if i.get("latent_mode") != "已知潛熱 kW":
        disable(["process_latent_kw"], "目前不以 kW 輸入製程水氣")
    if i.get("latent_mode") != "已知產濕量 kg/h":
        disable(["process_moisture_kg_h"], "目前不以 kg/h 輸入製程水氣")
    if i.get("upw_quality_mode") == "自動參考值":
        disable(["upw_res"], "採用水型的初估電阻率參考")
    for j in (1, 2, 3):
        if i.get(f"gas{j}_pressure_mode") != "本路管內壓力":
            disable([f"gas{j}_barg"], "採用共用最低管內壓力")
        if i.get(f"gas{j}_v_mode") != "自訂流速":
            disable([f"gas{j}_velocity"], "採用氣體種類的流速參考")
    for panel in ["up", "np"]:
        if i.get(f"e_{panel}_pf_mode") != "本盤獨立 PF":
            disable([f"e_{panel}_pf"], "本盤採共用 PF，獨立值只保留為草稿")
        if i.get(f"e_{panel}_type") != "馬達負載":
            disable([f"e_{panel}_largest_hp"], "目前不是馬達群負載")
    return {k: reason for k, reason in off.items() if k in FIELDS}


WATER_ROWS = [
    ("mchw", "mchw_q", "u_mchw"), ("chw", "chw_q", "u_chw"),
    ("dccw", "dccw_q", "u_dccw"), ("pcw", "pcw_tot", "u_pcw_tot"),
    ("hw", "hw_q", "u_hw"),
]


def _usable(value, spec, fallback):
    """Keep valid inactive inventory values; tolerate malformed inactive drafts."""
    import math
    options = spec.get("options")
    low, high = spec.get("low"), spec.get("high")
    if "limit" in spec:
        limit = spec["limit"]
        if isinstance(limit, list):
            options = limit
        elif isinstance(limit, tuple):
            low, high = limit
        else:
            return value if str(value).strip() else fallback
    if options:
        return value if value in options else fallback
    if spec.get("text"):
        return value if str(value).strip() else fallback
    try:
        n = float(value)
        if math.isfinite(n) and (low is None or n >= low) and (high is None or n <= high):
            return value
    except (ValueError, TypeError):
        pass
    return fallback


def effective_main(i):
    out = dict(i)
    for k in main_inactive(i):
        out[k] = _usable(i[k], FIELDS[k], DEFAULTS[k])
    return out


def effective_pressure(config, is_water=True):
    c = dict(config)
    if not is_water or c.get("boundary") == "閉式循環":
        c["static_m"] = "0"
    if c.get("equipment_known") != "已知設備壓差":
        c["equipment_drop"] = "0"
    if c.get("estimate_mode") == "簡易估算":
        c.update(mode="Darcy 自動", fitting_mode="直接 K 值", sum_k="0")
        for k in ["elbows", "tees", "reducers", "valves", "elbow_ld", "tee_ld", "reducer_ld", "valve_ld", "rate"]:
            c[k] = PD_DEFAULTS[k]
    else:
        c["allowance_pct"] = PD_DEFAULTS["allowance_pct"]
        if c.get("mode") != "手動阻力率":
            c["rate"] = PD_DEFAULTS["rate"]
        if c.get("fitting_mode") == "直接 K 值":
            for k in ["elbows", "tees", "reducers", "valves", "elbow_ld", "tee_ld", "reducer_ld", "valve_ld"]:
                c[k] = PD_DEFAULTS[k]
        else:
            c["sum_k"] = "0"
    return c


def ahu_inactive(i):
    off = {}
    def disable(keys, reason):
        off.update({k: reason for k in keys})

    seasonal = i.get("target_mode") == "主案分季需求"
    if seasonal:
        disable(["sa_t", "sa_rh", "flow", "flow_basis"], "使用分季目標與各季送風狀態實際風量")
    else:
        disable([s + suffix for s in ["summer", "winter"] for suffix in ["_sa_t", "_sa_rh", "_flow"]], "使用共用送風目標")
    disable(["linked_main_hash"], "來源快照識別，不能手動修改")
    if i.get("summer_c1_mode") != "自動需求":
        disable(["c1_t"], "分季指定／旁通優先，此為自動模式備用目標")
    for season in ["summer", "winter"]:
        for tag in ["h1", "c1", "c2", "h2"]:
            prefix = season + "_" + tag
            mode = i.get(prefix + "_mode", "")
            if not mode.startswith("指定"):
                disable([prefix + "_t"], "出口由自動需求或旁通決定")
            if tag.startswith("c") and mode != "指定出口 T/RH":
                disable([prefix + "_rh"], "濕度由盤管物理過程決定")
    steam = "蒸汽" in i.get("humidifier", "")
    if not steam:
        disable([k for k in i if k.startswith("steam_")], "目前未使用蒸汽加濕")
    elif "電極" not in i.get("humidifier", ""):
        disable(["steam_conductivity", "steam_cond_min", "steam_cond_max"], "目前不是電極式蒸汽")
    if "水洗" not in i.get("humidifier", ""):
        disable(["wash_mode", "wash_eff", "wash_rating", "media_area", "wetting_rate", "drift_lph", "spray_head", "spray_rise", "loop_loss", "pump_input_kw"], "目前未採用水洗加濕，設備記錄保留")
    any_common_water = False
    for tag in ["h1", "h2"]:
        if i.get(tag + "_source") not in ["電熱", "熱水＋電熱"]:
            disable([tag + "_kw", tag + "_eta"], "本段不採用直接電熱，配置資料保留")
        water = i.get(tag + "_source") in ["回收熱水", "熱水＋電熱"] and i.get("recovery", "").startswith("二期")
        if not water:
            disable([tag + "_hw_kw", tag + "_water_mode"], "本段目前不採用熱回收水")
        custom = water and i.get(tag + "_water_mode") == "本段獨立設定"
        if not custom:
            disable([tag + "_hw_" + k for k in ["in", "out", "approach"]], "本段不採用獨立熱水條件")
        any_common_water |= water and not custom
    if not any_common_water:
        disable(["hw_in", "hw_out", "hw_approach"], "沒有啟用共用回收熱水的段落")
    return {k: v for k, v in off.items() if k in NM_FIELDS}


def effective_ahu(i):
    out = dict(i)
    for k in ahu_inactive(i):
        fallback = NM_DEFAULTS[k]
        if k.endswith("_kw"):
            fallback = "0"
        out[k] = _usable(i[k], NM_FIELDS[k], fallback)
    return out


def error_text(error, fields=FIELDS):
    key = getattr(error, "field_name", None)
    label = fields.get(key, {}).get("label", key or "設計條件")
    return f"{label}：{error}"
