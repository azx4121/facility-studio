"""Real CLI subprocesses: UTF-8 pipes must not depend on the Windows code page."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

PLATFORM = os.environ.get("FACILITY_TEST_PLATFORM", "windows")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / PLATFORM))
from facility_studio import cli, design_basis


def run_cli(tmp_path, *args):
    env = dict(os.environ, PYTHONPATH=str(ROOT / PLATFORM),
               PYTHONIOENCODING="cp1252:strict", PYTHONUTF8="0",
               FACILITY_STUDIO_PREFERENCES=str(tmp_path / "preferences.json"))
    entry = ("import sys; assert sys.flags.utf8_mode == 0; "
                "assert sys.stdout.encoding == 'cp1252'; "
                "from facility_studio.cli import main; raise SystemExit(main())")
    command = [sys.executable, "-X", "utf8=0", "-c", entry, *map(str, args)]
    result = subprocess.run(command, env=env, capture_output=True,
                            encoding="utf-8", errors="strict", timeout=60)
    assert "\ufffd" not in result.stdout + result.stderr
    assert "UnicodeEncodeError" not in result.stderr and "Traceback" not in result.stderr
    return result


def test_tool_pipe_preserves_unicode_verbatim(tmp_path):
    path = tmp_path / "照明資料.json"
    name = "設備甲 Ω 照明 🏭"
    path.write_text(json.dumps({"report_project": name}, ensure_ascii=False), encoding="utf-8")
    result = run_cli(tmp_path, "--language", "en", "--tool", "lighting", "--tool-input", path)
    assert result.returncode == 0, result.stderr
    assert name in result.stdout and not result.stderr


def test_project_report_pipe_preserves_complete_unicode_report(tmp_path):
    from facility_studio.engine import calculate
    from facility_studio.reports import report
    from facility_studio.schema import default_project
    project = default_project()
    path = tmp_path / "合成主案.json"
    path.write_text(json.dumps(project, ensure_ascii=False), encoding="utf-8")
    result = run_cli(tmp_path, "--language", "zh-Hant", "--project", path)
    assert result.returncode == 0, result.stderr
    assert result.stdout == str(report(calculate(project), language="zh-Hant")) + "\n"


def test_dossier_pipe_retains_pending_status_and_unicode_json(tmp_path):
    path = design_basis.save_revision(design_basis.new_dossier(), tmp_path)
    result = run_cli(tmp_path, "--dossier-check", path)
    assert result.returncode == 3, result.stderr
    state = json.loads(result.stdout)
    assert not state["can_submit"] and state["missing_basis"]
    assert state["status"] == design_basis.evaluate(design_basis.load_revision(path), path.parent)["status"]
    assert any(ord(c) > 127 for c in result.stdout)


@pytest.mark.parametrize("mode", ["--capacity-plan", "--dossier-check", "--project"])
def test_error_pipe_preserves_unicode_filename_and_invalid_status(tmp_path, mode):
    path = tmp_path / "不存在的專案 Ω.json"
    result = run_cli(tmp_path, mode, path)
    assert result.returncode == 2
    assert path.name in result.stderr
    assert not result.stdout


def test_equipment_error_pipe_preserves_unicode_validation(tmp_path):
    result = run_cli(tmp_path, "--equipment", tmp_path / "missing.csv")
    assert result.returncode == 2 and result.stderr == "檔案：檔案不存在或超過20MB\n"
    assert not result.stdout


def test_tool_error_pipe_preserves_unicode_validation(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text('{"unknown": 1}', encoding="utf-8")
    result = run_cli(tmp_path, "--tool", "lighting", "--tool-input", path)
    assert result.returncode == 2 and "未知欄位" in result.stderr
    assert not result.stdout


def test_argument_help_pipe_is_utf8(tmp_path):
    result = run_cli(tmp_path, "--help")
    assert result.returncode == 0 and "Redirected stdout and stderr use UTF-8." in result.stdout
    assert "核對容量與擴建計畫" in result.stdout


def test_redirected_streams_are_strict_utf8_without_touching_terminal(monkeypatch):
    class Terminal(io.StringIO):
        def isatty(self):
            return True
        def reconfigure(self, **kwargs):
            raise AssertionError("Interactive terminal encoding must not change")

    target = io.BytesIO()
    redirected = io.TextIOWrapper(target, encoding="cp1252", errors="strict")
    terminal = Terminal()
    monkeypatch.setattr(sys, "stdout", terminal)
    monkeypatch.setattr(sys, "stderr", redirected)
    cli._configure_redirected_streams()
    redirected.write("設備甲 Ω 🏭")
    redirected.flush()
    assert target.getvalue() == "設備甲 Ω 🏭".encode("utf-8")
    assert redirected.errors == "strict"
    redirected.detach()
