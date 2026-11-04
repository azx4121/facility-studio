# Source and native release evidence guards

The assurance schema targets the approved 5.7.3 stable identity. Product branding, sandbox behavior and native package version changes are handled separately. These guards do not publish a release, certify engineering results, or replace native Windows/macOS acceptance.

## What is checked

- Both security scripts preserve their existing numeric `passed` count and JSON format, accept an optional `--output`, and exit nonzero if any check fails or no checks ran.
- The source-suite runner requires fresh JSON for security, stress, audit and report suites in addition to a successful process exit. It removes the previous output before each run and records failed evidence, timeouts and launch failures in `Source_Suite_Results.json`.
- `integration/source_provenance.py` compares actual build inputs to committed HEAD bytes, including their complete file sets. It covers all target product code/resources, recursive integration inputs, PyInstaller hooks and the repository license inputs used by the builder. Staged, unstaged, deleted, untracked, ignored and assume-unchanged modifications cannot silently claim the HEAD identity.
- Every resource file is hashed, including files inside a directory named `__pycache__`. Outside resources, only current-interpreter `.pyc` caches directly under `__pycache__`, with a neighboring source file and bytecode matching a fresh compile of that source, may be omitted. Cache filenames alone are insufficient: malformed, altered, orphaned, nested and appended-data files remain inputs. Standalone `.pyc` and ignored native modules also remain inputs. Symlinks are rejected before any cache exclusion; cached code is inspected, never executed.
- Source suites regenerate non-shipped files under `windows/evidence/**` and `macos/evidence/**`. These two directories may change without invalidating the source identity; the build manifest records this exclusion. This means build inputs are exact-HEAD validated, not that every filesystem byte in the checkout is unchanged.
- The builder checks inputs before reading dependencies and after freezing, then again before packaging. `--allow-dirty` permits deliberate development builds, marks them `source_clean: false` and `build_channel: non-release` (clean builds use `stable`), embeds a `NON_RELEASE_DEVELOPMENT.txt` warning, and keeps the hashes of the actual inputs. Ordinary verification rejects that evidence unless explicitly opted into non-release verification.
- Native reports identify their suite and include a canonical SHA-256 fingerprint of the embedded source identity. The validator requires the expected commit, suite and an independently prepared source manifest. It checks version, platform, source-clean status, complete hash maps, nonempty uniquely named passing checks and every present supported embedded manifest copy. Commit-only or self-reported-hash-only checks are no longer accepted.

## Required second-host CI changes

The second Windows host deliberately removes external Python and tools from PATH before running the shipped EXE. Prepare the expected source record **before** clearing PATH, because Git is needed to read HEAD. Use the checked-out source at the exact expected commit, never the downloaded package's manifest:

```powershell
$expectedSource = "$env:RUNNER_TEMP/Expected_Source_Manifest.json"
& $verifierPython -c "import json, os, pathlib; from integration.source_provenance import expected_source_manifest; root=pathlib.Path.cwd(); source=expected_source_manifest(root,'windows',expected_commit=os.environ['GITHUB_SHA']); (pathlib.Path(os.environ['RUNNER_TEMP'])/'Expected_Source_Manifest.json').write_text(json.dumps(source),encoding='utf-8')"
if ($LASTEXITCODE) { throw 'Independent checkout identity failed' }
```

After the shipped suites run with the restricted PATH, replace the existing portable verifier command with:

```powershell
& $verifierPython -c "import json, os, pathlib; from integration.acceptance_validation import validate_acceptance, validate_embedded_manifest; base=pathlib.Path(os.environ['RUNNER_TEMP']); expected=os.environ['GITHUB_SHA']; source=json.loads((base/'Expected_Source_Manifest.json').read_text(encoding='utf-8')); executables=list((base/'facility-extracted').rglob('Facility Studio 5.7.3.exe')); assert len(executables)==1; validate_embedded_manifest(executables[0].parent,expected,expected_manifest=source); [validate_acceptance(base/'facility-second-evidence'/(kind+'.json'),expected_commit=expected,expected_manifest=source,expected_suite=kind) for kind in ('fusion','facilities')]"
if ($LASTEXITCODE) { throw 'Second-host portable identity or acceptance failed' }
```

Pass the same `source` object to `windows_installer.verify(..., expected_commit=os.environ['GITHUB_SHA'], expected_manifest=source)`. Both signatures now require the expected source manifest. Add these focused tests to the workflow's pytest collection:

```text
integration/test_acceptance_validation.py
integration/test_source_provenance.py
integration/test_source_suite_validation.py
integration/test_candidate_acceptance.py
integration/test_release_identity.py
```

Keep the expected source JSON with the second-host evidence. Rebuild both native packages from the final commit after integrating this change, since the executable now emits the stronger evidence schema. Historical preview reports, including `5.7.3-preview.1` or a `preview` build channel, intentionally do not satisfy the stable gate.

## Clean checkout and test bytecode

Run native release verification from a fresh checkout of the exact intended commit. Set `PYTHONDONTWRITEBYTECODE=1` before running pytest in the checkout that will subsequently build the application. Pytest assertion-rewritten caches are not equivalent to ordinary source bytecode, so the source gate intentionally rejects them. Ordinary non-resource caches are excluded only when their contents match the adjacent source; all resource files remain part of the inventory. Do not weaken the source gate or use `--allow-dirty` to publish a release.

## Local verification

The added tests use temporary Git repositories and injected process/JSON failures. They do not require a GUI or mutate the user's working checkout. Run them with `python -m pytest` against the five files above. The actual security suites can run independently with `--output` outside the checkout.

A full source-suite run still needs a display; native builds still require supported Python 3.12 on Windows or Apple Silicon macOS. Passing the local guard tests does not substitute for those checks.
