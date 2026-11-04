"""Exact-HEAD source identity, including negative dirty/ignored input cases."""
import hashlib
import importlib.util
import marshal
import py_compile
from pathlib import Path
import subprocess
import sys

import pytest

from integration.source_provenance import expected_source_manifest, provenance_digest, verify_source_unchanged
from integration.test_acceptance_validation import manifest


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.PIPE).decode().strip()


def write(root, name, value="example\n"):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return path


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repository"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "user.name", "Local test")
    for name in ("integration/build.py", "integration/entry.py", "integration/nested/helper.py",
                 "windows/winrelease/hooks/hook-example.py", "LICENSE", "LICENSE_LEGACY_MIT",
                 "THIRD_PARTY_NOTICES.md", "macos/macos/PsychroLib-LICENSE.txt",
                 "windows/facility_studio/entry.py", "windows/facility_studio/resources/template.xlsx",
                 "windows/evidence/existing.json", "macos/evidence/existing.json"):
        write(root, name)
    write(root, ".gitignore", "__pycache__/\n*.pyc\n*.so\nignored.py\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "Synthetic test inputs")
    return root


def test_clean_source_hashes_are_exact_head_bytes(repo):
    result = expected_source_manifest(repo, "windows", expected_commit=git(repo, "rev-parse", "HEAD"))
    assert result["source_clean"] is True
    assert result["build_channel"] == "stable"
    assert result["product_source_sha256"]["facility_studio/entry.py"] == hashlib.sha256(b"example\n").hexdigest()
    assert "integration/nested/helper.py" in result["build_inputs_sha256"]
    assert "windows/winrelease/hooks/hook-example.py" in result["build_inputs_sha256"]
    assert "LICENSE" in result["build_inputs_sha256"]


@pytest.mark.parametrize("kind", ["modified", "staged", "deleted", "untracked", "ignored", "binary", "bytecode", "assume_unchanged"])
def test_dirty_product_source_cannot_claim_head(repo, kind):
    name = "windows/facility_studio/entry.py"
    if kind == "deleted":
        (repo / name).unlink()
    else:
        if kind in ("untracked", "ignored", "binary", "bytecode"):
            name = "windows/facility_studio/" + {"untracked": "new.py", "ignored": "ignored.py", "binary": "code.so", "bytecode": "injected.pyc"}[kind]
        if kind == "assume_unchanged":
            git(repo, "update-index", "--assume-unchanged", name)
        write(repo, name, "changed\n")
        if kind == "staged":
            git(repo, "add", name)
    with pytest.raises(RuntimeError, match="Dirty source tree"):
        expected_source_manifest(repo, "windows")
    preview = expected_source_manifest(repo, "windows", allow_dirty=True)
    assert preview["source_clean"] is False
    assert preview["build_channel"] == "non-release"


@pytest.mark.parametrize("name", ["integration/build.py", "integration/ignored.py", "LICENSE",
                                  "windows/winrelease/hooks/ignored.py", "windows/facility_studio/resources/template.xlsx"])
def test_all_real_packaging_inputs_are_protected(repo, name):
    write(repo, name, "changed\n")
    with pytest.raises(RuntimeError, match="Dirty source tree"):
        expected_source_manifest(repo, "windows")


def test_source_tests_may_regenerate_nonshipped_evidence_and_caches(repo):
    before = expected_source_manifest(repo, "windows")
    for name in ("windows/evidence/existing.json", "macos/evidence/existing.json",
                 "windows/evidence/new.json", "macos/evidence/new.json"):
        write(repo, name, "generated\n")
    py_compile.compile(str(repo / "windows/facility_studio/entry.py"), doraise=True)
    assert expected_source_manifest(repo, "windows") == before


def test_wrong_commit_and_platform_fail_before_build(repo):
    with pytest.raises(RuntimeError, match="expected build commit"):
        expected_source_manifest(repo, "windows", expected_commit="a" * 40)
    with pytest.raises(RuntimeError, match="Unsupported source platform"):
        expected_source_manifest(repo, "linux")


def test_symlink_product_source_is_not_silently_followed(repo):
    try:
        (repo / "windows/facility_studio/link.py").symlink_to(repo / "LICENSE")
    except OSError:
        pytest.skip("Test host does not permit symlinks")
    with pytest.raises(RuntimeError, match="Symlink"):
        expected_source_manifest(repo, "windows", allow_dirty=True)


def test_dirty_build_stops_before_creating_output_or_reading_dependencies(repo, tmp_path, monkeypatch):
    from integration import build
    write(repo, "integration/build.py", "uncommitted\n")
    output = tmp_path / "output"
    monkeypatch.setattr(build, "ROOT", repo)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "version_info", (3, 12))
    monkeypatch.setattr(sys, "argv", ["build.py", "--output", str(output)])
    monkeypatch.setattr(build.importlib.metadata, "distribution", lambda *_: pytest.fail("Dependency read before guard"))
    with pytest.raises(RuntimeError, match="Dirty source tree"):
        build.main()
    assert not output.exists()


@pytest.mark.parametrize("platform", ["windows", "macos"])
def test_frozen_runtime_identity_matches_independent_validator(platform, tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / platform / "facility_studio/candidate_acceptance.py"
    spec = importlib.util.spec_from_file_location("candidate_identity_" + platform, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = manifest(platform)
    import json
    write(tmp_path, "Build_Manifest.json", json.dumps(source))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert module.build_identity() == dict(build_commit=source["commit"],
                                           build_provenance_sha256=provenance_digest(source))
    monkeypatch.delattr(sys, "frozen")
    assert module.build_identity() == dict(build_commit=None, build_provenance_sha256=None)


def test_midbuild_source_drift_fails_but_output_files_do_not(repo):
    source = expected_source_manifest(repo, "windows")
    write(repo, "local-output/generated-manifest.json", "{}")
    verify_source_unchanged(repo, "windows", source)
    write(repo, "integration/entry.py", "changed during build")
    with pytest.raises(RuntimeError, match="changed while freezing"):
        verify_source_unchanged(repo, "windows", source)


def test_missing_git_identity_cannot_fall_back_to_arbitrary_hash(tmp_path):
    with pytest.raises(RuntimeError, match="Cannot establish source identity"):
        expected_source_manifest(tmp_path, "windows", allow_dirty=True)


@pytest.mark.parametrize("relative", [
    "windows/facility_studio/resources/__pycache__/unhashed.txt",
    "windows/facility_studio/resources/__pycache__/nested/data.json",
    "windows/facility_studio/__pycache__/unhashed.txt",
    "integration/__pycache__/unhashed.py",
    "windows/winrelease/hooks/__pycache__/unhashed.py",
])
def test_cache_named_directories_do_not_hide_noncache_inputs(repo, relative):
    write(repo, relative, "uncommitted payload")
    with pytest.raises(RuntimeError, match="Dirty source tree"):
        expected_source_manifest(repo, "windows")
    development = expected_source_manifest(repo, "windows", allow_dirty=True)
    combined = dict(development["build_inputs_sha256"])
    combined.update({"windows/" + key: value for key, value in development["product_source_sha256"].items()})
    assert relative in combined


@pytest.mark.parametrize("relative", [
    "windows/facility_studio/resources/__pycache__/linked.txt",
    "windows/facility_studio/__pycache__/linked.pyc",
    "integration/__pycache__/linked.pyc",
])
def test_cache_named_directories_never_hide_symlinks(repo, relative):
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.symlink_to(repo / "LICENSE")
    except OSError:
        pytest.skip("Test host does not permit symlinks")
    with pytest.raises(RuntimeError, match="Symlink"):
        expected_source_manifest(repo, "windows", allow_dirty=True)


@pytest.mark.parametrize("kind", ["invalid_bytes", "altered_code", "extra_payload", "orphan", "nested_directory"])
def test_pyc_looking_inputs_are_not_automatically_trusted(repo, kind):
    source = repo / "windows/facility_studio/entry.py"
    cached = Path(py_compile.compile(str(source), doraise=True))
    if kind == "invalid_bytes":
        cached.write_bytes(b"not really compiled bytecode")
    elif kind == "altered_code":
        cached.write_bytes(cached.read_bytes()[:16] + marshal.dumps(compile("unexpected = 42", str(source), "exec")))
    elif kind == "extra_payload":
        cached.write_bytes(cached.read_bytes() + b"unhashed payload")
    elif kind == "orphan":
        cached.rename(cached.with_name(cached.name.replace("entry.", "missing.")))
    else:
        nested = cached.parent / "nested"
        nested.mkdir()
        cached.rename(nested / cached.name)
    with pytest.raises(RuntimeError, match="Dirty source tree"):
        expected_source_manifest(repo, "windows")


def test_even_genuine_resource_bytecode_is_included_in_inventory(repo):
    source = write(repo, "windows/facility_studio/resources/example.py", "constant = 3\n")
    git(repo, "add", str(source.relative_to(repo)))
    git(repo, "commit", "-qm", "Synthetic resource source")
    before = expected_source_manifest(repo, "windows")
    cached = Path(py_compile.compile(str(source), doraise=True))
    with pytest.raises(RuntimeError, match="Dirty source tree"):
        expected_source_manifest(repo, "windows")
    after = expected_source_manifest(repo, "windows", allow_dirty=True)
    assert cached.relative_to(repo / "windows").as_posix() in after["product_source_sha256"]
    assert after != before


@pytest.mark.parametrize("optimization", [0, 1, 2])
def test_genuine_generated_nonresource_caches_preserve_clean_identity(repo, optimization):
    before = expected_source_manifest(repo, "windows")
    for name in ("windows/facility_studio/entry.py", "integration/build.py", "windows/winrelease/hooks/hook-example.py"):
        py_compile.compile(str(repo / name), doraise=True, optimize=optimization)
    assert expected_source_manifest(repo, "windows") == before
