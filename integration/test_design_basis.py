"""Counterexamples for document integrity; synthetic documents are not real approvals."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "macos"))
from facility_studio import design_basis as m


def filled():
    data = m.new_dossier()
    data["basis"] = {key: "合成測試－" + label for key, label in m.FIELDS.items()}
    data["standards"] = [dict(name="合成驗收規範", edition="R1", clause="3.1",
                              scope="100 m² 無塵室合成案例", source="SYNTHETIC-001")]
    return data


def attached(tmp_path):
    data = filled()
    source = tmp_path / "合成.txt"
    source.write_text("合成測試證據，非真實工程簽核", encoding="utf-8")
    for key in m.DELIVERABLES:
        m.attach(data, tmp_path, key, source)
    return data


def reviewed(tmp_path):
    data = attached(tmp_path)
    for key in m.DELIVERABLES:
        m.record_review(data, tmp_path, key, "合成覆核者", "accepted", "僅供測試：依合成規範逐項核對")
    return data


def test_blank_and_filled_basis_never_imply_complete_feed(tmp_path):
    state = m.evaluate(m.new_dossier(), tmp_path)
    assert len(state["missing_basis"]) == 10 and not state["can_submit"]
    state = m.evaluate(filled(), tmp_path)
    assert not state["missing_basis"] and not state["can_submit"]
    assert all("待人工覆核" in row["issues"] for row in state["rows"])


def test_fully_reviewed_register_is_only_document_readiness(tmp_path):
    data = reviewed(tmp_path)
    state = m.evaluate(data, tmp_path)
    assert state["can_submit"] and state["status"] == "文件齊備，可送工程審查"
    assert "不驗證內容正確性" in state["limitation"]
    assert "certified" not in state


@pytest.mark.parametrize("field", list(m.FIELDS))
def test_every_basis_change_invalidates_all_previous_reviews(tmp_path, field):
    data = reviewed(tmp_path)
    data["basis"][field] += " revised"
    state = m.evaluate(data, tmp_path)
    assert not state["can_submit"]
    assert all(any("失效" in s for s in row["issues"]) for row in state["rows"])


def test_standard_edition_and_new_evidence_invalidate_reviews(tmp_path):
    data = reviewed(tmp_path)
    original = deepcopy(data)
    data["standards"][0]["edition"] = "R2"
    assert not m.evaluate(data, tmp_path)["can_submit"]
    m.attach(original, tmp_path, "basis", tmp_path / "合成.txt")
    assert not m.evaluate(original, tmp_path)["can_submit"]


@pytest.mark.parametrize("operation", ["tamper", "missing", "symlink"])
def test_evidence_failure_blocks_readiness_and_new_acceptance(tmp_path, operation):
    data = reviewed(tmp_path)
    evidence = data["documents"]["balance"]["evidence"][0]
    path = tmp_path / evidence["path"]
    if operation == "tamper":
        path.write_bytes(b"changed")
    else:
        path.unlink()
        if operation == "symlink":
            path.symlink_to(tmp_path / "合成.txt")
    assert not m.evaluate(data, tmp_path)["can_submit"]
    with pytest.raises(ValueError):
        m.record_review(data, tmp_path, "balance", "合成覆核者", "accepted", "不可接受損壞證據")


def test_preserve_previous_revisions_and_source_file(tmp_path):
    data = reviewed(tmp_path)
    source_before = (tmp_path / "合成.txt").read_bytes()
    path1 = m.save_revision(data, tmp_path)
    original = path1.read_bytes()
    data["basis"]["revision"] = "R2"
    path2 = m.save_revision(data, tmp_path)
    assert path1 != path2 and path1.read_bytes() == original
    assert (tmp_path / "合成.txt").read_bytes() == source_before
    assert m.load_revision(path1)["basis"]["revision"] != "R2"


def test_rejection_and_exclusion_require_real_record(tmp_path):
    data = reviewed(tmp_path)
    m.record_review(data, tmp_path, "risk", "合成覆核者", "rejected", "危害分析尚缺事故情境")
    assert not m.evaluate(data, tmp_path)["can_submit"]
    data["documents"]["risk"] = dict(evidence=[], exclusion="合成無危害子系統範圍")
    assert not m.evaluate(data, tmp_path)["can_submit"]
    with pytest.raises(ValueError):
        m.record_review(data, tmp_path, "risk", "合成覆核者", "accepted", "OK")
    for key in m.DELIVERABLES:
        m.record_review(data, tmp_path, key, "合成覆核者", "accepted", "合成試驗範圍核對；排除理由已核對")
    assert m.evaluate(data, tmp_path)["can_submit"]


def test_preparer_cannot_self_review_or_accept_blank_documents(tmp_path):
    data = filled()
    with pytest.raises(ValueError):
        m.record_review(data, tmp_path, "basis", data["basis"]["preparer"], "accepted", "自行核對")
    with pytest.raises(ValueError):
        m.record_review(data, tmp_path, "basis", "合成覆核者", "accepted", "缺件不應接受")


@pytest.mark.parametrize("relative", ["../secret", "/etc/passwd", "evidence/../../secret", "evidence\\secret", "evidence/x.bin"])
def test_import_rejects_external_evidence_paths_before_read(tmp_path, relative):
    data = attached(tmp_path)
    data["documents"]["basis"]["evidence"][0]["path"] = relative
    with pytest.raises(ValueError):
        m.evaluate(data, tmp_path)


def test_import_rejects_duplicate_unknown_and_future_schema(tmp_path):
    path = tmp_path / "malformed.json"
    path.write_text('{"schema":1,"schema":2}', encoding="utf-8")
    with pytest.raises(ValueError):
        m.load_revision(path)
    data = filled()
    data["schema"] = 999
    with pytest.raises(ValueError):
        m.validate(data)
    data = filled()
    data["unrecognized"] = True
    with pytest.raises(ValueError):
        m.validate(data)


def test_empty_source_and_linked_folder_are_rejected(tmp_path):
    data = filled()
    source = tmp_path / "empty"
    source.touch()
    with pytest.raises(ValueError):
        m.attach(data, tmp_path, "basis", source)
    source.write_text("synthetic", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "evidence").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        m.attach(data, tmp_path, "basis", source)
    assert not list(outside.iterdir())


def test_report_rechecks_and_contains_names_sources_and_hashes(tmp_path):
    data = reviewed(tmp_path)
    first, state = m.export_review(data, tmp_path)
    assert state["can_submit"]
    text = first.read_text(encoding="utf-8")
    assert "SYNTHETIC-001" in text and "合成覆核者" in text and "SHA256" in text
    file = tmp_path / data["documents"]["basis"]["evidence"][0]["path"]
    file.write_text("changed", encoding="utf-8")
    second, state = m.export_review(data, tmp_path)
    assert not state["can_submit"] and first != second
    assert "證據內容已變更" in second.read_text(encoding="utf-8")
    assert first.read_text(encoding="utf-8") == text


def test_saved_dossier_cli_uses_real_readiness_exit_codes(tmp_path, monkeypatch, capsys):
    from facility_studio.cli import main
    data = reviewed(tmp_path)
    path = m.save_revision(data, tmp_path)
    monkeypatch.setattr(sys, "argv", ["facility", "--dossier-check", str(path)])
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["can_submit"]
    file = tmp_path / data["documents"]["basis"]["evidence"][0]["path"]
    file.unlink()
    assert main() == 3
    assert not json.loads(capsys.readouterr().out)["can_submit"]
    path.write_text("{}", encoding="utf-8")
    assert main() == 2
