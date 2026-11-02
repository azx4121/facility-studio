"""Explicit plant electrical boundary; never equates shaft/thermal kW to input."""
from .utils import US_RT_KW


def equipment_inputs(i, pressure, ffu_count, summer, winter, cooling_design_kw):
    n = lambda key, default="0": float(i.get(key, default))
    eta = n("motor_input_efficiency", ".9")
    pending = []
    fan = n("main_fan_input_kw")
    if fan <= 0:
        pending.append("本案 MAU／AHU 風機電氣輸入尚未提供，已知小計不代表完整 NP。")
    ffu = ffu_count * n("ffu_input_w") / 1000
    if ffu_count and n("ffu_input_w") <= 0:
        pending.append("FFU 電氣輸入未知；入室發熱不能直接當成設備輸入功率。")
    pump = sum(p["shaft_kw"] / eta for key, p in pressure.items() if key in ("MCHW", "CHW", "DCCW", "PCW", "HW"))
    exhaust = sum(p["shaft_kw"] / eta for key, p in pressure.items() if key not in ("MCHW", "CHW", "DCCW", "PCW", "HW"))
    heat = max(summer["reheat_kw"], winter["reheat_kw"])
    heat_input = heat / n("main_reheat_efficiency", "1") if i.get("main_reheat_source") == "電熱" else 0.
    if heat > 1e-8 and i.get("main_reheat_source", "未確認") == "未確認":
        pending.append("再熱熱源未確認，未將熱量直接當電力。")
    humid = n("main_humidifier_input_kw")
    if max(summer["humid_kg_h"], winter["humid_kg_h"]) > 1e-8 and humid <= 0:
        pending.append("本案加濕器輸入功率未知，未將空氣側加濕熱量直接當電力。")
    chiller = 0.
    if i.get("chiller_power_scope") == "本案冰機列NP":
        chiller = cooling_design_kw / US_RT_KW * n("chiller_input_kw_rt")
        if cooling_design_kw > 0 and n("chiller_input_kw_rt") <= 0:
            pending.append("冰機列入 NP，但整機 kW/RT 尚未提供。")
    for key, p in pressure.items():
        if p["flow_m3s"] > 0 and not p["equipment_included"]:
            pending.append(key + " 設備阻力未知，泵／風機輸入僅管路小計。")
    parts = dict(fan=fan + ffu + chiller, heat=heat_input, humid=humid, exh=exhaust, pump=pump)
    return dict(parts=parts, total_kw=sum(parts.values()), pending=pending,
                boundary="只加本案設備；手填 NP 為額外負荷。衍生設備採125%連續負載初估，不代表保護協調認證。")
