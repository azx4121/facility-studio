"""Fresh-process production entry/CLI launch; observe, never repair, placement."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "integration/windows_cold_startup_probe.py"


def test_probe_does_not_preimport_views_or_mutate_window_geometry():
    tree = ast.parse(PROBE.read_text(encoding="utf-8"))
    imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    imports += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
    assert not any(name.startswith("facility_studio") for name in imports)
    calls = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute)}
    assert not calls.intersection({"geometry", "SetWindowPos", "MoveWindow", "withdraw",
                                   "deiconify", "update", "update_idletasks", "mainloop"})
    assert "run_path" in calls


@pytest.mark.skipif(sys.platform != "win32", reason="Requires a real Windows desktop")
@pytest.mark.parametrize("language", ["zh-Hant", "en"])
@pytest.mark.parametrize("mode", ["simple", "workbench"])
@pytest.mark.parametrize("launch", range(4))
def test_cold_real_entry_contains_untouched_native_window(tmp_path, language, mode, launch, record_property):
    receipt = tmp_path / "Cold_Startup_Trace.json"
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    result = subprocess.run([sys.executable, str(PROBE), "--evidence", str(receipt),
        "--data", str(tmp_path / "data"), "--mode", mode, "--language", language],
        cwd=ROOT, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        encoding="utf-8", errors="replace", timeout=150)
    assert receipt.is_file(), result.stdout
    report = json.loads(receipt.read_text(encoding="utf-8"))
    record_property("cold_startup_readout", json.dumps(report, ensure_ascii=False))
    assert result.returncode == 0 and report["passed"], (report, result.stdout)
    assert any(row["event"] == "first_map" for row in report["events"])
    assert any(row.get("function") == "_place_initial_windows_window" for row in report["events"])
    assert not report["views_imported_when_tk_created"]["facility_studio.simple_desktop"]
    assert not report["views_imported_when_tk_created"]["facility_studio.desktop"]
