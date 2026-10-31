"""Run desktop suites sequentially under one display, with isolated settings."""

from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
records = []
commands = [
    ["tests/gui_features.py"],
    ["tests/v551_fixes.py"],
    ["tests/v552_interactions.py"],
    ["tests/simple_gui.py"],
    ["tests/v554_gui.py"],
    ["tests/maintenance_gui.py"],
    ["Facility_Studio_V5_5.py", "--gui-smoke"],
]
for command in commands:
    with tempfile.TemporaryDirectory(prefix="facility554_suite_") as directory:
        env = dict(os.environ, LOCALAPPDATA=directory)
        subprocess.run([sys.executable, *command], cwd=root, env=env, check=True)
    records.append(dict(command=command, passed=True))
(root / "evidence/GUI_Suite_Execution.json").write_text(
    json.dumps(dict(version="5.5.4", suites=records), ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print("All desktop suites and packaged GUI smoke contract passed", flush=True)
