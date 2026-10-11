"""Focused source regressions; real widgets are checked by native self-tests."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from facility_studio.resilience_acceptance import run_checks

result = run_checks()
(ROOT / "evidence/V559_Resilience_Checks.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("V559 resilience checks passed:", len(result["checks"]))
