"""Repeat original tests in fresh processes and preserve every attempt's result.

The prefix group reproduces collection/file order through test_combobox_wheel.py,
including the earlier AHU test. Tests and product sources are never rewritten.
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


HERE = Path(__file__).resolve().parent
TARGETS = [
    "integration/test_ahu_parent_close.py::test_parent_close_respects_independent_ahu_save_discard_cancel[None-workspace]",
    "integration/test_combobox_wheel.py::test_real_scrollable_frame_wheel_and_side_buttons",
]


def groups(source):
    prefix = sorted(str(p.relative_to(source)).replace("\\", "/")
                    for p in (source / "integration").glob("test_*.py")
                    if p.name <= "test_combobox_wheel.py")
    assert prefix and prefix[-1] == "integration/test_combobox_wheel.py", prefix
    return {
        "isolated": TARGETS,
        "module-context": ["integration/test_ahu_manager_callbacks.py",
                           "integration/test_ahu_n5_review.py",
                           "integration/test_ahu_parent_close.py",
                           "integration/test_combobox_wheel.py"],
        "prefix": prefix,
    }


def fingerprint(source):
    result = {}
    for folder in ("windows", "integration"):
        for path in sorted((source / folder).rglob("*.py")):
            result[path.relative_to(source).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def junit_summary(path):
    if not path.exists():
        return dict(error="JUnit output missing", accepted=False)
    cases = list(ET.parse(path).iter("testcase"))
    failures = [dict(classname=c.get("classname"), name=c.get("name"),
                     reason="\n".join((x.text or x.get("message", "")) for x in c
                                      if x.tag in ("failure", "error", "skipped")))
                for c in cases if any(c.find(tag) is not None for tag in ("failure", "error", "skipped"))]
    forbidden = [c for c in cases if c.find("skipped") is not None and
                 ("parent_close_respects" in c.get("name", "") or
                  "real_scrollable_frame_wheel" in c.get("name", ""))]
    present = {c.get("name", "") for c in cases}
    missing = [t for t in TARGETS if t.split("::", 1)[1] not in present]
    return dict(tests=len(cases), failures=sum(c.find("failure") is not None for c in cases),
                errors=sum(c.find("error") is not None for c in cases),
                skipped=sum(c.find("skipped") is not None for c in cases),
                exceptional_results=failures, required_targets_missing=missing,
                accepted=not forbidden and not missing and bool(cases) and
                         all(c.find("failure") is None and c.find("error") is None for c in cases))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--groups", nargs="+", choices=("isolated", "module-context", "prefix"),
                        default=["isolated", "module-context", "prefix"])
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args(argv)
    if sys.platform != "win32":
        parser.error("Native Windows required; Linux is not release evidence")
    if args.rounds < 1:
        parser.error("At least one round is required")
    source, output = args.source.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    before = fingerprint(source)
    (output / "source-python-sha256.json").write_text(json.dumps(before, indent=2), encoding="utf-8")
    selections = groups(source)
    receipts = []
    env = dict(os.environ, FACILITY_REQUIRE_DISPLAY="1", FACILITY_TEST_PLATFORM="windows",
               PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    prior_environment = {key: env.pop(key, None) for key in ("PYTHONPATH", "TCL_LIBRARY", "TK_LIBRARY")}
    # Only the diagnostic plugin is added. Tests select the original windows tree.
    env["PYTHONPATH"] = str(HERE)
    provenance = dict(native_windows=True, platform=platform.platform(), python=sys.version,
                      executable=sys.executable, source=str(source), groups=selections,
                      cleared_environment=prior_environment, rounds=args.rounds,
                      frozen_binary_tested=False, formal_feed_accepted=False)
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    for round_number in range(1, args.rounds + 1):
        for group in args.groups:
            attempt = output / f"round-{round_number:02d}-{group}"
            attempt.mkdir()
            attempt_env = dict(env, NATIVE_TK_TRACE=str(attempt / "tk-events.jsonl"),
                               FACILITY_STUDIO_DATA=str(attempt / "data"),
                               FACILITY_STUDIO_FUSION_DATA=str(attempt / "data"),
                               FACILITY_STUDIO_PREFERENCES=str(attempt / "preferences.json"),
                               MPLCONFIGDIR=str(attempt / "mpl-cache"))
            command = [sys.executable, "-m", "pytest", "-p", "native_tk_trace", *selections[group],
                       "-q", "--tb=long", "-ra", "-p", "no:cacheprovider",
                       "--junitxml=" + str(attempt / "results.xml")]
            start = time.monotonic()
            with (attempt / "pytest.log").open("w", encoding="utf-8") as stream:
                try:
                    result = subprocess.run(command, cwd=source, env=attempt_env,
                                            stdout=stream, stderr=subprocess.STDOUT, timeout=args.timeout)
                    code = result.returncode
                except subprocess.TimeoutExpired:
                    code = 124
                    stream.write("\nDIAGNOSTIC TIMEOUT: failure retained\n")
            summary = junit_summary(attempt / "results.xml")
            receipt = dict(round=round_number, group=group, command=command,
                           exit_code=code, seconds=round(time.monotonic() - start, 3),
                           junit=summary, passed=code == 0 and summary["accepted"])
            receipts.append(receipt)
            print(json.dumps(receipt), flush=True)
            (output / "receipts.json").write_text(json.dumps(receipts, indent=2), encoding="utf-8")
    unchanged = fingerprint(source) == before
    summary = dict(passed=unchanged and all(r["passed"] for r in receipts),
                   source_python_files_unchanged=unchanged, attempts=receipts,
                   policy="All attempts must pass; later success never replaces an earlier failure",
                   native_windows=True, frozen_binary_tested=False, formal_feed_accepted=False)
    (output / "SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
