import math

from .utils import dewpoint, state_trh


# Overall status of an assessment, worst first. Item statuses are "通過", "待資料", "待後續" and "未達".
#   未達      the design does not meet a condition
#   待資料    the user can supply the missing data in this tool
#   待後續    needs vendor data or a later design stage; no input of this tool can clear it
STATUS_FAIL = "未達條件"
STATUS_PENDING = "待補資料"
STATUS_DEFERRED = "初估完成（待後續階段確認）"
STATUS_PASS = "初估檢核通過"


def finding(items, name, status, detail, field=None):
    items.append(dict(name=name, status=status, detail=detail, field=field))


def assessment(items):
    state = (
        STATUS_FAIL
        if any((x["status"] == "未達" for x in items))
        else (
            STATUS_PENDING
            if any((x["status"] == "待資料" for x in items))
            else (STATUS_DEFERRED if any((x["status"] == "待後續" for x in items)) else STATUS_PASS)
        )
    )
    return dict(
        status=state,
        items=items,
        failed=sum((x["status"] == "未達" for x in items)),
        pending=sum((x["status"] == "待資料" for x in items)),
        deferred=sum((x["status"] == "待後續" for x in items)),
    )


def _coil_pinch_and_enthalpy_ok(c, tin_w, tout_w, p_kpa, pinch_min=0.5):
    """Check counterflow dry, fully-wet, and partially-wet coil pinch & saturation enthalpy."""
    ta_in = c["inlet"]["t"]
    ta_out = c["outlet"]["t"]
    dt_cold = ta_out - tin_w
    dt_hot = ta_in - tout_w
    if dt_cold < pinch_min - 1e-6 or dt_hot < pinch_min - 1e-6:
        return False
    if c.get("condensate_kg_s", 0.0) > 1e-9:
        h_sat_in = state_trh(tin_w, 100, p_kpa)["h"]
        if c["outlet"]["h"] <= h_sat_in + 1e-6:
            return False
        tdp_in = dewpoint(c["inlet"]["w"], p_kpa)
        if tout_w < tdp_in - 1e-6:
            # Fully wet coil: water outlet is below inlet air dewpoint
            h_sat_out = state_trh(tout_w, 100, p_kpa)["h"]
            if c["inlet"]["h"] <= h_sat_out + 1e-6:
                return False
        else:
            # Partially wet coil: dry sensible cooling from ta_in to tdp_in, wet below tdp_in
            dh_total = max(1e-9, c["inlet"]["h"] - c["outlet"]["h"])
            cp_in = 1.006 + 1.86 * c["inlet"]["w"]
            dh_dry = max(0.0, min(dh_total, cp_in * max(0.0, ta_in - tdp_in)))
            f_dry = dh_dry / dh_total
            tw_wet_boundary = tout_w - f_dry * (tout_w - tin_w)
            if tdp_in - tw_wet_boundary < pinch_min - 1e-6:
                return False
            h_air_boundary = c["inlet"]["h"] - dh_dry
            h_sat_boundary = state_trh(tw_wet_boundary, 100, p_kpa)["h"]
            if h_air_boundary <= h_sat_boundary + 1e-6:
                return False
    return True


def _coil_capacity_basis(items, r):
    """A dehumidifying coil solved without a BF floor has no verified row capacity."""
    for season, title in (("summer", "夏季"), ("winter", "冬季")):
        chain = r.get(season)
        for tag in ("c1", "c2"):
            c = chain.get(tag) if isinstance(chain, dict) else None
            if c and "bf_min" in c and c["bf_min"] <= 0 and c.get("air_kw", 0) > 1e-08:
                finding(
                    items,
                    title + " " + c["name"] + " 排數能力",
                    "待資料",
                    "未提供盤管 BF 下限（廠商性能或專案依據）；除濕可達性只依供水 ADP 檢核，未驗證盤管排數能力。",
                )


def _airflow_basis(items, r):
    """Judge a load-driven supply airflow by its inflation over the baseline, never by a fixed air-change rate.

    The baseline is the larger of the circulation / fresh-air floor and the sensible design airflow, so a
    cleanroom that circulates a lot is judged against what it already moves. Systems without this search
    (MAU: outdoor-air mass flow from a closed-form balance, FFU circulation counted separately) are skipped.
    """
    b = r.get("airflow_basis")
    if not b or not b.get("applicable") or not b.get("load_driven"):
        return
    v_da = r["room"]["v_da"]
    cmh = lambda kg_s: kg_s * v_da * 3600
    lim = b["limits"]
    name = "供風量合理性"
    facts = (
        f"供風量由{b['governing']}決定：基準 {cmh(b['m_start_kg_s']):,.0f} CMH 增為 {b['inflation']:.1f} 倍"
        f"（供風溫差 {b['supply_dt_k']:.2f} K）；室內露點 {b['room_dewpoint_c']:.2f}°C 與冰水 ADP {b['adp_floor_c']:.2f}°C 僅差 {b['dehumid_margin_k']:.2f} K"
    )
    remedy = ""
    if b.get("chw_needed_c") is not None:
        needed = math.floor(b["chw_needed_c"] * 100) / 100  # round down: the advice must land on the passing side
        remedy = f"；請將冰水供水降至 {needed:.2f}°C 以下（目前 {b['chw_supply_c']:.2f}°C）、提高室內相對濕度目標，或改用乾盤管／再熱"
    if b["inflation"] > lim["inflation_fail"] + 1e-9:
        finding(items, name, "未達",
                facts + f"，超過可行倍數 {lim['inflation_fail']:g}（供風溫差實務下限 {lim['min_supply_dt_k']:g} K）" + remedy, "chw2_in")
    elif b.get("condition_number") and b["condition_number"] > lim["condition_fail"]:
        finding(items, name, "未達",
                f"除濕裕度過小，風量對輸入極敏感（條件數 {b['condition_number']:.0f}，上限 {lim['condition_fail']:g}）" + remedy, "chw2_in")
    else:
        finding(items, name, "通過", facts + f"，未超過可行倍數 {lim['inflation_fail']:g}。", "chw2_in")


def assess_main(r):
    i = r.get("effective_inputs", r["project"]["inputs"])
    f = lambda k: float(i[k])
    p_kpa = f("atm_kpa")
    pinch_min = float(i.get("coil_pinch_min_k", "0.5"))
    items = []
    dcc_kw = r.get("dcc_design_kw", r["dcc_kw"])
    if dcc_kw > 1e-08:
        flow = (
            r.get("dcc_design_cmh", r.get("dcc_cmh", r["circulation_cmh"]))
            if i["dcc_airflow_mode"] == "沿用 FFU 循環"
            else f("dcc_airflow_cmh")
        )
        tw = f("dccw_in")
        tin = r["room"]["t"]
        md = flow / 3600 / r["room"]["v_da"]
        cp = 1.006 + 1.86 * r["room"]["w"]
        outlet = tin - dcc_kw / (md * cp) if md > 0 else None
        limit = max(0, md) * cp * max(0, tin - tw - f("dcc_air_approach"))
        r["dcc_airside"] = dict(
            flow_cmh=flow,
            inlet_c=tin,
            required_outlet_c=outlet,
            max_with_approach_kw=limit,
            water_in_c=tw,
            design_season=r.get("dcc_design_season", "summer"),
        )
        finding(
            items,
            "DCC 冷卻溫差",
            "通過" if tw < tin else "未達",
            f"入風 {tin:g}°C；供水 {tw:g}°C，供水必須低於入風。",
            "dccw_in",
        )
        finding(
            items,
            "DCC 循環風量與能力",
            "通過" if flow > 0 and dcc_kw <= limit + 1e-06 else "未達",
            f"採 {flow:,.0f} CMH；按最小端差的空氣側上限 {limit:.2f} kW，需求 {dcc_kw:.2f} kW。仍需原廠同工況性能。",
            "dcc_airflow_mode",
        )
        finding(
            items,
            "DCC 回水必要條件",
            "通過" if tw + f("dt_dccw") < tin else "未達",
            f"供／回水 {tw:g}/{tw + f('dt_dccw'):g}°C，回水須低於 {tin:g}°C 入風。",
            "dt_dccw",
        )
    for season in ["summer", "winter"]:
        for tag, water, delta in [
            ("c1", "chw1_in", "chw1_dt"),
            ("c2", "chw2_in", "dt_chw"),
        ]:
            c = r[season][tag]
            if c["air_kw"] <= 1e-08:
                continue
            tin_w = f(water)
            tout = tin_w + f(delta)
            ta = c["inlet"]["t"]
            valid = tout < ta and _coil_pinch_and_enthalpy_ok(c, tin_w, tout, p_kpa, pinch_min)
            finding(
                items,
                ("夏季" if season == "summer" else "冬季")
                + c["name"]
                + " 回水必要條件",
                "通過" if valid else "未達",
                f"回水 {tout:g}°C；入口空氣 {ta:.2f}°C。水量公式成立仍須滿足換熱溫差。",
                delta,
            )
    for key, w in r["water"].items():
        if not w["linked"] and w["capacity_kw"] + 1e-06 < w["load_kw"]:
            finding(
                items,
                key + " 獨立水量",
                "未達",
                f"水量可承擔 {w['capacity_kw']:.2f} kW，需求 {w['load_kw']:.2f} kW。",
                key.lower() + "_link",
            )
    for key, d in r["pressure"].items():
        if d["flow_m3s"] and (not d["equipment_included"]):
            finding(
                items,
                key + " 設備阻力",
                "待資料",
                "僅列管路小計；詳細與簡易模式皆未將未知阻力當成零。",
                "PD:" + key,
            )
    if i["latent_mode"].startswith("尚不清楚"):
        finding(
            items,
            "製程產濕",
            "待資料",
            "目前只計人員產濕，需確認製程水氣。",
            "latent_mode",
        )
    if r["qs"] or r["ql"]:
        finding(
            items,
            "設備同工況選型",
            "待後續",
            "本工具計算需求，仍需盤管／末端原廠選型與實際風機曲線。",
        )
    if (r["qs"] > 1e-08 or r["ql"] > 1e-08) and r.get("electric") and r["electric"].get("NP", {}).get("kw", 0) <= 1e-08:
        finding(
            items,
            "NP 空調與附屬設備用電",
            "待資料",
            "空調與照明已有負荷需求，但 NP 盤為 0 kW；請填列或由單機帶入。",
            "e_np_fan",
        )
    if any((e["kw"] for e in r["electric"].values())):
        finding(
            items,
            "配電候選覆核",
            "待後續",
            "原表僅供初估；需敷設方式、短路、接地及馬達保護資料。",
        )
    if any((g["standard_lpm"] for g in r["gas"].values())):
        finding(
            items,
            "氣體供壓／真空性能",
            "待後續",
            "目前為流速截面初估，需管路壓降與幫浦／調壓器性能。",
        )
    for g in r["gas"].values():
        if g.get("standard_lpm", 0) > 0 and g.get("liquefaction_risk") is True:
            finding(
                items,
                "特氣相態與液化檢核",
                "待資料",
                "管內絕壓高於同溫飽和蒸氣壓，氣體將液化；請降低供壓或配置伴熱。",
                "gas_barg",
            )
    if r.get("winter_room") and r["winter_room"].get("mau_overtemp_warning"):
        wr = r["winter_room"]
        finding(
            items,
            "冬季 MAU 送風溫度上限",
            "未達" if wr.get("terminal_heat_kw", 0.0) > 1e-6 else "待資料",
            f"冬季所需送風溫度 {wr['unconstrained_supply_t']:.1f}°C 高於 MAU 送風上限 {wr['max_mau_t']:g}"
            f"°C，易致氣流分層；剩餘室內熱損 {wr['terminal_heat_kw']:.2f}"
            + (" kW 已計入 HW；仍須確認室內加熱設備。" if wr.get("terminal_heat_source") == "HW"
               else " kW 未配置熱源（待指定），未計入 HW 或 NP；請指定室內加熱設備與熱源，或增加循環風量。"),
            "winter_model",
        )
    if r["light"].get("room_index_k") is not None and 0 < r["light"]["room_index_k"] < 0.8 and r["light"]["u"] >= 0.6:
        finding(
            items,
            "照明室指數與利用係數",
            "待資料",
            "室指數偏小而手填利用係數偏高；請核對燈具配光表。",
            "light_u",
        )
    np_supplied = bool(r.get("electric")) and r["electric"].get("NP", {}).get("kw", 0) > 1e-08
    if (r["winter"]["reheat_kw"] or r["winter"]["humid_kg_h"]) and not (r.get("winter_room") and np_supplied):
        finding(
            items,
            "冬季室內與電力範圍",
            "待資料",
            (
                "依明列負荷完成穩態室內熱濕收支；NP 仍須實際設備電力。"
                if r.get("winter_room")
                else "冬季目前為外氣處理基準；需另核室內熱濕與 NP 設備電力。"
            ),
        )
    _coil_capacity_basis(items, r)
    _airflow_basis(items, r)
    return assessment(items)


def assess_ahu(r):
    i = r["inputs"]
    f = lambda k: float(i[k])
    p_kpa = f("p")
    pinch_min = float(i.get("coil_pinch_min_k", "0.5"))
    items = []
    for season, title in [("summer", "夏季"), ("winter", "冬季")]:
        s = r[season]
        for key, passed in s["checks"].items():
            state = "通過" if passed else "未達"
            if not passed and (
                "蒸汽產量額定" == key
                and (not f("steam_capacity"))
                or ("蒸汽電力額定" == key and (not f("steam_kw")))
                or "給水" in key
            ):
                state = "待資料"
            finding(
                items,
                title + " " + key,
                state,
                "依本季需求與已填資料檢核；表列狀態為需求點。",
            )
        for tag in ["c1", "c2"]:
            c = s[tag]
            if c["air_kw"] > 1e-08:
                tin_w = f(tag + "_in")
                tout_w = f(tag + "_out")
                valid = (
                    tout_w < c["inlet"]["t"]
                    and _coil_pinch_and_enthalpy_ok(c, tin_w, tout_w, p_kpa, pinch_min)
                )
                finding(
                    items,
                    title + " " + tag.upper() + " 回水必要條件",
                    "通過" if valid else "未達",
                    f"回水 {tout_w:g}°C；入口空氣 {c['inlet']['t']:.2f}°C。",
                    tag + "_out",
                )
    dpkeys = [k for k in i if k.startswith("dp_") and k != "dp_status"]
    missing = [k for k in dpkeys if not i[k].strip()]
    if missing or not r["pressure_complete"]:
        finding(
            items,
            "風機壓差完整度",
            "待資料",
            "尚缺同風量各段終阻力。留空代表未知，明確 0 代表已知無此阻力。",
            "dp_status",
        )
    zero_components = [
        k
        for k in ["dp_filter", "dp_hepa", "dp_c1", "dp_c2"]
        if i[k].strip() and float(i[k]) <= 0
    ]
    if zero_components:
        r["pressure_complete"] = False
        finding(
            items,
            "已配置元件阻力",
            "待資料",
            "濾網、HEPA、盤管仍為 0；現有拓樸配置了這些元件，需提供阻力或改設計。",
            "dp_status",
        )
    if r["pressure_complete"]:
        finding(
            items,
            "EC 風機電力",
            "通過" if r["fan_capacity_pass"] else "未達",
            f"所需 {r['fan_required_kw']:.2f} kW；配置 {r['fan_installed_kw']:.2f} kW。尚須曲線運轉點。",
            "fan_unit_kw",
        )
    elif not r["fan_capacity_pass"]:
        finding(
            items,
            "EC 風機電力",
            "未達",
            f"僅目前已知阻力就需 {r['fan_required_kw']:.2f} kW，已超出配置 {r['fan_installed_kw']:.2f} kW。",
            "fan_unit_kw",
        )
    if f("fan_air_kw") > r["fan_installed_kw"] + 1e-08:
        finding(
            items,
            "風機入氣流熱",
            "未達",
            f"入氣流熱 {f('fan_air_kw'):g} kW 大於配置電力 {r['fan_installed_kw']:g} kW。",
            "fan_air_kw",
        )
    elif not f("fan_air_kw"):
        finding(
            items,
            "風機入氣流熱",
            "待資料",
            "目前採 0 kW 試算；需實際運轉電力、馬達位置及入氣流熱。",
            "fan_air_kw",
        )
    if "水洗" in i["humidifier"]:
        if r["circulation_lpm"] is None:
            finding(
                items,
                "水洗循環水量",
                "待資料",
                "需有效淋水面積與原廠淋水密度。",
                "media_area",
            )
        if r["pump_head_m"] is None:
            finding(
                items,
                "水洗循環泵揚程",
                "待資料",
                "需噴頭水頭、高差與管路損失；可填合法的 0m 高差。",
                "spray_rise",
            )
    finding(
        items,
        "原廠同工況性能",
        "待資料",
        "名目 RT／kW 與必要條件檢核不能替代同工況盤管、風機與加濕設備性能。",
    )
    _coil_capacity_basis(items, r)
    return assessment(items)
