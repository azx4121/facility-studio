"""Controlled Windows fd/sys capture A/B; retain every result, never retry tests.

This diagnostic intentionally exits nonzero if EITHER arm has any failure.
sys-only success is reported separately, never substituted for the failing arm.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from run_lifecycle_diagnostics import fingerprint, groups, junit_summary


HERE = Path(__file__).resolve().parent


def binary_identity(path):
    path = Path(path)
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size)


def minimal_summary(path, count):
    if not path.exists():
        return dict(accepted=False, error="JUnit output missing")
    cases = list(ET.parse(path).iter("testcase"))
    results = {tag: sum(c.find(tag) is not None for c in cases) for tag in ("failure", "error", "skipped")}
    names = {c.get("name", "") for c in cases}
    expected = {f"test_fresh_tcl_tk_initialization[{kind}-{i}]" for kind in ("tcl", "tk") for i in range(count)}
    return dict(tests=len(cases), expected_tests=count * 2, **results,
                missing=sorted(expected - names), unexpected=sorted(names - expected),
                accepted=names == expected and len(cases) == count * 2 and not any(results.values()))


def summarize(receipts, expected_attempts, unchanged):
    by_mode = {}
    for mode in ("fd", "sys"):
        selected = [r for r in receipts if r["capture"] == mode]
        by_mode[mode] = dict(attempts=len(selected), failures=sum(not r["passed"] for r in selected),
                             all_passed=bool(selected) and all(r["passed"] for r in selected))
    complete = len(receipts) == expected_attempts
    return dict(passed=complete and unchanged and all(r["passed"] for r in receipts),
                complete=complete, expected_attempts=expected_attempts, attempts=len(receipts),
                source_python_files_unchanged=unchanged, capture_modes=by_mode,
                policy="Both arms retained; no retry, skip, or later success replaces any failure",
                native_windows=True, product_source_changed=False,
                frozen_binary_tested=False, formal_feed_accepted=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--count", type=int, default=50, help="Fresh Tcl-only and Tk roots EACH, per minimal attempt")
    parser.add_argument("--source-groups", nargs="*", choices=("isolated", "module-context", "prefix"), default=[])
    parser.add_argument("--timeout", type=int, default=240, help="Per-attempt timeout")
    parser.add_argument("--budget-seconds", type=int, default=840, help="Whole-probe execution budget; incomplete is failure")
    args = parser.parse_args(argv)
    if sys.platform != "win32" or platform.python_version() != "3.12.16":
        parser.error("This controlled probe requires native Windows and Python 3.12.16")
    if args.rounds < 1 or not 1 <= args.count <= 200:
        parser.error("Need positive rounds and count between 1 and 200")
    source, output = args.source.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    before = fingerprint(source)
    (output / "source-python-sha256.json").write_text(json.dumps(before, indent=2), encoding="utf-8")
    import _tkinter
    provenance = dict(platform=platform.platform(), python=sys.version, executable=sys.executable,
                      base_prefix=sys.base_prefix, prefix=sys.prefix, source=str(source),
                      runtime_files=[binary_identity(sys.executable), binary_identity(_tkinter.__file__)],
                      diagnostics={p.name: binary_identity(p) for p in (
                          HERE / "test_tcl_capture_probe.py", HERE / "run_tcl_capture_ab.py",
                          HERE / "native_tk_trace.py", HERE / "tcl_capture_failure_trace.py")}, count=args.count, rounds=args.rounds,
                      source_groups=args.source_groups, varying_factor="pytest capture method only: fd versus sys")
    for path in sorted((Path(sys.base_prefix) / "DLLs").glob("*t*.dll")):
        if path.name.lower().startswith(("tcl", "tk")):
            provenance["runtime_files"].append(binary_identity(path))
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    env = dict(os.environ, FACILITY_REQUIRE_DISPLAY="1", FACILITY_TEST_PLATFORM="windows",
               PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(HERE))
    for key in ("TCL_LIBRARY", "TK_LIBRARY", "PYTEST_ADDOPTS"):
        env.pop(key, None)
    selection = groups(source)
    tasks = [("minimal", [str(HERE / "test_tcl_capture_probe.py")])]
    tasks += [(name, selection[name]) for name in args.source_groups]
    receipts = []
    deadline = time.monotonic() + args.budget_seconds
    expected_attempts = args.rounds * 2 * len(tasks)
    stop = False
    for round_number in range(1, args.rounds + 1):
        # Alternate arm order to avoid associating sys capture with a warmed host.
        modes = ("fd", "sys") if round_number % 2 else ("sys", "fd")
        for name, selected in tasks:
            for mode in modes:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    stop = True
                    break
                attempt = output / f"round-{round_number:02d}-{name}-{mode}"
                attempt.mkdir()
                attempt_env = dict(env, NATIVE_TK_TRACE=str(attempt / "tk-events.jsonl"),
                                   TCL_CAPTURE_FAILURE_EVENTS=str(attempt / "library-failures.jsonl"),
                                   TCL_CAPTURE_PROBE_EVENTS=str(attempt / "minimal-events.jsonl"),
                                   TCL_CAPTURE_PROBE_COUNT=str(args.count),
                                   FACILITY_STUDIO_DATA=str(attempt / "data"),
                                   FACILITY_STUDIO_FUSION_DATA=str(attempt / "data"),
                                   FACILITY_STUDIO_PREFERENCES=str(attempt / "preferences.json"),
                                   MPLCONFIGDIR=str(attempt / "mpl-cache"))
                command = [sys.executable, "-m", "pytest", "-p", "native_tk_trace",
                           "-p", "tcl_capture_failure_trace", *selected,
                           "--capture=" + mode, "-q", "-ra", "--tb=long", "-p", "no:cacheprovider",
                           "--junitxml=" + str(attempt / "results.xml")]
                start = time.monotonic()
                with (attempt / "pytest.log").open("w", encoding="utf-8") as stream:
                    try:
                        result = subprocess.run(command, cwd=source, env=attempt_env, stdout=stream,
                                                stderr=subprocess.STDOUT, timeout=min(args.timeout, remaining))
                        code = result.returncode
                    except subprocess.TimeoutExpired:
                        code = 124
                        stream.write("\nTIMEOUT: retained as failure; never retried\n")
                summary = (minimal_summary(attempt / "results.xml", args.count) if name == "minimal"
                           else junit_summary(attempt / "results.xml"))
                receipt = dict(round=round_number, group=name, capture=mode, command=command,
                               exit_code=code, seconds=round(time.monotonic() - start, 3),
                               junit=summary, passed=code == 0 and summary["accepted"])
                receipts.append(receipt)
                print(json.dumps(receipt), flush=True)
                (output / "receipts.json").write_text(json.dumps(receipts, indent=2), encoding="utf-8")
            if stop:
                break
        if stop:
            break
    result = summarize(receipts, expected_attempts, fingerprint(source) == before)
    (output / "SUMMARY.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
