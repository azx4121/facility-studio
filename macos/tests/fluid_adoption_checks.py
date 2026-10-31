"""Ledger water adoption must not replace a different main-project fluid without an explicit choice.

Source flows are computed for the source fluid (rho, cp, mu); when any of the three differs from
the main project's effective fluid, nothing is adopted automatically and the difference is pending.
"""

import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from facility_studio import api as a
from facility_studio import i18n
from facility_studio.ahu_schema import NM_DEFAULTS
from facility_studio.contributions import (
    ahu_contribution, empty_ledger, removed_ledger, updated_ledger, validate_ledger,
)
from facility_studio.errors import ValidationError
from facility_studio.schema import default_project

checks = []
CJK = re.compile(r"[\u3400-\u9fff]")
OWN = "本迴路獨立物性"
SHARED = "沿用共用參考"
CHW_FLUID = ("chw_fluid_mode", "chw_fluid_name", "chw_rho", "chw_cp", "chw_mu")
CHW_FLOW = ("chw_q", "u_chw", "chw_link", "dt_chw", "chw2_in")


def check(name, ok, detail=""):
    checks.append(dict(name=name, passed=bool(ok), detail=str(detail)[:260]))


def main_inputs(**values):
    i = default_project()["inputs"]
    i.update(values)
    return i


AHU_RESULT = a.nm_calculate(dict(NM_DEFAULTS, name="AHU-1"))


def ahu_entry(inputs, ident="ahu-1", result=AHU_RESULT):
    return ahu_contribution(result, ident, inputs)


def adopt(inputs, entry, ledger=None):
    d, updates, summary = updated_ledger(ledger or empty_ledger(), entry, inputs)
    after = dict(inputs)
    after.update(updates)
    return d, updates, summary, after


def chw_pending(summary):
    return [x for x in summary["pending"] if x.startswith("CHW 主案流體物性")]


def adopted_chw(updates):
    return {k: v for k, v in updates.items() if k in CHW_FLUID + CHW_FLOW}


# 0. The candidate structure carries mu, and the ledger insists on it.
entry = ahu_entry(main_inputs())
check("every AHU water record states rho, cp and mu",
      all({"rho", "cp", "mu"} <= set(w) for w in entry["water"]) and entry["water"], [sorted(w) for w in entry["water"]])
broken = copy.deepcopy(dict(empty_ledger(), entries={"x": entry}))
del broken["entries"]["x"]["water"][0]["mu"]
try:
    validate_ledger(broken)
    check("a water record without mu is rejected", False, "accepted")
except ValidationError:
    check("a water record without mu is rejected", True)

# 1. Reported counterexample: independent CHW with mu 0.0025 against clean-water source.
start = main_inputs(chw_fluid_mode=OWN, chw_rho="1000", chw_cp="4.1868", chw_mu="0.0025")
d, up, summary, after = adopt(start, ahu_entry(start))
check("mu-only difference: no CHW fluid or flow is adopted", not adopted_chw(up), adopted_chw(up))
check("mu-only difference: main CHW fields unchanged", all(after[k] == start[k] for k in CHW_FLUID + CHW_FLOW))
check("mu-only difference: pending names the property", any("mu 0.0025≠0.001" in x for x in chw_pending(summary)), summary["pending"])
check("AHU source warning includes mu", any("CHW" in x and "mu 0.0025≠0.001" in x for x in ahu_entry(start)["pending"]))

# 2. Each property alone, and all three equal.
for prop, value in (("chw_rho", "1035"), ("chw_cp", "3.75"), ("chw_mu", "0.0025")):
    base = main_inputs(chw_fluid_mode=OWN, chw_rho="1000", chw_cp="4.1868", chw_mu="0.001")
    base[prop] = value
    _, up, summary, _ = adopt(base, ahu_entry(base))
    check(f"{prop} differs: protected and pending", not adopted_chw(up) and chw_pending(summary), up)
same = main_inputs(chw_fluid_mode=OWN, chw_rho="1000", chw_cp="4.1868", chw_mu="0.001")
_, up, summary, _ = adopt(same, ahu_entry(same))
check("identical independent fluid: source adopted", up.get("chw_q") and up.get("chw_mu") == "0.001" and not chw_pending(summary), up)

# 3. Shared-reference mode uses the shared properties, not stale loop fields.
shared_water = main_inputs()
_, up, summary, _ = adopt(shared_water, ahu_entry(shared_water))
check("shared clean water: source adopted as before", up.get("chw_q") and not chw_pending(summary))
glycol = main_inputs(chw_fluid_mode=SHARED, water_rho="1035", water_cp="3.75", water_mu="0.0025")
_, up, summary, after = adopt(glycol, ahu_entry(glycol))
check("shared glycol: protected, all three listed",
      not adopted_chw(up) and any(all(s in x for s in ("rho 1035≠1000", "cp 3.75≠4.1868", "mu 0.0025≠0.001")) for x in chw_pending(summary)),
      summary["pending"])
check("shared glycol: loop stays on the shared reference", after["chw_fluid_mode"] == SHARED)
stale = main_inputs(chw_fluid_mode=SHARED, chw_rho="1035", chw_cp="3.75", chw_mu="0.0025")
_, up, summary, _ = adopt(stale, ahu_entry(stale))
check("shared clean water with stale loop fields: adopted (loop fields are inactive)", up.get("chw_q") and not chw_pending(summary), summary["pending"])

# 4. Explicit choice overrides, with a note; removing the source restores the main values.
d, up, summary, after = adopt(start, ahu_entry(start))
group = next(g for g in summary["water"] if g["loop"] == "CHW")
d["selections"]["CHW"] = group["id"]
d, up, summary, chosen = adopt(after, d["entries"]["ahu-1"], d)
check("explicit selection adopts the source fluid and flow", chosen["chw_mu"] == "0.001" and up.get("chw_q"), up)
check("explicit selection is noted, not pending",
      any("依使用者選擇" in x and "mu 0.0025≠0.001" in x for x in summary["notes"]) and not chw_pending(summary), summary["notes"])
d2, up2, _, _ = adopt(chosen, d["entries"]["ahu-1"], d)
check("re-adopting the chosen source does not drift", up2 == up)
d3, up3, _ = removed_ledger(d, "ahu-1", chosen)
restored = dict(chosen)
restored.update(up3)
check("removing the chosen source restores every main CHW field",
      all(restored[k] == start[k] for k in CHW_FLUID + CHW_FLOW), {k: (restored[k], start[k]) for k in CHW_FLUID + CHW_FLOW if restored[k] != start[k]})

# 5. Protected state is stable under update and repeat import.
d, up, summary, after = adopt(start, ahu_entry(start))
d, up_again, summary_again, after_again = adopt(after, ahu_entry(after), d)
check("repeat import of a protected source changes nothing", up_again == up and after_again == after)
bigger = a.nm_calculate(dict(NM_DEFAULTS, name="AHU-1", summer_flow="8000", winter_flow="8000", flow="8000"))
d, up_big, summary_big, _ = adopt(after, ahu_entry(after, result=bigger), d)
check("updated source with a different flow stays protected", not adopted_chw(up_big) and chw_pending(summary_big))
d, up_rm, _ = removed_ledger(d, "ahu-1", after)
check("removing a protected source leaves the main fluid as it was",
      all(dict(after, **up_rm)[k] == start[k] for k in CHW_FLUID + CHW_FLOW))

# 6. A manual fluid edit after adoption is the user's: protected, not overwritten or half-restored.
d, up, _, after = adopt(shared_water, ahu_entry(shared_water))
manual = dict(after, chw_mu="0.0025")
d, up_manual, summary_manual, kept = adopt(manual, ahu_entry(manual), d)
check("manual mu edit after adoption is not overwritten", kept["chw_mu"] == "0.0025" and "chw_mu" not in up_manual, up_manual)
check("manual edit makes the source pending",
      any(x.startswith("CHW 主案水力／流體欄位在帶入後已手動修改") for x in summary_manual["pending"]), summary_manual["pending"])
check("fluid fields are kept together (no partial restore)",
      all(kept[k] == manual[k] for k in CHW_FLUID), {k: (kept[k], manual[k]) for k in CHW_FLUID if kept[k] != manual[k]})

# 7. Generic source (equipment PCW) and stale explicit selection.
pcw_entry = dict(id="eq-1", name="EQ", kind="設備表", source_hash="h-eq", updates={}, power={}, notes=[], pending=[],
                 water=[dict(loop="PCW", circuit="G1", supply=25.0, **{"return": 30.0}, rho=1000.0, cp=4.1868, mu=.001,
                             summer_lpm=50.0, winter_lpm=50.0)])
pcw_main = main_inputs(pcw_fluid_mode=OWN, pcw_rho="1000", pcw_cp="4.1868", pcw_mu="0.0025")
_, up, summary, _ = adopt(pcw_main, pcw_entry)
check("equipment PCW source with different mu is protected",
      "pcw_tot" not in up and "pcw_mu" not in up and any(x.startswith("PCW 主案流體物性") for x in summary["pending"]), up)
d = empty_ledger()
d["selections"]["CHW"] = "missing-circuit"
_, up, summary, _ = adopt(shared_water, ahu_entry(shared_water), d)
check("stale explicit selection adopts nothing and is pending",
      not adopted_chw(up) and any("先前選擇的來源迴路已不存在" in x for x in summary["pending"]), summary["pending"])

# 8. Unreadable main properties are never treated as matching.
bad = main_inputs(chw_fluid_mode=OWN, chw_mu="abc")
_, up, summary, _ = adopt(bad, ahu_entry(main_inputs()))
check("unreadable main fluid is protected", not adopted_chw(up) and any("主案物性無法解讀" in x for x in chw_pending(summary)), summary["pending"])

# 9. English renderings contain no Chinese.
d, _, summary, after = adopt(start, ahu_entry(start))
group = next(g for g in summary["water"] if g["loop"] == "CHW")
d["selections"]["CHW"] = group["id"]
_, _, chosen_summary, _ = adopt(after, d["entries"]["ahu-1"], d)
_, _, stale_summary, _ = adopt(shared_water, ahu_entry(shared_water), dict(empty_ledger(), selections={"CHW": "missing"}))
texts = chw_pending(summary) + [x for x in ahu_entry(start)["pending"] if "CHW" in x]
texts += [x for x in chosen_summary["notes"] if "依使用者選擇" in x]
texts += [x for x in stale_summary["pending"] if "先前選擇" in x]
untranslated = [i18n.translate(x, "en") for x in texts if CJK.search(i18n.translate(x, "en"))]
check("new fluid messages translate fully to English", len(texts) == 4 and not untranslated, untranslated or len(texts))

failed = [c for c in checks if not c["passed"]]
(ROOT / "evidence").mkdir(exist_ok=True)
(ROOT / "evidence" / "Fluid_Adoption_Checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
for c in failed:
    print("FAIL", c["name"], c["detail"])
print(f"fluid adoption checks: {len(checks) - len(failed)}/{len(checks)} passed")
sys.exit(1 if failed else 0)
