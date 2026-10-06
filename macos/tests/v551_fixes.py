"""Targeted regression tests for bugs reproduced in the released V5.5 package."""

from pathlib import Path
import sys, json, copy, tempfile, os
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import tkinter as tk
from tkinter import messagebox
from facility_studio.desktop import DesktopApp
from facility_studio.ahu_desktop import AHUWindow
from facility_studio.workspace_view import WorkspaceWindow
from facility_studio.tools_view import QuickToolsWindow
from facility_studio.design_workflow import ahu_requirement_updates
from facility_studio.schema import FIELDS
from facility_studio.ahu_schema import NM_DEFAULTS, NM_V1_KEYS, NM_V3_KEYS
from facility_studio.ahu_engine import nm_read_project
from facility_studio.project_store import app_data, read_recovery
from facility_studio.reports import nm_report
from facility_studio.errors import ValidationError

checks = []
errors = []


def check(name, value):
    checks.append(dict(name=name, passed=bool(value)))
    assert value, name


def reject(name, fn):
    try:
        fn()
    except ValidationError:
        check(name, True)
    else:
        raise AssertionError(name)


messagebox.showerror = lambda *a, **k: errors.append(str(a))
messagebox.showinfo = lambda *a, **k: None
messagebox.askokcancel = lambda *a, **k: True
messagebox.askyesno = lambda *a, **k: True
original_read = Path.read_text
with tempfile.TemporaryDirectory(prefix="facility551_") as td, patch.dict(
    os.environ, {"LOCALAPPDATA": td}
):
    r = tk.Tk()
    a = DesktopApp(r)
    r.update()
    for zone in ["A", "B"]:
        a.variables["en_ach_" + zone].set("37")
        a.variables["en_p_" + zone].set("12")
        before = a.snapshot()
        a.preset(zone)
        check(zone + "_preset_is_applied", a.snapshot() != before)
        check(
            zone + "_preset_origin",
            a.provenance["en_ach_" + zone]["source"] == "系統預設",
        )
        a.undo_preset()
        check(zone + "_undo_complete_snapshot", a.snapshot() == before)
    # Emulate legacy Windows text defaults, without claiming a Windows execution test.
    for codec in ["cp950", "cp1252"]:

        def legacy_default(path, encoding=None, errors=None):
            return original_read(path, encoding=encoding or codec, errors=errors)

        (app_data() / "Quick_Tools.json").write_text(
            json.dumps(
                {"history": [], "favorites": ["濕空氣計算"]}, ensure_ascii=False
            ),
            encoding="utf-8",
        )
        with patch.object(Path, "read_text", legacy_default):
            w = WorkspaceWindow(r, a)
            r.update()
            check(codec + "_workspace_opens", w.win.winfo_exists())
            w.close(force=True)
            q = QuickToolsWindow(r, a)
            r.update()
            check(codec + "_Chinese_favorite_read", q.tool.get() == "濕空氣計算")
            q.close(force=True)
            q = QuickToolsWindow(r, a)
            r.update()
            check(
                codec + "_history_roundtrip",
                len(q.history) > 0 and "濕空氣計算" in q.favorites,
            )
            q.close(force=True)
    for version, keys in [
        (1, NM_V1_KEYS),
        (2, NM_V3_KEYS),
        (3, NM_V3_KEYS),
        (4, set(NM_DEFAULTS)),
    ]:
        p = Path(td) / f"ahu_v{version}.json"
        p.write_text(
            json.dumps(
                {
                    "kind": "ahu_stage",
                    "schema_version": version,
                    "inputs": {k: NM_DEFAULTS[k] for k in keys},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        doc = nm_read_project(p)
        check(
            "legacy_v" + str(version) + "_migrates",
            doc["schema_version"] == 4 and set(doc["inputs"]) == set(NM_DEFAULTS),
        )
        check(
            "legacy_v" + str(version) + "_unknown_pump",
            doc["inputs"]["pump_input_kw"] == "",
        )
    bad = Path(td) / "bad_recovery.json"
    bad.write_text("[]", encoding="utf-8")
    reject("bad_recovery_structured_error", lambda: read_recovery(bad))
    a.variables["sys_type"].set(FIELDS["sys_type"]["options"][0])
    a.recalculate()
    check("main_model_valid", a.result is not None)
    c = AHUWindow(r, a)

    def relink():
        c.link_requirements()

    relink()
    flows = [c.vars[s + "_flow"].get() for s in ["summer", "winter"]]
    c.target_preset(55)
    check(
        "seasonal_preset_both_targets",
        all(
            c.vars[s + "_sa_rh"].get() == "55" and c.vars[s + "_sa_t"].get() == "22"
            for s in ["summer", "winter"]
        ),
    )
    check(
        "seasonal_preset_retains_flows",
        flows == [c.vars[s + "_flow"].get() for s in ["summer", "winter"]],
    )
    check("preset_clears_link_claim", c.vars["linked_main_hash"].get() == "尚未連動")
    relink()
    c.vars["summer_sa_t"].set("21")
    check("manual_target_clears_link", c.vars["linked_main_hash"].get() == "尚未連動")
    relink()
    c.vars["h1_kw"].set("500")
    c.calculate()
    check(
        "rating_change_keeps_boundary_link",
        c.vars["linked_main_hash"].get() == ahu_requirement_updates(a.result)["linked_main_hash"],
    )
    relink()
    a.variables["oa_t"].set("36")
    a.recalculate()
    c.ensure()
    check("changed_main_flags_stale_link", "已過期" in c.result["link_status"])
    check("cached_report_includes_staleness", "已過期" in nm_report(c.result))
    c.target_preset(50)
    c.calculate()
    check("custom_target_report_clear", "未宣告" in nm_report(c.result))
    c.close(force=True)
    check("no_unexpected_dialogs", not errors)
    r.destroy()
(ROOT / "evidence/V551_Fix_Checks.json").write_text(
    json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"{len(checks)} V5.5.1 targeted checks passed", flush=True)
