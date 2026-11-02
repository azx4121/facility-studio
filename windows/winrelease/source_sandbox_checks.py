"""Run meaningful source suites and preserve every exit status in native CI."""

import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    a = parser.parse_args()
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]
    suites = [
        ["windows/tests/electrical_units.py", "--gui"],
        ["windows/tests/lighting_presets.py", "--gui"],
        ["windows/tests/regression.py"],
        ["windows/tests/security_checks.py"],
        ["windows/tests/bilingual.py"],
        ["windows/tests/v556_features.py"],
        ["windows/tests/v557_inactive.py"],
        ["windows/tests/v558_review.py"],
        ["windows/tests/v559_resilience.py"],
        ["windows/tests/v5510_keypad.py"],
        ["windows/tests/v560_features.py"],
        ["windows/tests/reference_psychrometrics.py"],
        ["windows/tests/airflow_guard_checks.py"],
        ["windows/tests/optional_inputs_checks.py"],
        ["windows/tests/panel_demand_checks.py"],
        ["windows/tests/c2_coil_feasibility_checks.py"],
        ["windows/tests/winter_terminal_heat_checks.py"],
        ["windows/tests/ahu_link_boundary_checks.py"],
        ["windows/tests/fluid_adoption_checks.py"],
        ["windows/tests/fluid_selection_history_checks.py"],
        ["windows/tests/ui_theme_and_actions_checks.py"],
        ["windows/tests/ui_scaling_checks.py"],
        ["windows/tests/text_clipping_checks.py"],
        ["tools/verify_platform_sync.py"],
        ["windows/tests/stress100.py", "--output", str(out / "stress100.json")],
        [
            "windows/tests/audit_regressions.py",
            "--gui",
            "--output",
            str(out / "audit-regressions.json"),
        ],
        [
            "-X",
            "utf8=0",
            "windows/tests/report_regressions.py",
            "--gui",
            "--output",
            str(out / "report-regressions.json"),
        ],
    ]
    results = []
    for n, args in enumerate(suites):
        log = out / (
            f"{n:02d}-" + Path(next(x for x in args if x.endswith(".py"))).stem + ".log"
        )
        with log.open("w", encoding="utf-8") as file:
            r = subprocess.run(
                [sys.executable, *args],
                cwd=root,
                stdout=file,
                stderr=subprocess.STDOUT,
                timeout=300,
            )
        results.append(
            {
                "command": [sys.executable, *args],
                "exit_code": r.returncode,
                "log": log.name,
            }
        )
        print(json.dumps(results[-1]), flush=True)
        (out / "Source_Suite_Results.json").write_text(
            json.dumps(results, indent=2) + "\n", encoding="utf-8"
        )
        if r.returncode:
            print(
                log.read_text(encoding="utf-8", errors="replace")[-16000:], flush=True
            )
            return r.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
