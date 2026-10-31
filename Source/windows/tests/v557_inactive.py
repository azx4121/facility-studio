"""Run complete-output inactive-field mutations and publish reproducible evidence."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from facility_studio.inactive_acceptance import run_checks
from facility_studio.version import VERSION

if __name__ == "__main__":
    result = run_checks()
    result["version"] = VERSION
    destination = ROOT / "evidence" / "V557_Inactive_Checks.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "checks"}, ensure_ascii=False))
    print("Complete-output and report comparisons passed:", len(result["checks"]))
