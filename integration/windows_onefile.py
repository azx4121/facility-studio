"""Inspect the embedded CArchive without running or trusting its manifest."""
import hashlib
import json
from pathlib import Path
import tempfile

try:
    from .acceptance_validation import validate_embedded_manifest
except ImportError:
    from acceptance_validation import validate_embedded_manifest


def validate_archive(executable, root, expected_manifest, *, allow_non_release=False):
    from PyInstaller.archive.readers import CArchiveReader

    archive = CArchiveReader(str(executable))
    entries = {name.replace("\\", "/"): name for name in archive.toc}
    required = {name: digest for name, digest in expected_manifest["product_source_sha256"].items()
                if name.startswith("facility_studio/resources/")}
    for source, target in (("README_繁體中文.md", "操作說明_繁體中文.md"),
                           ("README_English.md", "User_Guide_English.md")):
        required[target] = hashlib.sha256((root / "integration" / source).read_bytes()).hexdigest()
    for name, digest in required.items():
        if name not in entries or hashlib.sha256(archive.extract(entries[name])).hexdigest() != digest:
            raise RuntimeError("Missing or modified single-file resource: " + name)
    for name in ("第三方授權.txt", "Build_Manifest.json", "python3.dll"):
        if name not in entries or not archive.extract(entries[name]):
            raise RuntimeError("Missing embedded single-file dependency: " + name)
    notice = archive.extract(entries["第三方授權.txt"]).decode("utf-8").replace("\r\n", "\n")
    for source in ("LICENSE", "LICENSE_LEGACY_MIT", "THIRD_PARTY_NOTICES.md",
                   "macos/macos/PsychroLib-LICENSE.txt"):
        if (root / source).read_text(encoding="utf-8") not in notice:
            raise RuntimeError("Missing single-file license: " + source)
    with tempfile.TemporaryDirectory(prefix="onefile-manifest-") as directory:
        manifest = Path(directory) / "Build_Manifest.json"
        manifest.write_bytes(archive.extract(entries["Build_Manifest.json"]))
        validate_embedded_manifest(directory, expected_manifest["commit"],
                                   expected_manifest=expected_manifest,
                                   allow_non_release=allow_non_release)
        if json.loads(manifest.read_text(encoding="utf-8")).get("packaging") != "windows-onefile":
            raise RuntimeError("Single-file packaging identity missing")
    return dict(passed=True, packaging="windows-onefile", archive_entries=len(entries),
                verified_resource_sha256=required, embedded_notices=True,
                embedded_python3_dll=True, commit=expected_manifest["commit"])
