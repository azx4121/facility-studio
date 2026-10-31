"""Group C: metamorphic relations. Change one condition; the answer must move the way physics says."""
import sys; sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import collections
import json
import random

from fs_lib import FIELDS, NUMERIC, SYSTEMS, DEFAULT, run

rng = random.Random(77)
results = collections.OrderedDict()


def record(name, n, fail, examples, note=""):
    results[name] = dict(n=n, fail=fail, examples=examples[:3], note=note)
    print(f"{'PASS' if fail == 0 and n else ('NO DATA' if not n else 'FAIL'):7} {name:46} n={n:5d} fail={fail:4d} {examples[:2] if fail else ''} {note}")


def base_case(system=None):
    return dict(sys_type=system or SYSTEMS[1], oa_t=rng.uniform(28, 40), oa_rh=rng.uniform(50, 85), ra_t=rng.choice((22, 23, 24)), ra_rh=rng.choice((45, 50, 55)),
                eq_kw=rng.uniform(10, 120), chw2_in=rng.uniform(6, 8), en_L_A=rng.uniform(15, 40), en_W_A=rng.uniform(10, 30), ppl_A=rng.randint(0, 40))


def valid(**o):
    st, r = run(**o)
    return r if st == "ok" else None


# C1 chilled-water temperature rise doubles -> pump flow halves (exact), coil load unchanged
n = fail = 0; ex = []
for _ in range(200):
    c = base_case(); c["dt_chw"] = rng.choice((4, 5, 6))
    a, b = valid(**c), valid(**{**c, "dt_chw": c["dt_chw"] * 2})
    if not a or not b or a["water"]["CHW"]["lpm"] <= 0:
        continue
    n += 1
    ratio = b["water"]["CHW"]["lpm"] / a["water"]["CHW"]["lpm"]
    load_same = abs(b["water"]["CHW"]["load_kw"] - a["water"]["CHW"]["load_kw"]) < 1e-9
    if abs(ratio - 0.5) > 1e-9 or not load_same:
        fail += 1; ex.append((round(ratio, 6), load_same, c["dt_chw"]))
record("C1 dT_chw x2 -> flow x0.5, load unchanged", n, fail, ex)

# C2 hotter / more humid outdoor air -> summer cooling load never decreases
for driver, lo, hi in (("oa_t", 25, 42), ("oa_rh", 30, 95)):
    n = fail = 0; ex = []
    for _ in range(80):
        c = base_case(); series = []
        for v in [lo + (hi - lo) * i / 8 for i in range(9)]:
            r = valid(**{**c, driver: v})
            if r: series.append((v, r["q_total_kw"]))
        for (v1, q1), (v2, q2) in zip(series, series[1:]):
            n += 1
            if q2 < q1 - 1e-9:
                fail += 1; ex.append((driver, round(v1, 1), round(q1, 2), round(v2, 1), round(q2, 2)))
    record(f"C2 {driver} up -> coincident cooling kW non-decreasing", n, fail, ex)

# C3 lower atmospheric pressure (altitude) -> larger volumetric supply for the same sensible load
n = fail = 0; ex = []
for _ in range(150):
    c = base_case(SYSTEMS[1]); prev = None
    for p in (101.325, 95, 90, 85, 80, 75, 70):
        r = valid(**{**c, "atm_kpa": p})
        if r and prev is not None:
            n += 1
            if r["supply_room_cmh"] < prev - 1e-6: fail += 1; ex.append((p, prev, r["supply_room_cmh"]))
        prev = r["supply_room_cmh"] if r else prev
record("C3 pressure down -> supply CMH non-decreasing", n, fail, ex)

# C4 equipment heat up -> room sensible, supply air and chilled-water flow non-decreasing; and it is affine in eq_kw
n = fail = 0; ex = []; naff = faff = 0; exa = []
for _ in range(150):
    c = base_case(); vals = []
    for kw in (0, 20, 40, 80, 160):
        r = valid(**{**c, "eq_kw": kw})
        if r: vals.append((kw, r["qs"], r["supply_room_cmh"], r["water"]["CHW"]["lpm"]))
    for a, b in zip(vals, vals[1:]):
        n += 1
        if b[1] < a[1] - 1e-9 or b[2] < a[2] - 1e-6 or b[3] < a[3] - 1e-9: fail += 1; ex.append((a, b))
    q = {v[0]: v[1] for v in vals}
    if {0, 20, 40} <= q.keys():
        naff += 1
        if abs((q[40] - q[20]) - (q[20] - q[0])) > 1e-9: faff += 1; exa.append((q[0], q[20], q[40]))
record("C4 eq_kw up -> qs/supply/flow non-decreasing", n, fail, ex)
record("C4b qs is affine in eq_kw", naff, faff, exa)

# C5 feasibility is monotone: if a design is infeasible with chilled water at X, warmer water must also be infeasible
n = fail = 0; ex = []
for _ in range(150):
    c = base_case(); feas = []
    for t in (5, 6, 7, 8, 9, 10, 11, 12):
        feas.append((t, valid(**{**c, "chw2_in": t}) is not None))
    seen_infeasible = False
    for t, ok in feas:
        if not ok: seen_infeasible = True
        elif seen_infeasible:
            fail += 1; ex.append(feas); break
    n += 1
record("C5 warmer chilled water never restores feasibility", n, fail, ex)

# C6 inactive fields must not change any output
def core(r):
    return json.dumps({k: v for k, v in r.items() if k not in ("project", "effective_inputs", "inactive_fields", "hash")}, sort_keys=True, ensure_ascii=False, default=str)

n = fail = 0; ex = []; per_system = collections.Counter()
for system in SYSTEMS:
    base = valid(sys_type=system)
    ref = core(base)
    for key in base["inactive_fields"]:
        f = NUMERIC.get(key)
        if not f: continue
        d = float(DEFAULT[key]) if DEFAULT[key] not in ("", None) else f["low"]
        for v in (f["low"], f["high"], (f["low"] + f["high"]) / 2, d * 1.5 + 1 if d * 1.5 + 1 <= f["high"] else f["low"]):
            st, r = run(sys_type=system, **{key: v})
            n += 1
            if st != "ok" or core(r) != ref:
                fail += 1; per_system[system[:3]] += 1
                if len(ex) < 6: ex.append((system[:3], key, v, st))
record("C6 inactive fields never change outputs", n, fail, ex, note=f"by system {dict(per_system)}")

# C7 determinism and language invariance
from facility_studio import api, i18n
n = fail = 0; ex = []
for _ in range(60):
    c = base_case(rng.choice(SYSTEMS)); st, r1 = run(**c)
    if st != "ok": continue
    n += 1
    s1 = core(r1)
    i18n.set_language("en", persist=False)
    st2, r2 = run(**c)
    i18n.set_language("zh-Hant", persist=False)
    st3, r3 = run(**c)
    num = lambda r: sorted(v for _, v in __import__("fs_lib").numbers(r))
    if core(r3) != s1 or st2 != "ok" or num(r2) != num(r1):
        fail += 1; ex.append(c["sys_type"][:3])
record("C7 repeat + English give identical numbers", n, fail, ex)

json.dump(results, open(sys.argv[1] if len(sys.argv) > 1 else "stress_c.json", "w"), ensure_ascii=False, indent=1)
