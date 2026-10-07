from .i18n import localized_report, verbatim
from .engine import pv_to_torr
from .schema import VERSION
from .utils import US_RT_KW, dewpoint


@localized_report
def report(r):
    i = dict(r["project"]["inputs"])
    from .schema import DEFAULTS

    i["project_name"] = verbatim(i["project_name"], DEFAULTS["project_name"])
    i.update({k: r["effective_inputs"][k] for k in r.get("inactive_fields", {})})
    lines = []
    a = lines.append
    sf = r["sf"]
    s = r["summer"]
    w = r["winter"]
    a(i["project_name"] + "｜設計條件與計算摘要")
    a("系統：" + i["sys_type"] + "｜V" + VERSION + "｜需求初估")
    a(
        "整體狀態："
        + r["quality"]["status"]
        + "；設備台數為需求候選，未達條件不可直接選用。"
    )
    for q in r["quality"]["items"]:
        if q["status"] != "通過":
            a("[" + q["status"] + "] " + q["name"] + "：" + q["detail"])
    for rec in r.get("source_receipts", []):
        if rec["status"] != "已由手動或其他來源取代":
            a(
                "來源："
                + verbatim(rec["source_name"])
                + "；帶入 "
                + rec["captured_at"]
                + "；"
                + rec["status"]
            )
    a("\n一、設計條件")
    demand = r.get("demand_summary")
    if demand and demand["sources"]:
        a("已納入需求來源：" + "；".join(verbatim(x["name"]) for x in demand["sources"]))
        a("水量彙整：同迴路夏／冬各自求和，設計=max(Σ夏季LPM, Σ冬季LPM)；不同供回水／介質／群組分列。")
        for group in demand["water"]:
            a(f"{group['loop']} {verbatim(group['circuit'])} {group['supply']:g}/{group['return']:g}°C：夏 {group['summer_lpm']:.2f}，冬 {group['winter_lpm']:.2f}，設計 {group['design_lpm']:.2f} LPM；" + ("主案採用" if group["adopted"] else "獨立迴路，未映射主案水力列"))
    a(
        f"大氣壓 {i['atm_kpa']} kPa；夏季 {i['oa_t']}°C / {i['oa_rh']}%RH；冬季 {i['ow_t']}°C / {i['ow_rh']}%RH；室內 {i['ra_t']}°C / {i['ra_rh']}%RH（精確目標）。"
    )
    for z, d in r["zones"].items():
        a(
            f"{z} 區 {d['area']:.1f} m²、{d['volume']:.1f} m³；{i['mode_' + z]} 需求 {d['cmh']:.1f} CMH；潔淨紀錄 {i['c_' + z.lower()]}。"
        )
    a(
        f"補償外氣下限 {r['minimum_oa_cmh']:.2f} CMH；採用 {r['oa_room_cmh']:.2f} CMH；额外洩壓需求 {r['extra_relief_cmh']:.2f} CMH（均以室內狀態基準）。"
    )
    a(
        f"照明 {r['light']['qty']} 盞／{r['light']['kw']:.3f} kW；室內顯熱 {r['qs']:.3f} kW；潛熱參考 {r['ql']:.3f} kW；產濕 {r['moisture'] * 3600:.3f} kg/h。"
    )
    a(
        f"產濕來源：人員 {r['latent']['people_kg_h']:.3f}＋額外製程 {r['latent']['process_kg_h']:.3f} kg/h；製程方式：{i['latent_mode']}。外氣水氣由盤管另算，不重複加進室內。"
    )
    a("\n二、空調分工與狀態")
    a(
        f"一段供水 {i['chw1_in']}°C／ΔT {i['chw1_dt']} K；二段 {i['chw2_in']}°C／ΔT {i['dt_chw']} K；DCCW {i['dccw_in']}°C／ΔT {i['dt_dccw']} K；容量餘裕 {i['sf']}%。"
    )
    a(
        f"處理風量 {r['supply_room_cmh']:.2f} CMH（室內基準）；{('FFU 循環另計 ' + format(r['circulation_cmh'], '.2f') + ' CMH' if i['sys_type'].startswith('MAU') else '外氣於空調入口混合')}。"
    )
    a("點位             乾球°C    RH%       w(g/kg乾空氣)       h(kJ/kg乾空氣)")
    for title, state in [
        ("入口", s["enter"]),
        ("一段出口", s["c1"]["outlet"]),
        ("二段出口", s["c2"]["outlet"]),
        ("最終送風", s["supply"]),
        ("室內", r["room"]),
    ]:
        a(
            f"{title:<10} {state['t']:9.3f} {state['rh']:8.3f} {state['w'] * 1000:16.6f} {state['h']:18.6f}"
        )
    for c in [s["c1"], s["c2"]]:
        a(
            f"{c['name']}：空氣側 {c['air_kw']:.3f} kW；水側 {c['water_kw']:.3f} kW；含餘裕 {c['water_kw'] * sf / r['rt_kw']:.3f} RT；凝結水 {c['condensate_kg_s'] * 3600:.3f} kg/h。"
        )
    a(
        f"DCC 顯熱 {r['dcc_kw']:.3f} kW；夏季再熱 {s['reheat_kw']:.3f} kW；加濕 {s['humid_kg_h']:.3f} kg/h（空氣側 {s['humid_air_kw']:.3f} kW）。"
    )
    a(
        "設備初估："
        + (
            "；".join((f"{k} {v} 台" for k, v in r["counts"].items() if v))
            or "無設備需求"
        )
    )
    if r.get("winter_room"):
        wr = r["winter_room"]
        a(
            f"冬季室內熱濕平衡：顯熱 {wr['sensible_kw']:.3f} kW；送風 {w['supply']['t']:.3f}°C／{w['supply']['rh']:.3f}%RH；加熱 {w['reheat_kw']:.3f} kW、加濕 {w['humid_kg_h']:.3f} kg/h。"
        )
        a(
            f"DCC 夏冬較大需求 {r['dcc_design_kw']:.3f} kW；冬季為明列負荷的穩態估算，非逐時建築模擬。"
        )
    else:
        a(
            f"冬季外氣處理基準：同設計質量流量處理至室內 T/RH，未扣冬季室內得熱；加熱 {w['reheat_kw']:.3f} kW、加濕 {w['humid_kg_h']:.3f} kg/h。"
        )
    a("\n三、管路／流速／壓差")
    for k, d in r["water"].items():
        if d["lpm"]:
            a(
                f"{k}：{d['lpm']:.3f} LPM，ΔT {d['delta_t']:.2f} K，{d['runs']} 支×{d['size']}／ID {d['id_mm']:.1f} mm，{d['velocity_mps']:.3f} m/s；壓差 {r['pressure'][k]['total_pa']:.3f} Pa。"
            )
            fluid = d["fluid_properties"]
            a(f"  採用物性：ρ {fluid['rho']:g} kg/m³；cp {fluid['cp']:g} kJ/(kg·K)；μ {fluid['mu']:g} Pa·s；來源 {fluid['source']}。")
    for k, d in r["ducts"].items():
        if d["flow_cmh"]:
            dims = (
                f"{d['w_mm']}×{d['h_mm']} mm"
                if d["shape"] == "方管"
                else f"ID {d['diameter_m'] * 1000:.1f} mm"
            )
            a(
                f"{k}：{d['nominal_cmh']:.2f}→{d['flow_cmh']:.2f} CMH，{d['shape']} {dims}，{d['velocity_mps']:.3f} m/s；壓差 {r['pressure'][k]['total_pa']:.3f} Pa。"
            )
    for k, g in r["gas"].items():
        if g["standard_lpm"]:
            a(
                f"{g['type']}：{g['standard_lpm']:.2f} SLPM→{g['actual_lpm']:.2f} ALPM（{g['pressure_abs_pa'] / 1000:.3f} kPa abs），{g['size']}／ID {g['selected_id_mm']:.1f} mm；{g['velocity_mps']:.3f} m/s。"
            )
    for j in (1, 2, 3):
        g = r["gas"][str(j)]
        if g["standard_lpm"]:
            a(
                f"特氣 {j} 定寸：管內表壓 {(g['pressure_abs_pa'] / 1000 - float(i['atm_kpa'])) / 100:.3f} bar(g)，絕壓 {g['pressure_abs_pa'] / 1000:.3f} kPa；設計流速上限 {g['velocity_limit_mps']:.3f} m/s。"
            )
    a(f"PV 設計流速上限 {r['gas']['4']['velocity_limit_mps']:.3f} m/s。")
    a(
        f"氣體標準體積：{i['gas_std_t']}°C／{i['gas_std_kpa']} kPa；管內 {i['gas_temp']}°C，Z 比 {i['gas_z_ratio']}；僅流速初估。"
    )
    if float(i["pv_q"]):
        a(
            f"PV 壓力輸入：{i['pv_torr']} {i['pv_pressure_unit']}（絕壓）；等值 {pv_to_torr(i['pv_torr'], i['pv_pressure_unit']):.6f} Torr。"
        )
    if r["upw"]["lpm"]:
        a(
            f"{i['upw_type']}：{i['upw_q']} LPM，{i['upw_v_mode']} {i['upw_v']} m/s ⇒ ID {r['upw']['relation']} {r['upw']['id_mm']:.3f} mm；{i['upw_mat']}。"
        )
        a(
            f"水質規格紀錄：{r['upw']['resistivity']}，TOC {i['upw_toc']}，DO {i['upw_do']}，溫度 {i['upw_temp']}°C。"
        )
    simple = [
        f"{k} {d['allowance_pct']:g}%"
        for k, d in r["pressure"].items()
        if d["flow_m3s"] and d["estimate_mode"] == "簡易估算"
    ]
    if simple:
        a(
            "壓損簡易初估："
            + "、".join(simple)
            + " 管件等效長度餘裕；Δp＝直管摩擦×(1＋餘裕)＋已知設備壓差＋適用靜揚程。"
        )
    a("\n四、配電候選")
    a(
        f"{i['e_volt']}；PF {i['e_pf']}；HP 換算效率 {i['e_eff']}；{i['e_wire']}；端子 {i['e_terminal_c']}°C；單程 {i['e_length_m']} m；排序 {i['e_sort']}。"
    )
    for k, e in r["electric"].items():
        c = e["selected"]
        a(
            f"{k}：運轉 {e['current_a']:.3f} A，設計 {e['design_current_a']:.3f} A；NFB 候選 {c['nfb_candidate_a']} AT，{c['runs']} 組×{c['size_mm2']} mm²/相，Iz {c['iz_a']:.3f} A，壓降 {c['voltage_drop_pct']:.3f}%；接地紀錄：{i['e_' + k.lower() + '_ground']}。"
        )
        if i.get("e_" + k.lower() + "_pf_mode") == "本盤獨立 PF":
            a(f"  {k} 採用獨立 PF={e['pf']:.6g}；匯入設計電流下限 {i['e_' + k.lower() + '_design_floor']} A。")
    a("\n五、主要公式與簡短說明")
    a(
        f"照明 N=ceil(E×A/(Φ×U×M))=ceil({i['light_lux']}×{r['light']['area_m2']:g}/({i['light_lm']}×{i['light_u']}×{i['light_m']}))={r['light']['qty']} 盞。"
    )
    a(
        f"室內顯熱 Qs=m_da(1.006+1.86ws)(Tr−Ts)+QDCC={r['qs']:.3f} kW；產濕 G=3600×m_da(wr−ws)={r['moisture'] * 3600:.3f} kg/h。"
    )
    a(
        "h=1.006T+w(2501+1.86T)；盤管 Qair=m_da(hin−hout)；Qwater=Qair−m凝結水×cp水×T凝結水。"
    )
    a(
        "水量 LPM=60000Q/(ρcpΔT)；方管 A=WH、Dh=2WH/(W+H)；並聯 v=V̇/(nA)；Δp=f(L/Dh)ρv²/2+管件+設備壓差。"
    )
    a(
        "三相 I=1000P/(√3VLL·PF)；HP 為軸輸出，先乘 0.7456999/η 換輸入 kW；一般候選需滿足設計電流≤AT≤有效載流與小線保護上限。"
    )
    a(
        "盤管為需求／ADP 近似，非廠商性能選定；電纜沿用專案表並加保守條件，端子、短路、接地及馬達啟動仍需覆核。"
    )
    if r["warnings"]:
        a("\n本案待確認：")
        for msg in r["warnings"]:
            a("• " + msg)
    a(
        "資料依據：隨附版本化工程表為初估參考，並非已確認適用的法規載流表。參數來源另存於專案 JSON／HTML 附錄。"
    )
    return "\n".join(lines).replace("额外", "額外").replace("侧", "側") + "\n"


def _nm_report_base(r):
    from .ahu_schema import NM_DEFAULTS

    i = dict(r["inputs"])
    i["name"] = verbatim(i["name"], NM_DEFAULTS["name"])
    lines = [
        i["name"] + "｜MAU 分段需求與額定容量校核",
        "此表為需求反算；未達額定檢核時，表列目標狀態不代表已配置設備實際可達。",
        f"風量 {i['flow']} CMH，基準：{i['flow_basis']}；大氣 {i['p']} kPa；送風目標 {i['sa_t']}°C／{i['sa_rh']}%RH。",
        f"H1 電熱 {i['h1_kw']} kW、H2 電熱 {i['h2_kw']} kW 完整保留；回收熱水 {i['hw_in']}/{i['hw_out']}°C，情境：{i['recovery']}。",
        f"C1 水溫 {i['c1_in']}/{i['c1_out']}°C；C2 {i['c2_in']}/{i['c2_out']}°C；濕膜有效度 {i['wash_eff']}（初估／待選型），容量餘裕 {i['sf']}%。",
    ]
    if i.get("target_mode") == "主案分季需求":
        lines[2] = (
            "分季送風目標："
            + "；".join(
                f"{label} {i[season+'_flow']} CMH（送風狀態）／{i[season+'_sa_t']}°C／{i[season+'_sa_rh']}%RH"
                for season, label in [("summer", "夏季"), ("winter", "冬季")]
            )
            + "；來源主案 "
            + i["linked_main_hash"]
        )
    a = lines.append
    for key, title in [("summer", "夏季"), ("winter", "冬季")]:
        s = r[key]
        a(
            f"\n{title}：外氣 {s['oa']['t']:.2f}°C／{s['oa']['rh']:.2f}%RH，乾空氣流率 {s['mass']:.5f} kg/s"
        )
        a(
            "段落                    乾球°C      RH%      露點°C       w g/kg      h kJ/kg"
        )
        for name, st in s["nodes"]:
            a(
                f"{name:<19} {st['t']:9.3f} {st['rh']:9.3f} {dewpoint(st['w'], float(i['p'])):10.3f} {st['w'] * 1000:11.6f} {st['h']:12.6f}"
            )
        for h in [s["h1"], s["h2"]]:
            a(
                f"{h['tag']}：{h['inlet']['t']:.3f}°C／{h['inlet']['rh']:.3f}% → {h['outlet']['t']:.3f}°C／{h['outlet']['rh']:.3f}%；總熱需求 {h['air_kw']:.3f} kW；热水 {h['hw_kw']:.3f} kW／{h['water_lpm']:.3f} LPM；電力需求 {h['electric_kw']:.3f} kW；無回收時電力需求 {h['backup_electric_kw']:.3f} kW。"
            )
            if h["note"]:
                a(h["tag"] + "：" + h["note"])
        for c, delta in [
            (s["c1"], float(i["c1_out"]) - float(i["c1_in"])),
            (s["c2"], float(i["c2_out"]) - float(i["c2_in"])),
        ]:
            a(
                f"{c['name']}：水側 {c['water_kw']:.3f} kW／{c['water_kw'] / US_RT_KW:.3f} US RT；需水 {c['water_kw'] * 60000 / (1000 * 4.1868 * delta):.3f} LPM；凝結水 {c['condensate_kg_s'] * 3600:.3f} kg/h。"
            )
        a(
            f"水洗蒸發需求 {s['evap_kg_h']:.3f} kg/h（非循環泵流量）；本季水洗{('運轉' if s['wash_on'] else '旁通')}。"
        )
        a(
            "額定／必要條件檢核："
            + "；".join(
                (
                    k + ("：通過初估" if v else "：未達／需修正")
                    for k, v in s["checks"].items()
                )
            )
        )
    a("\n水洗循環與風機")
    a(
        "循環水量："
        + (
            f"{r['circulation_lpm']:.3f} LPM＝有效淋水面積×原廠單位面積水量"
            if r["circulation_lpm"] is not None
            else "待廠商提供有效淋水面積及淋水密度，不套用蒸發量固定倍數。"
        )
    )
    a(
        "循環泵揚程："
        + (
            f"{r['pump_head_m']:.3f} m＝噴頭水頭＋高差＋管路／濾網損失"
            if r["pump_head_m"] is not None
            else "待噴頭工作壓力、高差及管路／濾網阻力，不自動定為 20 m。"
        )
    )
    a(
        f"最大蒸發補水約 {r['evap_makeup_lph']:.3f} L/h；另加輸入的飛水／排污後 {r['makeup_plus_allowance_lph']:.3f} L/h，未包含未提供的排污或啟動補槽量。"
    )
    a(
        f"已填空氣側壓差 {r['air_dp_pa']:.1f} Pa（{('資料已標記完整，仍需風機曲線' if r['pressure_complete'] else '資料未完整，不可據以完成選機')}）；EC 配置 {i['fan_qty']}×{i['fan_unit_kw']} kW。"
    )
    a(
        f"按所填壓差／效率的風機電力需求 {r['fan_required_kw']:.3f} kW；電熱＋EC 已配置名目電力 {r['installed_electric_kw']:.3f} kW，未含循環泵與附屬設備。"
    )
    if r["pressure_complete"]:
        a(
            "風機電力初估："
            + (
                "未超出名目電力；仍需風機曲線／運轉點"
                if r["fan_capacity_pass"]
                else "超出名目電力，需重選／核對"
            )
        )
    a(
        "\n主要公式：m_da=V(CMH)/(3600×v_da)；Q=m_daΔh；純加熱 w 不變；水洗以 h_out≈h_in、T_out=T_in−ε(T_in−T_as)；蒸發 G=m_daΔw×3600；盤管水侧扣除凝結水液態焓。"
    )
    a(
        "計算限制：濕膜採循環水近似絕熱模型，忽略液態補水顯熱、泵入水熱及水溫調控；不保證飽和或 AMC 去除率。回收盤管能力須由廠商依同工況提供，端差只作必要條件篩選。"
    )
    a(
        "送風 T/RH 是本單機邊界；若它其實是室內設定，須先扣室內產濕求所需送風含濕量。風量基準、膜有效度、C1 出口、風機熱與額定能力需原始送審資料核對。"
    )
    return "\n".join(lines).replace("热", "熱").replace("侧", "側") + "\n"


@localized_report
def nm_report(r):
    s = _nm_report_base(r)
    i = r["inputs"]
    if r.get("link_status"):
        s = "主案連動：" + r["link_status"] + "\n" + s
    extra = [
        "\n逐段控制與選用熱源（V5.5.5）",
        f"H1：{i['h1_source']}；H2：{i['h2_source']}；加濕：{i['humidifier']}。保留的名目電熱欄位不代表停用熱源仍在供熱。",
    ]
    for season, title in [("summer", "夏季"), ("winter", "冬季")]:
        sr = r[season]
        extra.append(title + "：" + sr["control_basis"])
        for tag in ["h1", "c1", "c2", "h2"]:
            k = season + "_" + tag
            mode = i[k + "_mode"]
            extra.append(
                tag.upper()
                + " "
                + mode
                + (f" {i[k + '_t']}°C" if mode.startswith("指定") else "")
                + (f"／{i[k + '_rh']}%RH" if mode == "指定出口 T/RH" else "")
            )
        for tag in ["h1", "h2"]:
            effective = sr[tag].get("effective_water")
            if effective:
                extra.append(
                    f"{tag.upper()} 採用熱水 {effective['hw_in']:g}/{effective['hw_out']:g}°C，端差 {effective['hw_approach']:g} K，電熱效率 {effective['heat_eta']:g}。"
                )
            if sr[tag].get("unserved_kw", 0) > 1e-06:
                extra.append(
                    f"{tag.upper()} 尚無已選熱源供應的熱需求：{sr[tag]['unserved_kw']:.3f} kW；圖表該點為未供應的需求點。"
                )
        if "蒸汽" in i["humidifier"]:
            st = sr["steam"]
            extra.append(
                f"蒸汽需求 {st['kg_h']:.3f} kg/h；入空氣熱 {st['air_kw']:.3f} kW；發生器電力 {st['electric_kw']:.3f} kW。"
            )
    extra.append(
        f"本案選用設備名目電力 {r['active_installed_electric_kw']:.3f} kW（未含水洗泵／附屬設備）；未自動加進整廠 NP，避免重複。"
    )
    extra.append(
        "蒸汽與水洗分開：Δh_air=ṁsteam×hsteam/ṁda；Psteam=ṁsteam(hsteam−cp水×T補水)/η。電極式需導電水，給水及原廠電導率範圍未確認時不判定合格。"
    )
    header = (
        "整體狀態："
        + r["quality"]["status"]
        + "（通過僅指已知條件的初估，非原廠性能認證）\n"
    )
    for q in r["quality"]["items"]:
        if q["status"] != "通過":
            header += "[" + q["status"] + "] " + q["name"] + "：" + q["detail"] + "\n"
    return header + s + "\n".join(extra).replace("需求点", "需求點") + "\n"
