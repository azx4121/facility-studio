"""Fail-closed validation of frozen-package evidence; no runtime/GUI imports."""
import json
from pathlib import Path


EXPECTED_VERSION = "5.7.3-preview.1"


def _read_object(path):
    path = Path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise RuntimeError(f"Cannot read acceptance evidence: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"Evidence must be a JSON object: {path}")
    return value


def _require_commit(value, expected_commit, path):
    if not isinstance(expected_commit, str) or not expected_commit.strip():
        raise RuntimeError("An expected build commit is required.")
    if value != expected_commit:
        raise RuntimeError(f"Build commit mismatch: {path}")


def validate_acceptance(path, *, expected_commit=None):
    """Require a passing frozen candidate report, optionally tied to its build."""
    report = _read_object(path)
    checks = report.get("checks")
    if (report.get("passed") is not True
            or report.get("frozen") is not True
            or report.get("version") != EXPECTED_VERSION
            or not isinstance(checks, list) or not checks
            or any(not isinstance(check, dict) or check.get("passed") is not True
                   for check in checks)):
        raise RuntimeError(f"Frozen acceptance evidence is invalid or failed: {path}")
    if expected_commit is not None:
        _require_commit(report.get("build_commit"), expected_commit, path)
    return report


def validate_embedded_manifest(app, expected_commit):
    """Check every present manifest in supported PyInstaller bundle layouts."""
    app = Path(app)
    if app.suffix == ".app":
        candidates = [app / "Contents/Resources/Build_Manifest.json",
                      app / "Contents/Frameworks/Build_Manifest.json"]
    else:
        candidates = [app / "_internal/Build_Manifest.json", app / "Build_Manifest.json"]
    present = [path for path in candidates if path.is_file()]
    if not present:
        raise RuntimeError(f"Embedded Build_Manifest.json is missing: {app}")
    for path in present:
        _require_commit(_read_object(path).get("commit"), expected_commit, path)
    return _read_object(present[0])
