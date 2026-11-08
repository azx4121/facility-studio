"""Product-free Windows Tcl/Tk initialization across pytest capture phases.

Each parameter is a separate test, forcing the normal capture suspend/resume
boundaries. No retries, shared interpreter, application imports or forced GC.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback

import pytest


def library_inventory():
    """Read every Tcl/Tk support file, including nested scripts, after an error."""
    bases = {Path(sys.base_prefix) / "tcl"}
    bases.update(Path(os.environ[k]) for k in ("TCL_LIBRARY", "TK_LIBRARY") if os.environ.get(k))
    records = []
    seen = set()
    for base in sorted(bases, key=str):
        if not base.is_dir():
            records.append(dict(path=str(base), readable=False, error="Library directory is absent"))
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or str(path) in seen:
                continue
            seen.add(str(path))
            row = dict(path=str(path))
            try:
                content = path.read_bytes()
                row.update(readable=True, bytes=len(content), sha256=hashlib.sha256(content).hexdigest(),
                           mtime_ns=path.stat().st_mtime_ns)
            except OSError as error:
                row.update(readable=False, error=repr(error), winerror=getattr(error, "winerror", None))
            records.append(row)
    return records


def std_handles():
    """Observe OS/CRT handles without changing or duplicating any handle."""
    if sys.platform != "win32":
        return {"native_windows": False}
    import msvcrt
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.GetStdHandle.argtypes = [ctypes.c_uint32]
    api.GetStdHandle.restype = ctypes.c_void_p
    api.GetHandleInformation.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    api.GetHandleInformation.restype = ctypes.c_int
    api.GetFileType.argtypes = [ctypes.c_void_p]
    api.GetFileType.restype = ctypes.c_uint32
    result = {}
    for fd, name, selector in ((0, "stdin", -10), (1, "stdout", -11), (2, "stderr", -12)):
        handle = api.GetStdHandle(selector)
        row = dict(os_handle=handle)
        try:
            row["crt_handle"] = msvcrt.get_osfhandle(fd)
        except OSError as error:
            row["crt_error"] = repr(error)
        flags = ctypes.c_uint32()
        ctypes.set_last_error(0)
        row["valid"] = bool(api.GetHandleInformation(handle, ctypes.byref(flags)))
        row["handle_error"] = ctypes.get_last_error()
        row["flags"] = flags.value
        ctypes.set_last_error(0)
        row["file_type"] = api.GetFileType(handle)
        row["file_type_error"] = ctypes.get_last_error()
        result[name] = row
    return result


def record(row):
    path = os.environ.get("TCL_CAPTURE_PROBE_EVENTS")
    if path:
        with Path(path).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=True, default=str) + "\n")


def verify_tcl_bootstrap(interpreter):
    """Check eager initialization plus the standard lazy library-load contract.

    Tcl 8.6's init.tcl defines auto_load. Its tclIndex maps tcl_findLibrary
    to auto.tcl, so a Tcl-only interpreter need not expose that command yet.
    This explicit load is an assertion, not a retry of failed initialization.
    """
    assert interpreter.call("info", "commands", "auto_load"), "Missing initialized Tcl auto_load command"
    before = bool(interpreter.call("info", "commands", "tcl_findLibrary"))
    loaded = int(interpreter.call("auto_load", "tcl_findLibrary"))
    assert loaded == 1, "Tcl could not autoload its tcl_findLibrary library procedure"
    assert interpreter.call("info", "procs", "tcl_findLibrary"), "Autoload did not define tcl_findLibrary"
    return dict(tcl_findLibrary_initially_available=before, tcl_findLibrary_autoload_result=loaded)


@pytest.mark.parametrize("iteration", range(int(os.environ.get("TCL_CAPTURE_PROBE_COUNT", "50"))))
@pytest.mark.parametrize("kind", ["tcl", "tk"])
def test_fresh_tcl_tk_initialization(iteration, kind, request):
    import tkinter as tk
    assert sys.platform == "win32", "Native Windows required; no skip"
    root = None
    row = dict(iteration=iteration, kind=kind, pid=os.getpid(),
               capture=request.config.getoption("capture"), monotonic=time.monotonic(),
               handles_before=std_handles(), passed=False)
    try:
        root = tk.Tk(useTk=kind == "tk")
        row["tcl"] = root.tk.call("info", "patchlevel")
        row["library"] = root.tk.call("info", "library")
        row.update(verify_tcl_bootstrap(root.tk))
        row["channels"] = root.tk.call("chan", "names")
        # This reads through Tcl, distinct from Python's independent file reads.
        path = str(Path(row["library"]) / "init.tcl")
        channel = root.tk.call("open", path, "rb")
        try:
            body = root.tk.call("read", channel)
            row["tcl_init_read_bytes"] = len(body)
            assert len(body) > 1000, "Tcl returned a truncated/empty init.tcl"
        finally:
            root.tk.call("close", channel)
        if kind == "tk":
            row["tk"] = root.tk.call("package", "present", "Tk")
            assert root.tk.call("tk", "windowingsystem") == "win32"
            root.withdraw()
            root.update()
        row["passed"] = True
    except BaseException:
        row["error"] = traceback.format_exc()
        # Snapshot ALL support files, not just init.tcl/tk.tcl. This includes the
        # actual scrlbar/icons/fonts/msgcat subfiles named by initialization errors.
        row["all_library_files_after_failure"] = library_inventory()
        raise
    finally:
        try:
            if root is not None and kind == "tk":
                root.destroy()
        except BaseException:
            row["passed"] = False
            row["cleanup_error"] = traceback.format_exc()
            row["all_library_files_after_failure"] = library_inventory()
            raise
        finally:
            row["handles_after"] = std_handles()
            record(row)

