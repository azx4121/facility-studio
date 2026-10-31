"""The AHU link boundary must not change when a ledger return only reformats a number.

The ledger writes supply temperatures with format(.15g) ("7"), while the main project may
hold "7.0". Both are the same boundary; a different hash would refuse every later return
of the same AHU as a stale snapshot.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from facility_studio.design_workflow import ahu_requirement_updates
from facility_studio.engine import calculate
from facility_studio.schema import FIELDS, default_project

checks = []


def check(name, ok, detail=""):
    checks.append(dict(name=name, passed=bool(ok), detail=str(detail)[:260]))


def boundary(**values):
    project = default_project()
    project["inputs"].update(sys_type=FIELDS["sys_type"]["options"][0], **values)
    return ahu_requirement_updates(calculate(project, isolate_utilities=True))


# Default single coil: only CHW2 feeds the AHU coil.
base = boundary(chw1_in="12.0", chw2_in="7.0")
returned = boundary(chw1_in="12", chw2_in="7")
check("single coil: returned '7' and main '7.0' give the same link hash", base["linked_main_hash"] == returned["linked_main_hash"],
      {k: (base[k], returned[k]) for k in base if base[k] != returned[k]})
check("single coil: CHW2 inlet is written in one form", base["c2_in"] == returned["c2_in"] == "7.0", (base["c2_in"], returned["c2_in"]))
check("single coil: a real CHW2 change still changes the hash", boundary(chw2_in="7.5")["linked_main_hash"] != base["linked_main_hash"])

# Optional precooling coil: CHW1 is part of the boundary too.
DUAL = FIELDS["pre_mode"]["options"][1]
dual = boundary(pre_mode=DUAL, chw1_in="12.0", chw2_in="7.0")
dual_returned = boundary(pre_mode=DUAL, chw1_in="12", chw2_in="7")
check("dual coil: reformatted CHW1/CHW2 give the same link hash", dual["linked_main_hash"] == dual_returned["linked_main_hash"],
      {k: (dual[k], dual_returned[k]) for k in dual if dual[k] != dual_returned[k]})
check("dual coil: a real CHW1 change still changes the hash",
      boundary(pre_mode=DUAL, chw1_in="13", chw2_in="7.0")["linked_main_hash"] != dual["linked_main_hash"])

failed = [c for c in checks if not c["passed"]]
(ROOT / "evidence").mkdir(exist_ok=True)
(ROOT / "evidence" / "AHU_Link_Boundary_Checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
for c in failed:
    print("FAIL", c["name"], c["detail"])
print(f"AHU link boundary checks: {len(checks) - len(failed)}/{len(checks)} passed")
sys.exit(1 if failed else 0)
