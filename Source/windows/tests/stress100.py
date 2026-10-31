"""Source entry point for the same recipes bundled native self-tests execute."""
import argparse
import json
from pathlib import Path
import sys

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from facility_studio.stress_acceptance import run_checks

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--repeat', type=int, default=20)
args = parser.parse_args()
evidence = run_checks(scenarios=100, repeat=args.repeat)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps({k: v for k, v in evidence.items() if k not in ('cases', 'failed_checks')}, ensure_ascii=False))
for failure in evidence['cases']:
    if not failure['software_pass']:
        print(failure['id']+': '+failure['error_message'], file=sys.stderr)
sys.exit(0 if evidence['passed'] else 1)
