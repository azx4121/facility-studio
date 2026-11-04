"""Source runner must reject false/stale evidence despite a zero process exit."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("source_sandbox_checks", ROOT / "windows/winrelease/source_sandbox_checks.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def payload(suite):
    checks = [dict(name="sample", passed=True)]
    if suite == "security_checks":
        return dict(source="windows", checks=checks, passed=1, failed=[])
    if suite == "stress100":
        return dict(passed=True, failed_checks=[], software_failed=0, scenario_count=100,
                    cases=[dict(software_pass=True) for _ in range(100)])
    checks.append(dict(name="GUI sample", passed=True))
    if suite == "audit_regressions":
        return dict(passed=True, checks=2, formula_checks=1, assertions=checks, gui_checks=1)
    return dict(passed=True, checks=checks, numeric_and_report_checks=1, gui_checks=1, callback_errors=[])


def execute(tmp_path, monkeypatch, suite, value, *, exit_code=0, failure=None, stale=False):
    out = tmp_path / "evidence"
    out.mkdir()
    path = out / "result.json"
    if stale:
        path.write_text(json.dumps(payload(suite)))

    def run(*args, **kwargs):
        if failure:
            raise failure
        if value is not None:
            path.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")
        return SimpleNamespace(returncode=exit_code)

    monkeypatch.setattr(runner.subprocess, "run", run)
    result = runner.run_suites([[f"windows/tests/{suite}.py", "--output", str(path)]], tmp_path, out)
    summary = json.loads((out / "Source_Suite_Results.json").read_text())
    return result, summary


@pytest.mark.parametrize("suite", ["security_checks", "stress100", "audit_regressions", "report_regressions"])
def test_valid_evidence_and_success_exit_pass(tmp_path, monkeypatch, suite):
    result, summary = execute(tmp_path, monkeypatch, suite, payload(suite))
    assert result == 0
    assert summary[0]["passed"] is True


@pytest.mark.parametrize("suite", ["security_checks", "stress100", "audit_regressions", "report_regressions"])
@pytest.mark.parametrize("case", ["missing", "malformed", "list", "stale", "false", "lying_summary", "empty"])
def test_zero_exit_does_not_override_failed_or_stale_report(tmp_path, monkeypatch, suite, case):
    value = copy.deepcopy(payload(suite))
    if case in ("missing", "stale"):
        value = None
    elif case == "malformed":
        value = "{"
    elif case == "list":
        value = []
    elif case == "false":
        value["passed"] = False
    else:
        key = {"security_checks": "checks", "stress100": "cases", "audit_regressions": "assertions",
               "report_regressions": "checks"}[suite]
        if case == "empty":
            value[key] = []
        else:
            value[key][0]["software_pass" if suite == "stress100" else "passed"] = False
    result, summary = execute(tmp_path, monkeypatch, suite, value, stale=case == "stale")
    assert result != 0
    assert summary[0]["exit_code"] == 0
    assert summary[0]["passed"] is False
    assert summary[0]["evidence_error"]


@pytest.mark.parametrize("failure", [subprocess.TimeoutExpired("test", 300), OSError("cannot execute")])
def test_timeout_or_launch_failure_preserves_failed_summary(tmp_path, monkeypatch, failure):
    result, summary = execute(tmp_path, monkeypatch, "security_checks", None, failure=failure)
    assert result != 0
    assert summary[0]["passed"] is False
    assert summary[0]["exit_code"] is None
    assert type(failure).__name__ in summary[0]["evidence_error"]


def test_nonzero_exit_never_passes_even_with_valid_evidence(tmp_path, monkeypatch):
    result, summary = execute(tmp_path, monkeypatch, "security_checks", payload("security_checks"), exit_code=3)
    assert result == 3
    assert summary[0]["passed"] is False


@pytest.mark.parametrize("platform", ["macos", "windows"])
@pytest.mark.parametrize("checks,exit_code", [([{"passed": True}], 0), ([{"passed": False}], 1),
                                             ([{"passed": True}, {"passed": False}], 1),
                                             ([{"passed": 1}], 1), ([], 1)])
def test_security_entrypoint_exits_nonzero_for_any_failed_result(platform, checks, exit_code):
    # Exercise the real script's finalization without requiring numerical dependencies.
    tree = ast.parse((ROOT / platform / "tests/security_checks.py").read_text(encoding="utf-8"))
    termination = ast.Module(body=[tree.body[-1]], type_ignores=[])
    with pytest.raises(SystemExit) as result:
        exec(compile(termination, "security_checks.py", "exec"), {"checks": checks})
    assert result.value.code == exit_code


def test_duplicate_json_keys_are_rejected(tmp_path, monkeypatch):
    result, summary = execute(tmp_path, monkeypatch, "security_checks", '{"passed":0,"passed":1}')
    assert result != 0
    assert summary[0]["evidence_error"]


def test_empty_suite_selection_cannot_pass(tmp_path):
    with pytest.raises(RuntimeError, match="No source suites"):
        runner.run_suites([], tmp_path, tmp_path)


REAL_SCHEMA_FIXTURES = {
    "audit_regressions": "source_suite_audit_repeated_labels.json",
    "report_regressions": "source_suite_report_schema.json",
}


def real_schema(suite):
    return json.loads((ROOT / "integration/fixtures" / REAL_SCHEMA_FIXTURES[suite]).read_text(encoding="utf-8"))


@pytest.mark.parametrize("suite", REAL_SCHEMA_FIXTURES)
def test_representative_real_source_schema_is_accepted(tmp_path, monkeypatch, suite):
    report = real_schema(suite)
    if suite == "audit_regressions":
        checks = report["assertions"]
        assert len(checks) > len({check["name"] for check in checks})
    result, summary = execute(tmp_path, monkeypatch, suite, report)
    assert result == 0
    assert summary[0]["passed"] is True


@pytest.mark.parametrize("suite", REAL_SCHEMA_FIXTURES)
@pytest.mark.parametrize("mutation", [
    "overall_false", "overall_int", "failed_observation", "numeric_passed", "missing_passed",
    "empty_name", "missing_name", "nonobject_check", "empty_checks", "missing_checks",
    "dropped_observation", "added_observation", "numeric_count_wrong", "numeric_count_missing",
    "numeric_count_bool", "numeric_count_zero", "gui_count_wrong", "gui_count_missing",
    "gui_count_bool", "gui_count_zero",
])
def test_real_schema_negative_mutations_fail_closed(tmp_path, monkeypatch, suite, mutation):
    report = real_schema(suite)
    key = "assertions" if suite == "audit_regressions" else "checks"
    numeric = "formula_checks" if suite == "audit_regressions" else "numeric_and_report_checks"
    checks = report[key]
    # Mutate the last occurrence, ensuring a passing earlier duplicate cannot
    # mask failure in a later observation.
    check = checks[-1]
    if mutation == "overall_false":
        report["passed"] = False
    elif mutation == "overall_int":
        report["passed"] = 1
    elif mutation == "failed_observation":
        check["passed"] = False
    elif mutation == "numeric_passed":
        check["passed"] = 1
    elif mutation == "missing_passed":
        del check["passed"]
    elif mutation == "empty_name":
        check["name"] = " "
    elif mutation == "missing_name":
        del check["name"]
    elif mutation == "nonobject_check":
        checks[-1] = True
    elif mutation == "empty_checks":
        report[key] = []
    elif mutation == "missing_checks":
        del report[key]
    elif mutation == "dropped_observation":
        checks.pop()
    elif mutation == "added_observation":
        checks.append(dict(name="unexpected extra", passed=True))
    else:
        field = numeric if mutation.startswith("numeric_count") else "gui_checks"
        if mutation.endswith("missing"):
            del report[field]
        elif mutation.endswith("bool"):
            report[field] = True
        elif mutation.endswith("zero"):
            report[field] = 0
        else:
            report[field] += 1
    result, summary = execute(tmp_path, monkeypatch, suite, report)
    assert result != 0
    assert summary[0]["exit_code"] == 0
    assert summary[0]["passed"] is False
    assert summary[0]["evidence_error"]


@pytest.mark.parametrize("total", [None, True, "7", 6, 8])
def test_audit_total_is_a_strict_matching_count(tmp_path, monkeypatch, total):
    report = real_schema("audit_regressions")
    report["checks"] = total
    result, _ = execute(tmp_path, monkeypatch, "audit_regressions", report)
    assert result != 0


@pytest.mark.parametrize("errors", [None, {}, "", ["unhandled callback"]])
def test_report_callback_errors_are_required_and_empty(tmp_path, monkeypatch, errors):
    report = real_schema("report_regressions")
    report["callback_errors"] = errors
    result, _ = execute(tmp_path, monkeypatch, "report_regressions", report)
    assert result != 0


def test_security_and_report_duplicate_names_remain_invalid(tmp_path, monkeypatch):
    report = real_schema("report_regressions")
    report["checks"][-1]["name"] = report["checks"][0]["name"]
    result, _ = execute(tmp_path, monkeypatch, "report_regressions", report)
    assert result != 0
    assert not runner._passing_checks([dict(name="same", passed=True)] * 2)
