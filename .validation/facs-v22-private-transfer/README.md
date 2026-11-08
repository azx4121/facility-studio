# Private Windows same-byte handoff (local review package)

Prepared locally only. No release, asset, workflow, or repository was changed by preparing or testing these files. This package does not contain publication or release-deletion code. The unrelated macOS draft `facs-v22-r3-macos-arm64-unvalidated` is outside its fixed tag/marker scope.

## Integration

Copy these files into `.validation/facs-v22-private-transfer/` on the authorized validation branch:

- `private_draft_transfer.py`: producer, consumer download, and read-only inspection.
- `validate_downloaded_candidate.py`: Windows Server 2025 frozen/CLI/capture controller.
- `prepare_diagnostics.py`: non-executable diagnostics staging.
- `test_private_transfer.py`: offline tests.
- `private-windows-handoff.yml`: install separately at `.github/workflows/private-windows-handoff.yml`.

The workflow uses the existing `.validation/facs-v22-reviewed/run_reviewed_validation.py`, reviewed display helper, `.validation/facs-v22-extended/build_reviewed_candidate.py`, and its `frozen_checks/` files. Install the final external-check revisions, including actual DWM visible-window captures and Excel Instructions assertions, together with this package. The parent must bind the reviewed source/correction hashes and independently check both source-CI gates. This template does not replace those checks. Current source controller commit is `4fdf4aa8fc0e3f20c30c91941049fba3e5d1fb05`; the complete source validation run is `42482351137`. The controlled Tcl capture comparison is retained separately in run `42480872985`, where fd arms failed and sys arms passed. This package does not claim complete source acceptance yet.

A push trigger is narrowly scoped to the validation branch and these private-transfer/workflow paths. There is also a manual dispatch trigger. Disable the older extended-build push trigger before installing together if one candidate build is desired. There is no publishing job.

Producer checks before any release creation/upload:

1. Matching successful build receipt, unchanged executable SHA-256 and byte length.
2. Four distinct frozen runs: both suites from both plain and Unicode/space paths, all exit zero.
3. Matching successful external receipt with exactly 118 commands, eight startup captures, and unchanged executable.
4. Clean Windows v5.7.3 source provenance.

The Windows 2022 producer then creates an **empty** draft with a unique `facs-v22-windows-private-candidate-{run_id}-{run_attempt}` tag and explicit unvalidated marker. It verifies authenticated draft metadata and anonymous HTTP 404 from exact release-ID, predicted tag/API/web paths, and the actual returned `html_url`, including GitHub's possible `untagged-...` URL. Only then can it upload the exact Windows EXE and a minimal provenance/identity manifest. Both assets must pass metadata, anonymous exact-ID/predicted/actual-download-URL checks, authenticated exact-asset-ID download, byte length, and SHA-256 checks. The manifest deliberately remains `unvalidated: true` and `published: false` even after this workflow passes.

The second job consumes the producer's exact release ID, asset IDs, manifest hash, EXE hash, lengths, and original producer run/attempt identity through job outputs. Failed-consumer-job reruns therefore do not silently switch to a new producer attempt. Downloads go to a fresh randomly named directory. It reconstructs source independently, compares all source provenance fields, calls existing `verify_single_exe`, then external CLI and eight captures, and rechecks hashes. Its OS build must be 26100 (Windows Server 2025). Python is installed as the **controller**; tested EXE launch PATH contains only Windows/System32 and Windows, and reachable python.exe, python3.exe or py.exe aliases are recorded rather than assumed absent. For every tested launch, native Job Object coverage and retained process-image queries must prove that all processes use the copied EXE, including its onefile bootloader child. Any other image, missing query, or incomplete process coverage fails closed. This is observed standalone execution, not an OS policy that makes installed Python inaccessible. Existing launch helpers copy only the EXE to fresh plain and Unicode paths. The application network audit hook is not OS network isolation.

Only allowlisted `.json`, `.jsonl`, `.log`, `.txt`, `.png`, `.xml`, `.csv`, and `.xlsx` diagnostics are copied into dedicated artifact roots. Executable magic, executable XLSX members, non-XLSX ZIPs, links, and reparse points are rejected. `source-v22.zip`, the build-output root, private download directory, EXEs and other binaries are never artifact sources. Screenshots remain available for required pixel review. Public CI diagnostics must themselves be approved for exposure; synthetic capture data is used. A passing workflow still needs actual screenshot review and all other release gates before a separately authorized public release.

## Token and confidentiality assumptions

- `GH_TOKEN` is provided only in transfer/inspection steps from `${{ github.token }}`. It is never accepted as a CLI argument, printed, saved, or sent outside this repository's GitHub API/upload hosts. Checkout credentials are not persisted.
- Root workflow permissions are `contents: read`. The producer and consumer each have job-local `contents: write`, because private draft reads can require push-capable repository access. Consumer code never writes release state. Token availability and effective draft access must be verified in the real run; 401/403 are failures, never treated as privacy proof.
- Authenticated download redirects are handled explicitly. Authorization is stripped before following HTTPS URLs on exactly `release-assets.githubusercontent.com` or `objects.githubusercontent.com`; no other host or second redirect is followed. Signed URLs and response bodies are not logged. New GitHub storage host behavior fails closed and needs review.
- GitHub draft ACLs are the privacy boundary. These drafts are not private from repository writers/administrators or GitHub. Anonymous HTTP 404 probes establish current visibility only. A collaborator concurrently publishing the draft could expose assets between checks. Workflow concurrency prevents overlapping instances of this workflow, not other administrators or workflows. Stop if this residual assumption is unacceptable.
- A post-upload privacy failure stops immediately but cannot undo a prior exposure. There is deliberately no automatic deletion or publication. Keep the draft unvalidated and escalate for inspection.
- The workflow's code, full source/correction hashes, API responses over TLS, GitHub runner, dependencies, and same-run job outputs are trusted. This is not a protection against a malicious repository writer or compromised runner.

## Uncertain outcomes and resuming

There are no automatic POST retries. On uncertain draft creation, the script lists authenticated releases and prints only matching candidate IDs/status. On uncertain upload, it reads the exact draft asset inventory and prints IDs, names, state, and sizes. An interrupted empty draft can remain safely unvalidated. A `starter` upload or conflicting/mismatched asset stops the operation; scripts never overwrite or delete it.

Use the original run ID/attempt/workflow commit with the `inspect` command and exact `--release-id`. Draft lookup uses authenticated release listing/exact IDs, not the unreliable draft-by-tag API. Only after a known nonexecuted operation or inspected outcome should the operator choose the next step. `stage --resume-release-id ID` can reconcile already-uploaded assets by exact digest and authenticated readback, but requires the original authorized producer run context and unchanged local files. It never silently resumes a discovered tag. A whole-workflow rerun gets a new attempt-tag and does not alter the old draft; do not mistake that for a cleanup/resume mechanism. Recovery across runs requires deliberate review, not changing environment identity to bypass the guard.

## Local checks

From the parent directory:

`python -B -m unittest discover -s private_transfer -p test_private_transfer.py -v`

The tests are completely offline and use synthetic bytes, including non-public gates, actual untagged URLs, no unintended writes, uncertain outcomes, strict receipt counts, credential redirect handling, and binary artifact exclusion. They are not evidence of live GitHub ACL behavior, Windows execution, or product acceptance. Those have not been run by this worker.

## Startup placement revalidation

The Windows-only first-map placement fix and 16 untouched native launches are now included in the reconstructed source. Rebuild and rerun every same-byte validation gate. Prior source and binary successes do not accept this revision. No capture positioning, cropping or containment gate is changed.
