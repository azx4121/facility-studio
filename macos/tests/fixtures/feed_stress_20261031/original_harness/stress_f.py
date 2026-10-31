"""Group F: hand calculation of every load term from the inputs, and 'never select smaller than required' invariants."""
import sys; sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import collections, json, math, random
from fs_lib import DEFAULT, SYSTEMS, run

rng = random.Random(555)
out = collections.OrderedDict()


class R:
    def __init__(self, name, tol): self.name, self.tol, self.n, self.fail, self.worst, self.ex = name, tol, 0, 0, 0.0, []
    def add(self, dev, tag):
        self.n += 1; self.worst = max(self.worst, abs(dev))
        if abs(dev) > self.tol:
            self.fail += 1
            if len(self.ex) < 3: self.ex.append((round(dev, 6), tag))


rows = {k: R(k, t) for k, t in dict(
    F1_equipment_net=1e-9, F1_people=1e-9, F1_wall=1e-9, F1_floor=1e-9, F1_oven_solar_fan=1e-9, F1_qs_is_sum_of_parts=1e-9,
    F2_ffu_capacity_ge_airflow=0.0, F2_dcc_capacity_ge_load=0.0, F2_rcu_capacity_ge_load=0.0, F2_fcu_capacity_ge_load=0.0, F2_pipe_velocity_within_limit=0.0,
    F3_current_formula_rel=1e-6, F3_design_current_ge_running=0.0, F3_breaker_ge_design_current=0.0, F3_cable_ge_breaker=0.0, F3_cable_ge_design_current=0.0, F3_continuous_load_125pct=0.0, F3_largest_motor_plus_25pct=0.0).items()}

valid = 0
for k in range(1500):
    system = SYSTEMS[k % 4]
    c = dict(sys_type=system, oa_t=rng.uniform(25, 42), ra_t=rng.choice((20, 22, 24, 26)), eq_kw=rng.uniform(0, 150), eq_rt=rng.uniform(40, 100), exh_ratio=rng.uniform(0, 30),
             ppl_A=rng.randint(0, 60), en_wall=rng.uniform(0, 500), wall_u=rng.uniform(0.3, 3.0), en_floor=rng.uniform(0, 500), floor_u=rng.uniform(0.3, 3.5), floor_adj_t=rng.uniform(15, 40),
             oven_kw=rng.choice((0, 0, 5)), solar_kw=rng.choice((0, 0, 3)), fan_room_kw=rng.choice((0, 0, 2)), sf=rng.choice((0, 10, 20)),
             u_unit=rng.choice(("kcal/(h·m²·K)", "W/(m²·K)")), e_np_fan=rng.uniform(5, 80), e_np_heat=rng.choice((0, 15)), e_np_type=rng.choice(('一般負載', '連續負載', '馬達負載')), e_np_largest_hp=rng.choice((0, 5, 10, 25)), water_velocity_max=rng.choice((1.5, 2.0, 2.5, 3.0)))
    st, r = run(**c)
    if st != "ok": continue
    valid += 1
    e = r["effective_inputs"]; f = lambda key: float(e[key]); parts = r["parts"]; tag = f"{system[:3]}"
    uconv = 4.1868 / 3600 if e["u_unit"] == "kcal/(h·m²·K)" else 0.001
    gross = f("eq_kw") * f("eq_rt") / 100
    rows["F1_equipment_net"].add(parts["equipment_net"] - (gross - parts["pcw_removed"] - gross * f("exh_ratio") / 100), tag)
    rows["F1_people"].add(parts["people"] - (f("ppl_A") + f("ppl_B")) * f("people_sensible_w") / 1000, tag)
    rows["F1_wall"].add(parts["wall"] - f("en_wall") * f("wall_u") * (f("oa_t") - f("ra_t")) * uconv, tag)
    rows["F1_floor"].add(parts["floor"] - f("en_floor") * f("floor_u") * (f("floor_adj_t") - f("ra_t")) * uconv, tag)
    rows["F1_oven_solar_fan"].add(abs(parts["oven"] - f("oven_kw")) + abs(parts["solar"] - f("solar_kw")) + abs(parts["fan"] - f("fan_room_kw") - r["ffu_count"] * f("ffu_w") / 1000), tag)
    rows["F1_qs_is_sum_of_parts"].add(r["qs"] - sum(v for kk, v in parts.items() if kk not in ("pcw_removed", "exhaust_removed")), tag)
    sfm = 1 + f("sf") / 100
    rtkw = r["rt_kw"]
    cnt = r["counts"]
    if r["ffu_count"]:
        rows["F2_ffu_capacity_ge_airflow"].add(0.0 if r["ffu_count"] * r["ffu_unit_cmh"] >= r["ffu_total_cmh"] - 1e-6 else 1.0, tag)
    if cnt["DCC"]:
        rows["F2_dcc_capacity_ge_load"].add(0.0 if cnt["DCC"] * f("en_dcc_rt") * rtkw >= r["dcc_design_kw"] * sfm - 1e-9 else 1.0, f"{tag} n={cnt['DCC']} need={r['dcc_design_kw']*sfm:.2f}")
    if cnt["RCU"]:
        rows["F2_rcu_capacity_ge_load"].add(0.0 if cnt["RCU"] * f("en_rcu_rt") * rtkw >= r["terminal_cooling_kw"] * sfm - 1e-9 else 1.0, f"{tag} n={cnt['RCU']} need={r['terminal_cooling_kw']*sfm:.2f}")
    if cnt["FCU"]:
        rows["F2_fcu_capacity_ge_load"].add(0.0 if cnt["FCU"] * f("fcu_rt") * rtkw >= r["terminal_cooling_kw"] * sfm - 1e-9 else 1.0, f"{tag} n={cnt['FCU']} need={r['terminal_cooling_kw']*sfm:.2f}")
    for loop, w in r["water"].items():
        if w["lpm"] > 0 and w["velocity_mps"] > 0:
            over = w["velocity_mps"] > f("water_velocity_max") + 1e-9
            rows["F2_pipe_velocity_within_limit"].add(1.0 if over else 0.0, f"{tag} {loop} {w['velocity_mps']:.2f}>{f('water_velocity_max')} size={w['size']}")
    for pan, d in r["electric"].items():
        if d["kw"] > 0 and d.get("selected") and d["voltage"] == 380.0 and d["pf"] > 0:
            s = d["selected"]
            rows["F3_current_formula_rel"].add((d["current_a"] - d["kw"] * 1000 / (math.sqrt(3) * d["voltage"] * d["pf"])) / d["current_a"] if not d["has_motor"] and d.get("hp", 0) == 0 else 0.0, f"{tag} {pan}")
            rows["F3_design_current_ge_running"].add(0.0 if d["design_current_a"] >= d["current_a"] - 1e-9 else 1.0, f"{tag} {pan}")
            rows["F3_breaker_ge_design_current"].add(0.0 if s["nfb_candidate_a"] >= d["design_current_a"] - 1e-9 else 1.0, f"{tag} {pan} nfb={s['nfb_candidate_a']} design={d['design_current_a']:.1f}")
            rows["F3_cable_ge_breaker"].add(0.0 if s["iz_a"] >= s["nfb_candidate_a"] - 1e-9 else 1.0, f"{tag} {pan} iz={s['iz_a']} nfb={s['nfb_candidate_a']}")
            if d["kind"] == "連續負載":
                rows["F3_continuous_load_125pct"].add(0.0 if d["design_current_a"] >= 1.25 * d["current_a"] - 1e-9 else 1.0, f"{tag} {pan} design={d['design_current_a']:.2f} run={d['current_a']:.2f}")
            if d["has_motor"] and d.get("largest_hp", 0) > 0:
                hpkw = 0.745699871582 / d["eff"]  # motor electrical input per HP
                exp = d["current_a"] + 0.25 * d["largest_hp"] * hpkw * 1000 / (math.sqrt(3) * d["voltage"] * d["pf"])
                rows["F3_largest_motor_plus_25pct"].add(0.0 if d["design_current_a"] >= exp - 1e-6 else 1.0, f"{tag} {pan} design={d['design_current_a']:.2f} need={exp:.2f}")
            rows["F3_cable_ge_design_current"].add(0.0 if s["iz_a"] >= d["design_current_a"] - 1e-9 else 1.0, f"{tag} {pan}")

print("valid cases", valid)
for k, r in rows.items():
    flag = "PASS" if r.fail == 0 and r.n else ("NO DATA" if not r.n else "FAIL")
    print(f"{flag:7} {k:36} n={r.n:6d} fail={r.fail:5d} worst={r.worst:.3g} {r.ex[:2] if r.fail else ''}")
json.dump({k: dict(n=r.n, fail=r.fail, worst=r.worst, examples=r.ex) for k, r in rows.items()}, open(sys.argv[1] if len(sys.argv) > 1 else "stress_f.json", "w"), ensure_ascii=False, indent=1)
