# Native macOS release building (V5.5.8 mac.1)

The original V5.5.4 mac.1 package passed byte-level checks but failed Apple's native deep
signature validation on both macOS 15 architectures. Static verification must
not be treated as native release acceptance. Historical assets are retained. V5.5.8 includes the repaired runtime and bilingual presentation; [current verification](../../docs/2026-10-10-v5.5.8-review-followup.md) records the review follow-up; its status remains pending until both native jobs pass. These commands are for developers; normal users use the [bundled downloads](../../README.en.md#download-and-run).

## Shipping build

The public publisher now offers only the tested DMG and its public SHA256SUMS. The developer ZIP below is retained in build artifacts for cross-architecture acceptance; the two currently recommended releases do not offer their complete ZIPs. Internal checksum files remain intact for verification. See [download changes](../../docs/2026-10-08-downloads.md) and [Developer ID/notarization requirements](../../docs/signing.en.md).

On a native Mac, from the repository root:

```sh
python3 macos/macos/build_native_release.py --output /absolute/path/fresh-mac555-build
```

No Zig or third-party signing tool is needed for this rebuild. The builder:

1. Verifies the original runtime ZIP's pinned SHA-256 and extracts it with `ditto`.
2. Replaces application sources with this checkout, including current security
   fixes and license files; retains the FY icon and Universal native launcher.
3. Retains Tcl/Tk build-only scripts under framework Resources, applies the
   documented five-second Matplotlib discovery limits, and updates RECORD.
4. Signs Mach-O files, nested frameworks, the outer framework and app with Apple
   `codesign`; requires `--verify --deep --strict` to pass.
5. Executes all seven CLI tools and native GUI/Excel/equipment acceptance,
   including language changes, readonly choices and invalid-input export blocking.
   The workflow also runs bilingual parity and worked-example checks.
6. Creates the delivery ZIP with `ditto`, extracts it again, checks its native
   signature and executes the extracted app. Creates a DMG, mounts it read-only,
   verifies its app and repeats native acceptance before detaching.
7. Writes checksums and evidence. Fails the build when any required check fails.

To validate those exact delivery files on a second Mac architecture:

```sh
python3 macos/macos/verify_native_release.py \
  --package /absolute/path/Facility_Studio_V5_5_8_macOS_mac1_OneClick.zip \
  --dmg /absolute/path/Facility_Studio_V5_5_8_macOS_mac1.dmg \
  --checksums /absolute/path/SHA256SUMS.txt \
  --output /absolute/path/second-mac-evidence
```

The workflow `.github/workflows/macos-native-release.yml` uses Apple Silicon
macOS 15 to build and Intel macOS 15 to execute the same ZIP and DMG. On the
repair branch it only tests. On main, publication runs only after both jobs pass;
the publisher targets `v5.5.8-mac.1` without replacing existing public assets or moving tags.
For a future release, update version and output names in the builder, verifier,
publisher and workflow together; do not try to overwrite the already published
v5.5.8 files after a source change.
GitHub upload sizes and SHA-256 digests must match before the draft is published.

These are ad-hoc integrity signatures, not Developer ID or notarization.
Finder quarantine, managed Mac policies, macOS versions outside the CI matrix,
physical keyboards/trackpads, Retina layout and Excel for Mac require separate
user-machine acceptance. Never disable Gatekeeper globally to mask packaging errors.
Runtime patch details and attribution: `../MAC_RUNTIME_PATCHES.md`.

---

# macOS bundle build

This source package targets macOS 11+, Intel x86_64 and Apple Silicon arm64.
The bundle is not a Windows EXE renamed as an app. Its C entry point embeds
the official CPython universal2 framework using `Py_BytesMain` on the main
thread. Every native dependency remains inside the bundle or is a macOS system
library. Matplotlib and its dependencies are separated by CPU architecture.

General users should open the already-built `Facility Studio.app`.

## Historical cross-platform runtime preparation

Use an isolated Python environment with Zig 0.16.0 and Pillow. Obtain
rcodesign 0.29.0 from its official project release and verify that release's
SHA256. Prefer an actual Mac for final acceptance.

```sh
python3 -m pip install 'ziglang==0.16.0' pillow
python3 macos/prepare_runtime.py /absolute/path/new-runtime
python3 macos/build_bundle.py \
  --runtime /absolute/path/new-runtime \
  --output /absolute/path/new-build \
  --signer /absolute/path/rcodesign
python3 macos/verify_bundle.py \
  '/absolute/path/new-build/Facility Studio.app' \
  --report /absolute/path/new-build/Independent_Bundle_Checks.json
```

`prepare_runtime.py` does not install the Python PKG or execute its package
scripts. It extracts the verified framework. It verifies each wheel against
both `Wheel_Integrity.json` and PyPI metadata before using it. The two C
launchers use `-headerpad,0x1000` so a new signature load command fits safely.
The shipping launchers were also compiled with `-Wall -Wextra -Werror`.

`build_bundle.py` refuses to overwrite an existing build. It copies the
runtime, removes unused interpreter developer tools, relocates framework
loads, copies the application and offline wheel sets, and signs all nested
entities with ad-hoc signatures. This does not supply Developer ID identity
or Apple notarization. Runtime and source files must not be changed after
signing; build a fresh app after every source change.

`verify_bundle.py` checks target CPUs, minimum OS load commands, contained
dynamic dependencies, all signature code-page hashes, embedded requirement
hashes, nested code hashes, sealed resource hashes, Info.plist binding,
relative symlinks and executable permissions. It cannot replace Gatekeeper
or native execution. rcodesign 0.29.0's own `verify` reports a known empty-CMS
parse issue for ad-hoc signatures; its diagnostic output is retained in the
build evidence rather than mislabeled as a pass.

On a Mac, execute `Verify_on_Mac.command` beside the finished app. It runs
Apple's `codesign --verify --deep --strict` before the native acceptance tests.
For public commercial distribution, finish Mac hardware QA and use your own
Developer ID signing and notarization workflow after the final build.

ZIP delivery must retain Unix executable permissions and symlink entries.
The historical ZIP builder is `macos/make_package.py`; ordinary Python ZIP
extraction may turn symlinks into text files, so its byte-verification routine
recreates them using their stored Unix file types.



V5.5.8 mac.1 / 獨立空調箱草稿保存修訂
簡易工具左下角持續顯示 DESIGNED BY ANDY HUANG ©。
簡易工具、完整工程工作台及單台空調箱的「新手教學」可開啟離線中英逐步教學。
完整 ZIP 的 Beginner_Tutorial/START_HERE.html 也可直接閱讀。
V5.5.8 可由完整工作台「開啟練習新案」建立副本；原廠選型與設備阻力等待補資料仍需補。
V5.5.8 retains author credit and offline walkthroughs. mac.1 unifies displayed versions and wraps compact workbench actions.
No additional Python installation or internet is needed for the tutorial.
