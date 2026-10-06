"""Real Tk interaction test. Run with an available desktop/display."""

from pathlib import Path
import sys, json, copy, tempfile, os

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import tkinter as tk
from tkinter import messagebox
from PIL import ImageGrab
from facility_studio.desktop import DesktopApp
from facility_studio.ahu_desktop import AHUWindow
from facility_studio.tools_view import QuickToolsWindow, TOOLS
from facility_studio.workspace_view import WorkspaceWindow, apply_updates
from facility_studio.schema import FIELDS

checks = []


def check(name, value):
    checks.append(dict(name=name, passed=bool(value)))
    assert value, name


# All dialogs are recorded; errors cannot block automation.
errors = []
messagebox.showerror = lambda *a, **k: errors.append(str(a))
messagebox.showinfo = lambda *a, **k: None
messagebox.askokcancel = lambda *a, **k: True
messagebox.askyesno = lambda *a, **k: True
messagebox.askyesnocancel = lambda *a, **k: False
r = tk.Tk()
a = DesktopApp(r)
r.update()
check("default_valid", a.result is not None)
for page in range(8):
    a.show_page(page)
    r.update()
    check("page_" + str(page), a.pages[page].winfo_ismapped())
a.show_page(0)
r.geometry("1240x900")
r.update()
ImageGrab.grab().save(ROOT / "evidence/UI_Overview.png")
a.view_mode.set("進階模式")
r.update()
check("advanced_rows", len(a.widgets) == len(FIELDS))
a.variables["e_pf"].set("0")
a.recalculate()
r.update()
check("invalid_blocks_export", a.result is None)
a.variables["e_pf"].set(".85")
a.recalculate()
r.update()
check("valid_recovers", a.result is not None)
a.variables["sys_type"].set(FIELDS["sys_type"]["options"][0])
a.recalculate()
check("MAU_valid", a.result is not None)
quick = QuickToolsWindow(r, a)
r.update()
for name in TOOLS:
    quick.tool.set(name)
    quick.build()
    quick.calculate()
    r.update()
    check("quick_" + name, quick.result is not None)
quick.tool.set("濕空氣計算")
quick.build()
quick.calculate()
r.update()
ImageGrab.grab().save(ROOT / "evidence/UI_QuickTools.png")
quick.values["second"].set("101")
r.update()
check("quick_change_clears", quick.result is None)
quick.calculate()
check("quick_invalid", quick.result is None)
quick.values["second"].set("70")
quick.calculate()
check("quick_restores", quick.result is not None)
quick.close(force=True)
work = WorkspaceWindow(r, a)
r.update()
check("source_rows", len(work.tree.get_children()) == len(FIELDS))
work.tree.selection_set("oa_t")
r.update()
work.origin.set("原廠資料")
work.note.set("TEST-DOC-001")
work.mark()
check("provenance_mark", a.provenance["oa_t"]["source"] == "原廠資料")
work.capture("A")
a.variables["light_lux"].set("650")
a.recalculate()
work.capture("B")
check("AB_frozen", a.comparisons["A"]["hash"] != a.comparisons["B"]["hash"])
check("AB_text", "室內顯熱" in work.comparison_string())
r.update()
ImageGrab.grab().save(ROOT / "evidence/UI_Project_Workspace.png")
work.close(force=True)
c = AHUWindow(r, a)
r.update()
check("AHU_valid", c.result is not None)
c.link_requirements()
r.update()
check("AHU_link_valid", c.result is not None)
check("AHU_seasonal_enabled", str(c.widgets["summer_sa_t"].cget("state")) == "normal")
check("AHU_shared_disabled", str(c.widgets["sa_t"].cget("state")) == "disabled")
check(
    "AHU_link_mass", abs(c.result["winter"]["mass"] - a.result["winter"]["mass"]) < 1e-6
)
c.nb.select(1)
r.update()
ImageGrab.grab().save(ROOT / "evidence/UI_AHU.png")
# Preview is applied twice without adding loads repeatedly.
c.return_utilities()
first = {k: v.get() for k, v in a.variables.items() if k.startswith("e_np")}
c.return_utilities()
check(
    "return_idempotent",
    first == {k: v.get() for k, v in a.variables.items() if k.startswith("e_np")},
)
c.close(force=True)
r.geometry("880x600")
a.view_mode.set("基本模式")
a.show_page(0)
r.update()
check(
    "minwidth_calc_visible",
    a.calc_button.winfo_ismapped()
    and a.calc_button.winfo_rootx() + a.calc_button.winfo_width()
    <= r.winfo_rootx() + r.winfo_width(),
)
ImageGrab.grab().save(ROOT / "evidence/UI_Compact.png")
a.autosave()
check("autosave_runs", True)

original = a.snapshot()
apply_updates(a, {"oa_t": "34"}, "test")
a.undo_preset()
check("linked_undo", a.snapshot() == original)
invalid = a.snapshot()
invalid["inputs"]["oa_t"] = ""
a.restore_snapshot(invalid)
check("restore_invalid_raw", a.variables["oa_t"].get() == "" and a.result is None)
a.restore_snapshot(original)
check("restore_valid_snapshot", a.result is not None)

check("no_modal_errors", not errors)
(ROOT / "evidence/GUI_V55_Checks.json").write_text(
    json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"{len(checks)} real Tk checks passed", flush=True)
r.destroy()
