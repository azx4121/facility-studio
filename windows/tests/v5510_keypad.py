"""Key identity and insertion behavior; delivered widgets use native self-tests."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from facility_studio.keypad_acceptance import run_checks

result = run_checks()
(ROOT / "evidence/V5510_Keypad_Checks.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("V5510 keypad checks passed:", len(result["checks"]))
