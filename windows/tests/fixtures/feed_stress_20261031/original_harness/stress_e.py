"""Group E: what a reader of the report is told, against the calculation and against thermodynamic hard limits."""
import sys; sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
import collections
import json
import random
import re

from fs_lib import FIELDS, SYSTEMS, numbers, run, states
from facility_studio import api, i18n

rng = random.Random(4242)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
out = collections.OrderedDict()


def record(name, n, fail, examples, note=""):
    out[name] = dict(n=n, fail=fail, examples=examples[:3], note=note)
    print(f"{'PASS' if fail == 0 and n else ('NO DATA' if not n else 'FAIL'):7} {name:58} n={n:6d} fail={fail:5d} {examples[:2] if fail else ''} {note}")


def case():
    return dict(sys_type=SYSTEMS[rng.randrange(4)], oa_t=rng.uniform(20, 46), oa_rh=rng.uniform(15, 100), ow_t=rng.uniform(-20, 15), ow_rh=rng.uniform(20, 100),
                atm_kpa=rng.choice((101.325, 95, 85, 75)), ra_t=rng.choice((20, 22, 23, 24, 26)), ra_rh=rng.choice((30, 40, 50, 60)),
                chw2_in=rng.uniform(4, 12), dt_chw=rng.choice((4, 5, 6)), eq_kw=rng.uniform(0, 200), sf=rng.choice((0, 10, 20)),
                en_L_A=rng.uniform(10, 60), en_W_A=rng.uniform(8, 40), ppl_A=rng.randint(0, 80), en_ach_A=rng.uniform(0, 60))


valid = []
tries = 0
while len(valid) < N and tries < N * 5:
    tries += 1
    c = case(); st, r = run(**c)
    if st == "ok":
        valid.append((c, r))
out["valid_cases"] = len(valid)

# E1 report integrity and cross-check against the calculation
BAD = re.compile(r"\bnan\b|\binf\b|(?<!\()\bNone\b(?!\))|[{}]|Traceback|KeyError|%s|\bundefined\b", re.I)  # "(None)" is the cleanroom-class option name
integ = [0, 0, []]; xs = collections.OrderedDict((k, [0, 0, []]) for k in ("status_header", "total_kw_and_rt", "CHW_lpm", "zh_en_same_numbers"))
for c, r in valid[:600]:
    i18n.set_language("zh-Hant", persist=False)
    rep = str(api.report(r))
    integ[0] += 1
    m = BAD.search(rep)
    if m: integ[1] += 1; integ[2].append((c["sys_type"][:3], m.group(0), rep[max(0, m.start() - 40):m.start() + 40].replace("\n", " ")))
    xs["status_header"][0] += 1
    h = re.search(r"整體狀態：([^；\n]+)", rep)
    if not h or h.group(1).strip() != r["quality"]["status"]: xs["status_header"][1] += 1; xs["status_header"][2].append((h and h.group(1), r["quality"]["status"]))
    num = lambda x: float(x.replace(",", ""))
    m = re.search(re.escape(r["q_total_basis"]) + r"\s+([\d.,]+) kW / ([\d.,]+) US RT", rep)
    if r["q_total_kw"] > 0:
        xs["total_kw_and_rt"][0] += 1
        if not m or abs(num(m.group(1)) - r["q_total_kw"]) > 0.0051 or abs(num(m.group(2)) - r["q_total_rt"]) > 0.0051:
            xs["total_kw_and_rt"][1] += 1; xs["total_kw_and_rt"][2].append((m and m.groups(), round(r["q_total_kw"], 3), round(r["q_total_rt"], 3)))
    m = re.search(r"(?<![A-Z])CHW ([\d.,]+) LPM", rep)
    if r["water"]["CHW"]["lpm"] > 0:
        xs["CHW_lpm"][0] += 1
        if not m or abs(num(m.group(1)) - r["water"]["CHW"]["lpm"]) > 0.0051: xs["CHW_lpm"][1] += 1; xs["CHW_lpm"][2].append((m and m.group(1), round(r["water"]["CHW"]["lpm"], 3)))
    i18n.set_language("en", persist=False)
    rep_en = str(api.report(r))
    i18n.set_language("zh-Hant", persist=False)
    strip = lambda t: re.sub(r"(?m)^\s*\d+\.\s", "", t)  # section / list ordinals differ by language, not data
    tok = lambda t: collections.Counter(x.replace(",", "") for x in re.findall(r"(?<![A-Za-z0-9_.])\d[\d,]*(?:\.\d+)?(?![0-9])", strip(t)))
    nz, ne = tok(rep), tok(rep_en)
    if r["effective_inputs"]["sys_type"].startswith("MAU"): ne["100"] = max(0, ne["100"] - 1)  # "全外氣" is rendered "100% OA"
    xs["zh_en_same_numbers"][0] += 1
    if nz != ne:
        xs["zh_en_same_numbers"][1] += 1
        xs["zh_en_same_numbers"][2].append((dict(list((nz - ne).items())[:4]), dict(list((ne - nz).items())[:4])))
record("E1 report has no nan/inf/None/{}/Traceback tokens", *integ[:3])
for k, v in xs.items(): record(f"E1 report {k}", *v)

# E2 thermodynamic hard limits on every valid result
rules = collections.OrderedDict((k, [0, 0, []]) for k in (
    "state_in_range (t -60..120, 0<=w<=0.2, rh<=100)", "coil_never_heats_or_humidifies", "condensate_non_negative",
    "coil_leaving_air_not_colder_than_entering_water", "engine_own_residuals_below_1e-6", "supply_not_supersaturated", "flows_and_loads_non_negative"))


def chk(name, ok, detail):
    rules[name][0] += 1
    if not ok:
        rules[name][1] += 1
        if len(rules[name][2]) < 3: rules[name][2].append(detail)


for c, r in valid:
    tag = c["sys_type"][:3]
    for path, s in states(r):
        chk("state_in_range (t -60..120, 0<=w<=0.2, rh<=100)", -60 <= s["t"] <= 120 and 0 <= s["w"] <= 0.2 and 0 <= s["rh"] <= 100.0001, (tag, path, s["t"], s["w"], s["rh"]))
    water_in = {"c1": float(r["effective_inputs"]["chw1_in"]), "c2": float(r["effective_inputs"]["chw2_in"])}
    for season in ("summer", "winter"):
        for cn in ("c1", "c2"):
            cc = r[season].get(cn)
            if not cc or "air_kw" not in cc: continue
            chk("coil_never_heats_or_humidifies", cc["outlet"]["h"] <= cc["inlet"]["h"] + 1e-9 and cc["outlet"]["w"] <= cc["inlet"]["w"] + 1e-12, (tag, season, cn))
            chk("condensate_non_negative", cc["condensate_kg_s"] >= -1e-12 and cc["liquid_kw"] >= -1e-12, (tag, season, cn, cc["condensate_kg_s"]))
            if cc["air_kw"] > 1e-6 and not (cn == "c1" and r[season]["coil_configuration"] == "單盤管"):
                # CHW supply temperature is the coldest water the coil sees (HW or DCC coils excluded: only cooling coils with CHW supply)
                chk("coil_leaving_air_not_colder_than_entering_water", cc["outlet"]["t"] >= water_in[cn] - 1e-6, (tag, season, cn, round(cc["outlet"]["t"], 2), water_in[cn], c))
    for k in ("mass_residual", "sensible_residual"):
        if isinstance(r.get(k), (int, float)): chk("engine_own_residuals_below_1e-6", abs(r[k]) < 1e-6, (tag, k, r[k]))
    for season in ("summer", "winter"): chk("engine_own_residuals_below_1e-6", abs(r[season].get("energy_residual_kw", 0)) < 1e-6, (tag, season, r[season].get("energy_residual_kw")))
    sup = r["summer"]["supply"]; chk("supply_not_supersaturated", sup["rh"] <= 100.0001, (tag, sup["rh"]))
    chk("flows_and_loads_non_negative", all(w["lpm"] >= 0 and w["load_kw"] >= 0 and w["capacity_kw"] >= 0 for w in r["water"].values()) and r["q_total_kw"] >= 0 and r["supply_room_cmh"] >= 0, (tag,))
for k, v in rules.items(): record("E2 " + k, *v)

json.dump(out, open(sys.argv[2] if len(sys.argv) > 2 else "stress_e.json", "w"), ensure_ascii=False, indent=1, default=str)
