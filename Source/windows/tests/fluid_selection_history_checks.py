"""Explicit circuit selection is consent for the values it produced, not a permanent licence.

Every scenario runs the real ledger calls (updated_ledger with select=, manual edits of the
main inputs, removed_ledger) and checks that the CHW loop is always one consistent set:
the main project's own values, the adopted source values, or the user's manual values.
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
from facility_studio.contributions import MANUAL_HOLD, ahu_contribution, empty_ledger, loop_keys, removed_ledger, updated_ledger
from facility_studio.errors import ValidationError
from facility_studio.schema import default_project

checks = []
CJK = re.compile(r"[\u3400-\u9fff]")
KEYS = loop_keys("CHW")
MANUAL = "CHW 主案水力／流體欄位在帶入後已手動修改"
STALE = "CHW 先前選擇的來源迴路已不存在"


def check(name, ok, detail=""):
    checks.append(dict(name=name, passed=bool(ok), detail=str(detail)[:260]))


def group(inputs):
    return {k: inputs[k] for k in KEYS}


def has(summary, prefix, field="pending"):
    return any(x.startswith(prefix) for x in summary[field])


class Session:
    """Main inputs plus ledger, updated only through the ledger API (as the workbench does)."""

    def __init__(self, inputs):
        self.inputs, self.ledger = dict(inputs), empty_ledger()

    def update(self, entry, select=None):
        self.ledger, updates, summary = updated_ledger(self.ledger, entry, self.inputs, select=select)
        self.inputs.update(updates)
        return updates, summary

    def remove(self, ident):
        self.ledger, updates, summary = removed_ledger(self.ledger, ident, self.inputs)
        self.inputs.update(updates)
        return updates, summary

    def circuit(self, summary):
        return next(g["id"] for g in summary["water"] if g["loop"] == "CHW")

    def copy(self):
        clone = Session(self.inputs)
        clone.ledger = copy.deepcopy(self.ledger)
        return clone


def ahu(**values):
    return ahu_contribution(a.nm_calculate(dict(NM_DEFAULTS, name="AHU-1", **values)), "ahu-1", default_project()["inputs"])


START = default_project()["inputs"]
START.update(chw_fluid_mode="本迴路獨立物性", chw_rho="1000", chw_cp="4.1868", chw_mu="0.0025")
SOURCE = ahu()

# A. Explicit selection, then a manual edit (reported case).
s = Session(START)
_, first = s.update(SOURCE)
check("A1 differing fluid is protected before any selection", group(s.inputs) == group(START))
_, picked = s.update(SOURCE, select={"CHW": s.circuit(first)})
adopted = group(s.inputs)
check("A2 explicit selection adopts the source", adopted["chw_mu"] == "0.001" and adopted["chw_q"] != START["chw_q"], adopted)
check("A2 note promises restoration only while unedited", any("之後若未手動修改" in n for n in picked["notes"]), picked["notes"])
after_select = s.copy()
s.inputs["chw_mu"] = "0.003"
manual = group(s.inputs)
up3, sum3 = s.update(SOURCE)
check("A3 manual edit is not overwritten by the old selection", "chw_mu" not in up3 and s.inputs["chw_mu"] == "0.003", up3)
check("A3 the whole CHW loop keeps the current values", group(s.inputs) == manual, {k: (s.inputs[k], manual[k]) for k in KEYS if s.inputs[k] != manual[k]})
check("A3 a fresh explicit choice is requested", has(sum3, MANUAL), sum3["pending"])
check("A3 the old selection is replaced by a manual hold", s.ledger["selections"].get("CHW") == MANUAL_HOLD, s.ledger["selections"])
check("A3 no note claims removal restores values", not any("依使用者選擇" in n for n in sum3["notes"]))
up4, sum4 = s.update(SOURCE)
check("A4 repeat update does not drift", up4 == up3 and group(s.inputs) == manual and has(sum4, MANUAL))
branch = s.copy()
s.remove("ahu-1")
check("A5 removing the source keeps the manual loop whole", group(s.inputs) == manual, {k: (s.inputs[k], manual[k]) for k in KEYS if s.inputs[k] != manual[k]})
_, again = branch.update(SOURCE, select={"CHW": branch.circuit(sum4)})
check("A6 re-selecting adopts the source again", branch.inputs["chw_mu"] == "0.001" and "CHW" in branch.ledger["selections"])
branch.remove("ahu-1")
check("A6 removal after re-selection restores the values chosen over (manual set)", group(branch.inputs) == manual,
      {k: (branch.inputs[k], manual[k]) for k in KEYS if branch.inputs[k] != manual[k]})
after_select.remove("ahu-1")
check("A7 removal without edits restores the original loop", group(after_select.inputs) == group(START))
round_trip = after_select.copy()
round_trip.ledger = json.loads(json.dumps(round_trip.ledger))
check("A8 ledger survives a JSON round trip", round_trip.ledger == after_select.ledger)

# B. Automatic adoption, then a manual flow edit.
shared = default_project()["inputs"]
b = Session(shared)
b.update(SOURCE)
check("B1 matching shared fluid is adopted automatically", b.inputs["chw_q"] != shared["chw_q"])
b.inputs["chw_q"] = "123.4"
edited = group(b.inputs)
upb, sumb = b.update(SOURCE)
check("B2 manual flow edit is kept with the whole loop", group(b.inputs) == edited and "chw_q" not in upb and has(sumb, MANUAL), upb)
upb2, sumb2 = b.update(SOURCE)
check("B3 a later update still does not re-adopt over the manual flow (fluid matches)",
      group(b.inputs) == edited and "chw_q" not in upb2 and has(sumb2, MANUAL), upb2)
b.remove("ahu-1")
check("B4 removal keeps the edited loop whole and ends the hold", group(b.inputs) == edited and "CHW" not in b.ledger["selections"])

# C. Selection, then the source's water temperatures change (new circuit id).
c = Session(START)
_, sumc = c.update(SOURCE)
c.update(SOURCE, select={"CHW": c.circuit(sumc)})
chosen = group(c.inputs)
warm = ahu(c2_in="8", c2_out="14")
_, sum_warm = c.update(warm)
check("C1 changed circuit is not adopted", group(c.inputs) != chosen and c.inputs["chw2_in"] != "8")
check("C1 the whole loop returns to the main values before adoption", group(c.inputs) == group(START),
      {k: (c.inputs[k], START[k]) for k in KEYS if c.inputs[k] != START[k]})
check("C1 the change is reported and the selection released", has(sum_warm, STALE) and "CHW" not in c.ledger["selections"], sum_warm["pending"])
up_c2, sum_c2 = c.update(warm)
check("C2 next update: no repeated stale notice, fluid difference pending, no drift",
      not has(sum_c2, STALE) and has(sum_c2, "CHW 主案流體物性") and group(c.inputs) == group(START), sum_c2["pending"])
c.update(warm, select={"CHW": c.circuit(sum_c2)})
check("C3 selecting the new circuit adopts its temperatures", c.inputs["chw2_in"] == "8" and c.inputs["chw_mu"] == "0.001")
c.remove("ahu-1")
check("C3 removal restores the original loop", group(c.inputs) == group(START))
m = Session(START)
_, summ = m.update(SOURCE)
m.update(SOURCE, select={"CHW": m.circuit(summ)})
m.inputs["chw_mu"] = "0.003"
manual_c = group(m.inputs)
_, sum_mc = m.update(warm)
check("C4 manual edit then circuit change keeps the manual loop", group(m.inputs) == manual_c and has(sum_mc, MANUAL)
      and m.ledger["selections"].get("CHW") == MANUAL_HOLD, sum_mc["pending"])

# D. Removing the selected source, then adding it back: consent is not resurrected.
r = Session(START)
_, sumr = r.update(SOURCE)
r.update(SOURCE, select={"CHW": r.circuit(sumr)})
r.remove("ahu-1")
check("D1 removal restores the loop and releases the selection", group(r.inputs) == group(START) and "CHW" not in r.ledger["selections"])
_, sum_back = r.update(SOURCE)
check("D2 re-adding the source needs a new choice", group(r.inputs) == group(START) and has(sum_back, "CHW 主案流體物性"), sum_back["pending"])

# E. A fresh selection of a circuit that does not exist, and an invalid selection.
e = Session(START)
_, sum_e = e.update(SOURCE, select={"CHW": "no-such-circuit"})
check("E1 unknown circuit: nothing adopted, reported, not stored",
      group(e.inputs) == group(START) and has(sum_e, STALE) and "CHW" not in e.ledger["selections"], sum_e["pending"])
try:
    Session(START).update(SOURCE, select={"XYZ": "id"})
    check("E2 selection of an unknown loop is rejected", False, "accepted")
except ValidationError:
    check("E2 selection of an unknown loop is rejected", True)

# G. Unapplied adoption versus manual edits.
g = Session(START)
_, sum_g = g.update(SOURCE)
gid = g.circuit(sum_g)
g.ledger, up_g, _ = updated_ledger(g.ledger, SOURCE, g.inputs, select={"CHW": gid})
not_applied = dict(g.inputs)  # the caller did not apply up_g (for example a declined preview)
g.ledger, up_g2, sum_g2 = updated_ledger(g.ledger, SOURCE, not_applied)
check("G1 an adoption that was never applied is not a manual edit", up_g2.get("chw_mu") == "0.001" and not has(sum_g2, MANUAL), sum_g2["pending"])
p_rev = Session(START)
_, sum_p = p_rev.update(SOURCE)
p_rev.update(SOURCE, select={"CHW": p_rev.circuit(sum_p)})
p_rev.inputs["chw_mu"] = START["chw_mu"]  # only one field typed back to its old value
mixed = group(p_rev.inputs)
up_p, sum_pr = p_rev.update(SOURCE)
check("G2 typing back one field is a manual edit (loop kept, choice requested)",
      group(p_rev.inputs) == mixed and "chw_mu" not in up_p and has(sum_pr, MANUAL), up_p)
lim = Session(START)
_, sum_l = lim.update(SOURCE)
lim.update(SOURCE, select={"CHW": lim.circuit(sum_l)})
lim.inputs.update(group(START))  # the whole loop retyped exactly as before adoption
up_l, _ = lim.update(SOURCE)
check("G3 known limitation: retyping the whole loop as before looks unapplied, so the stored choice re-adopts",
      up_l.get("chw_mu") == "0.001", up_l)

# F. English renderings of the new messages.
texts = [x for x in sum3["pending"] if x.startswith(MANUAL)] + [x for x in sum_warm["pending"] if x.startswith(STALE)]
texts += [n for n in picked["notes"] if "依使用者選擇" in n]
bad = [i18n.translate(x, "en") for x in texts if CJK.search(i18n.translate(x, "en"))]
check("F1 new messages translate fully to English", len(texts) == 3 and not bad, bad or len(texts))

failed = [c for c in checks if not c["passed"]]
(ROOT / "evidence").mkdir(exist_ok=True)
(ROOT / "evidence" / "Fluid_Selection_History_Checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
for c in failed:
    print("FAIL", c["name"], c["detail"])
print(f"fluid selection history checks: {len(checks) - len(failed)}/{len(checks)} passed")
sys.exit(1 if failed else 0)
