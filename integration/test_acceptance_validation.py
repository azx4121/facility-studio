"""Release evidence rejects successful process exits with invalid JSON results."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from integration.acceptance_validation import validate_acceptance, validate_embedded_manifest
from integration import windows_installer


COMMIT = "a" * 40


def report():
    return dict(passed=True, frozen=True, version="5.7.3-preview.1",
                build_commit=COMMIT, checks=[dict(name="offline", passed=True)])


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_valid_frozen_report(tmp_path):
    path = write(tmp_path / "acceptance.json", report())
    assert validate_acceptance(path, expected_commit=COMMIT) == report()


@pytest.mark.parametrize("field,value", [
    ("passed", False), ("passed", 1), ("passed", "true"),
    ("frozen", False), ("frozen", 1), ("version", "5.7.3"),
    ("version", "5.7.2-preview.1"), ("checks", []), ("checks", {}),
    ("checks", [True]), ("checks", [{}]),
    ("checks", [{"passed": 1}]), ("checks", [{"passed": False}]),
    ("checks", [{"passed": True}, {"passed": False}]),
    ("build_commit", None), ("build_commit", "b" * 40),
])
def test_invalid_fields_fail_closed(tmp_path, field, value):
    payload = report()
    payload[field] = value
    with pytest.raises(RuntimeError):
        validate_acceptance(write(tmp_path / "report.json", payload), expected_commit=COMMIT)


@pytest.mark.parametrize("field", ["passed", "frozen", "version", "checks", "build_commit"])
def test_missing_fields_fail_closed(tmp_path, field):
    payload = report()
    del payload[field]
    with pytest.raises(RuntimeError):
        validate_acceptance(write(tmp_path / "report.json", payload), expected_commit=COMMIT)


@pytest.mark.parametrize("contents", [None, "{", "[]", "null", "\udcff"])
def test_unreadable_or_nonobject_report_fails(tmp_path, contents):
    path = tmp_path / "report.json"
    if contents is not None:
        path.write_bytes(contents.encode("utf-8", errors="surrogateescape"))
    with pytest.raises(RuntimeError):
        validate_acceptance(path, expected_commit=COMMIT)


@pytest.mark.parametrize("relative", [
    "App/_internal/Build_Manifest.json", "App/Build_Manifest.json",
    "App.app/Contents/Resources/Build_Manifest.json",
    "App.app/Contents/Frameworks/Build_Manifest.json",
])
def test_supported_manifest_layouts(tmp_path, relative):
    path = write(tmp_path / relative, {"commit": COMMIT})
    app = tmp_path / Path(relative).parts[0]
    assert validate_embedded_manifest(app, COMMIT)["commit"] == COMMIT
    write(path, {"commit": "b" * 40})
    with pytest.raises(RuntimeError, match="commit mismatch"):
        validate_embedded_manifest(app, COMMIT)


def test_missing_or_conflicting_embedded_manifest_fails(tmp_path):
    with pytest.raises(RuntimeError, match="missing"):
        validate_embedded_manifest(tmp_path, COMMIT)
    write(tmp_path / "_internal/Build_Manifest.json", {"commit": COMMIT})
    write(tmp_path / "Build_Manifest.json", {"commit": "b" * 40})
    with pytest.raises(RuntimeError, match="commit mismatch"):
        validate_embedded_manifest(tmp_path, COMMIT)


@pytest.mark.parametrize("suite", ["Installed_Acceptance.json", "Installed_Facilities_Acceptance.json"])
def test_installer_rejects_false_report_even_when_process_succeeds(tmp_path, monkeypatch, suite):
    install = tmp_path / "installer acceptance"
    write(install / "_internal/Build_Manifest.json", {"commit": COMMIT})
    calls = []

    def subprocess_run(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0)

    def runner(args, log, **kwargs):
        payload = report()
        if Path(args[-1]).name == suite:
            payload["passed"] = False
        write(Path(args[-1]), payload)

    monkeypatch.setattr(windows_installer.subprocess, "run", subprocess_run)
    with pytest.raises(RuntimeError, match="invalid or failed"):
        windows_installer.verify(tmp_path / "Setup.exe", tmp_path, "App", runner, {},
                                 expected_commit=COMMIT)
    assert len(calls) == 1  # No protection/uninstall success report after invalid evidence.
    assert not (tmp_path / "evidence/Installer_Protection.json").exists()
