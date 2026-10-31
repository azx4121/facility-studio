"""Same 4000 random AHU projects against two source trees; the measures use only result fields both trees have."""
import json, random, sys, collections
sys.path.insert(0, "/home/user/facility-studio/Source/windows/tests/feed_stress")  # fs_lib reads FS_SRC (the tree under test)
from fs_lib import SYSTEMS, run
from facility_studio.utils import state_trh
rng = random.Random(2026)
c = collections.Counter(); extreme = []
for k in range(4000):
    o = dict(sys_type=SYSTEMS[1], oa_t=rng.uniform(25, 46), oa_rh=rng.uniform(20, 100), ra_t=rng.choice((20, 22, 24)), ra_rh=rng.choice((30, 40, 50, 60)), chw2_in=rng.uniform(5, 12),
             eq_kw=rng.uniform(0, 200), en_L_A=rng.uniform(10, 80), en_W_A=rng.uniform(8, 50), en_H_A=rng.uniform(3, 6), ppl_A=rng.randint(0, 100))
    st, r = run(**o)
    if st != "ok":
        c["rejected"] += 1
        if "任何風量都無法除濕" in str(r): c["rejected: no airflow can dehumidify (explicit cause)"] += 1
        elif "無法求得" in str(r): c["rejected: generic 'cannot solve airflow'"] += 1
        elif "冷卻盤管無法除濕" in str(r) or "冷卻盤管所需露點" in str(r): c["rejected: later coil solver"] += 1
        continue
    c["accepted"] += 1
    e = r["effective_inputs"]; P = float(e["atm_kpa"]); room, oa = r["room"], r["oa"]
    minw = state_trh(float(e["chw2_in"]) + float(e["coil_approach"]), 100, P)["w"]
    m = r["summer"]["mass"]; lam = r["oa_mass"] * (oa["w"] - room["w"]) + r["moisture"]
    ws = room["w"] - r["moisture"] / m
    m_floor = max(r["circulation_cmh"] / room["v_da"] / 3600, r["oa_mass"], 1e-8)
    m_start = max(m_floor, abs(r["qs"]) / 10, r["moisture"] / 0.002)
    infl = m / m_start
    status = r["quality"]["status"]
    if not (lam <= 1e-12 or ws >= minw - 1e-12):
        c["accepted but physically impossible (coil cannot reach the supply humidity)"] += 1
        if status != "未達條件": c["   ...of which status NOT 未達條件"] += 1
    if infl > 5.0 + 1e-9:
        c["accepted with airflow > 5x baseline"] += 1
        if status != "未達條件": c["   ...of which status NOT 未達條件 (silent)"] += 1
    if r["supply_room_cmh"] > 1e9: c["accepted with airflow > 1e9 CMH"] += 1
    if infl > 1 + 1e-9: c["moisture/ADP-limited designs solved (airflow above baseline)"] += 1
print(json.dumps(dict(c), ensure_ascii=False, indent=1))
