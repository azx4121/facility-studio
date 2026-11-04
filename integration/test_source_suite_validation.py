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
    if suite == "audit_regressions":
        return dict(passed=True, checks=1, assertions=checks, gui_checks=1)
    return dict(passed=True, checks=checks, gui_checks=1, callback_errors=[])


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
