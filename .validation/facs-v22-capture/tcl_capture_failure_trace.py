"""Additional A/B evidence: complete support-file inventory for every failure.

No roots/interpreters are created here. Existing stable native_tk_trace is intact.
"""
import json
import os
from pathlib import Path
import time

from test_tcl_capture_probe import library_inventory, std_handles

BASELINE_PATHS = set()
CAPTURE = None


def emit(event, **data):
    with Path(os.environ["TCL_CAPTURE_FAILURE_EVENTS"]).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(dict(event=event, pid=os.getpid(), monotonic=time.monotonic(),
                                    capture=CAPTURE, **data), default=str) + "\n")


def pytest_configure(config):
    global BASELINE_PATHS, CAPTURE
    CAPTURE = config.getoption("capture")
    rows = library_inventory()
    BASELINE_PATHS = {row["path"] for row in rows}
    emit("library_baseline", all_library_files=rows, standard_handles=std_handles())


def pytest_runtest_logreport(report):
    if not report.failed:
        return
    rows = library_inventory()
    present = {row["path"] for row in rows}
    rows.extend(dict(path=path, readable=False, error="Previously inventoried file is now absent")
                for path in sorted(BASELINE_PATHS - present))
    emit("failed_test_inventory", nodeid=report.nodeid, phase=report.when,
         original_failure=str(report.longrepr), all_library_files=rows,
         standard_handles=std_handles())
