def finding(items, name, status, detail, field=None):
    items.append(dict(name=name, status=status, detail=detail, field=field))


def assessment(items):
    state = (
        "未達條件"
        if any((x["status"] == "未達" for x in items))
        else (
            "待補資料"
            if any((x["status"] == "待資料" for x in items))
            else "初估檢核通過"
        )
    )
    return dict(
        status=state,
        items=items,
        failed=sum((x["status"] == "未達" for x in items)),
        pending=sum((x["status"] == "待資料" for x in items)),
    )


def assess_main(r):
    i = r.get("effective_inputs", r["project"]["inputs"])
    f = lambda k: float(i[k])
    items = []
    dcc_kw = r.get("dcc_design_kw", r["dcc_kw"])
    if dcc_kw > 1e-08:
        flow = (
            r["circulation_cmh"]
            if i["dcc_airflow_mode"] == "沿用 FFU 循環"
            else f("dcc_airflow_cmh")
        )
        tw = f("dccw_in")
        tin = r["room"]["t"]
        md = flow / 3600 / r["room"]["v_da"]
        cp = 1.006 + 1.86 * r["room"]["w"]
        outlet = tin - dcc_kw / (md * cp) if md else None
        limit = md * cp * max(0, tin - tw - f("dcc_air_approach"))
        r["dcc_airside"] = dict(
            flow_cmh=flow,
            inlet_c=tin,
            required_outlet_c=outlet,
            max_with_approach_kw=limit,
            water_in_c=tw,
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
            tout = f(water) + f(delta)
            ta = c["inlet"]["t"]
            finding(
                items,
                ("夏季" if season == "summer" else "冬季")
                + c["name"]
                + " 回水必要條件",
                "通過" if tout < ta else "未達",
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
            "待資料",
            "本工具計算需求，仍需盤管／末端原廠選型與實際風機曲線。",
        )
    if any((e["kw"] for e in r["electric"].values())):
        finding(
            items,
            "配電候選覆核",
            "待資料",
            "原表僅供初估；需敷設方式、短路、接地及馬達保護資料。",
        )
    if any((g["standard_lpm"] for g in r["gas"].values())):
        finding(
            items,
            "氣體供壓／真空性能",
            "待資料",
            "目前為流速截面初估，需管路壓降與幫浦／調壓器性能。",
        )
    if r["winter"]["reheat_kw"] or r["winter"]["humid_kg_h"]:
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
    return assessment(items)


def assess_ahu(r):
    i = r["inputs"]
    f = lambda k: float(i[k])
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
                valid = f(tag + "_out") < c["inlet"]["t"]
                finding(
                    items,
                    title + " " + tag.upper() + " 回水必要條件",
                    "通過" if valid else "未達",
                    f"回水 {f(tag + '_out'):g}°C；入口空氣 {c['inlet']['t']:.2f}°C。",
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
    return assessment(items)
