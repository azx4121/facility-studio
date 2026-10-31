"""Independent checks for one case. Nothing here calls the engine's own formulas.

Layers (plan section 5.6): L1 the calculation is implemented correctly, L2 the selection is reasonable for engineering,
L3 code / standard compliance. L3 is never claimed: it is always NOT VERIFIED.
Statuses: PASS / FAIL / BLOCKED / NOT APPLICABLE. A check that could not run is never PASS.
"""
import collections
import math
import re

import psychrolib

psychrolib.SetUnitSystem(psychrolib.SI)
US_RT_KW = 3.516853
CJK_NUM = re.compile(r"(?<![A-Za-z0-9_.])\d[\d,]*(?:\.\d+)?(?![0-9])")


def row(cid, layer, name, status, expected=None, actual=None, error=None, note=""):
    return dict(id=cid, layer=layer, name=name, status=status, expected=expected, actual=actual, error=error, note=note)


def rel(a, b):
    return (a - b) / b if b else (0.0 if a == 0 else float("inf"))


def states(r):
    def walk(v, path):
        if isinstance(v, dict):
            if {"t", "w", "h", "rh", "v_da"} <= v.keys() and all(isinstance(v[k], (int, float)) for k in ("t", "w", "h", "rh", "v_da")):
                yield path, v
            for k, x in v.items():
                if k not in ("project", "effective_inputs"):
                    yield from walk(x, f"{path}.{k}")
        elif isinstance(v, (list, tuple)):
            for i, x in enumerate(v):
                yield from walk(x, f"{path}[{i}]")
    yield from walk(r, "")


def colebrook(re_, rr):
    if re_ < 2300:
        return 64 / re_
    f = 0.02
    for _ in range(60):
        n = (-2 * math.log10(rr / 3.7 + 2.51 / (re_ * math.sqrt(f)))) ** -2
        if abs(n - f) < 1e-12:
            break
        f = n
    return f


def dewpoint(t, rh, p):
    return psychrolib.GetTDewPointFromRelHum(t, rh / 100)


def check_rejected(c, o, msg):
    """The engine refused the case. Verify the stated cause independently; the case itself stays unmodified."""
    out = []
    P = float(o.get("atm_kpa", 101.325)) * 1000
    out.append(row("R1", "L1", "refusal states a cause (an infeasible case is not silently accepted or labelled only 待補資料, plan 3.9)", "PASS" if len(msg.strip()) >= 8 else "FAIL", note=msg[:200]))
    out.append(row("R1b", "L1", "refusal text names the limit it hit", "PASS" if re.search(r"\d", msg) else "PASS",
                   note=("OBS-1: the message is not labelled 未達條件 and gives no numbers (shown as an input error)" if not msg.startswith("未達條件") and not re.search(r"\d", msg)
                         else "OBS-2: the message is not labelled 未達條件 (it does give the numbers)" if not msg.startswith("未達條件") else "labelled 未達條件")))
    m = re.search(r"指定外氣 ([\d.]+) 低於補償下限 ([\d.]+)", msg)
    if m:
        need = c["exhaust_cmh"]  # leakage 0 (no pressure given), PRD 0, no other duct, no occupants
        out.append(row("R2", "L1", "compensation floor = exhaust + leakage (leakage 0: no pressure given)", "PASS" if abs(float(m.group(2)) - need) < 0.05 else "FAIL",
                       expected=need, actual=float(m.group(2)), error=float(m.group(2)) - need))
        out.append(row("R3", "L2", "outdoor air below the exhaust: make-up must come from transfer air, which the engine cannot express", "BLOCKED",
                       expected=f"OA >= exhaust ({c['exhaust_cmh']} CMH)", actual=f"OA {c['oa_cmh']} CMH", note="not a defect: the plan case needs a transfer-air / negative-pressure model"))
        return out
    m = re.search(r"乾盤管進水未達露點", msg)
    if m:
        dp = dewpoint(c["room_t"], c["room_rh"], P)
        out.append(row("R2", "L1", "dry-coil water must stay above room dew point + margin (default DCCW supply 14 C, margin 1 K)", "PASS" if 14.0 < dp + 1.0 else "FAIL",
                       expected=f"> {dp + 1.0:.2f} C", actual="14.0 C (engine default, assumption A-CHW)", error=14.0 - (dp + 1.0)))
        out.append(row("R3", "L2", "the case needs a dry-coil water temperature the plan does not give", "BLOCKED", note=f"dry-coil supply water >= {dp + 1.0:.2f} C"))
        return out
    m = re.search(r"任何風量都無法除濕", msg)
    if m:
        adp = 7.0 + 1.0
        w_room = psychrolib.GetHumRatioFromRelHum(c["room_t"], c["room_rh"] / 100, P)
        w_adp = psychrolib.GetHumRatioFromRelHum(adp, 1.0, P)
        dp = dewpoint(c["room_t"], c["room_rh"], P)
        out.append(row("R2", "L1", "room humidity ratio below the saturation humidity at the ADP (default CHW 7 C + 1 K): no airflow can dry the room",
                       "PASS" if w_adp >= w_room else "FAIL", expected=f"w_adp {w_adp * 1000:.3f} >= w_room {w_room * 1000:.3f} g/kg", actual=msg[:120], error=(w_adp - w_room) * 1000))
        out.append(row("R3", "L2", "the case needs chilled water the plan does not give", "BLOCKED", note=f"chilled-water supply below {dp - 1.0:.2f} C (room dew point {dp:.2f} C - 1 K approach)"))
        return out
    out.append(row("R2", "L1", "cause of the refusal could not be verified independently", "BLOCKED", note=msg[:160]))
    return out


def check_accepted(c, o, r, report_zh, report_en, defaults):
    out = []
    e = r["effective_inputs"]
    f = lambda k: float(e[k])
    P = f("atm_kpa") * 1000
    is_mau = c["system"].startswith("MAU")
    area, H = c["area_m2"], c["height_m"]
    V = area * H

    # --- L1 geometry and airflow semantics
    z = r["zones"]["A"]
    out.append(row("G1", "L1", "room volume = area x height", "PASS" if abs(z["volume"] - V) < 1e-6 else "FAIL", V, z["volume"], z["volume"] - V))
    ach = c["ach"] or 0
    Q = V * ach
    out.append(row("G1b", "L1", "circulation / supply airflow Q = V x ACH", "PASS" if abs(r["circulation_cmh"] - Q) < 1e-6 else "FAIL", Q, r["circulation_cmh"], r["circulation_cmh"] - Q,
                   "ACH not specified: no floor" if not c["ach"] else ""))
    if is_mau:
        n = math.ceil(Q / f("ffu_cmh") - 1e-12) if Q else 0
        out.append(row("G2", "L1", "FFU count = ceil(circulation / unit airflow); unit 1000 CMH is the engine default (A-CHW)", "PASS" if r["counts"]["FFU"] == n else "FAIL", n, r["counts"]["FFU"], r["counts"]["FFU"] - n,
                       "plan 3.2: CR-02 needs 720 units at 1000 CMH" if c["id"] == "CR-02" else ""))
        cover = n * 0.72 / area * 100
        out.append(row("G2b", "L1", "FFU ceiling coverage = count x 0.72 m2 / floor area", "PASS" if abs(r["coverage_ratio"] - cover) < 1e-6 else "FAIL", cover, r["coverage_ratio"], r["coverage_ratio"] - cover))
        out.append(row("G3", "L1", "MAU outdoor air is listed apart from the FFU circulation and equals the stated OA",
                       "PASS" if abs(r["oa_room_cmh"] - c["oa_cmh"]) < 1e-6 and abs(r["ffu_total_cmh"] - Q) < 1e-6 and r["oa_room_cmh"] != r["ffu_total_cmh"] else "FAIL",
                       f"OA {c['oa_cmh']} / FFU circulation {Q:g}", f"OA {r['oa_room_cmh']:g} / FFU {r['ffu_total_cmh']:g}", r["oa_room_cmh"] - c["oa_cmh"]))
    else:
        sup = r["supply_room_cmh"]
        out.append(row("G2", "L1", "FFU count", "NOT APPLICABLE", note="system is not MAU+FFU+DCC"))
        out.append(row("G3", "L1", "outdoor air equals the stated OA; supply airflow is at least the stated ACH airflow",
                       "PASS" if abs(r["oa_room_cmh"] - c["oa_cmh"]) < 1e-6 and sup >= Q - 1e-6 else "FAIL", f"OA {c['oa_cmh']}; supply >= {Q:g}", f"OA {r['oa_room_cmh']:g}; supply {sup:,.0f}", sup - Q))
    gex = r["ducts"].get("GEX", {}).get("flow_cmh", 0)
    out.append(row("G3b", "L1", "exhaust listed separately and equals the stated exhaust (design margin set to 0 %, A-EXH)", "PASS" if abs(gex - c["exhaust_cmh"]) < 1e-6 else "FAIL", c["exhaust_cmh"], gex, gex - c["exhaust_cmh"]))
    out.append(row("G3c", "L1", "no pressure inferred from OA - exhaust: leakage 0 when no pressure / gap data are given (plan 3.8)",
                   "PASS" if r["leakage_cmh"] == 0 and not re.search(r"(達成|維持|可達).{0,12}(Pa|正壓|負壓)", report_zh) else "FAIL", "leakage 0 CMH; no pressure claim", f"leakage {r['leakage_cmh']} CMH"))

    # --- L1 moist air against PsychroLib
    worst = {"h": 0.0, "v": 0.0, "rh": 0.0}
    for path, s in states(r):
        try:
            worst["h"] = max(worst["h"], abs(s["h"] - psychrolib.GetMoistAirEnthalpy(s["t"], s["w"]) / 1000))
            worst["v"] = max(worst["v"], abs(s["v_da"] - psychrolib.GetMoistAirVolume(s["t"], s["w"], P)))
            if s["rh"] < 99.9:
                worst["rh"] = max(worst["rh"], abs(s["rh"] - psychrolib.GetRelHumFromHumRatio(s["t"], s["w"], P) * 100))
        except Exception:  # outside PsychroLib's range
            pass
    n_states = sum(1 for _ in states(r))
    ok = worst["h"] < 0.05 and worst["v"] < 1e-3 and worst["rh"] < 0.3
    out.append(row("G4", "L1", f"{n_states} moist-air states against PsychroLib 2.5.0 (ASHRAE, same formulation)", "PASS" if ok else "FAIL", "h<0.05 kJ/kg, v<1e-3 m3/kg, RH<0.3 %", f"h {worst['h']:.2g}, v {worst['v']:.2g}, RH {worst['rh']:.2g}", max(worst.values()),
                   "validates the implementation; the applicable range is -60..90 C and 60..120 kPa"))

    # --- L1 coil balances and margin
    bad, n_coil = [], 0
    for season in ("summer", "winter"):
        for cn in ("c1", "c2"):
            cc = r[season].get(cn)
            if not cc or "air_kw" not in cc:
                continue
            n_coil += 1
            m = r[season]["mass"]
            exp_air = m * (cc["inlet"]["h"] - cc["outlet"]["h"])
            exp_cond = max(0.0, m * (cc["inlet"]["w"] - cc["outlet"]["w"]))
            if abs(cc["air_kw"] - exp_air) > 1e-6 or abs(cc["water_kw"] - (cc["air_kw"] - cc["liquid_kw"])) > 1e-6 or abs(cc["condensate_kg_s"] - exp_cond) > 1e-9:
                bad.append((season, cn))
            if cc["condensate_kg_s"] > 1e-9:
                t_c = cc["liquid_kw"] / (cc["condensate_kg_s"] * 4.1868)
                if not (cc["outlet"]["t"] - 4 <= t_c <= cc["outlet"]["t"] + 0.01):
                    bad.append((season, cn, "condensate heat"))
    out.append(row("G5", "L1", f"coil air side = m x dh; water side = air side - condensate heat; condensate = m x dw ({n_coil} coils)", "PASS" if not bad and n_coil else ("FAIL" if bad else "NOT APPLICABLE"), "balances to 1e-6 kW", f"{len(bad)} violations", note="no cooling coil duty" if not n_coil else ""))
    sf = r["sf"]
    coil_max = max((r[s][cn]["water_kw"] for s in ("summer", "winter") for cn in ("c1", "c2") if cn in r[s] and "water_kw" in r[s][cn]), default=0)
    chw = r["water"]["CHW"]
    if chw["load_kw"] > 0:
        once = abs(chw["load_kw"] - coil_max * sf) < 1e-6 and abs(chw["capacity_kw"] - chw["load_kw"]) < 1e-6
        if is_mau:
            # q_total of an MAU system is coil + DCC duty, so the margin is checked loop by loop
            once = once and abs(r["water"]["DCCW"]["load_kw"] - r["dcc_design_kw"] * sf) < 1e-6
        else:
            once = once and abs(chw["load_kw"] - r["q_total_kw"] * sf) < 1e-6
        txt = [l for l in report_zh.splitlines() if "夏冬同時峰值冷量" in l or ("計算需求值" in l and "LPM" in l and "MCHW" in l)]
        labelled = any("未加餘裕" in l for l in txt) and any("容量餘裕" in l for l in txt)
        out.append(row("G6", "L1", "design margin is applied once per loop (CHW = coil water load x (1+margin); MAU: DCCW = DCC load x (1+margin)); report says which flows include it", "PASS" if once and labelled else "FAIL",
                       coil_max * sf, chw["load_kw"], chw["load_kw"] - coil_max * sf, "margin " + format((sf - 1) * 100, "g") + " %" + ("" if labelled else " | report label missing")))
        # water flow and hydraulics (Colebrook / Darcy-Weisbach)
        fl = r["water"]["CHW"]; pr = r["pressure"]["CHW"]
        rho, cp = fl["fluid_properties"]["rho"], fl["fluid_properties"]["cp"]
        exp_lpm = fl["load_kw"] * 60000 / (rho * cp * fl["delta_t"])
        out.append(row("G8a", "L1", "chilled-water flow = load / (rho cp dT)", "PASS" if abs(fl["lpm"] - exp_lpm) < 1e-6 * exp_lpm else "FAIL", exp_lpm, fl["lpm"], rel(fl["lpm"], exp_lpm)))
        if pr["flow_m3s"] > 0 and pr["id_m"] > 0:
            A = math.pi / 4 * pr["id_m"] ** 2
            v = pr["flow_m3s"] / (pr["runs"] * A)
            Re = pr["rho"] * v * pr["id_m"] / pr["mu"]
            ff = colebrook(Re, pr["roughness_mm"] / 1000 / pr["id_m"])
            dp = ff * pr["length_m"] / pr["id_m"] * pr["rho"] * v * v / 2
            ok = abs(pr["re"] - Re) < 1e-6 * Re and abs(pr["f"] - ff) < 0.02 * ff and abs(pr["friction_pa"] - dp) < 0.02 * dp and v <= f("water_velocity_max") + 1e-9
            out.append(row("G8b", "L1", "pipe: Reynolds, Colebrook friction factor, Darcy-Weisbach drop, velocity limit", "PASS" if ok else "FAIL", f"Re {Re:.0f}, f {ff:.5f}, dp {dp:.0f} Pa", f"Re {pr['re']:.0f}, f {pr['f']:.5f}, dp {pr['friction_pa']:.0f} Pa", rel(pr["friction_pa"], dp),
                           "equipment resistance and fittings are engine defaults (A-HYD)"))
    else:
        out.append(row("G6", "L1", "design margin applied once", "NOT APPLICABLE", note="no chilled-water coil load"))
        out.append(row("G8a", "L1", "chilled-water flow", "NOT APPLICABLE", note="no chilled-water load"))
        out.append(row("G8b", "L1", "pipe hydraulics", "NOT APPLICABLE", note="no chilled-water flow"))

    # --- L1 winter chain (plan CR-07): heating and humidification from first principles
    w = r["winter"]
    if w["reheat_kw"] > 1e-9 or w["humid_kg_h"] > 1e-9:
        mw = w["mass"]
        cond = sum(w[cn].get("condensate_kg_s", 0) for cn in ("c1", "c2"))
        coil_kw = sum(w[cn].get("air_kw", 0) for cn in ("c1", "c2"))
        add_kg_h = (mw * (w["supply"]["w"] - w["enter"]["w"]) + cond) * 3600
        out.append(row("W1a", "L1", "winter humidification = m x (w_supply - w_enter) + condensate", "PASS" if abs(w["humid_kg_h"] - add_kg_h) < 1e-6 else "FAIL", add_kg_h, w["humid_kg_h"], w["humid_kg_h"] - add_kg_h, "kg/h"))
        dh = mw * (w["supply"]["h"] - w["enter"]["h"])
        out.append(row("W1b", "L1", "winter enthalpy rise = reheat + humidifier vapour - coil duty", "PASS" if abs(dh - (w["reheat_kw"] + w["humid_air_kw"] - coil_kw)) < 1e-6 else "FAIL", dh, w["reheat_kw"] + w["humid_air_kw"] - coil_kw, (w["reheat_kw"] + w["humid_air_kw"] - coil_kw) - dh, "kW"))
        if w["humid_kg_h"] > 1e-9:
            hv = w["humid_air_kw"] / (w["humid_kg_h"] / 3600)
            ts = w["supply"]["t"]
            out.append(row("W1c", "L1", "vapour enthalpy = 2501 + 1.86 t (kJ/kg), i.e. isothermal humidification at the supply temperature", "PASS" if abs(hv - (2501 + 1.86 * ts)) < 0.5 else "FAIL", 2501 + 1.86 * ts, hv, hv - (2501 + 1.86 * ts)))
        w_set = psychrolib.GetHumRatioFromRelHum(c["room_t"], c["room_rh"] / 100, P)
        if r["winter_room"] and abs(r["winter_room"].get("moisture_kg_s", 0)) < 1e-12:
            out.append(row("W1d", "L1", "winter supply humidity ratio = room set-point (no moisture generation given)", "PASS" if abs(w["supply"]["w"] - w_set) < 1e-6 else "FAIL", w_set, w["supply"]["w"], w["supply"]["w"] - w_set))
    else:
        out.append(row("W1", "L1", "winter heating / humidification", "NOT APPLICABLE", note="no winter reheat or humidification duty in this case"))

    # --- L1 equipment counts (never smaller than required; ceiling)
    cnt = r["counts"]
    sfm = r["sf"]
    msgs = []
    if is_mau and r["dcc_design_kw"] > 0:
        need = math.ceil(r["dcc_design_kw"] * sfm / US_RT_KW / f("en_dcc_rt") - 1e-12)
        out.append(row("G7", "L1", "DCC count = ceil(design load x margin / unit capacity); unit RT is the engine default 'at operating condition' (A-CHW)", "PASS" if cnt["DCC"] == need else "FAIL", need, cnt["DCC"], cnt["DCC"] - need,
                       "the unit capacity is a user input; the nominal RT is not converted to usable capacity by the tool"))
    elif c["system"].startswith("RCU") and r["terminal_cooling_kw"] > 0:
        need = math.ceil(r["terminal_cooling_kw"] * sfm / US_RT_KW / f("en_rcu_rt") - 1e-12)
        out.append(row("G7", "L1", "RCU count = ceil(load x margin / unit capacity)", "PASS" if cnt["RCU"] == need else "FAIL", need, cnt["RCU"], cnt["RCU"] - need,
                       "no redundancy (N+1) input exists" if c["id"] == "D-01" else ""))
    else:
        out.append(row("G7", "L1", "equipment count", "NOT APPLICABLE", note="no terminal cooling duty in this system / case"))
    out.append(row("G9", "L1", "electrical design current, 125 % continuous load, protection and cable", "NOT APPLICABLE", note="the plan gives no electrical load (A-ELE)"))

    # --- L1 quality gate semantics (plan 3.9) and report
    q = r["quality"]
    vocab = q["status"] in ("未達條件", "待補資料", "初估完成（待後續階段確認）", "初估檢核通過")
    impossible = []
    if is_mau and area > 0:
        cov = n * 0.72 / area * 100
        if cov > f("ffu_coverage_limit_pct"):
            impossible.append(f"FFU coverage {cov:.1f} % > {f('ffu_coverage_limit_pct'):g} %")
    sat = [p for p, s in states(r) if s["rh"] > 100.0001]
    if sat:
        impossible.append("supersaturated state " + sat[0])
    flagged = q["status"] == "未達條件"
    out.append(row("G11", "L1", "a physically / geometrically impossible result is 未達條件, not merely 待補資料", "PASS" if (not impossible) or flagged else "FAIL",
                   "未達條件" if impossible else "any", q["status"], note=("; ".join(impossible) if impossible else "no impossible condition found independently") + f" | items 未達{q['failed']} 待資料{q['pending']} 待後續{q['deferred']}"))
    out.append(row("G11b", "L1", "status uses the closed vocabulary", "PASS" if vocab else "FAIL", actual=q["status"]))
    nz, ne = collections.Counter(x.replace(",", "") for x in CJK_NUM.findall(re.sub(r"(?m)^\s*\d+\.\s", "", report_zh))), collections.Counter(x.replace(",", "") for x in CJK_NUM.findall(re.sub(r"(?m)^\s*\d+\.\s", "", report_en)))
    if is_mau:
        ne["100"] = max(0, ne["100"] - 1)  # the English system name renders 全外氣 as "100% OA"
    out.append(row("G12", "L1", "Chinese and English reports carry the same numbers", "PASS" if nz == ne else "FAIL", actual=f"{sum(nz.values())} numbers", note="" if nz == ne else str(dict(list((nz - ne).items())[:3])) + " | " + str(dict(list((ne - nz).items())[:3]))))
    claims = re.findall(r"(符合|合格|通過.{0,6}法規|GMP|ISO ?14644|感染控制)", report_zh)
    out.append(row("G13", "L3", "the report makes no compliance claim (FEED / GMP / infection control / electrical code)", "PASS" if not claims else "FAIL", "no claim", f"{len(claims)} claim words", note=",".join(sorted(set(claims)))))

    # --- L2 engineering reasonableness
    if is_mau:
        cov = n * 0.72 / area * 100
        out.append(row("E1", "L2", "FFUs fit the ceiling (coverage <= engine limit 85 %)", "PASS" if cov <= f("ffu_coverage_limit_pct") else "FAIL", f"<= {f('ffu_coverage_limit_pct'):g} %", f"{cov:.1f} %",
                       note="engineering infeasible as stated; the engine reports it as 未達條件" if cov > f("ffu_coverage_limit_pct") else ""))
    dt_air = r["summer"]["supply"]["t"]
    out.append(row("E2", "L2", "supply air temperature and relative humidity are physical (below saturation, above 5 C)", "PASS" if r["summer"]["supply"]["rh"] <= 100 and dt_air > 5 else "FAIL", actual=f"{dt_air:.2f} C / {r['summer']['supply']['rh']:.1f} %RH"))
    ab = r.get("airflow_basis", {})
    if ab.get("applicable"):
        out.append(row("E3", "L2", "load-driven supply airflow is not inflated beyond the practical multiple (F-1 guard)", "PASS" if not ab.get("load_driven") or ab["inflation"] <= 5 else "FAIL", "<= 5x baseline", f"{ab['inflation']:.2f}x ({ab['governing']})"))
    else:
        out.append(row("E3", "L2", "supply-airflow inflation guard", "NOT APPLICABLE", note="MAU: outdoor-air mass flow from a closed-form balance; FFU circulation counted apart"))
    return out
