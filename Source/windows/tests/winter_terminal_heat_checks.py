"""Winter room heating left over when the MAU supply temperature is capped.

No heat-source selection is available in this build, so the remaining loss must be
reported as an unassigned demand: never in the HW design load, never claimed for HW or NP.
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
from facility_studio.errors import ValidationError
from facility_studio.schema import default_project

checks = []
CJK = re.compile(r"[\u3400-\u9fff]")


def check(name, ok, detail=""):
    checks.append(dict(name=name, passed=bool(ok), detail=str(detail)[:240]))


def project(**inputs):
    p = default_project()
    p["inputs"].update(
        sys_type="MAU+FFU+DCC (全外氣/無塵室)", winter_model="室內熱濕平衡（定風量）", winter_gain_ratio="0",
        winter_ffu_ratio="100", winter_mau_max_t="40", ffu_w="150", ow_t="-15", en_wall="2500", wall_u="1.8",
        allow_reheat="1", allow_humidify="1",
    )
    p["inputs"].update(inputs)
    return p


r = a.calculate(project())
wr = r["winter_room"]
report = a.report(r)
pending = [x for x in r["quality"]["items"] if x["name"] == "冬季 MAU 送風溫度上限"]

# 1. FFU heat and the energy balance are unchanged.
check("FFU heat is retained when process gains are 0 %", wr["fan_retained_kw"] > 0, wr["fan_retained_kw"])
half = a.calculate(project(winter_ffu_ratio="50"))["winter_room"]
check("FFU running ratio scales retained fan heat independently", abs(half["fan_retained_kw"] - 0.5 * wr["fan_retained_kw"]) < 1e-9,
      (half["fan_retained_kw"], wr["fan_retained_kw"]))
check("MAU supply is capped at the stated limit", wr["mau_temp_capped"] and abs(wr["supply_t"] - 40) < 1e-9, wr["supply_t"])
check("remaining room heat loss is positive", wr["terminal_heat_kw"] > 0, wr["terminal_heat_kw"])
check("winter sensible balance closes", abs(wr["sensible_residual_kw"]) < 1e-6, wr["sensible_residual_kw"])

# 2. The unassigned demand stays out of HW and NP.
check("no heat source is assigned", wr["terminal_heat_source"] is None)
hw = r["water"]["HW"]
expected = max(r["summer"]["reheat_kw"], r["winter"]["reheat_kw"]) * r["sf"]
check("HW design load excludes the unassigned room heat", abs(hw["load_kw"] - expected) < 1e-6, (hw["load_kw"], expected))
if hw["linked"]:
    check("linked HW flow is sized from that load", abs(hw["capacity_kw"] - hw["load_kw"]) < 1e-6, (hw["capacity_kw"], hw["load_kw"]))
mild = a.calculate(project(ow_t="20", winter_gain_ratio="100"))
check("milder winter needs no room heat", mild["winter_room"]["terminal_heat_kw"] == 0 and not mild["winter_room"]["mau_temp_capped"])
check("NP design is unaffected by the unassigned room heat",
      abs(mild["electric"]["NP"]["design_current_a"] - r["electric"]["NP"]["design_current_a"]) < 1e-9)

# 3. Every text states the actual allocation.
claims_hw = ("已轉列室內加熱需求並計入 HW", "已計入 HW")
warn = [w for w in r["warnings"] if "冬季 MAU 送風溫度已限制於上限" in w]
check("warning names an unassigned demand pending a heat source",
      warn and "未配置室內加熱需求" in warn[0] and "待指定熱源" in warn[0] and "未計入 HW 或 NP" in warn[0], warn)
check("no warning claims the heat is in HW", not any(c in w for w in r["warnings"] for c in claims_hw))
check("report states the unassigned demand", "未配置熱源，待指定；未計入 HW 或 NP" in report)
check("report does not claim the heat is in HW", "（已計入 HW）" not in report)
check("quality lists the cap as pending data", len(pending) == 1 and pending[0]["status"] == "待資料", pending)
detail = pending[0]["detail"] if pending else ""
check("quality detail uses the stated limit and the unassigned amount",
      "40°C" in detail and f"{wr['terminal_heat_kw']:.2f} kW" in detail and "未計入 HW 或 NP" in detail, detail)
r35 = a.calculate(project(winter_mau_max_t="35"))
d35 = next(x["detail"] for x in r35["quality"]["items"] if x["name"] == "冬季 MAU 送風溫度上限")
check("a different limit is reported as set (not a fixed 40 °C)", "35°C" in d35 and "40°C" not in d35, d35)
check("milder winter adds no room-heat note or pending item",
      "室內加熱需求" not in a.report(mild) and not any(x["name"] == "冬季 MAU 送風溫度上限" for x in mild["quality"]["items"]))

# 4. English renderings of the new texts contain no Chinese.
term_line = next((line for line in report.splitlines() if "室內加熱需求" in line), "")
for name, text in (("warning", warn[0] if warn else ""), ("quality detail", detail), ("report line", term_line)):
    english = i18n.translate(text, "en")
    check(f"{name} translates fully to English", text and not CJK.search(english), english)

# 5. There is no way to assign a heat source in this build.
q = copy.deepcopy(project())
q["inputs"]["winter_terminal_heat_source"] = "HW"
try:
    a.validate_project(q)
    check("heat-source selection is not an accepted input in this build", False, "accepted")
except ValidationError as e:
    check("heat-source selection is not an accepted input in this build", e.field_name == "winter_terminal_heat_source", e)

failed = [c for c in checks if not c["passed"]]
(ROOT / "evidence").mkdir(exist_ok=True)
(ROOT / "evidence" / "Winter_Terminal_Heat_Checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
for c in failed:
    print("FAIL", c["name"], c["detail"])
print(f"winter terminal heat checks: {len(checks) - len(failed)}/{len(checks)} passed")
sys.exit(1 if failed else 0)
