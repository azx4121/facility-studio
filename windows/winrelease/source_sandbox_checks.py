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
        ["windows/tests/security_checks.py", "--output", str(out / "security-checks.json")],
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
    return run_suites(suites, root, out)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate evidence key: " + key)
        result[key] = value
    return result


def _passing_checks(checks):
    return (isinstance(checks, list) and bool(checks)
            and all(isinstance(c, dict) and c.get("passed") is True
                    and isinstance(c.get("name"), str) and c["name"].strip() for c in checks)
            and len({c["name"] for c in checks}) == len(checks))


def validate_report(path, suite):
    """A successful process is insufficient when its structured results fail."""
    try:
        report = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, ValueError) as exc:
        raise RuntimeError(f"Missing or unreadable source evidence: {path}") from exc
    if not isinstance(report, dict):
        raise RuntimeError(f"Source evidence must be an object: {path}")
    if suite == "security_checks":
        checks = report.get("checks")
        passed = report.get("passed")
        valid = (report.get("source") == "windows" and report.get("failed") == []
                 and type(passed) is int and _passing_checks(checks)
                 and passed == len(checks))
    elif suite == "stress100":
        cases = report.get("cases")
        valid = (report.get("passed") is True and report.get("failed_checks") == []
                 and report.get("software_failed") == 0 and report.get("scenario_count") == 100
                 and isinstance(cases, list) and len(cases) == 100
                 and all(isinstance(c, dict) and c.get("software_pass") is True for c in cases))
    elif suite in ("audit_regressions", "report_regressions"):
        checks = report.get("assertions" if suite == "audit_regressions" else "checks")
        valid = (report.get("passed") is True and _passing_checks(checks)
                 and type(report.get("gui_checks")) is int and report["gui_checks"] > 0)
        if suite == "audit_regressions":
            valid = valid and report.get("checks") == len(checks)
        else:
            valid = valid and report.get("callback_errors") == []
    else:
        raise RuntimeError(f"No source evidence validator for suite: {suite}")
    if not valid:
        raise RuntimeError(f"Source evidence contains failed or invalid results: {path}")


def run_suites(suites, root, out):
    if not suites:
        raise RuntimeError("No source suites were selected.")
    results = []
    summary = out / "Source_Suite_Results.json"
    summary.write_text("[]\n", encoding="utf-8")
    for n, args in enumerate(suites):
        suite = Path(next(x for x in args if x.endswith(".py"))).stem
        log = out / (f"{n:02d}-" + suite + ".log")
        report = Path(args[args.index("--output") + 1]) if "--output" in args else None
        if report is not None:
            # A previous green result must never satisfy a new process's check.
            report.unlink(missing_ok=True)
        error = None
        exit_code = None
        with log.open("w", encoding="utf-8") as file:
            try:
                r = subprocess.run([sys.executable, *args], cwd=root, stdout=file,
                                   stderr=subprocess.STDOUT, timeout=300)
                exit_code = r.returncode
            except (OSError, subprocess.TimeoutExpired) as exc:
                error = f"{type(exc).__name__}: {exc}"
        if exit_code == 0 and report is not None:
            try:
                validate_report(report, suite)
            except RuntimeError as exc:
                error = str(exc)
        passed = exit_code == 0 and error is None
        results.append(dict(command=[sys.executable, *args], exit_code=exit_code,
                            log=log.name, passed=passed, evidence_error=error))
        print(json.dumps(results[-1]), flush=True)
        summary.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        if not passed:
            print(log.read_text(encoding="utf-8", errors="replace")[-16000:], flush=True)
            return exit_code if exit_code and exit_code > 0 else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
