"""Release evidence rejects success exits, forged identities and source drift."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from integration.acceptance_validation import validate_acceptance, validate_embedded_manifest
from integration.source_provenance import provenance_digest
from integration import windows_installer

COMMIT = "a" * 40


def manifest(platform="windows"):
    return dict(provenance_schema=1, commit=COMMIT, version="5.7.3",
                source_platform=platform, source_clean=True, build_channel="stable",
                build_inputs_sha256={"integration/entry.py": "1" * 64},
                product_source_sha256={"facility_studio/entry.py": "2" * 64})


def report(suite="fusion", source=None):
    return dict(passed=True, frozen=True, version="5.7.3", suite=suite,
                build_commit=COMMIT, checks=[dict(name="offline", passed=True)],
                build_provenance_sha256=provenance_digest(source or manifest()))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def validate(path, source=None, **kwargs):
    return validate_acceptance(path, expected_commit=COMMIT, expected_manifest=source or manifest(),
                               expected_suite="fusion", **kwargs)


def test_valid_frozen_report(tmp_path):
    path = write(tmp_path / "acceptance.json", report())
    assert validate(path) == report()


@pytest.mark.parametrize("field,value", [
    ("passed", False), ("passed", 1), ("passed", "true"),
    ("frozen", False), ("frozen", 1), ("version", "5.7.3-preview.1"),
    ("version", "5.7.2-preview.1"), ("suite", "facilities"),
    ("checks", []), ("checks", {}), ("checks", [True]), ("checks", [{}]),
    ("checks", [{"name": "offline", "passed": 1}]),
    ("checks", [{"name": "offline", "passed": False}]),
    ("checks", [{"passed": True}]), ("checks", [{"name": " ", "passed": True}]),
    ("checks", [{"name": "offline", "passed": True}] * 2),
    ("build_commit", None), ("build_commit", "b" * 40),
    ("build_provenance_sha256", None), ("build_provenance_sha256", "3" * 64),
])
def test_invalid_fields_fail_closed(tmp_path, field, value):
    payload = report()
    payload[field] = value
    with pytest.raises(RuntimeError):
        validate(write(tmp_path / "report.json", payload))


@pytest.mark.parametrize("field", list(report()))
def test_missing_fields_fail_closed(tmp_path, field):
    payload = report()
    del payload[field]
    with pytest.raises(RuntimeError):
        validate(write(tmp_path / "report.json", payload))


@pytest.mark.parametrize("contents", [None, "{", "[]", "null", "\udcff", '{"passed":false,"passed":true}'])
def test_unreadable_or_nonobject_report_fails(tmp_path, contents):
    path = tmp_path / "report.json"
    if contents is not None:
        path.write_bytes(contents.encode("utf-8", errors="surrogateescape"))
    with pytest.raises(RuntimeError):
        validate(path)


@pytest.mark.parametrize("commit", [None, "", "abc", "x" * 40, "A" * 40, 1, True])
def test_expected_commit_cannot_be_fabricated_short_or_invalid(tmp_path, commit):
    payload = report()
    payload["build_commit"] = commit
    source = manifest()
    source["commit"] = commit
    with pytest.raises(RuntimeError):
        validate_acceptance(write(tmp_path / "report.json", payload), expected_commit=commit,
                            expected_manifest=source, expected_suite="fusion")


@pytest.mark.parametrize("relative", [
    "App/_internal/Build_Manifest.json", "App/Build_Manifest.json",
    "App.app/Contents/Resources/Build_Manifest.json",
    "App.app/Contents/Frameworks/Build_Manifest.json",
])
def test_supported_manifest_layouts(tmp_path, relative):
    source = manifest("macos" if relative.startswith("App.app") else "windows")
    path = write(tmp_path / relative, source)
    app = tmp_path / Path(relative).parts[0]
    assert validate_embedded_manifest(app, COMMIT, expected_manifest=source) == source
    write(path, dict(source, commit="b" * 40))
    with pytest.raises(RuntimeError, match="commit mismatch"):
        validate_embedded_manifest(app, COMMIT, expected_manifest=source)


def test_missing_or_conflicting_embedded_manifest_fails(tmp_path):
    with pytest.raises(RuntimeError, match="missing"):
        validate_embedded_manifest(tmp_path, COMMIT, expected_manifest=manifest())
    write(tmp_path / "_internal/Build_Manifest.json", manifest())
    different = manifest()
    different["product_source_sha256"]["facility_studio/entry.py"] = "3" * 64
    write(tmp_path / "Build_Manifest.json", different)
    with pytest.raises(RuntimeError, match="provenance mismatch"):
        validate_embedded_manifest(tmp_path, COMMIT, expected_manifest=manifest())


@pytest.mark.parametrize("field", ["build_inputs_sha256", "product_source_sha256"])
@pytest.mark.parametrize("change", ["missing", "empty", "wrong_hash", "missing_file", "extra_file", "wrong_type",
                                     "uppercase", "short", "traversal", "absolute", "backslash", "duplicate_separator"])
def test_hash_maps_are_verified_not_just_recorded(tmp_path, field, change):
    source = manifest()
    payload = copy.deepcopy(source)
    key = next(iter(payload[field]))
    if change == "missing":
        del payload[field]
    elif change == "empty":
        payload[field] = {}
    elif change == "missing_file":
        del payload[field][key]
    elif change == "extra_file":
        payload[field]["facility_studio/extra.py"] = "3" * 64
    elif change == "wrong_type":
        payload[field][key] = True
    elif change in ("traversal", "absolute", "backslash", "duplicate_separator"):
        name = {"traversal": "../entry.py", "absolute": "/entry.py", "backslash": "folder\\entry.py",
                "duplicate_separator": "folder//entry.py"}[change]
        payload[field][name] = payload[field].pop(key)
    else:
        payload[field][key] = {"wrong_hash": "9" * 64, "uppercase": "A" * 64, "short": "a" * 63}[change]
    write(tmp_path / "Build_Manifest.json", payload)
    with pytest.raises(RuntimeError):
        validate_embedded_manifest(tmp_path, COMMIT, expected_manifest=source)


@pytest.mark.parametrize("field,value", [("source_platform", "macos"), ("version", "5.7.3-preview.1"),
                                         ("provenance_schema", True), ("source_clean", 1),
                                         ("build_channel", "release"), ("build_channel", "preview")])
def test_manifest_identity_is_verified(tmp_path, field, value):
    payload = manifest()
    payload[field] = value
    write(tmp_path / "Build_Manifest.json", payload)
    with pytest.raises(RuntimeError):
        validate_embedded_manifest(tmp_path, COMMIT, expected_manifest=manifest())


def test_bundle_platform_must_match_expected_source(tmp_path):
    write(tmp_path / "Build_Manifest.json", manifest("macos"))
    with pytest.raises(RuntimeError, match="platform identity"):
        validate_embedded_manifest(tmp_path, COMMIT, expected_manifest=manifest("macos"))


def test_dirty_preview_requires_explicit_opt_in_and_never_passes_release_gate(tmp_path):
    source = dict(manifest(), source_clean=False, build_channel="non-release")
    write(tmp_path / "Build_Manifest.json", source)
    path = write(tmp_path / "report.json", report(source=source))
    with pytest.raises(RuntimeError, match="Non-release"):
        validate(path, source)
    with pytest.raises(RuntimeError, match="Non-release"):
        validate_embedded_manifest(tmp_path, COMMIT, expected_manifest=source)
    assert validate(path, source, allow_non_release=True)["passed"]
    assert validate_embedded_manifest(tmp_path, COMMIT, expected_manifest=source,
                                      allow_non_release=True) == source


@pytest.mark.parametrize("suite", ["Installed_Acceptance.json", "Installed_Facilities_Acceptance.json"])
def test_installer_rejects_false_report_even_when_process_succeeds(tmp_path, monkeypatch, suite):
    install = tmp_path / "installer acceptance"
    write(install / "_internal/Build_Manifest.json", manifest())
    calls = []

    def subprocess_run(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0)

    def runner(args, log, **kwargs):
        payload = report("fusion" if args[1] == "--fusion-self-test" else "facilities")
        if Path(args[-1]).name == suite:
            payload["passed"] = False
        write(Path(args[-1]), payload)

    monkeypatch.setattr(windows_installer.subprocess, "run", subprocess_run)
    with pytest.raises(RuntimeError, match="invalid or failed"):
        windows_installer.verify(tmp_path / "Setup.exe", tmp_path, "App", runner, {},
                                 expected_commit=COMMIT, expected_manifest=manifest())
    assert len(calls) == 1
    assert not (tmp_path / "evidence/Installer_Protection.json").exists()
