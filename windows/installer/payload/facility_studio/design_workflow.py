"""Explicit previews for links and comparisons: no hidden additive load updates."""

import copy
from .utils import project_hash, US_RT_KW
from .schema import FIELDS
from .errors import ValidationError


def ahu_requirement_updates(main_result):
    r = main_result
    i = r.get("effective_inputs", r["project"]["inputs"])
    if not i["sys_type"].startswith("MAU"):
        raise ValidationError(
            "分段空調箱主案連動目前限全外氣 MAU；混風 AHU 的回風路徑不能當成全外氣箱。",
            "sys_type",
        )
    updates = {
        "p": i["atm_kpa"],
        "target_mode": "主案分季需求",
        "c1_in": i["chw1_in"],
        "c1_out": str(float(i["chw1_in"]) + float(i["chw1_dt"])),
        "c2_in": i["chw2_in"],
        "c2_out": str(float(i["chw2_in"]) + float(i["dt_chw"])),
    }
    for season in ["summer", "winter"]:
        ch = r[season]
        sa = ch["supply"]
        enter = ch["enter"]
        updates.update(
            {
                season + "_t": str(enter["t"]),
                season + "_rh": str(enter["rh"]),
                season + "_sa_t": str(sa["t"]),
                season + "_sa_rh": str(sa["rh"]),
                season + "_flow": str(ch["mass"] * sa["v_da"] * 3600),
            }
        )
    updates["linked_main_hash"] = project_hash(updates)
    return updates


def ahu_source_hash(inputs):
    from .field_state import effective_ahu, ahu_inactive

    effective = effective_ahu(inputs)
    inactive = ahu_inactive(inputs)
    return project_hash({k: v for k, v in effective.items()
                         if k not in inactive and k not in ["name", "linked_main_hash"]})


def ahu_utility_preview(ahu_result):
    r = ahu_result
    i = r["inputs"]
    updates = {}
    notes = []
    for tag, key, flowkey, unitkey, dtkey in [
        ("c1", "mchw", "mchw_q", "u_mchw", "chw1_dt"),
        ("c2", "chw", "chw_q", "u_chw", "dt_chw"),
    ]:
        dt = float(i[tag + "_out"]) - float(i[tag + "_in"])
        kw = max(r[s][tag]["water_kw"] for s in ["summer", "winter"]) * (
            1 + float(i["sf"]) / 100
        )
        updates.update(
            {
                flowkey: str(kw * 60000 / (1000 * 4.1868 * dt)),
                unitkey: "LPM",
                key + "_link": "獨立輸入",
                dtkey: str(dt),
                "chw1_in" if tag == "c1" else "chw2_in": i[tag + "_in"],
            }
        )
    fan = float(i["fan_qty"]) * float(i["fan_unit_kw"])
    heat = sum(
        float(i[t + "_kw"])
        for t in ["h1", "h2"]
        if i[t + "_source"] in ["電熱", "熱水＋電熱"]
    )
    steam = float(i["steam_kw"]) if "蒸汽" in i["humidifier"] else 0.0
    if "蒸汽" in i["humidifier"] and steam <= 0:
        raise ValidationError("蒸汽設備電力未知，不能回傳成零負荷", "steam_kw")
    for key, value in [("fan", fan), ("heat", heat), ("humid", steam)]:
        updates["e_np_" + key] = str(value)
        updates["u_e_np_" + key] = "kW"
    if "水洗" in i["humidifier"] and i["pump_input_kw"].strip():
        updates.update(e_np_pump=i["pump_input_kw"], u_e_np_pump="kW")
    elif "水洗" in i["humidifier"]:
        notes.append("水洗泵電力未知：主案 NP 水泵值維持不變，仍需補確認。")
    heater_waters = [
        r[s][t]["effective_water"]
        for s in ["summer", "winter"]
        for t in ["h1", "h2"]
        if r[s][t]["hw_kw"] > 1e-8
    ]
    if heater_waters:
        pairs = {(x["hw_in"], x["hw_out"]) for x in heater_waters}
        if len(pairs) == 1:
            tin, tout = next(iter(pairs))
            flow = max(
                sum(r[s][t]["water_lpm"] for t in ["h1", "h2"])
                for s in ["summer", "winter"]
            ) * (1 + float(i["sf"]) / 100)
            updates.update(
                hw_q=str(flow), u_hw="LPM", dt_hw=str(tin - tout), hw_link="獨立輸入"
            )
        else:
            notes.append(
                "H1/H2 熱水供回水條件不同：不合併成單一 HW，主案 HW 保持原值。"
            )
    else:
        notes.append("本空調箱未採用回收熱水；主案 HW 保持原值，避免清除其他服務負荷。")
    notes.extend(
        [
            "回傳值為取代所列欄位，不是疊加；其他廠務設備須另列。",
            "水側採純水 1000 kg/m³、4.1868 kJ/(kg·K)、黏度 0.001 Pa·s 初估；回傳會影響主案全部水迴路，應確認水溫與水質。",
            "電力採已填額定值，不是由冷量直接換成耗電；仍需確認 PF、同時使用及馬達保護。",
            "空調箱與主案保留各自計算邊界；回傳水量後需重新確認主案服務範圍。",
        ]
    )
    updates.update(water_rho="1000", water_cp="4.1868", water_mu="0.001")
    return dict(updates=updates, notes=notes, quality=r["quality"]["status"])


def compare_results(a, b):
    metrics = {
        "室內顯熱 kW": lambda r: r["qs"],
        "室內產濕 kg/h": lambda r: r["moisture"] * 3600,
        "外氣 CMH（室內基準）": lambda r: r["oa_room_cmh"],
        "處理風量 CMH（室內基準）": lambda r: r["supply_room_cmh"],
        "夏季水側冷量 kW": lambda r: sum(
            r["summer"][k]["water_kw"] for k in ["c1", "c2"]
        ),
        "DCC 設計需求 kW": lambda r: r.get("dcc_design_kw", r["dcc_kw"]),
        "冬季加熱 kW": lambda r: r["winter"]["reheat_kw"],
        "冬季加濕 kg/h": lambda r: r["winter"]["humid_kg_h"],
        "NP 運轉電流 A": lambda r: r["electric"]["NP"]["current_a"],
    }
    rows = [
        dict(name=name, a=fn(a), b=fn(b), delta=fn(b) - fn(a))
        for name, fn in metrics.items()
    ]
    changes = []
    for k in FIELDS:
        av = a["project"]["inputs"][k]
        bv = b["project"]["inputs"][k]
        if av != bv:
            changes.append(dict(field=k, name=FIELDS[k]["label"], a=av, b=bv))
    for system, config in a["project"]["pressure_drop"].items():
        for k, av in config.items():
            bv = b["project"]["pressure_drop"][system][k]
            if av != bv:
                changes.append(
                    dict(
                        field="PD:" + system + ":" + k,
                        name=system + " " + k,
                        a=av,
                        b=bv,
                    )
                )
    return dict(
        metrics=rows,
        changes=changes,
        status_a=a["quality"]["status"],
        status_b=b["quality"]["status"],
        hash_a=a["hash"],
        hash_b=b["hash"],
    )
