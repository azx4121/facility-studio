"""Portable gatekeeping checks; never native Tcl/Tk acceptance."""
import json
from pathlib import Path

import run_tcl_capture_ab as ab
import test_tcl_capture_probe as probe


def test_minimal_summary_requires_every_parameter_without_failure(tmp_path):
    path = tmp_path / "results.xml"
    assert not ab.minimal_summary(path, 2)["accepted"]
    names = [f"test_fresh_tcl_tk_initialization[{kind}-{i}]" for kind in ("tcl", "tk") for i in range(2)]
    path.write_text("<testsuite>" + "".join(f'<testcase name="{name}"/>' for name in names) + "</testsuite>")
    assert ab.minimal_summary(path, 2)["accepted"]
    path.write_text(path.read_text().replace('/>', '><error message="initialization failed"/></testcase>', 1))
    assert not ab.minimal_summary(path, 2)["accepted"]


def test_passing_sys_arm_does_not_hide_failed_fd_arm():
    result = ab.summarize([dict(capture="fd", passed=False), dict(capture="sys", passed=True)], 2, True)
    assert not result["passed"]
    assert result["capture_modes"]["sys"]["all_passed"]
    assert result["capture_modes"]["fd"]["failures"] == 1


def test_incomplete_or_mutated_source_cannot_pass():
    rows = [dict(capture="fd", passed=True), dict(capture="sys", passed=True)]
    assert not ab.summarize(rows, 4, True)["passed"]
    assert not ab.summarize(rows, 2, False)["passed"]
    assert ab.summarize(rows, 2, True)["passed"]


def test_inventory_includes_nested_tk_script_files(tmp_path, monkeypatch):
    path = tmp_path / "tcl" / "tk8.6" / "ttk" / "scrlbar.tcl"
    path.parent.mkdir(parents=True)
    path.write_text("# synthetic nested script\n")
    monkeypatch.setattr(probe.sys, "base_prefix", str(tmp_path))
    monkeypatch.delenv("TCL_LIBRARY", raising=False)
    monkeypatch.delenv("TK_LIBRARY", raising=False)
    rows = probe.library_inventory()
    assert len(rows) == 1 and rows[0]["path"] == str(path)
    assert rows[0]["readable"] and len(rows[0]["sha256"]) == 64
