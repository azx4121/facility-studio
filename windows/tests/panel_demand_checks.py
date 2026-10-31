"""Ledger feeder demand: same panel, same voltage, classified sources.

Expected values are written out by hand from the rule
    1.25 x non-motor continuous + 1.00 x other non-motor + 1.00 x motors
    + 0.25 x largest single motor of the whole group, P and Q separately.
"""

import copy
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from facility_studio import api as a
from facility_studio.ahu_schema import NM_DEFAULTS
from facility_studio.contributions import (
    ahu_contribution, aggregate_ledger, empty_ledger, equipment_contribution, removed_ledger, updated_ledger, validate_ledger,
)
from facility_studio.equipment_analysis import analyze_equipment
from facility_studio.equipment_io import Cell
from facility_studio.equipment_schema import SCHEMA_ID
from facility_studio.errors import ValidationError
from facility_studio.panel_demand import composition_design, make_composition
from facility_studio.schema import default_project
from facility_studio.utils import VOLTAGE_MAP

checks = []
V380 = next(k for k, v in VOLTAGE_MAP.items() if v == 380.0)
HP_KW = 0.745699871582


def check(name, ok, detail=""):
    checks.append(dict(name=name, passed=bool(ok), detail=str(detail)[:240]))


def amps(p_kw, q_kvar=0.0, volts=380.0):
    return math.hypot(p_kw, q_kvar) * 1000 / (math.sqrt(3) * volts)


def close(name, actual, expected, tol=1e-6):
    check(name, abs(actual - expected) <= tol * max(1, abs(expected)), f"actual={actual} expected={expected}")


def panel_inputs(kind="馬達負載", base_kw=100.0, largest_kw=20.0, pf="1"):
    i = default_project()["inputs"]
    i.update(e_volt=V380, e_pf=pf, e_eff="1", e_up_type=kind, e_up_eq="0", u_e_up_eq="kW",
             e_up_oven=format(base_kw, ".15g"), u_e_up_oven="kW",
             e_up_largest_hp=format(largest_kw / HP_KW, ".15g") if largest_kw else "0")
    return i


def source(ident, kw, kvar=0.0, comp=None, design=None, branch=0.0, volts=380.0):
    if comp is not None:
        design = composition_design(comp)
    power = dict(kw=kw, kvar=kvar, design_kw=design[0], design_kvar=design[1], branch_floor_a=branch, length_m=0.0, voltage=volts)
    if comp is not None:
        power["composition"] = comp
    return dict(id=ident, name=ident, kind="設備表", source_hash="h-" + ident + json.dumps(power, sort_keys=True),
                updates={"e_up_eq": format(kw, ".15g"), "u_e_up_eq": "kW"}, water=[], power={"UP": power}, notes=[], pending=[])


def adopt(inputs, *entries, ledger=None):
    d, current, summary = ledger or empty_ledger(), dict(inputs), None
    for entry in entries:
        d, updates, summary = updated_ledger(d, entry, current)
        current.update(updates)
    return d, current, summary


def continuous(kw, kvar=0.0):
    return make_composition(continuous=(kw, kvar))


def motor(kw, kvar=0.0, largest=None):
    largest = (kw, kvar) if largest is None else largest
    return make_composition(motor=(kw, kvar), largest_motor=largest)


def floor(current):
    return float(current["e_up_design_floor"])


# 1. Reproduced case: base 100 kW motors (largest 20 kW), two 100 kW sources, PF 1.
_, cur, _ = adopt(panel_inputs(), source("S1", 100, comp=continuous(100)), source("S2", 100, comp=continuous(100)))
close("non-motor continuous sources: 100+125+125+0.25x20 = 355 kVA", floor(cur), amps(355))
_, cur, _ = adopt(panel_inputs(), source("S1", 100, comp=motor(100)), source("S2", 100, comp=motor(100)))
close("motor sources: 100+100+100+0.25x100 = 325 kVA", floor(cur), amps(325))
calc = a.calculate(dict(default_project(), inputs=cur))
check("main calculation accepts the adopted design floor", calc["electric"]["UP"]["design_current_a"] >= floor(cur) - 1e-6,
      calc["electric"]["UP"]["design_current_a"])

# 2. Legacy sources without classification stay readable, conservative and pending.
_, cur, summary = adopt(panel_inputs(), source("L1", 100, design=(125, 0)), source("L2", 100, design=(125, 0)))
close("legacy unclassified sources add their own design (355)", floor(cur), amps(355))
check("legacy unclassified sources are marked pending", any("未提供負載分類" in x for x in summary["pending"]), summary["pending"])
_, cur, summary = adopt(panel_inputs(), source("L1", 100, design=(125, 0)), source("M1", 100, comp=motor(100)))
close("legacy + classified motor: 100+125+100+0.25x100 = 350", floor(cur), amps(350))

# 3. Mixed power factors: P and Q combined separately.
tan = lambda pf: math.tan(math.acos(pf))
q1, q2, qb = 100 * tan(0.8), 50 * tan(0.95), 40 * tan(0.9)
_, cur, _ = adopt(panel_inputs("一般負載", 40, 0, pf="0.9"),
                  source("M1", 100, q1, comp=motor(100, q1)), source("C1", 50, q2, comp=continuous(50, q2)))
p_expected = 40 + 100 + 1.25 * 50 + 0.25 * 100
q_expected = qb + q1 + 1.25 * q2 + 0.25 * q1
close("mixed PF design current", floor(cur), amps(p_expected, q_expected))
close("mixed PF operating panel PF", float(cur["e_up_pf"]), 190 / math.hypot(190, qb + q1 + q2))

# 4. Base without motors; a stale inactive largest motor must not count.
_, cur, _ = adopt(panel_inputs("一般負載", 100, largest_kw=50), source("M1", 10, comp=motor(10)), source("M2", 10, comp=motor(10)))
close("non-motor base: 100+10+10+0.25x10 (stale 50 kW ignored)", floor(cur), amps(122.5))
_, cur, _ = adopt(panel_inputs("連續負載", 100, largest_kw=0), source("M1", 100, comp=motor(100)), source("M2", 100, comp=motor(100)))
close("continuous base: 125+100+100+0.25x100 = 350", floor(cur), amps(350))

# 5. Missing information is conservative and pending.
_, cur, summary = adopt(panel_inputs("馬達負載", 100, largest_kw=0), source("C1", 100, comp=continuous(100)))
close("unknown base largest motor uses the largest row: 100+125+0.25x100", floor(cur), amps(250))
check("unknown base largest motor is pending", any("最大單台馬達未填" in x for x in summary["pending"]), summary["pending"])
_, cur, summary = adopt(panel_inputs("未知盤型", 100, largest_kw=0), source("C1", 100, comp=continuous(100)))
close("unrecognized base type counted as continuous: 125+125", floor(cur), amps(250))
check("unrecognized base type is pending", any("無法辨識" in x for x in summary["pending"]), summary["pending"])

# 6. Update, idempotence and removal back to the original panel.
start = panel_inputs()
d, cur, _ = adopt(start, source("S1", 100, comp=continuous(100)), source("S2", 100, comp=continuous(100)))
d, up, _ = updated_ledger(d, source("S2", 60, comp=motor(60)), cur)
cur.update(up)
close("update S2 to a 60 kW motor: 100+125+60+0.25x60 = 300", floor(cur), amps(300))
d_again, up_again, _ = updated_ledger(d, source("S2", 60, comp=motor(60)), cur)
check("re-adopting the same source does not drift", up_again.get("e_up_design_floor") == cur["e_up_design_floor"])
d, up, _ = removed_ledger(d, "S1", cur)
cur.update(up)
close("remove S1: 100+60+0.25x60 = 175", floor(cur), amps(175))
d, up, _ = removed_ledger(d, "S2", cur)
cur.update(up)
for key in ("e_up_type", "e_up_design_floor", "e_up_pf", "e_up_pf_mode", "e_up_eq", "u_e_up_eq"):
    check(f"removing all sources restores {key}", cur[key] == start[key], (cur[key], start[key]))

# 7. Source branch requirement remains a floor; voltage stays one group.
_, cur, _ = adopt(panel_inputs(), source("B1", 10, comp=continuous(10), branch=2000.0))
close("source branch design current is kept as a floor", floor(cur), 2000.0)
try:
    adopt(panel_inputs(), source("V1", 10, comp=continuous(10), volts=208.0))
    check("other-voltage source rejected", False, "accepted")
except ValidationError:
    check("other-voltage source rejected", True)

# 8. Invalid compositions are rejected; JSON round trip keeps the classification.
ledger, _, _ = adopt(panel_inputs(), source("S1", 100, comp=motor(100)))
check("ledger with composition survives JSON round trip", validate_ledger(json.loads(json.dumps(ledger))) == ledger)
bad_cases = {
    "sum differs from kw": lambda c: c.update(motor_kw=90.0),
    "NaN value": lambda c: c.update(motor_kw=float("nan")),
    "negative value": lambda c: c.update(continuous_kw=-1.0),
    "unknown key": lambda c: c.update(motor_add_kw=5.0),
    "motor without largest": lambda c: c.update(largest_motor_kw=0.0),
    "design differs": lambda c: c.update(largest_motor_kw=50.0),
}
for name, mutate in bad_cases.items():
    broken = copy.deepcopy(ledger)
    mutate(broken["entries"]["S1"]["power"]["UP"]["composition"])
    try:
        validate_ledger(broken)
        check(f"invalid composition rejected: {name}", False, "accepted")
    except ValidationError:
        check(f"invalid composition rejected: {name}", True)
broken = copy.deepcopy(ledger)
broken["entries"]["S1"]["power"]["UP"]["motor_add_kw"] = 5.0
try:
    validate_ledger(broken)
    check("unknown power key still rejected", False, "accepted")
except ValidationError:
    check("unknown power key still rejected", True)

# 9. Real producers: AHU source and equipment schedule groups.
ahu = dict(NM_DEFAULTS, humidifier="循環水洗濕膜", pump_input_kw="3", fan_qty="2", fan_unit_kw="5.5", h2_source="電熱", h2_kw="20")
result = a.nm_calculate(ahu)
entry = ahu_contribution(result, "ahu-1", default_project()["inputs"])
comp = entry["power"]["NP"]["composition"]
i = result["inputs"]
fan = float(i["fan_qty"]) * float(i["fan_unit_kw"])
heat = sum(float(i[t + "_kw"]) for t in ("h1", "h2") if i[t + "_source"] in ("電熱", "熱水＋電熱"))
steam = float(i["steam_kw"]) if "蒸汽" in i["humidifier"] else 0.0
close("AHU motors = fans + wash pump", comp["motor_kw"], fan + 3.0)
close("AHU continuous = electric heat + steam", comp["continuous_kw"], heat + steam)
check("AHU scenario really contains electric heat", heat == 20.0, heat)
close("AHU largest motor = max(single fan, pump)", comp["largest_motor_kw"], max(float(i["fan_unit_kw"]), 3.0))
check("AHU unknown wash pump count is pending, not assumed",
      any("水洗泵台數與單台額定未知" in x for x in entry["pending"]), entry["pending"])
no_pump = ahu_contribution(a.nm_calculate(dict(ahu, humidifier="不加濕")), "ahu-2", default_project()["inputs"])
_, _, ahu_summary = adopt(default_project()["inputs"], entry)
check("pump pending item reaches the ledger summary", any("水洗泵台數與單台額定未知" in x for x in ahu_summary["pending"]))
check("AHU without wash pump has no pump pending item",
      not any("水洗泵台數" in x for x in no_pump["pending"]), no_pump["pending"])
try:
    validate_ledger(dict(empty_ledger(), entries={"ahu-1": entry}))
    check("AHU source validates", True)
except ValidationError as e:
    check("AHU source validates", False, e)


def rec(row, **cells):
    cells.setdefault("enabled", 1)
    return dict(system="電力", row=row, cells={k: Cell(v) for k, v in cells.items()})


common = dict(voltage=380, phases="3", length=30)
schedule = analyze_equipment(dict(schema_id=SCHEMA_ID, source_name="t.csv", systems=[], records=[
    rec(6, id="M1", name="pump", group="G1", quantity=2, usage=100, power=15, pf=0.85, kind="馬達", **common),
    rec(7, id="C1", name="heater", group="G1", quantity=1, usage=100, power=10, pf=1.0, kind="連續運轉", **common),
    rec(8, id="N1", name="tools", group="G1", quantity=3, usage=60, power=5, pf=0.9, kind="一般設備", **common),
    rec(9, id="M2", name="fan", group="G2", quantity=1, usage=100, power=22, pf=0.85, kind="馬達", **common),
]))
groups = {g["group"]: g for g in schedule["groups"] if g["system"] == "電力"}
for name, group in groups.items():
    dp, dq = composition_design(group["composition"])
    close(f"schedule {name} composition reproduces group design kW", dp, group["design_kw"])
    close(f"schedule {name} composition reproduces group design kvar", dq, group["design_kvar"])
inputs = panel_inputs("一般負載", 0, 0, pf="1")
entries = [equipment_contribution(schedule, groups[n], inputs, "UP") for n in ("G1", "G2")]
_, cur, summary = adopt(inputs, *entries)
t85, t90 = tan(0.85), tan(0.9)
p_expected = 30 + 1.25 * 10 + 9 + 22 + 0.25 * 22
q_expected = 30 * t85 + 9 * t90 + 22 * t85 + 0.25 * 22 * t85
close("two schedule groups share one largest motor (22 kW), not one per group", floor(cur), amps(p_expected, q_expected))

failed = [c for c in checks if not c["passed"]]
(ROOT / "evidence").mkdir(exist_ok=True)
(ROOT / "evidence" / "Panel_Demand_Checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
for c in failed:
    print("FAIL", c["name"], c["detail"])
print(f"panel demand checks: {len(checks) - len(failed)}/{len(checks)} passed")
sys.exit(1 if failed else 0)
