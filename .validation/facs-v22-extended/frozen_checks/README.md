# External frozen EXE checks

These new validation files do not modify the application, build candidate, or
historical v22 source. The tested EXE is copied byte-for-byte into otherwise
empty ordinary and Traditional-Chinese/space directories. A required, previously
trusted SHA-256 binds both copies to the existing build. The original and launch
copies are hashed before and after testing. Manifest-to-source binding remains
the responsibility of the separate build/manifest gate.

## Native Windows invocation

Use the build/validation Python environment, including its already locked Pillow
version for screenshots. The application itself is invoked only through the
single EXE, with external Python/Tcl/Tk locations removed from its launch PATH.
Do not install Python or any other dependencies on an end user's machine.

```powershell
python -B windows_validation/frozen_checks/run_frozen_cli.py `
  --exe 'C:\validation\FACS.exe' `
  --sha256 '<trusted SHA-256 of the unchanged EXE>' `
  --candidate 'C:\validation\onefile-candidate' `
  --evidence 'C:\validation\new-frozen-evidence' `
  --screenshots
```

`--evidence` must not exist. Use the actual EXE filename and verified digest.
`--screenshots` is optional, but if requested, any startup/capture/close failure
fails the gate. Do not rerun failed cases into the same evidence directory.
The existing `integration/onefile_validation.py` launcher contains every child in
its kill-on-close Windows job. It fails closed when containment cannot be set up.
Each CLI launch is bounded to 180 seconds by default (`--timeout`, 30–600).
No network/firewall/system-security settings are changed. The application audit
hook is not an OS-level offline guarantee. No EXE rebuild or remote publication
is performed.

## What is checked

Both executable path cases run the same CLI matrix:

There are 59 bounded commands per path case (118 total), plus eight bounded
visible launches when screenshots are requested. A fail-fast run may stop earlier.

- All 12 independent tools export strict UTF-8 JSON and text in English and
  Traditional Chinese. Reports must contain their expected localized title;
  canonical JSON must agree between languages. Independent physical/arithmetic
  identities check the result values instead of importing calculation code.
- Nonzero motor-power input and zero-load electrical paths are exercised.
  Fresh electrical exports, equipment rows/groups, and full-project exports
  must keep automatic sizing blocked and restricted selections null.
- The public XLSX template is exported in both languages, parsed independently
  as OOXML, and reimported through the EXE. Seven system sheets and an instruction
  sheet are required. The untouched template must refuse calculation because
  its examples are disabled. An independent copy enables only the known 10 kW
  electrical sample and must import with the expected load/current. A real Chinese CSV with enabled
  electrical equipment verifies counts, diversity, power/current, and language
  independence.
  The existing English instructions sheet is named `填寫 Description`; the
  runner records this partial-localization finding explicitly. A functional
  template pass does not certify complete English translation.
- Three actual `--write-default` save/overwrite operations and `--project`
  reloads must be deterministic. A fourth reload uses the result's canonical
  project serialized by this validator. These are CLI serialization checks,
  **not evidence of GUI Save/Open interactions**.
- Unknown fields, bad numeric strings, negative power, malformed JSON,
  non-finite JSON, invalid projects, and invalid CSV are each tested against
  fresh and stale output paths. Exit 2 must leave fresh exports absent and old
  exports byte-for-byte unchanged. A timeout or setup failure is never accepted
  as an input refusal. Existing output files remaining after refusal are an
  explicit behavior, **not a claim that stale exports are deleted or invalidated**.
- Actual `--gui-smoke` runs exercise the packaged simple-tool GUI in both
  languages. This built-in check is separate from visible startup evidence.

Optional screenshots cover simple/full × English/Traditional Chinese × both
executable path cases (eight images). Capture requires an actual visible,
responsive Tk window whose owning process image matches the unique EXE launch
copy, a stable window rectangle, foreground identity before and after capture,
and nonuniform pixels. Physical primary/virtual display bounds and the nearest
monitor/work area are recorded. Any part of the native window outside that
monitor or work area fails the visual gate; padded or clipped images cannot pass.
Native `WM_CLOSE` must end the bounded launch with exit 0.
Only the target window rectangle is captured; unrelated desktop windows are
not captured intentionally. Native metadata, screenshot hashes, and all process
logs are retained. **Screenshots prove startup only. They do not prove forms,
buttons, report previews, persistence interactions, localization completeness,
or readability. Human pixel review remains required.**

`Frozen_External_Checks.json` starts with `passed: false`, is updated after each
launch, and only becomes true after all requested stages finish. Failures retain
the traceback and artifacts. The matrix is fail-fast: later cases after a
failure are **not run**, not implicitly passed. Individual command pass flags refer to process
exit behavior; the top-level pass flag also requires independent output checks.

## Local validator tests

```sh
python -B -m unittest discover -s windows_validation/frozen_checks -p 'test_*.py' -v
```

These tests use synthetic outputs and mocked process launches. They validate
the checking code, never the product or Windows. The main runner and native
capture explicitly refuse non-Windows hosts. Run the gate on the actual frozen
EXE on each required Windows version, inspect all images, and retain the exact
SHA-256 before describing the release as natively verified. Installation on a
clean end-user machine, signing/reputation warnings, and manual interaction
coverage are separate release gates.
