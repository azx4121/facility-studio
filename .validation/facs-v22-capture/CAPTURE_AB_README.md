# Controlled native Windows Tcl capture experiment

Hypothesis, not yet a finding: pytest's default `fd` capture changes Windows
standard handles between test phases. Tcl can retain stale native handles.
Changing to `sys` capture avoids those descriptor changes while preserving test
execution and Python-output capture. We must reproduce this distinction locally
on the affected native hosts before treating it as the cause or the fix.

Relevant evidence:
- https://core.tcl-lang.org/tcl/tktview/91c9bc1c45 describes stale Tcl standard
  handles after Windows CRT `dup2`. It is not proof of our particular failure.
- https://github.com/israel-dryer/ttkbootstrap/blob/master/pyproject.toml documents
  using `--capture=sys` for intermittent Windows Tcl file reads.
- https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html documents
  exactly which capture modes change operating-system file descriptors.
- python-build-standalone issue 939 is primarily a macOS/venv lookup problem and
  must not be cited as the direct cause of this Windows problem.

## Recommended command (fits a 15-minute job budget)

Use the same managed Python 3.12.16 and unchanged source tree from the failed run:

    python native_diagnostics/run_tcl_capture_ab.py --source SOURCE --output NEW_OUTPUT_DIRECTORY --rounds 3 --count 50 --source-groups isolated module-context --budget-seconds 840

Each minimal attempt creates 50 fresh Tcl-only interpreters and 50 fresh native
Tk roots, each in a separate pytest test with normal capture-phase boundaries.
There are three rounds per capture mode. The application is never imported by
the minimal test. Source groups are optional, remain unchanged and run under both
capture modes. Alternating arm order reduces a simple cold/warm-host confound.

The optional `prefix` source group adds the full historical predecessor context,
but prior measurements were approximately 120 seconds per prefix attempt. Adding
six of those to this experiment can exceed 15 minutes. First use the two smaller
source groups above; use a separately budgeted job for the full prefix if needed.

The runner records Python, OS, executable/_tkinter/Tcl-DLL hashes, source hashes,
diagnostic hashes, exact commands, actual capture settings, all test outcomes,
Windows OS/CRT standard-handle values, and complete Tcl/Tk support-file inventory
at baseline and after every failed test (including nested scripts such as
scrlbar.tcl). Missing/changed files are independently observable. Original Tk
exceptions and lifecycle snapshots remain recorded by the existing plugin.

**An fd-arm failure makes the overall command exit 1 even when sys passes.**
This is expected evidence, not a reason to rerun until green. Upload artifacts
with `if: always()`. `SUMMARY.json` reports both arms separately. Missing tests,
timeouts, skipped minimal cases, source changes and incomplete experiments fail.
No application source, runtime, library path, Tcl binary, test assertion, display
mode, garbage-collection policy or shared-interpreter strategy is changed.

Search of the integration test sources found `capsys` in two modules and no
`capfd`/`capfdbinary` dependency; changing global capture should not remove a
requested fd assertion. The full unchanged suite remains a later acceptance gate.

## New files only

- test_tcl_capture_probe.py
- tcl_capture_failure_trace.py
- run_tcl_capture_ab.py
- test_capture_ab_harness.py
- CAPTURE_AB_README.md

The earlier six diagnostic files have not been changed for this experiment.

## First A/B run: harness defect preserved

The first native A/B run on Windows 2022 and 2025 incorrectly required
`tcl_findLibrary` to exist immediately after creating a Tcl-only interpreter.
Every minimal Tcl-only case therefore failed the probe's assertion, in both
capture arms. The 50 Tk cases per attempt and all isolated/module-context source
attempts passed in both arms. This run does not demonstrate a capture-mode cause.
Retain its artifacts and do not relabel its Tcl-only cases as passed.

The corrected probe requires eager `auto_load` initialization, explicitly calls
`auto_load tcl_findLibrary`, requires return value 1, and verifies that the library
procedure was actually defined. It does not retry `Tk()` or ignore an exception.
Real Tcl-only regression tests cover the normal initially-lazy state, the
already-loaded state and broken/missing/false-success autoload behavior.

Official Tcl 8.6.15 sources establish this lazy-loading contract:
- https://github.com/tcltk/tcl/blob/core-8-6-15/library/tclIndex maps
  `auto_index(tcl_findLibrary)` to `source ... auto.tcl`.
- https://github.com/tcltk/tcl/blob/core-8-6-15/library/auto.tcl defines the procedure.

The earlier mistake was failing to validate the minimal probe against a real
Tcl-only interpreter before native submission. The new real-interpreter tests
must run with future probe edits; portable bookkeeping tests alone are insufficient.
