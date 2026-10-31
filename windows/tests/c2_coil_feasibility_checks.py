"""Cooling-coil (C2) feasible region: every reported operating point must be self-consistent.

An independent dense scan of the admissible ADP interval (written here, not shared with the
engine) classifies each case as direct, reheat or infeasible; the solver must agree.
"""

import copy
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from facility_studio import api as a
from facility_studio.ahu_schema import NM_DEFAULTS
from facility_studio.engine import solve_c2_bypass
from facility_studio.errors import ValidationError
from facility_studio.schema import default_project
from facility_studio.utils import dewpoint, state_trh, state_tw

checks = []
P = 101.325
# Keys returned by the previous (v2) solve_c2_bypass; callers may read any of them.
V2_KEYS = {"tc", "direct_tc", "achievable_without_reheat", "adp_req_c", "bf_req", "bf_min",
           "low_bf_warning", "tdp", "t_at_a2", "feasible_adp"}


def check(name, ok, detail=""):
    checks.append(dict(name=name, passed=bool(ok), detail=str(detail)[:240]))


def coil_point(s1, wc, adp_t):
    sat = state_trh(adp_t, 100, P)
    bf = (wc - sat["w"]) / (s1["w"] - sat["w"])
    h = bf * s1["h"] + (1 - bf) * sat["h"]
    return bf, (h - 2501 * wc) / (1.006 + 1.86 * wc)


def solve(s1, ts, wc, a2, **kw):
    try:
        return solve_c2_bypass(s1, ts, wc, a2, P, **kw), None
    except ValidationError as e:
        return None, e


# 1. Reported case: inlet 22.192 °C / 50.86 %, wc 8.184 g/kg, ts 12.208 °C, a2 8 °C.
s1, wc, ts = state_trh(22.192, 50.86, P), 0.008184, 12.208
for reheat in ("1", "0"):
    r, err = solve(s1, ts, wc, 8.0, allow_reheat=reheat, bf_min=0.15)
    check(f"BF floor 0.15, reheat={reheat}: no admissible path is reported", err is not None and "再熱無法解決" in str(err), err)
r, _ = solve(s1, ts, wc, 8.0, allow_reheat="1", bf_min=0.15, raise_on_infeasible=False)
check("non-raising mode marks the case infeasible without ADP/BF", r and r["path"] == "infeasible" and not r["feasible_adp"]
      and r["adp_req_c"] is None and r["bf_req"] is None, r and r["path"])
lo, hi = 8.0, dewpoint(wc, P)
for _ in range(80):
    mid = 0.5 * (lo + hi)
    lo, hi = (mid, hi) if coil_point(s1, wc, mid)[0] >= 0.15 else (lo, mid)
check("reported minimum outlet equals the BF=0.15 coil point", r and abs(r["t_min_reachable"] - coil_point(s1, wc, lo)[1]) < 1e-6,
      (r and r["t_min_reachable"], coil_point(s1, wc, lo)[1]))
r, _ = solve(s1, ts, wc, 8.0, allow_reheat="1", bf_min=0.0)
check("no BF floor: direct path with BF 0.10998", r and r["path"] == "direct" and abs(r["bf_req"] - 0.10998) < 5e-5, r and r["bf_req"])
check("no BF floor is reported as pending equipment data", r and r["bf_min"] == 0 and "待資料" in r["bf_basis"])
r_none, _ = solve(s1, ts, wc, 8.0, allow_reheat="1")
check("bf_min omitted behaves as not provided", r_none and r_none["bf_min"] == 0 and r_none["path"] == "direct")
r, _ = solve(s1, ts, wc, 8.0, allow_reheat="1", bf_min=0.10)
check("BF floor below the direct requirement: direct with stated basis", r and r["path"] == "direct" and r["bf_basis"] == "專案指定")
r, _ = solve(s1, 21.0, wc, 8.0, allow_reheat="1", bf_min=0.15)
check("target above warmest outlet: reheat from the warmest admissible point", r and r["path"] == "reheat" and r["tc"] < 21.0)
r, err = solve(s1, 21.0, wc, 8.0, allow_reheat="0", bf_min=0.15)
check("reheat needed but not allowed is rejected on allow_reheat", err is not None and err.field_name == "allow_reheat", err)
r, err = solve(s1, ts, wc, 8.0, allow_reheat="1", bf_min=0.9)
check("BF floor above BF(a2) cannot dehumidify", err is not None and "無法除濕" in str(err), err)
r, err = solve(s1, ts, wc, 12.0, allow_reheat="1", bf_min=0.0)
check("dew point below chilled-water limit is rejected", err is not None and "露點" in str(err), err)

# English rendering of every new message has no untranslated Chinese.
import re
from facility_studio import i18n
messages = []
for kw in (dict(ts=12.208, bf_min=0.15), dict(ts=12.208, bf_min=0.9), dict(ts=21.0, bf_min=0.15, allow_reheat="0")):
    kw.setdefault("allow_reheat", "1")
    _, err = solve(s1, kw.pop("ts"), wc, 8.0, **kw)
    messages.append(str(err))
cjk = [m for m in messages if re.search(r"[\u3400-\u9fff]", i18n.translate(m, "en"))]
check("infeasible coil messages translate fully to English", not cjk, [i18n.translate(m, "en") for m in cjk])

# Caller compatibility: every path returns the previous keys; infeasible non-raising results
# carry no ADP/BF and an unsaturated placeholder outlet.
compat = []
for label, ts_, a2_, bf_, rh_ in (("direct", ts, 8.0, 0.0, "1"), ("reheat", 21.0, 8.0, 0.15, "1"),
                                   ("below reach", ts, 8.0, 0.15, "1"), ("BF(a2) short", ts, 8.0, 0.9, "1"),
                                   ("dew point < a2", ts, 12.0, 0.0, "1"), ("reheat not allowed", 21.0, 8.0, 0.15, "0")):
    r, err = solve(s1, ts_, wc, a2_, allow_reheat=rh_, bf_min=bf_, raise_on_infeasible=False)
    if err is not None or not V2_KEYS <= set(r):
        compat.append((label, "raised" if err else sorted(V2_KEYS - set(r))))
        continue
    try:
        state_tw(r["tc"], wc, P)
    except ValidationError as e:
        compat.append((label, "saturated placeholder", e))
    if not r["feasible_adp"] and (r["adp_req_c"] is not None or r["bf_req"] is not None or r["low_bf_warning"]):
        compat.append((label, "infeasible result carries ADP/BF"))
    if r["feasible_adp"] and r["low_bf_warning"] != (r["bf_req"] < 0.05):
        compat.append((label, "low_bf_warning inconsistent"))
r, _ = solve(s1, ts, wc, 12.0, allow_reheat="1", bf_min=0.0, raise_on_infeasible=False)
check("dew point below a2 keeps t_at_a2 = tdp as before", r and abs(r["t_at_a2"] - r["tdp"]) < 1e-12)
check("all paths keep the previous return keys and valid placeholders", not compat, compat)
r, _ = solve(s1, 21.0, wc, 8.0, allow_reheat="0", bf_min=0.15, raise_on_infeasible=False)
check("reheat not allowed (non-raising): admissible coil point, flagged for the reheat stage",
      r and r["feasible_adp"] and r["path"] == "reheat_required" and not r["achievable_without_reheat"]
      and r["reason"] and r["adp_req_c"] is not None, r and r["path"])

# 2. Independent dense scan versus solver over random cases.
random.seed(20261030)
stats = dict(compared=0, direct=0, reheat=0, reheat_required=0, infeasible=0, beyond_t_at_a2=0, bypass_line_crosses_saturation=0, boundary_skipped=0)
mismatch, inconsistent = [], []
while stats["compared"] < 1500:
    t1 = random.uniform(8, 38)
    s = state_trh(t1, random.uniform(35, 99.5), P)
    w = s["w"] * random.uniform(0.55, 0.98)
    tdp = dewpoint(w, P)
    a2 = random.uniform(max(-2.0, tdp - 9), tdp - 0.3)
    bf_min = random.choice([None, 0.0, 0.03, 0.08, 0.12, 0.2, 0.3])
    lim = bf_min or 0.0
    grid = [a2 + (tdp - a2) * k / 4000 * 0.99999 for k in range(4001)]
    # Admissible: BF floor met and an unsaturated outlet (bypass lines may cross saturation).
    adm = [(x,) + coil_point(s, w, x) for x in grid
           if coil_point(s, w, x)[0] >= lim and coil_point(s, w, x)[1] >= tdp - 1e-9]
    if lim == 0:  # without a stated floor the ideal end point A = tdp (BF = 0) is admissible
        adm.append((tdp, 0.0, tdp))
    target = random.uniform(tdp - 1, t1 + 1)
    reheat = random.choice(["1", "0"])
    if a2 > tdp:  # chilled water cannot reach the required dew point
        adm = []
    if adm:
        tmin, tmax = min(t for _, _, t in adm), max(t for _, _, t in adm)
        if min(abs(target - tmin), abs(target - tmax)) < 0.01:
            stats["boundary_skipped"] += 1
            continue
        expected = "infeasible" if target < tmin else "direct" if target <= tmax else ("reheat" if reheat == "1" else "reheat_required")
    else:
        expected = "infeasible"
    r, err = solve(s, target, w, a2, allow_reheat=reheat, bf_min=bf_min, raise_on_infeasible=False)
    if err is not None:
        mismatch.append(("raised", str(err)[:60]))
        continue
    stats["compared"] += 1
    stats[expected] += 1
    if r["path"] != expected:
        mismatch.append((expected, r["path"], round(t1, 2), round(w * 1000, 3), round(a2, 2), bf_min, round(target, 3)))
        continue
    if expected == "direct" and target > coil_point(s, w, a2)[1] + 0.01:
        stats["beyond_t_at_a2"] += 1
    if coil_point(s, w, a2)[1] < tdp:
        stats["bypass_line_crosses_saturation"] += 1
    try:
        state_tw(r["tc"], w, P)
    except ValidationError:
        inconsistent.append(("saturated tc", round(t1, 2), round(w * 1000, 3), round(a2, 2), bf_min, round(target, 3)))
    if not r["feasible_adp"] and (r["adp_req_c"] is not None or r["bf_req"] is not None):
        inconsistent.append(("infeasible with ADP/BF", round(t1, 2)))
    if r["feasible_adp"]:
        bf_chk, t_chk = coil_point(s, w, r["adp_req_c"])
        ok = (abs(t_chk - r["tc"]) < 1e-6 and abs(bf_chk - r["bf_req"]) < 1e-9 and r["bf_req"] >= lim - 1e-9
              and a2 - 1e-9 <= r["adp_req_c"] <= tdp + 1e-9 and r["tc"] <= target + 1e-6)
        if expected == "direct":
            ok = ok and abs(r["tc"] - target) < 1e-6
            roots = [bf0 + (bf1 - bf0) * (target - t0) / (t1_ - t0)
                     for (_, bf0, t0), (_, bf1, t1_) in zip(adm, adm[1:]) if (t0 - target) * (t1_ - target) <= 0 and t1_ != t0]
            ok = ok and bool(roots) and r["bf_req"] >= max(roots) - 1e-3
        else:
            ok = ok and abs(r["tc"] - tmax) < 1e-3
        if not ok:
            inconsistent.append((expected, round(t1, 2), round(w * 1000, 3), round(a2, 2), bf_min, round(target, 3)))
check("solver path agrees with independent scan", not mismatch, f"{len(mismatch)} e.g. {mismatch[:3]}")
check("every feasible point is self-consistent and respects ADP/BF limits", not inconsistent, f"{len(inconsistent)} e.g. {inconsistent[:3]}")
check("sweep covers direct, reheat and infeasible cases", all(stats[k] > 50 for k in ("direct", "reheat", "infeasible", "reheat_required")), stats)
check("direct cases above t(a2) (non-monotonic outlet) are found", stats["beyond_t_at_a2"] > 0, stats)
check("sweep includes bypass lines crossing saturation", stats["bypass_line_crosses_saturation"] > 50, stats)

# 3. Engine and AHU integration: missing BF floor is pending, not passed.
p = default_project()
r = a.calculate(p)
c2 = r["summer"]["c2"]
dehumid = "bf_min" in c2 and c2["air_kw"] > 1e-8
check("default project dehumidifies at the cooling coil", dehumid, c2.get("bf_min"))
items = {x["name"]: x["status"] for x in r["quality"]["items"]}
check("missing BF floor appears as pending coil capacity", any("排數能力" in k and v == "待資料" for k, v in items.items()), items)
pending = [x for x in r["quality"]["items"] if "排數能力" in x["name"]]
check("pending coil capacity item translates fully to English",
      pending and not any(re.search(r"[\u3400-\u9fff]", i18n.translate(x["name"] + x["detail"], "en")) for x in pending),
      [i18n.translate(x["name"] + " " + x["detail"], "en") for x in pending])
q = copy.deepcopy(p)
q["inputs"]["c2_bf_min"] = "0.05"
r2 = a.calculate(q)
check("stated BF floor removes the pending item",
      not any("排數能力" in x["name"] for x in r2["quality"]["items"]) and r2["summer"]["c2"]["bf_min"] == 0.05)
q["inputs"]["c2_bf_min"] = "0.5"
try:
    a.calculate(q)
    check("unreachable BF floor stops the main calculation", False, "accepted")
except ValidationError as e:
    check("unreachable BF floor stops the main calculation", "BF" in str(e), e)
ahu = a.nm_calculate(dict(NM_DEFAULTS))
ahu_c2 = ahu["summer"]["c2"]
if "bf_min" in ahu_c2 and ahu_c2["air_kw"] > 1e-8:
    check("AHU coil without BF floor is pending",
          any("排數能力" in x["name"] and x["status"] == "待資料" for x in ahu["quality"]["items"]))
else:
    check("AHU default scenario dehumidifies (needed for the pending check)", False, ahu_c2.get("air_kw"))

# AHU caller with raise_on_infeasible=False: chilled water too warm for the target dew point.
warm = dict(NM_DEFAULTS, c2_in="16", c2_out="21", c2_adp="1")
try:
    res = a.nm_calculate(warm)
    adp_checks = {k: v for k, v in res["summer"]["checks"].items() if "C2" in k and "ADP" in k}
    check("AHU completes when the C2 path is infeasible", True)
    check("AHU reports the infeasible C2 as not met", adp_checks and not all(adp_checks.values()), adp_checks)
except ValidationError as e:
    check("AHU completes when the C2 path is infeasible", False, e)

failed = [c for c in checks if not c["passed"]]
(ROOT / "evidence").mkdir(exist_ok=True)
(ROOT / "evidence" / "C2_Coil_Feasibility_Checks.json").write_text(
    json.dumps(dict(checks=checks, sweep=stats), ensure_ascii=False, indent=2), encoding="utf-8")
for c in failed:
    print("FAIL", c["name"], c["detail"])
print(f"C2 coil feasibility checks: {len(checks) - len(failed)}/{len(checks)} passed; sweep {stats}")
sys.exit(1 if failed else 0)
