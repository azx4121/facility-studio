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
        # Normalised like the outlets: a returned "7" must not differ from the main "7.0",
        # or the boundary hash changes and every later return is refused as stale.
        "c1_in": str(float(i["chw1_in"])),
        "c1_out": str(float(i["chw1_in"]) + float(i["chw1_dt"])),
        "c2_in": str(float(i["chw2_in"])),
        "c2_out": str(float(i["chw2_in"]) + float(i["dt_chw"])),
    }
    if i["pre_mode"] == "單盤管（一般空調箱）":
        updates.update(summer_c1_mode="旁通", winter_c1_mode="旁通")
    else:
        updates.update(summer_c1_mode="旁通" if i["pre_mode"] == "停用／旁通" else "自動需求",
                       winter_c1_mode="旁通")
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


def ahu_utility_preview(ahu_result, main_inputs=None):
    from .engine import water_properties
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
        # Retain the AHU source's own water properties (1000 / 4.1868 / 0.001) without silent recalculation;
        # warn explicitly if the destination main project uses different fluid properties.
        if isinstance(main_inputs, dict):
            dest_fluid = water_properties(main_inputs, key)
            if abs(dest_fluid["rho"] - 1000.0) > 1e-6 or abs(dest_fluid["cp"] - 4.1868) > 1e-6:
                notes.append(f"{key.upper()} 主案流體物性與單機清水基準不同；保留單機來源物性並標示，不靜默重算。")
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
            "水側採清水 1000 kg/m³、4.1868 kJ/(kg·K)、黏度 0.001 Pa·s 初估；只設定本箱對應 MCHW／CHW 及採用的 HW 迴路。",
            "電力採已填額定值，不是由冷量直接換成耗電；仍需確認 PF、同時使用及馬達保護。",
            "空調箱與主案保留各自計算邊界；回傳水量後需重新確認主案服務範圍。",
        ]
    )
    for loop in ["mchw", "chw"] + (["hw"] if "hw_q" in updates else []):
        updates.update({
            loop + "_fluid_mode": "本迴路獨立物性",
            loop + "_fluid_name": "清水（空調箱初估）",
            loop + "_rho": "1000", loop + "_cp": "4.1868", loop + "_mu": "0.001",
        })
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


def capacity_source_binding(workspace):
    """Fingerprint the live engineering sources, not unrelated A/B navigation."""
    return dict(project_id=workspace["project_id"], fingerprint=project_hash({
        key: workspace[key] for key in ("project_id", "main", "ahus", "demand_ledger")
    }))


def capacity_plan_from_ledger(workspace):
    """Copy ledger sources exactly once, without adding the already-adopted main totals.

    This is deliberately a partial register, not a silent whole-plant total.
    Unspecified frequency, fluids and exhaust rating conditions remain unknown.
    """
    from .contributions import validate_ledger, circuit_id
    from .capacity_planning import new_plan, new_row, validate_plan

    ledger = validate_ledger(workspace["demand_ledger"])
    p = new_plan(workspace["main"]["inputs"]["project_name"] + "｜容量與擴建")
    p["binding"] = capacity_source_binding(workspace)
    p["scope"] = "僅已帶入需求彙整的電力／CHW／PCW／排氣來源；未加主案已含來源的總量。其他既有負荷、基數及供應容量須另核對。"
    docs = {d["id"]: d for d in workspace["ahus"]}
    for entry in ledger["entries"].values():
        rows = []
        def row_id(suffix):
            return "ledger-" + project_hash([entry["id"], suffix])[:40]
        for panel, power in entry["power"].items():
            row = new_row("demand", row_id(panel))
            row.update(name=entry["name"][:100], boundary=panel,
                       conditions=dict(voltage_v=power["voltage"], phases=3, frequency_hz=None),
                       values={c: power["kw"] for c in p["cases"]})
            row["notes"].append("取來源運轉有功 kW，不重加設計電流或熱負荷；季節分配未提供，暫在兩工況保留相同值。")
            row["pending"].append("電力頻率、季節同時率及 kW 容量額定條件須覆核；不由 kVA 直接視為 kW。")
            rows.append(row)
        for water in entry["water"]:
            if water["loop"] not in ("CHW", "PCW"):
                continue
            row = new_row("demand", row_id(circuit_id(water)), water["loop"])
            row.update(name=entry["name"][:100], boundary=water["circuit"],
                       conditions=dict(fluid=None, supply_c=water["supply"], return_c=water["return"],
                                       rho_kg_m3=water["rho"], cp_kj_kgk=water["cp"]),
                       values={c: water[c + "_lpm"] for c in p["cases"]}, included_margin_pct=None)
            row["pending"].append("來源含自身裕度及同時率，保留已計算水量；介質名稱、原始裕度及實際工況待核對。")
            rows.append(row)
        for prefix in ("gex", "sex", "aex", "vex", "hex"):
            key = prefix + "_q"
            if key not in entry["updates"]:
                continue
            if entry["updates"].get("u_" + prefix) != "CMH":
                raise ValidationError("容量來源排氣需明列 CMH 單位，不能猜測換算")
            try:
                flow = float(entry["updates"][key])
            except (ValueError, TypeError):
                raise ValidationError("容量來源排氣數值無法解讀；請先修正需求彙整來源") from None
            row = new_row("demand", row_id(prefix), "EXHAUST")
            row.update(name=entry["name"][:100], boundary=prefix.upper(),
                       conditions=dict(exhaust_type=prefix.upper(), temperature_c=None, absolute_kpa=None, required_static_pa=None),
                       values={c: flow for c in p["cases"]})
            row["pending"].append("排氣 CMH 的實際溫壓、同時工況及需求靜壓待核對；不同排氣類別不得混合。")
            rows.append(row)
        for row in rows:
            row["source"] = dict(reference="需求彙整：" + entry["name"][:990], revision=entry["source_hash"], fingerprint=project_hash(entry))
            row["notes"].extend(entry["notes"])
            row["pending"].extend(entry["pending"])
            if entry["kind"] == "AHU" and (entry["id"] not in docs or ahu_source_hash(docs[entry["id"]]["inputs"]) != entry["source_hash"]):
                row["pending"].append("空調箱來源已變更或缺少原始資料；先重新計算並帶入來源，不能沿用舊數值。")
        p["demands"].extend(rows)
    return validate_plan(p)
