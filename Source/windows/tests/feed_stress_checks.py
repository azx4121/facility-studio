"""Stress campaign A-F plus the F-1 regression, run as one test.

    python tests/feed_stress_checks.py              moderate sizes (about 3 minutes), no display needed
    python tests/feed_stress_checks.py --full       the sizes of the original campaign (3,000 / 2,000 / 1,500 cases)
    python tests/feed_stress_checks.py --mutation   also plant 19 engineering errors; every one must be noticed (about 6 minutes)

Groups (tests/feed_stress/)
  D  robustness: every active field at and beyond its bounds, 15 kinds of garbage text, random multi-field combinations
  A/B  every moist-air state against PsychroLib (pip install psychrolib==2.5.0); coil balances, water flow and pipe
       pressure drop recomputed from first principles; B11: an accepted airflow lets the coil reach its supply humidity
  C  one-factor changes move the answer the way physics says; inactive fields never change an output
  E  report numbers equal calculation numbers, thermodynamic hard limits, load-driven airflow above the multiple is 未達條件
  F  every load term by hand, equipment is never selected smaller than required
  G  airflow_guard_checks.py: the F-1 regression (reproducer, boundary scans, golden cases, vocabulary, PV range)

The original record of the campaign (before the F-1 fix) is in tests/fixtures/feed_stress_20261031/.
Linux/virtual-display evidence is not Windows-native acceptance; these checks need no display at all.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent
FULL = "--full" in sys.argv
MUTATION = "--mutation" in sys.argv
try:
    import psychrolib  # noqa: F401
except ImportError:
    raise SystemExit("BLOCKED: psychrolib is not installed (python -m pip install psychrolib==2.5.0); the PsychroLib comparison cannot run")

OUT = ROOT / "evidence" / "feed_stress"
OUT.mkdir(parents=True, exist_ok=True)
JOBS = [
    ("D robustness", ["feed_stress/stress_d.py", "3000" if FULL else "400", str(OUT / "d.json")]),
    ("A/B oracles", ["feed_stress/stress_ab.py", "2000" if FULL else "400", str(OUT / "ab.json")]),
    ("C one-factor changes", ["feed_stress/stress_c.py", str(OUT / "c.json")]),
    ("E report and hard limits", ["feed_stress/stress_e.py", "1500" if FULL else "400", str(OUT / "e.json")]),
    ("F hand calculation", ["feed_stress/stress_f.py", str(OUT / "f.json")]),
    ("G F-1 regression", ["airflow_guard_checks.py"]),
]
if MUTATION:
    JOBS.append(("Mutation test (19 planted errors)", ["feed_stress/mutate.py"]))

records = []
for name, argv in JOBS:
    started = time.perf_counter()
    done = subprocess.run([sys.executable, str(TESTS / argv[0]), *argv[1:]], cwd=ROOT, capture_output=True, text=True,
                          env=dict(os.environ, FS_SRC=str(ROOT)), timeout=3600)
    last = [l for l in (done.stdout + done.stderr).splitlines() if l.strip()]
    passes = sum(1 for l in done.stdout.splitlines() if l.startswith("PASS"))
    records.append(dict(group=name, passed=done.returncode == 0, seconds=round(time.perf_counter() - started, 1), checks_passed=passes or None,
                        tail=last[-1][:200] if last else "", failures=[l[:240] for l in done.stdout.splitlines() if l.startswith(("FAIL", "FAILED", "SURVIVED", "NOT APPLIED", "=="))][:12]))
    print(f"{'PASS' if done.returncode == 0 else 'FAIL':4} {name:34} {records[-1]['seconds']:7.1f}s  {records[-1]['tail'][:100]}", flush=True)
    for line in records[-1]["failures"]:
        print("       ", line)

(OUT / "summary.json").write_text(json.dumps(dict(full=FULL, mutation=MUTATION, groups=records), ensure_ascii=False, indent=2), encoding="utf-8")
failed = [r for r in records if not r["passed"]]
print(f"feed stress checks: {len(records) - len(failed)}/{len(records)} groups passed" + (" (full size)" if FULL else " (moderate size)"))
sys.exit(1 if failed else 0)
