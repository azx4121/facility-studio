"""Opt-in pytest diagnostics; never retries, creates a root, or cleans leaked roots.

Load via -p native_tk_trace with NATIVE_TK_TRACE=/path/to/events.jsonl.
Unexpected display skips fail the run. The original failure/skip is also logged.
"""
from __future__ import annotations

import gc
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback
import weakref

import pytest

ROOTS = weakref.WeakValueDictionary()
DESTINATION = None
CURRENT = None
ORIGINAL_INIT = ORIGINAL_DESTROY = None
COUNTER = 0
EVENT_SEQUENCE = 0


def expected_skip(nodeid, reason):
    return (nodeid.endswith("::test_tk9_side_buttons_do_not_scroll_page") and
            "Tk 8.6 Button-4/5 on X11 represent wheel events" in reason)


def process_resources():
    result = dict(python_threads=threading.active_count())
    if sys.platform == "win32":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        user = ctypes.WinDLL("user32", use_last_error=True)
        handle = ctypes.c_void_p(-1)  # GetCurrentProcess pseudo-handle.
        count = ctypes.c_uint32()
        kernel.GetProcessHandleCount.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        kernel.GetProcessHandleCount.restype = ctypes.c_int
        user.GetGuiResources.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        user.GetGuiResources.restype = ctypes.c_uint32
        if kernel.GetProcessHandleCount(handle, ctypes.byref(count)):
            result["windows_handles"] = count.value
        result["gdi_objects"] = user.GetGuiResources(handle, 0)
        result["user_objects"] = user.GetGuiResources(handle, 1)
    return result


def emit(event, **data):
    global EVENT_SEQUENCE
    if DESTINATION is None:
        return
    EVENT_SEQUENCE += 1
    record = dict(event=event, sequence=EVENT_SEQUENCE, monotonic=time.monotonic(),
                  pid=os.getpid(), thread=threading.get_ident(), nodeid=CURRENT, **data)
    with DESTINATION.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=True, default=str) + "\n")


def readable_paths():
    """Python reads of candidate Tcl/Tk init files; no interpreter side effects."""
    paths = set()
    for key in ("TCL_LIBRARY", "TK_LIBRARY"):
        if os.environ.get(key):
            paths.add(Path(os.environ[key]) / ("init.tcl" if key == "TCL_LIBRARY" else "tk.tcl"))
    for prefix in {sys.prefix, sys.base_prefix, str(Path(sys.executable).parent)}:
        base = Path(prefix)
        for pattern in ("tcl/tcl*/init.tcl", "tcl/tk*/tk.tcl", "lib/tcl*/init.tcl",
                        "lib/tk*/tk.tcl", "../tcl/tcl*/init.tcl"):
            paths.update(base.glob(pattern))
    for root in list(ROOTS.values()):
        try:
            paths.add(Path(root.tk.call("info", "library")) / "init.tcl")
        except Exception:
            pass
    records = []
    for path in sorted(paths, key=str):
        item = dict(path=str(path))
        try:
            data = path.read_bytes()
            stat = path.stat()
            item.update(readable=True, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                        mtime_ns=stat.st_mtime_ns)
        except Exception as error:
            item.update(readable=False, error=repr(error))
        records.append(item)
    return records


def roots_snapshot():
    result = []
    for serial, root in list(ROOTS.items()):
        record = dict(serial=serial, python_id=id(root))
        try:
            path = str(Path(root.tk.call("info", "library")) / "init.tcl")
            record["tcl_init_path"] = path
            record["tcl_file_readable"] = root.tk.call("file", "readable", path)
        except Exception as error:
            record["tcl_readable_error"] = repr(error)
        try:
            record["exists"] = bool(int(root.tk.call("winfo", "exists", ".")))
            record["children"] = root.tk.call("winfo", "children", ".")
            record["pending_after"] = root.tk.call("after", "info")
        except Exception as error:
            record["query_error"] = repr(error)
        result.append(record)
    return result


def environment():
    import tkinter as tk
    default = getattr(tk, "_default_root", None)
    return dict(cwd=os.getcwd(), gc_counts=gc.get_count(), gc_thresholds=gc.get_threshold(),
                process_resources=process_resources(),
                default_root_id=id(default) if default is not None else None,
                environment={key: os.environ.get(key) for key in (
                    "TCL_LIBRARY", "TK_LIBRARY", "TCLLIBPATH", "PYTHONHOME", "PYTHONPATH",
                    "FACILITY_TEST_PLATFORM", "FACILITY_REQUIRE_DISPLAY", "DISPLAY")},
                roots=roots_snapshot(), init_files=readable_paths())


def traced_init(root, *args, **kwargs):
    global COUNTER
    COUNTER += 1
    serial = COUNTER
    emit("tk_init_before", serial=serial, state=environment(), kwargs=kwargs)
    try:
        ORIGINAL_INIT(root, *args, **kwargs)
    except BaseException:
        emit("tk_init_error", serial=serial, error=traceback.format_exc(), state=environment())
        raise
    ROOTS[serial] = root
    details = {}
    for key, command in (("tcl", ("info", "patchlevel")), ("library", ("info", "library")),
                         ("auto_path", ("set", "auto_path")),
                         ("tcl_executable", ("info", "nameofexecutable")),
                         ("tk", ("package", "present", "Tk")),
                         ("windowing", ("tk", "windowingsystem"))):
        try:
            details[key] = root.tk.call(*command)
        except Exception as error:
            details[key] = repr(error)
    emit("tk_init_success", serial=serial, python_id=id(root), details=details)


def traced_destroy(root, *args, **kwargs):
    emit("tk_destroy_before", python_id=id(root), roots=roots_snapshot())
    try:
        return ORIGINAL_DESTROY(root, *args, **kwargs)
    finally:
        emit("tk_destroy_after", python_id=id(root), roots=roots_snapshot())


def pytest_configure(config):
    global DESTINATION, ORIGINAL_INIT, ORIGINAL_DESTROY
    import tkinter as tk
    filename = os.environ.get("NATIVE_TK_TRACE")
    if not filename:
        raise pytest.UsageError("native_tk_trace requires NATIVE_TK_TRACE")
    DESTINATION = Path(filename).resolve()
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    ORIGINAL_INIT, ORIGINAL_DESTROY = tk.Tk.__init__, tk.Tk.destroy
    tk.Tk.__init__, tk.Tk.destroy = traced_init, traced_destroy
    emit("session_start", executable=sys.executable, python=sys.version,
         platform=sys.platform, state=environment())


def pytest_collection_finish(session):
    emit("collected", nodeids=[item.nodeid for item in session.items])


def pytest_runtest_logstart(nodeid, location):
    global CURRENT
    CURRENT = nodeid
    emit("test_start", state=environment())


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    original = str(report.longrepr) if report.longrepr else ""
    if report.skipped:
        emit("original_skip", phase=report.when, reason=original)
        if not expected_skip(item.nodeid, original):
            report.outcome = "failed"
            report.longrepr = "Unexpected native suite skip (original reason retained): " + original
    emit("test_report", phase=report.when, outcome=report.outcome,
         detail=str(report.longrepr) if report.longrepr else None)


def pytest_runtest_logfinish(nodeid, location):
    emit("test_finish", state=environment())


def pytest_sessionfinish(session, exitstatus):
    emit("session_finish", exitstatus=int(exitstatus), state=environment())


def pytest_unconfigure(config):
    import tkinter as tk
    if ORIGINAL_INIT is not None:
        tk.Tk.__init__, tk.Tk.destroy = ORIGINAL_INIT, ORIGINAL_DESTROY
