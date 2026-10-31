"""Groups A and B: independent oracles on valid results.
A: every moist-air state against PsychroLib (ASHRAE).  B: balances and hydraulics recomputed from first principles."""
import sys; sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import collections
import json
import math
import random

import psychrolib

from fs_lib import SYSTEMS, run, states

psychrolib.SetUnitSystem(psychrolib.SI)
rng = random.Random(31102026)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 1200

CLIMATES = {  # summer dry bulb / RH, winter dry bulb / RH, pressure kPa
    "hot_humid_default": (35, 70, 8, 70, 101.325),
    "tropical_wet": (33, 90, 22, 85, 101.325),
    "desert_dry": (46, 15, -5, 40, 95),
    "cold_continental": (30, 50, -25, 60, 100),
    "high_altitude_3000m": (28, 50, -10, 40, 70),
    "marine_saturated": (30, 100, 5, 100, 101.325),
    "mild": (26, 55, 10, 65, 101.325),
}


class Stat:
    def __init__(self, tol):
        self.tol, self.n, self.fail, self.worst, self.examples = tol, 0, 0, 0.0, []

    def add(self, dev, tag):
        self.n += 1
        self.worst = max(self.worst, abs(dev))
        if abs(dev) > self.tol:
            self.fail += 1
            if len(self.examples) < 3:
                self.examples.append((round(dev, 6), tag))


S = {k: Stat(t) for k, t in dict(
    A_enthalpy_kJkg=0.05, A_volume_m3kg=0.001, A_rh_pct=0.3, A_density_identity=1e-6, A_no_supersaturation=1e-5,
    B1_coil_air_kw=1e-5, B2_coil_water_kw=1e-5, B3_condensate_kg_s=1e-9, B4_liquid_enthalpy_sign=0.0, B4b_liquid_heat_magnitude=0.0,
    B5_water_lpm_rel=1e-6, B5b_capacity_ge_load=0.0, B5c_capacity_eq_load=1e-9, B5d_chw_load_eq_coil_x_margin=1e-6, B6_velocity_rel=1e-6, B6b_area_rel=1e-6,
    B7_reynolds_rel=1e-6, B7_friction_factor_rel=0.02, B7_friction_pa_rel=0.02, B7_local_pa_rel=1e-6, B7_total_pa_rel=1e-6,
    B8_room_sensible_rel=0.02, B9_oa_mass_rel=0.01, B10_rt_conversion_rel=1e-4,
).items()}


def colebrook(re, rel_rough):
    if re < 2300:
        return 64 / re
    f = 0.02
    for _ in range(60):
        f_new = (-2 * math.log10(rel_rough / 3.7 + 2.51 / (re * math.sqrt(f)))) ** -2
        if abs(f_new - f) < 1e-12:
            break
        f = f_new
    return f


def climate_case():
    name = rng.choice(list(CLIMATES))
    st, sr, wt, wr, p = CLIMATES[name]
    j = lambda x, s: x + rng.uniform(-s, s)
    over = dict(sys_type=SYSTEMS[len(done) % 4], atm_kpa=p, oa_t=j(st, 2), oa_rh=min(100, max(0, j(sr, 8))), ow_t=j(wt, 3), ow_rh=min(100, max(0, j(wr, 8))),
                ra_t=rng.choice((20, 22, 23, 24, 26)), ra_rh=rng.choice((35, 40, 45, 50, 55, 60)),
                chw2_in=rng.uniform(5, 10), dt_chw=rng.choice((4, 5, 6, 7)), eq_kw=rng.uniform(0, 150), sf=rng.choice((0, 10, 15, 20)),
                en_L_A=rng.uniform(10, 60), en_W_A=rng.uniform(8, 40), en_H_A=rng.uniform(3, 6), en_ach_A=rng.uniform(0, 60), ppl_A=rng.randint(0, 80))
    return name, over


done = []
by_climate = collections.Counter()
tries = 0
while len(done) < N and tries < N * 6:
    tries += 1
    name, over = climate_case()
    status, res = run(**over)
    if status != "ok":
        by_climate[name + ":rejected"] += 1
        continue
    by_climate[name + ":ok"] += 1
    done.append((name, over, res))
    tag = f"{name}|{over['sys_type'][:3]}"
    P = res["effective_inputs"]["atm_kpa"]
    P = float(P) * 1000

    # A. every state against PsychroLib
    for path, s in states(res):
        t, w = s["t"], s["w"]
        try:
            ws = psychrolib.GetHumRatioFromRelHum(t, 1.0, P)
            S["A_enthalpy_kJkg"].add(s["h"] - psychrolib.GetMoistAirEnthalpy(t, w) / 1000, tag + path)
            S["A_volume_m3kg"].add(s["v_da"] - psychrolib.GetMoistAirVolume(t, w, P), tag + path)
            if w <= ws * (1 - 1e-9) and s["rh"] < 99.9:
                S["A_rh_pct"].add(s["rh"] - psychrolib.GetRelHumFromHumRatio(t, w, P) * 100, tag + path)
            S["A_density_identity"].add(s["rho_moist"] - (1 + w) / s["v_da"], tag + path)
            S["A_no_supersaturation"].add(max(0.0, w - ws), tag + path)
        except Exception:  # state outside PsychroLib's range
            pass

    # B. coils
    for season in ("summer", "winter"):
        sea = res[season]
        mass = sea.get("mass") or 0
        for cname in ("c1", "c2"):
            c = sea.get(cname)
            if not c or "air_kw" not in c:
                continue
            exp_air = mass * (c["inlet"]["h"] - c["outlet"]["h"])
            S["B1_coil_air_kw"].add(c["air_kw"] - exp_air, f"{tag}|{season}.{cname}")
            S["B2_coil_water_kw"].add(c["water_kw"] - (c["air_kw"] - c["liquid_kw"]), f"{tag}|{season}.{cname}")
            S["B3_condensate_kg_s"].add(c["condensate_kg_s"] - max(0.0, mass * (c["inlet"]["w"] - c["outlet"]["w"])), f"{tag}|{season}.{cname}")
            if c["condensate_kg_s"] > 1e-9:
                # condensate leaves between the coil outlet and inlet temperature: its enthalpy must be c*4.1868*T for such a T
                t_eq = c["liquid_kw"] / (c["condensate_kg_s"] * 4.1868)
                lo, hi = c["outlet"]["t"] - 4, c["outlet"]["t"] + 0.01  # condensate leaves at about the coil-outlet air temperature
                S["B4b_liquid_heat_magnitude"].add(0.0 if lo <= t_eq <= hi else 1.0, f"{tag}|{season}.{cname}|T_cond={t_eq:.1f} outside [{lo:.1f},{hi:.1f}]")
            S["B4_liquid_enthalpy_sign"].add(0.0 if c["liquid_kw"] >= -1e-12 else 1.0, f"{tag}|{season}.{cname}")

    # B. water loops and hydraulics
    for loop, w in res["water"].items():
        fp = w["fluid_properties"]
        if loop == "CHW" and w["load_kw"] > 0 and res["water"].get("MCHW", {}).get("load_kw", 0) == 0:
            sf = float(res["effective_inputs"]["sf"])
            coil = max((res[sn][cn]["water_kw"] for sn in ("summer", "winter") for cn in ("c1", "c2") if cn in res[sn] and "water_kw" in res[sn][cn]), default=0)
            S["B5d_chw_load_eq_coil_x_margin"].add((w["load_kw"] - coil * (1 + sf / 100)) / w["load_kw"], f"{tag}|CHW")
        if w["lpm"] > 0 and w["delta_t"] > 0:
            S["B5c_capacity_eq_load"].add((w["capacity_kw"] - w["load_kw"]) / w["load_kw"], f"{tag}|{loop}")
            exp = w["load_kw"] * 60 / ((fp["rho"] / 1000) * fp["cp"] * w["delta_t"])
            S["B5_water_lpm_rel"].add((w["lpm"] - exp) / exp, f"{tag}|{loop}")
            S["B5b_capacity_ge_load"].add(0.0 if w["capacity_kw"] >= w["load_kw"] - 1e-9 else 1.0, f"{tag}|{loop}")
            if w["area_m2"] > 0 and w["runs"] > 0 and w["velocity_mps"] > 0:
                S["B6_velocity_rel"].add((w["velocity_mps"] - w["lpm"] / 60000 / (w["area_m2"] * w["runs"])) / w["velocity_mps"], f"{tag}|{loop}|water")
    for loop, p in res["pressure"].items():
        if p["flow_m3s"] <= 0 or p["id_m"] <= 0:
            continue
        a_exp = math.pi / 4 * p["id_m"] ** 2
        S["B6b_area_rel"].add((p["area_m2"] - a_exp) / a_exp, f"{tag}|{loop}")
        v_exp = p["flow_m3s"] / (p["runs"] * a_exp)
        S["B6_velocity_rel"].add((p["velocity_mps"] - v_exp) / v_exp, f"{tag}|{loop}")
        re_exp = p["rho"] * v_exp * p["id_m"] / p["mu"]
        S["B7_reynolds_rel"].add((p["re"] - re_exp) / re_exp, f"{tag}|{loop}")
        if p["re"] > 4000 and p.get("mode", "").startswith("Darcy"):
            f_exp = colebrook(re_exp, p["roughness_mm"] / 1000 / p["id_m"])
            S["B7_friction_factor_rel"].add((p["f"] - f_exp) / f_exp, f"{tag}|{loop}|Re={p['re']:.0f}")
            fp_exp = f_exp * p["length_m"] / p["id_m"] * p["rho"] * v_exp ** 2 / 2
            if fp_exp > 0:
                S["B7_friction_pa_rel"].add((p["friction_pa"] - fp_exp) / fp_exp, f"{tag}|{loop}")
        S["B7_total_pa_rel"].add(p["loss_pa"] - (p["friction_pa"] + p["local_pa"] + p["equipment_pa"]) if p["loss_pa"] else 0.0, f"{tag}|{loop}")
        if p["friction_pa"] > 0 and p.get("fitting_mode") == "直接 K 值" and p["sum_k"] == 0:
            # equivalent-length fittings: local loss is the friction rate over the equivalent length
            S["B7_local_pa_rel"].add((p["local_pa"] - p["friction_pa"] * p["equivalent_length_m"] / p["length_m"]) / p["friction_pa"], f"{tag}|{loop}")
    # B. room sensible balance, B9 outdoor air mass, B10 RT conversion
    sea = res["summer"]
    ra_t = float(res["effective_inputs"]["ra_t"])
    if sea.get("mass") and res["qs"] > 0 and over["sys_type"].startswith("AHU") and ra_t - sea["supply"]["t"] > 0.5:
        cp = 1.006 + 1.86 * sea["supply"]["w"]
        S["B8_room_sensible_rel"].add((sea["mass"] * cp * (ra_t - sea["supply"]["t"]) - res["qs"]) / res["qs"], tag)
    if res["minimum_oa_cmh"] > 0 and res["room"]["v_da"] > 0 and res["oa_mass"] > 0:
        # outdoor-air CMH is stated at room conditions ("室內基準 CMH"), so it converts with the room specific volume
        # MAU supplies all-outdoor air: its mass flow follows the full supply airflow, not the minimum fresh-air rate
        basis = res["oa_room_cmh"] if over["sys_type"].startswith("MAU") else res["minimum_oa_cmh"]
        exp = basis / 3600 / res["room"]["v_da"]
        S["B9_oa_mass_rel"].add((res["oa_mass"] - exp) / exp, tag + "|" + over["sys_type"][:3])
    if res["q_total_kw"] > 0:
        S["B10_rt_conversion_rel"].add((res["q_total_kw"] / res["q_total_rt"] - 3.516853) / 3.516853, tag)

rows = {}
for k, st in S.items():
    rows[k] = dict(n=st.n, fail=st.fail, worst=st.worst, tol=st.tol, examples=st.examples)
out = dict(requested=N, valid_cases=len(done), attempts=tries, by_climate=dict(by_climate), checks=rows)
open(sys.argv[2] if len(sys.argv) > 2 else "stress_ab.json", "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
print(f"valid cases {len(done)} / attempts {tries}")
print("climate outcomes:", dict(by_climate))
for k, r in rows.items():
    flag = "PASS" if r["fail"] == 0 and r["n"] else ("NO DATA" if not r["n"] else "FAIL")
    print(f"{flag:7} {k:28} n={r['n']:7d} fail={r['fail']:6d} worst={r['worst']:.3g} (tol {r['tol']:g}) {r['examples'][:2] if r['fail'] else ''}")
