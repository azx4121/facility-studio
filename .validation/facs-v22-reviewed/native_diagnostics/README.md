# Native Windows display and Tk lifecycle diagnostics

These are **new harness files only**. They do not edit sealed v22, replace product
assertions, lower requested client sizes, retry a failed test into success, or
establish frozen-binary / formal FEED acceptance. Run against the intended source
tree explicitly and retain its provenance separately.

## What the first native evidence establishes

- Windows 2022 and 2025 reported a 1024x768 desktop. Ten strict header checks asked
  for clients up to 1480x1000 and correctly failed when the native WM clamped them.
  Those original assertions must remain unchanged on a sufficiently large desktop.
- Windows 2022's combobox error was in `tk.Tk()` before widget construction:
  Tcl could not read its managed-CPython `tcl/tcl8.6/init.tcl`, with `No error`.
  Many earlier/later roots worked. This is not proof of a missing Tcl install.
- The Windows 2022 AHU cancellation case also stopped in `tk.Tk()`. That original
  test converts any TclError to "Real Tk display required", losing the original
  exception. The original report cannot determine whether it was the same error.
- Immediate AHU predecessor was the `None-simple` case. Combobox predecessors
  include 12 real roots and a Tk-8.6 feature skip, followed by fake-interpreter
  policy tests. No Tcl-library environment mutation was found in those test files.
- Current evidence does **not** establish the lifecycle root cause. Tracing is
  diagnostic: Python/Tcl init-file readability, hashes, search paths, root births,
  destruction, remaining roots/timers, GC counters, Win32 handle/GDI/USER counts,
  environment and exact collection order help distinguish path corruption,
  resource leakage, delayed interpreter destruction, and transient file access.

## Large-desktop context wrapper

Run with the same managed Python used by the suite:

    python native_diagnostics/windows_display.py --width 1920 --height 1080 --client 1480x1000 --evidence EVIDENCE/display-large.json -- python FULL_NATIVE_RUNNER.py

The primary display is changed with Microsoft's `EnumDisplaySettingsExW` and
`ChangeDisplaySettingsExW`. Only advertised >=24-bit modes qualify. `CDS_TEST`
must return success, then a flags=0 session-only change is applied. Registry
settings are not persisted. Win32 metrics, work area, Tcl/Tk versions, actual Tk
screen dimensions, requested/realized 1480x1000 client and native outer window
rectangle are recorded. The child starts only when all gates pass. The saved
original mode is restored in `finally` and restoration is verified. Mode-setting,
verification, child-command, and restoration failures remain nonzero.

Run the entire GUI suite *inside* the wrapper, not after the wrapper returns.
The JSON retains the pre-change mode and enumerated modes, even on failure.
If the runner exposes no qualifying mode, this is an explicit environment blocker;
do not reduce geometry assertions or call a virtual display native acceptance.
An externally killed wrapper cannot guarantee restoration; use an ephemeral CI
runner and retain the original-mode JSON. The script does not install drivers or
change RDP/security/network settings.

Microsoft API contracts:
- https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-enumdisplaysettingsexw
- https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-changedisplaysettingsexw
- https://learn.microsoft.com/windows/win32/api/wingdi/ns-wingdi-devmodew

## Passive pytest tracing, including the full suite

After any baseline environment sanitization, add this directory to `PYTHONPATH`.
Set `NATIVE_TK_TRACE` to a fresh JSONL output path. Then:

    python -m pytest -p native_tk_trace integration -q -ra --tb=long --junitxml=EVIDENCE/full-integration.xml

The plugin observes `Tk.__init__` and `Tk.destroy` and records test boundaries. It
does not create probe roots, cancel callbacks, call GC, clean leaks, change Tcl
library paths, or retry creation. Failed `Tk.__init__` exceptions are logged before
the original test can mask them. Every unexpected skip becomes a failure. The only
allowlisted skip is the exact original Tk-8.6-only reason for
`test_tk9_side_buttons_do_not_scroll_page`. Original skip reasons remain in JSONL.
Tracing itself adds I/O/timing overhead; compare instrumented with uninstrumented
runs if intermittent behavior disappears. No diagnostic pass erases an earlier fail.

## Repeated affected tests and predecessors

    python native_diagnostics/run_lifecycle_diagnostics.py --source SOURCE --output NEW_EVIDENCE_DIRECTORY --rounds 3

Each round runs fresh subprocesses for:
1. Both affected target cases in isolation.
2. AHU-manager, AHU N5, AHU-parent-close and all combobox tests in original file order.
3. The complete sorted integration-file prefix through the combobox file, including
   the original AHU predecessors and all preceding suite side effects.

Use `--groups isolated module-context` for a smaller diagnostic, but retain the
full prefix for the release investigation. `--timeout` is per attempt. Each
attempt has a separate log, JUnit and JSONL. All attempts must pass, both affected
targets must actually execute, and all source Python hashes must be unchanged.
Missing JUnit, timeout, unexpected skip, or any failure makes the aggregate fail.

## Real 1024x768 coverage in addition to large-screen tests

Set `NATIVE_DIAGNOSTICS_SOURCE=SOURCE`, `FACILITY_TEST_PLATFORM=windows`,
`FACILITY_REQUIRE_DISPLAY=1`, `PYTHONPATH=native_diagnostics`, and a fresh
`NATIVE_TK_TRACE`. Then:

    python native_diagnostics/windows_display.py --width 1024 --height 768 --exact --client 980x600 --evidence EVIDENCE/display-small.json -- python -m pytest -p native_tk_trace native_diagnostics/test_native_smallscreen.py -q -ra --tb=long --junitxml=EVIDENCE/small-screen.xml

The added checks require an actual 1024x768 Windows desktop. They retain the real
app fixture and its header overlap/hit checks, add physical work-area containment,
exercise both UI languages, send a wheel event through the actual hit target over
an overflowing real product form, and open the actual review/settings dialogs to
hit-test/dismiss their controls without moving them artificially. These are
Tk-generated input events after physical hit testing, not hardware-input claims.
Any uncovered small-screen defect is a real failure to fix, not an allowed skip.

## Local harness checks

    python -m pytest native_diagnostics/test_diagnostic_harness.py -q

These portable tests check ABI layout, advertised-mode selection, fail-closed
command gating, restoration, preserved child failures, skip handling and missing
target detection. They are not native Windows display or product evidence.
