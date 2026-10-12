"""V5.6 water capacity, factory gases, T/P/Z and old-project migration."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from facility_studio.v560_acceptance import run_checks

result = run_checks()
(ROOT / 'evidence/V560_Expansion_Checks.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('V560 engineering checks passed:', len(result['checks']))
