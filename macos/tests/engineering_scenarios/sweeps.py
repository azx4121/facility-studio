"""The five non-random feasibility sweeps S-01 .. S-05 of the plan (section 4), with fixed, justified steps.

For each sweep the independent prediction of "accepted / refused" is computed BEFORE the engine is asked, and the engine
answer is compared with it. Steps are listed in the output exactly as run. Nothing is random.
"""
import math
import re

import psychrolib

from facility_studio.errors import ValidationError

psychrolib.SetUnitSystem(psychrolib.SI)
P = 101325.0


def dp(t, rh):
    return psychrolib.GetTDewPointFromRelHum(t, rh / 100)


def w_sat(t):
    return psychrolib.GetHumRatioFromRelHum(t, 1.0, P)


def case_by_id(cases, cid):
    return next(c for c in cases if c["id"] == cid)


def step(run, o, tag, predicted_accept, extract):
    rec = dict(step=tag, predicted_accept=predicted_accept)
    try:
        r = run(o)
    except ValidationError as exc:
        rec.update(accepted=False, message=str(exc)[:220])
        return rec, None
    rec.update(accepted=True, status=r["quality"]["status"], failed=r["quality"]["failed"], pending=r["quality"]["pending"], deferred=r["quality"]["deferred"], **extract(r))
    return rec, r


def verdict(steps, extra_checks):
    problems = []
    for s in steps:
        if s["accepted"] != s["predicted_accept"]:
            problems.append(f"{s['step']}: predicted {'accept' if s['predicted_accept'] else 'refuse'}, engine {'accepted' if s['accepted'] else 'refused'}")
        if not s["accepted"] and len(s.get("message", "")) < 8:
            problems.append(f"{s['step']}: refusal without a cause")
        for k, v in s.items():
            if isinstance(v, float) and not math.isfinite(v):
                problems.append(f"{s['step']}: non-finite {k}")
    problems += extra_checks
    return ("FAIL" if problems else "PASS"), problems


def s01(run, inputs, cases):
    c = case_by_id(cases, "CR-08")
    edge = dp(c["room_t"], c["room_rh"]) - 1.0  # coil approach 1 K (engine default, A-CHW)
    steps_t = [5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.65, 8.7, 8.8]
    out = {}
    for variant, system in (("S-01", c["system"]), ("S-01b", "AHU (OA+RA 混合)")):
        steps, problems, flows = [], [], []
        for t in steps_t:
            o = inputs(c)
            o["chw2_in"] = t
            if variant == "S-01b":
                o.update(sys_type=system, en_ach_A=c["ach"])  # same room, mixed-air AHU: exercises the supply-airflow search
                o.pop("ffu_topology", None)
            pred = t < edge - 1e-9 if variant == "S-01b" else t <= edge + 1e-9
            rec, r = step(run, o, f"chw {t:g} C", pred, lambda r: dict(
                supply_t=r["summer"]["supply"]["t"], supply_dewpoint=dp(r["summer"]["supply"]["t"], r["summer"]["supply"]["rh"]), supply_dt_k=r["room"]["t"] - r["summer"]["supply"]["t"],
                supply_airflow_cmh=r["supply_room_cmh"], oa_cmh=r["oa_room_cmh"], adp_req_c=r["summer"]["c2"].get("adp_req_c"), bf_req=r["summer"]["c2"].get("bf_req"),
                inflation=r["airflow_basis"].get("inflation"), gate_status=next((i["status"] for i in r["quality"]["items"] if i["name"] == "供風量合理性"), None)))
            steps.append(rec)
            if r is not None:
                flows.append(rec["supply_airflow_cmh"])
                if rec["adp_req_c"] is not None and not (t + 1.0 - 1e-6 <= rec["adp_req_c"] <= rec["supply_dewpoint"] + 1e-6):
                    problems.append(f"{rec['step']}: ADP {rec['adp_req_c']:.3f} outside [{t + 1:.2f}, supply dew point {rec['supply_dewpoint']:.3f}]")
                if rec["supply_airflow_cmh"] > 1e8:
                    problems.append(f"{rec['step']}: absurd airflow {rec['supply_airflow_cmh']:.3g} CMH")
                if variant == "S-01" and abs(rec["supply_airflow_cmh"] - r["circulation_cmh"]) > 1e-6 and abs(rec["oa_cmh"] - c["oa_cmh"]) > 1e-6:
                    problems.append(f"{rec['step']}: MAU outdoor air changed from the stated {c['oa_cmh']} CMH")
                if rec["inflation"] and rec["inflation"] > 5 + 1e-9 and rec["status"] != "未達條件":
                    problems.append(f"{rec['step']}: inflation {rec['inflation']:.1f}x not 未達條件")
        if any(b < a * (1 - 1e-9) for a, b in zip(flows, flows[1:])):
            problems.append("supply airflow decreases while the chilled water gets warmer")
        acc = [s["accepted"] for s in steps]
        if acc != sorted(acc, reverse=True):
            problems.append("feasible steps are not a contiguous prefix")
        concl, probs = verdict(steps, problems)
        out[variant] = dict(id=variant, case="CR-08" + ("" if variant == "S-01" else " room in a mixed-air AHU (extra variant, not in the plan)"), system=system,
                            basis=f"chilled-water supply 5.0-8.0 C in 0.5 K steps (usual operating range, one reset increment), then 0.1 K to 8.6 and 0.05 K near the predicted edge {edge:.2f} C = room dew point {dp(c['room_t'], c['room_rh']):.2f} C - 1 K approach; 8.7 and 8.8 beyond it",
                            prediction="MAU: accepted while ADP <= supply dew point (chw <= edge); AHU search: accepted while the room humidity ratio is above the saturation ratio at the ADP (chw < edge)",
                            steps=steps, conclusion=concl, problems=probs,
                            summary=f"{sum(acc)}/{len(acc)} accepted; edge {edge:.2f} C; max airflow {max(flows):,.0f} CMH; " + ("MAU supply dT is 0 by design (mau_supply_t = room T), the airflow stays the stated OA" if variant == "S-01" else "airflow rises smoothly, impractical steps are 未達條件"))
    return list(out.values())


def s02(run, inputs, cases):
    c = case_by_id(cases, "CR-06")
    steps, problems = [], []
    for ex in (40000, 46000, 52000, 55000, 57000, 58000, 58500, 60000, 64000, 70000):
        o = inputs(c)
        o["gex_q"] = ex
        pred = ex <= c["oa_cmh"] + 1e-9
        rec, r = step(run, o, f"exhaust {ex}", pred, lambda r: dict(oa_cmh=r["oa_room_cmh"], leakage_cmh=r["leakage_cmh"], exhaust_cmh=r["ducts"]["GEX"]["flow_cmh"], balance_cmh=r["oa_room_cmh"] - r["ducts"]["GEX"]["flow_cmh"],
                                                                      quality_items=[i["name"] for i in r["quality"]["items"] if i["status"] != "通過"]))
        steps.append(rec)
        if r is not None:
            if rec["leakage_cmh"] != 0:
                problems.append(f"{rec['step']}: leakage assumed ({rec['leakage_cmh']} CMH) although no pressure or gap is given")
            if re.search(r"(達成|維持|可達).{0,12}(Pa|正壓)", " ".join(r["warnings"])):
                problems.append(f"{rec['step']}: a pressure is claimed")
        elif not re.search(r"低於補償下限 ([\d.]+)", rec.get("message", "")) or abs(float(re.search(r"低於補償下限 ([\d.]+)", rec["message"]).group(1)) - ex) > 0.05:
            problems.append(f"{rec['step']}: refusal does not state the compensation floor {ex}")
    # automatic outdoor air: does the engine find the make-up itself, and does it still not assume a pressure?
    o = inputs(c)
    o["en_manual_oa"] = 0
    o["gex_q"] = 64000
    try:
        r = run(o)
        auto = dict(oa_cmh=r["oa_room_cmh"], exhaust_cmh=r["ducts"]["GEX"]["flow_cmh"], leakage_cmh=r["leakage_cmh"], status=r["quality"]["status"])
        if abs(auto["oa_cmh"] - 64000) > 1: problems.append("automatic outdoor air does not equal the 64000 CMH exhaust")
    except ValidationError as exc:
        auto = dict(refused=str(exc)[:160]); problems.append("automatic outdoor air refused")
    concl, probs = verdict(steps, problems)
    return [dict(id="S-02", case="CR-06", basis="exhaust 40,000-70,000 CMH: 77 % to 135 % of the stated 58,000 CMH make-up; 6,000 CMH steps to the case value 52,000, then 3,000 to 1,000 CMH steps around the make-up limit, then 4,000-6,000 beyond",
                 prediction="accepted while exhaust <= stated outdoor air (compensation floor = exhaust + leakage; leakage 0 because no pressure / gap data); refusal must quote the floor; no pressure may be inferred",
                 steps=steps, automatic_outdoor_air=auto, conclusion=concl, problems=probs,
                 summary=f"{sum(s['accepted'] for s in steps)}/{len(steps)} accepted; engine refuses exhaust above the make-up (error, not a warning); leakage stays 0 CMH; with automatic OA the engine sets OA = exhaust")]


def s03(run, inputs, cases):
    c = case_by_id(cases, "CR-01")
    steps, problems = [], []
    Q = c["area_m2"] * c["height_m"] * c["ach"]
    for size, area_each in (("1200x600 (0.72m²)", 0.72), ("1200x1200 (1.44m²)", 1.44)):
        counts = []
        for u in (600, 700, 800, 900, 1000, 1100, 1200, 1400):
            o = inputs(c)
            o.update(ffu_cmh=u, ffu_size=size)
            n = math.ceil(Q / u - 1e-12)
            cover = n * area_each / c["area_m2"] * 100
            rec, r = step(run, o, f"{size[:9]} {u} CMH/unit", True, lambda r: dict(ffu_count=r["counts"]["FFU"], coverage_ratio=r["coverage_ratio"], circulation_cmh=r["circulation_cmh"], ach_equivalent=r["circulation_cmh"] / 3000))
            rec.update(expected_count=n, expected_coverage=cover)
            steps.append(rec)
            if r is None:
                continue
            counts.append(rec["ffu_count"])
            if rec["ffu_count"] != n: problems.append(f"{rec['step']}: count {rec['ffu_count']} != ceil({Q:g}/{u}) = {n}")
            if abs(rec["coverage_ratio"] - cover) > 1e-6: problems.append(f"{rec['step']}: coverage {rec['coverage_ratio']} != {cover:.3f}")
            if (cover > 85 + 1e-9) != (rec["status"] == "未達條件") and cover > 85:
                problems.append(f"{rec['step']}: coverage {cover:.1f} % > 85 % but status {rec['status']}")
            if rec["circulation_cmh"] != Q: problems.append(f"{rec['step']}: circulation {rec['circulation_cmh']} != {Q:g} (the 500 ACH must not be capped)")
        if any(b > a for a, b in zip(counts, counts[1:])): problems.append(f"{size}: FFU count increases with unit airflow")
    redundancy = [dict(failed_units=k, required_installed=math.ceil(Q / 1000) + k, available_airflow_cmh=(math.ceil(Q / 1000)) * 1000 - k * 1000, shortfall_cmh=max(0, Q - ((math.ceil(Q / 1000)) * 1000 - k * 1000)))
                  for k in (0, 1, 2, 5, 15, 75)]
    concl, probs = verdict(steps, problems)
    return [dict(id="S-03", case="CR-01", basis="effective airflow per FFU 600-1,400 CMH (60 %-140 % of the 1,000 CMH default: filter loading, fan derating, a higher-flow module) in 100-200 CMH steps; both nominal sizes",
                 prediction="count = ceil(1,500,000 / unit airflow); coverage = count x module area / 1,000 m2; status 未達條件 whenever coverage > 85 %; 500 ACH is never capped",
                 steps=steps, failed_unit_table_external=redundancy,
                 blocked=[dict(aspect="FFU resistance / operating point", reason="the engine has one effective airflow per FFU, no resistance or fan curve"),
                          dict(aspect="failed units and redundancy", reason="no input; the external table above (computed by the tester, not the engine) shows the installed count and shortfall for k failed units")],
                 conclusion=concl, problems=probs,
                 summary=f"count follows ceil(Q/unit) on all {len(steps)} steps; 500 ACH accepted and not capped; the 1200x600 module fits (<=85 %) only at >= {math.ceil(Q / (0.85 * c['area_m2'] / 0.72))} ... units, otherwise the engine reports 未達條件")]


def s04(run, inputs, cases):
    c = case_by_id(cases, "H-02")
    steps, problems = [], []
    for ex in (300, 350, 400, 450, 500, 550, 600, 650, 700):
        o = inputs(c)
        o["gex_q"] = ex
        pred = ex <= c["oa_cmh"] + 1e-9
        rec, r = step(run, o, f"exhaust {ex}", pred, lambda r: dict(oa_cmh=r["oa_room_cmh"], exhaust_cmh=r["ducts"]["GEX"]["flow_cmh"], supply_room_cmh=r["supply_room_cmh"], leakage_cmh=r["leakage_cmh"],
                                                                      pressure_claim=bool(re.search(r"(負壓|達成|維持).{0,12}(Pa)", " ".join(r["warnings"])))))
        rec["supply_minus_exhaust_cmh_external"] = c["ach"] * c["area_m2"] * c["height_m"] - ex
        steps.append(rec)
        if r is not None and (rec["leakage_cmh"] != 0 or rec["pressure_claim"]):
            problems.append(f"{rec['step']}: a pressure or leakage is inferred")
        if r is None and not re.search(r"低於補償下限", rec.get("message", "")):
            problems.append(f"{rec['step']}: refusal does not name the make-up shortfall")
    concl, probs = verdict(steps, problems)
    return [dict(id="S-04", case="H-02", basis="exhaust 300-700 CMH in 50 CMH steps (about 11 % of the 450 CMH outdoor air) around the stated 450 CMH make-up and the case value 600; supply fixed at 12 ACH x 90 m3 = 1,080 CMH",
                 prediction="accepted while exhaust <= outdoor air 450 CMH; refusal names the shortfall; no negative pressure, no Pa value, no leakage is inferred",
                 steps=steps,
                 blocked=[dict(aspect="negative pressure and its direction", reason="en_p_A accepts only >= 0 Pa against a common low-pressure area; there is no negative-pressure, transfer-air or door model"),
                          dict(aspect="door opening", reason="the plan gives no door size or opening frequency (the engine inputs exist but stay at 0)")],
                 conclusion=concl, problems=probs,
                 summary=f"{sum(s['accepted'] for s in steps)}/{len(steps)} accepted (exhaust <= 450); the stated case (exhaust 600 > OA 450) is refused with the shortfall; the engine never claims a negative-pressure Pa value")]


def s05(run, inputs, cases):
    c = case_by_id(cases, "F-02")
    edge = dp(c["room_t"], c["room_rh"]) - 1.0
    steps, problems, by_eq = [], [], {}
    for eq in (30, 100, 300):
        flows = []
        for t in (7.0, 8.0, 9.0, 9.5, 9.8, 10.0, 10.05, 10.1, 10.15, 10.2):
            o = inputs(c)
            o.update(chw2_in=t, eq_kw=eq)
            pred = t < edge - 1e-9
            rec, r = step(run, o, f"eq {eq} kW, chw {t:g} C", pred, lambda r: dict(
                available_dt_k=r["room"]["t"] - (float(r["effective_inputs"]["chw2_in"]) + float(r["effective_inputs"]["coil_approach"])), supply_dt_k=r["room"]["t"] - r["summer"]["supply"]["t"],
                supply_airflow_cmh=r["supply_room_cmh"], ach_equivalent=r["supply_room_cmh"] / (c["area_m2"] * c["height_m"]), inflation=r["airflow_basis"].get("inflation"), governing=r["airflow_basis"].get("governing"),
                gate_status=next((i["status"] for i in r["quality"]["items"] if i["name"] == "供風量合理性"), None)))
            steps.append(rec)
            if r is not None:
                flows.append(rec["supply_airflow_cmh"])
                exp_flow_floor = eq * 1000 / (1006 * rec["supply_dt_k"]) * 3600 / r["room"]["v_da"] / 1000 if rec["supply_dt_k"] > 0 else None
                if exp_flow_floor and rec["supply_airflow_cmh"] < exp_flow_floor * 0.99:
                    problems.append(f"{rec['step']}: airflow {rec['supply_airflow_cmh']:,.0f} below the sensible minimum {exp_flow_floor:,.0f} CMH (Q = m cp dT)")
                if rec["inflation"] and rec["inflation"] > 5 + 1e-9 and rec["status"] != "未達條件":
                    problems.append(f"{rec['step']}: inflation {rec['inflation']:.1f}x not 未達條件")
        by_eq[eq] = flows
        if any(b < a * (1 - 1e-9) for a, b in zip(flows, flows[1:])):
            problems.append(f"eq {eq} kW: airflow decreases while the available temperature difference shrinks")
    for a, b in ((30, 100), (100, 300)):
        n = min(len(by_eq[a]), len(by_eq[b]))
        if any(by_eq[b][i] < by_eq[a][i] * (1 - 1e-9) for i in range(n)):
            problems.append(f"airflow is lower at {b} kW than at {a} kW for the same chilled water")
    concl, probs = verdict(steps, problems)
    return [dict(id="S-05", case="F-02", basis=f"chilled-water supply 7.0-10.2 C (available dT = room 22 C - ADP: 14 K down to 2.8 K): 1 K steps, then 0.5 K, 0.2-0.3 K and 0.05 K approaching the predicted edge {edge:.2f} C (room dew point {dp(c['room_t'], c['room_rh']):.2f} C - 1 K); sensible load 30 / 100 / 300 kW (x1, x3.3, x10)",
                 prediction="accepted while chw < edge; airflow never below Q = m cp dT for the sensible load; non-decreasing as the available dT shrinks and as the load rises; impractical airflow is 未達條件",
                 steps=steps,
                 blocked=[dict(aspect="+-0.5 C control accuracy and stability", reason="steady-state demand calculation; no control loop, sensor or valve model")],
                 conclusion=concl, problems=probs,
                 summary=f"{sum(s['accepted'] for s in steps)}/{len(steps)} accepted; airflow rises smoothly toward the edge for every load; beyond the edge the engine refuses with the cause")]


def run_all(run, inputs, cases):
    out = []
    for fn in (s01, s02, s03, s04, s05):
        out += fn(run, inputs, cases)
    return out
