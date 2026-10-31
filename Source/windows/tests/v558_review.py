"""Review follow-up source checks; GUI checks are run by native release self-tests."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from facility_studio.review_acceptance import run_checks

result = run_checks()
output = ROOT / "evidence/V558_Review_Checks.json"
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in result.items() if k != "checks"}, ensure_ascii=False))
print("Review follow-up checks passed:", len(result["checks"]))

