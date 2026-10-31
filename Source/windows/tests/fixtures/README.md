# Historical V5.5.4 installer inputs

`v554-installer-members.zip` is an offline fixture for the retained
`windows/Facility_Studio_V5_5_4_Setup.exe`. It contains **62 source/resource
members (826,796 uncompressed bytes)**, including the original installer
bootstrap and payload manifest. It does **not** contain the Setup EXE.

| Identity | Pinned value |
| --- | --- |
| Upstream tag | `v5.5.4-win.1` |
| Immutable source commit | `6ada894438805a00c8c795f63451916b1d759a84` |
| Fixture bytes | `312489` |
| Fixture SHA256 | `567f0bb3fa3debf61a518f5597324c5833a62df8deeecb20be64f7fefff6af42` |
| Retained Setup EXE SHA256 | `799b3fb496881547466253154beb66d3a30f10a23838b1533a4813a69da2acc4` |
| Original `payload_sha256.json` SHA256 | `0d70989d0e36fe892b18691bbd08ad057732c87f165932c41ba9fea6bd1e01d8` |

Provenance: [immutable installer source directory](https://github.com/azx4121/facility-studio/tree/6ada894438805a00c8c795f63451916b1d759a84/windows/installer)
and [the same commit's integrity evidence](https://github.com/azx4121/facility-studio/blob/6ada894438805a00c8c795f63451916b1d759a84/windows/evidence/Installer_Integrity_Checks.json).
Every fixture member was retrieved from that commit and independently checked
against its recorded `member_sha256` entry before archiving. Expected bytes
were **not** reconstructed from the binary under test. The original payload
project is schema 9; current installer staging contains later sources, so it
is not the expected input for this historical executable.

`installer_fixture.py` pins both the fixture and EXE hashes and rejects changed
archives, duplicate names and unsafe paths. `installer_integrity_checks.py`
then runs the original **21 checks**, including full decompression, exact
member comparison, the extracted bootstrap's own manifest verification, and
16 corruption/truncation/unsafe-input rejections. `nsis_integrity.py` is
unchanged. `packaging_checks.py` still verifies the **current staged payload**
and its rejection rules; only its historical EXE comparison uses this fixture.
Neither test downloads data or runs the Windows installer.

`packaging_checks.py` check `02_payload_matches_release_sources` intentionally
requires fresh staging for a new installer release. It rejects the retained
older staging after application sources change; the standalone historical
installer suite passing does not make the whole packaging suite pass. This
revision does not run the legacy `stage_payload()` path, which is tied to the
V5.5.4 output and would overwrite the historical snapshot. Keep that equality
check intact and prepare separately versioned staging when building a new
installer.

To reproduce a fixture deliberately, retrieve exactly the 62 installer paths
listed by the immutable evidence above, verify every SHA256, and ZIP them in
sorted path order. This archive uses DEFLATE level 9, timestamp
`1980-01-01 00:00:00`, Unix regular-file mode `0644`, and retains each member's
exact bytes. Compressor versions can change archive bytes; do not regenerate
or update the pinned hash as a routine source/build refresh. A deliberate
replacement needs a separately reviewed provenance check.

Do not overwrite the retained EXE or current `windows/installer/payload` to
make a historical test pass. New installer releases require their own source
snapshot, manifest, binary identity and native acceptance.
