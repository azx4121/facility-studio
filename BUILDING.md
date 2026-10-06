# macOS bundle build

This source package targets macOS 11+, Intel x86_64 and Apple Silicon arm64.
The bundle is not a Windows EXE renamed as an app. Its C entry point embeds
the official CPython universal2 framework using `Py_BytesMain` on the main
thread. Every native dependency remains inside the bundle or is a macOS system
library. Matplotlib and its dependencies are separated by CPU architecture.

General users should open the already-built `Facility Studio.app`.

## Rebuild

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
The tested delivery builder is `macos/make_package.py`; ordinary Python ZIP
extraction may turn symlinks into text files, so its byte-verification routine
recreates them using their stored Unix file types.
