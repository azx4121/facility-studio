"""Portable checks of gatekeeping. These are not native Windows UI evidence."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

import native_tk_trace as trace
import run_lifecycle_diagnostics as lifecycle
import windows_display as display


def mode(width, height, bits=32):
    value = display.DEVMODEW()
    value.dmSize = ctypes.sizeof(value)
    value.dmPelsWidth, value.dmPelsHeight, value.dmBitsPerPel = width, height, bits
    value.dmDisplayFrequency = 60
    return value


def test_devmode_windows_abi_and_selection():
    assert ctypes.sizeof(display.DEVMODEW) == 220
    modes = [mode(1024, 768), mode(1920, 1080), mode(2560, 1440)]
    assert display.describe(display.choose_mode(modes, 1600, 1050))["width"] == 1920
    assert display.describe(display.choose_mode(modes, 1024, 768, True))["height"] == 768
    with pytest.raises(RuntimeError, match="No advertised"):
        display.choose_mode(modes, 1920, 1200, True)
    with pytest.raises(RuntimeError, match="No advertised"):
        display.choose_mode([mode(1920, 1080, 8)], 1920, 1080)


class FakeDisplay:
    def __init__(self, reject=False, bad_tk=False):
        self.original, self.large = mode(1024, 768), mode(1920, 1080)
        self.current = self.original
        self.reject, self.bad_tk = reject, bad_tk
        self.changes = []

    def mode(self, index):
        return self.current

    def modes(self):
        return [self.original, self.large]

    def change(self, mode, test=False):
        self.changes.append((mode, test))
        if test:
            return -2 if self.reject else 0
        self.current = mode
        return 0

    def metrics(self):
        return dict(screen=[self.current.dmPelsWidth, self.current.dmPelsHeight],
                    current_mode=display.describe(self.current), work_area=[0, 0, 1920, 1040])

    def verify_tk(self, *args):
        if self.bad_tk:
            raise AssertionError("Actual Tk geometry was not realized")
        return {"verified": True}


@pytest.mark.parametrize("child_code", [0, 7])
def test_display_restores_and_preserves_child_exit(monkeypatch, tmp_path, child_code):
    fake = FakeDisplay()
    monkeypatch.setattr(display, "NativeDisplay", lambda: fake)
    monkeypatch.setattr(display.time, "sleep", lambda _: None)
    monkeypatch.setattr(display.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=child_code))
    path = tmp_path / "evidence.json"
    assert display.main(["--evidence", str(path), "--", "child"]) == child_code
    receipt = json.loads(path.read_text())
    assert receipt["passed"] is (child_code == 0)
    assert fake.current is fake.original
    assert fake.changes == [(fake.large, True), (fake.large, False), (fake.original, False)]


@pytest.mark.parametrize("reject,bad_tk", [(True, False), (False, True)])
def test_display_precondition_failure_never_runs_child(monkeypatch, tmp_path, reject, bad_tk):
    fake = FakeDisplay(reject, bad_tk)
    monkeypatch.setattr(display, "NativeDisplay", lambda: fake)
    monkeypatch.setattr(display.time, "sleep", lambda _: None)
    monkeypatch.setattr(display.subprocess, "run", lambda *a, **kw: pytest.fail("Child must not run"))
    path = tmp_path / "evidence.json"
    assert display.main(["--evidence", str(path), "--", "child"]) == 1
    assert not json.loads(path.read_text())["passed"]
    assert fake.current is fake.original


def test_only_one_documented_tk86_feature_skip_is_expected():
    reason = "Tk 8.6 Button-4/5 on X11 represent wheel events"
    assert trace.expected_skip("test_combobox_wheel.py::test_tk9_side_buttons_do_not_scroll_page", reason)
    assert not trace.expected_skip("test_other.py::test_gui", reason)
    assert not trace.expected_skip("test_combobox_wheel.py::test_tk9_side_buttons_do_not_scroll_page",
                                   "Real Tk display required")


def test_plugin_retains_and_fails_an_unexpected_skip(tmp_path):
    test = tmp_path / "test_skip.py"
    test.write_text("import pytest\ndef test_gui():\n    pytest.skip('Real Tk display required')\n")
    path = tmp_path / "trace.jsonl"
    env = dict(os.environ, PYTHONPATH=str(Path(trace.__file__).parent), NATIVE_TK_TRACE=str(path))
    result = subprocess.run([sys.executable, "-m", "pytest", "-p", "native_tk_trace", str(test),
                             "-q", "-p", "no:cacheprovider"], env=env, capture_output=True, text=True)
    assert result.returncode == 1, result.stdout + result.stderr
    events = [json.loads(line) for line in path.read_text().splitlines()]
    assert any(e["event"] == "original_skip" and "Real Tk display required" in e["reason"] for e in events)
    assert any(e["event"] == "test_report" and e["outcome"] == "failed" for e in events)


def test_plugin_captures_tcl_error_before_original_test_masks_it(tmp_path):
    test = tmp_path / "test_masked_error.py"
    test.write_text("""import pytest
import tkinter as tk
import native_tk_trace

def test_gui(monkeypatch):
    def failed_init(*args, **kwargs):
        raise tk.TclError('diagnostic synthetic init.tcl read failure')
    monkeypatch.setattr(native_tk_trace, 'ORIGINAL_INIT', failed_init)
    try:
        tk.Tk()
    except tk.TclError:
        pytest.skip('Real Tk display required')
""")
    path = tmp_path / "trace.jsonl"
    env = dict(os.environ, PYTHONPATH=str(Path(trace.__file__).parent), NATIVE_TK_TRACE=str(path))
    result = subprocess.run([sys.executable, "-m", "pytest", "-p", "native_tk_trace", str(test),
                             "-q", "-p", "no:cacheprovider"], env=env, capture_output=True, text=True)
    assert result.returncode == 1, result.stdout + result.stderr
    events = [json.loads(line) for line in path.read_text().splitlines()]
    assert any(e["event"] == "tk_init_error" and "synthetic init.tcl read failure" in e["error"] for e in events)
    assert any(e["event"] == "original_skip" for e in events)


def test_junit_does_not_accept_missing_or_skipped_targets(tmp_path):
    assert not lifecycle.junit_summary(tmp_path / "missing.xml")["accepted"]
    path = tmp_path / "results.xml"
    targets = [t.split("::", 1)[1] for t in lifecycle.TARGETS]
    path.write_text('<testsuite>' + ''.join(
        '<testcase name="' + t + '"><skipped message="display"/></testcase>' for t in targets) + '</testsuite>')
    assert not lifecycle.junit_summary(path)["accepted"]
    path.write_text('<testsuite>' + ''.join('<testcase name="' + t + '"/>' for t in targets) + '</testsuite>')
    assert lifecycle.junit_summary(path)["accepted"]
