"""Headless candidate scenarios and simulated identity checks, not native GUI proof."""
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / os.environ.get("FACILITY_TEST_PLATFORM", "windows")))
from facility_studio import candidate_acceptance as acceptance


def test_frozen_compatible_headless_scenarios(tmp_path):
    checks = []
    def check(name, condition):
        checks.append(name)
        assert condition, name
    acceptance.run_headless(tmp_path, check)
    assert len(checks) == 10
    assert len(checks) == len(set(checks))
    assert {p.name for p in tmp_path.iterdir()} == {
        "capacity.txt", "synthetic.ies", "synthetic.ldt", "direct.html", "direct.csv", "direct.json"}


def test_source_mode_does_not_claim_bundled_commit(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert acceptance.build_commit() is None


def test_frozen_mode_uses_bundled_manifest(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    commit = "a" * 40
    (tmp_path / "Build_Manifest.json").write_text(json.dumps({"commit": commit}), encoding="utf-8")
    assert acceptance.build_commit() == commit


@pytest.mark.parametrize("commit", [None, "", "a" * 7, "x" * 40, True, 1, "A" * 40])
def test_frozen_mode_rejects_invalid_commit(monkeypatch, tmp_path, commit):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    (tmp_path / "Build_Manifest.json").write_text(json.dumps({"commit": commit}), encoding="utf-8")
    with pytest.raises(ValueError):
        acceptance.build_commit()


def test_frozen_mode_rejects_missing_manifest(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    with pytest.raises(FileNotFoundError):
        acceptance.build_commit()
