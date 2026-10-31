"""Reproduction record for the four V5.5 regression paths."""

from pathlib import Path
import sys, tempfile, json, copy
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import tkinter as tk
from facility_studio.desktop import DesktopApp
from facility_studio.ahu_desktop import AHUWindow
from facility_studio.workspace_view import WorkspaceWindow
from facility_studio.design_workflow import ahu_requirement_updates
from facility_studio.schema import FIELDS
from facility_studio.ahu_schema import NM_DEFAULTS, NM_V3_KEYS
from facility_studio.ahu_engine import nm_read_project

records = []


def record(name, fn):
    try:
        records.append(dict(name=name, result=fn()))
    except Exception as e:
        records.append(dict(name=name, error=type(e).__name__ + ": " + str(e)))


r = tk.Tk()
a = DesktopApp(r)
r.update()
record("grade_preset_undo", lambda: (a.preset("A"), a.undo_preset()))
original = Path.read_text


def cp950(path, encoding=None, errors=None):
    return original(path, encoding=encoding or "cp950", errors=errors)


with patch.object(Path, "read_text", cp950):
    record("project_workspace_CP950", lambda: WorkspaceWindow(r, a) and "opened")
a.variables["sys_type"].set(FIELDS["sys_type"]["options"][0])
a.recalculate()
c = AHUWindow(r, a)
i = c.snapshot()
i.update(ahu_requirement_updates(a.result))
c.apply(i)
c.target_preset(55)
records.append(
    dict(
        name="seasonal_target_button",
        expected=55,
        actual=float(c.vars["summer_sa_rh"].get()),
    )
)
with tempfile.TemporaryDirectory() as d:
    p = Path(d) / "v2.json"
    p.write_text(
        json.dumps(
            {
                "kind": "ahu_stage",
                "schema_version": 2,
                "inputs": {k: NM_DEFAULTS[k] for k in NM_V3_KEYS},
            }
        ),
        encoding="utf-8",
    )
    record("legacy_AHU_v2", lambda: nm_read_project(p)["schema_version"])
(ROOT / "evidence/V551_Before_Fix.json").write_text(
    json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(records, ensure_ascii=False, indent=2), flush=True)
r.destroy()
