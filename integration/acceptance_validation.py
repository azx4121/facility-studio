"""Fail-closed validation of frozen-package evidence; no runtime/GUI imports."""
import json
from pathlib import Path, PurePosixPath
import re

try:
    from .source_provenance import EXPECTED_VERSION, PROVENANCE_FIELDS, provenance_digest
except ImportError:  # Direct script invocation.
    from source_provenance import EXPECTED_VERSION, PROVENANCE_FIELDS, provenance_digest


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate evidence key: " + key)
        result[key] = value
    return result


def _read_object(path):
    path = Path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, ValueError) as exc:
        raise RuntimeError(f"Cannot read acceptance evidence: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"Evidence must be a JSON object: {path}")
    return value


def _require_commit(value, expected_commit, path):
    if not isinstance(expected_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", expected_commit):
        raise RuntimeError("A full lowercase expected build commit is required.")
    if value != expected_commit:
        raise RuntimeError(f"Build commit mismatch: {path}")


def _hash_mapping(value, field, path):
    if not isinstance(value, dict) or not value:
        raise RuntimeError(f"Missing source hashes ({field}): {path}")
    for name, digest in value.items():
        if (not isinstance(name, str) or not name or "\\" in name
                or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
                or PurePosixPath(name).as_posix() != name
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise RuntimeError(f"Invalid source hash ({field}): {path}")
        if field == "product_source_sha256" and not name.startswith("facility_studio/"):
            raise RuntimeError(f"Invalid product source path: {path}")


def _validate_manifest(manifest, expected_commit, path, *, allow_non_release=False):
    if not isinstance(manifest, dict):
        raise RuntimeError("An independent expected source manifest is required.")
    _require_commit(manifest.get("commit"), expected_commit, path)
    if (type(manifest.get("provenance_schema")) is not int or manifest["provenance_schema"] != 1
            or manifest.get("version") != EXPECTED_VERSION
            or manifest.get("source_platform") not in ("macos", "windows")
            or type(manifest.get("source_clean")) is not bool
            or manifest.get("build_channel") != ("stable" if manifest["source_clean"] else "non-release")):
        raise RuntimeError(f"Invalid build identity: {path}")
    if not manifest["source_clean"] and not allow_non_release:
        raise RuntimeError(f"Non-release development evidence cannot pass a release gate: {path}")
    for field in ("build_inputs_sha256", "product_source_sha256"):
        _hash_mapping(manifest.get(field), field, path)


def validate_acceptance(path, *, expected_commit, expected_manifest, expected_suite,
                        allow_non_release=False):
    """Bind a passing frozen suite to independently verified checkout bytes."""
    _validate_manifest(expected_manifest, expected_commit, "expected source", allow_non_release=allow_non_release)
    if expected_suite not in ("fusion", "facilities"):
        raise RuntimeError("The expected acceptance suite is required.")
    report = _read_object(path)
    checks = report.get("checks")
    if (report.get("passed") is not True
            or report.get("frozen") is not True
            or report.get("version") != EXPECTED_VERSION
            or report.get("suite") != expected_suite
            or not isinstance(checks, list) or not checks
            or any(not isinstance(check, dict) or check.get("passed") is not True
                   or not isinstance(check.get("name"), str) or not check["name"].strip()
                   for check in checks)):
        raise RuntimeError(f"Frozen acceptance evidence is invalid or failed: {path}")
    if len({check["name"] for check in checks}) != len(checks):
        raise RuntimeError(f"Duplicate acceptance checks: {path}")
    _require_commit(report.get("build_commit"), expected_commit, path)
    if report.get("build_provenance_sha256") != provenance_digest(expected_manifest):
        raise RuntimeError(f"Acceptance source provenance mismatch: {path}")
    return report


def validate_embedded_manifest(app, expected_commit, *, expected_manifest, allow_non_release=False):
    """Check all bundle copies against expected hashes, not self-reported hashes."""
    _validate_manifest(expected_manifest, expected_commit, "expected source", allow_non_release=allow_non_release)
    app = Path(app)
    platform = "macos" if app.suffix == ".app" else "windows"
    if expected_manifest["source_platform"] != platform:
        raise RuntimeError(f"Bundle platform identity mismatch: {app}")
    if platform == "macos":
        candidates = [app / "Contents/Resources/Build_Manifest.json",
                      app / "Contents/Frameworks/Build_Manifest.json"]
    else:
        candidates = [app / "_internal/Build_Manifest.json", app / "Build_Manifest.json"]
    present = [path for path in candidates if path.is_file()]
    if not present:
        raise RuntimeError(f"Embedded Build_Manifest.json is missing: {app}")
    for path in present:
        manifest = _read_object(path)
        _validate_manifest(manifest, expected_commit, path, allow_non_release=allow_non_release)
        for field in PROVENANCE_FIELDS:
            if manifest[field] != expected_manifest[field]:
                raise RuntimeError(f"Embedded source provenance mismatch ({field}): {path}")
    return _read_object(present[0])
