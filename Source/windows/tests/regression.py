"""52 inherited scenarios, independently reconstructed physical quantities."""

import sys, json, importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from facility_studio import api as a

s = importlib.util.spec_from_file_location("independent", ROOT / "tests/independent.py")
ind = importlib.util.module_from_spec(s)
s.loader.exec_module(ind)
ind.a = a
checks = []
results = []
for c in json.loads((ROOT / "tests/scenarios.json").read_text(encoding="utf-8")):
    try:
        r = (
            a.calculate(c["project"])
            if c["model"] == "main"
            else a.nm_calculate(c["project"])
        )
        checks.extend(ind.independent_checks(c, r))
        report = a.report(r) if c["model"] == "main" else a.nm_report(r)
        (ROOT / "evidence" / f"{c['id']}.txt").write_text(report, encoding="utf-8")
        results.append(
            dict(
                id=c["id"], status=r["quality"]["status"], failed=r["quality"]["failed"]
            )
        )
    except a.ValidationError as e:
        results.append(dict(id=c["id"], error=str(e), field=e.field_name))
assert len(results) == 52 and {r["id"] for r in results if "error" in r} == {"F12", "F13", "F14", "B07", "B12", "B20", "N13"}, results
assert len(checks) == 1247 and all(x["passed"] for x in checks), [
    x for x in checks if not x["passed"]
]
(ROOT / "evidence/Scenario_Results.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
)
(ROOT / "evidence/Numeric_Checks.json").write_text(
    json.dumps(checks, indent=2), encoding="utf-8"
)
print("52 scenarios / 1247 independent checks passed; 7 expected rejections; B08 now adopts zero closed-loop static head")
