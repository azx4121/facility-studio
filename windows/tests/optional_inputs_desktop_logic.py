"""Desktop snapshot/load/restore data logic with a stand-in tkinter module.

This exercises the real DesktopApp methods without opening a window. It does
not prove widget behaviour, event ordering or rendering on a real Tk display;
those still need tests/gui_all.py on Windows.
"""

import copy
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class _Anything:
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return _Anything()

    def __getattr__(self, name):
        return _Anything()


def _used_names():
    import re
    names = set()
    for path in (ROOT / "facility_studio").glob("*.py"):
        names |= set(re.findall(r"\b(?:tk|ttk|tkfont|messagebox|filedialog)\.([A-Za-z_]\w*)", path.read_text(encoding="utf-8")))
    return sorted(names)


_NAMES = _used_names()


class _StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Anything

    def __dir__(self):
        return _NAMES


for name in (
    "tkinter", "tkinter.ttk", "tkinter.messagebox", "tkinter.filedialog",
    "tkinter.font", "tkinter.simpledialog", "tkinter.scrolledtext", "tkinter.colorchooser", "_tkinter",
):
    sys.modules[name] = _StubModule(name)
sys.modules["tkinter"].ttk = sys.modules["tkinter.ttk"]
sys.modules["tkinter"].TclError = type("TclError", (Exception,), {})

from facility_studio.desktop import DesktopApp  # noqa: E402
from facility_studio.errors import ValidationError  # noqa: E402
from facility_studio.schema import FIELDS, default_project  # noqa: E402
from facility_studio.workspace_store import new_workspace, validate_workspace  # noqa: E402

checks = []


def check(name, ok, detail=""):
    checks.append(dict(name=name, passed=bool(ok), detail=str(detail)[:200]))


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def app():
    """A DesktopApp shell: real data methods, inert UI hooks."""
    shell = DesktopApp.__new__(DesktopApp)
    base = default_project()
    shell.variables = {k: Var(v) for k, v in base["inputs"].items()}
    shell.pd = {k: {f: Var(v) for f, v in row.items()} for k, row in base["pressure_drop"].items()}
    shell.provenance = base["provenance"]
    shell.extra_inputs = {}
    shell.field_drafts, shell.transfer_receipts, shell.demand_ledger = {}, [], {}
    shell.unit_previous = {}
    for hook in ("interlocks", "recalculate", "notify_children", "normalize_auto_values", "update_visibility"):
        setattr(shell, hook, lambda *a, **k: None)
    return shell


MAU = next(o for o in FIELDS["sys_type"]["options"] if o.startswith("MAU"))
AHU = next(o for o in FIELDS["sys_type"]["options"] if o.startswith("AHU"))
EXTRA = {"winter_ffu_ratio": "50", "coil_pinch_min_k": "1.5"}

# Open a saved project that carries optional values (previously KeyError).
p = default_project()
p["inputs"].update(sys_type=MAU, **EXTRA)
shell = app()
try:
    shell._load_validated_project(copy.deepcopy(p))
    check("load project with optional keys", True)
except Exception as e:
    check("load project with optional keys", False, f"{type(e).__name__}: {e}")
snap = shell.snapshot()
check("snapshot keeps optional values", all(snap["inputs"].get(k) == v for k, v in EXTRA.items()), snap["inputs"].get("winter_ffu_ratio"))
check("optional values are not form variables", not set(EXTRA) & set(shell.variables))
saved = new_workspace(snap)
check("snapshot saves as workspace", saved["main"]["inputs"]["winter_ffu_ratio"] == "50")

# Restore from workspace/recovery/undo path.
other = app()
other.restore_snapshot(copy.deepcopy(validate_workspace(saved)["main"]))
check("restore keeps optional values", all(other.snapshot()["inputs"].get(k) == v for k, v in EXTRA.items()))
check("restore -> snapshot round trip", other.snapshot()["inputs"] == snap["inputs"])
other.remember_main_undo()
check("undo snapshot keeps optional values", other.undo_project["inputs"].get("winter_ffu_ratio") == "50")

# Inactive invalid drafts survive load and save.
draft = default_project()
draft["inputs"].update(sys_type=AHU, winter_ffu_ratio="bad")
shell = app()
shell._load_validated_project(copy.deepcopy(draft))
check("inactive invalid draft survives load", shell.snapshot()["inputs"]["winter_ffu_ratio"] == "bad")
check("inactive invalid draft saves", new_workspace(shell.snapshot())["main"]["inputs"]["winter_ffu_ratio"] == "bad")

# Rejections and legacy files.
bad = copy.deepcopy(snap)
bad["inputs"]["foo"] = "1"
try:
    app().restore_snapshot(bad)
    check("restore rejects unknown key", False, "accepted")
except (ValueError, ValidationError) as e:
    check("restore rejects unknown key", getattr(e, "field_name", None) == "foo", e)
shell = app()
shell.extra_inputs = {"winter_ffu_ratio": "70"}
shell._load_validated_project(default_project())
check("loading a legacy project clears previous optional values", shell.extra_inputs == {} and set(shell.snapshot()["inputs"]) == set(FIELDS))

failed = [c for c in checks if not c["passed"]]
for c in failed:
    print("FAIL", c["name"], c["detail"])
print(f"desktop data-logic checks (stand-in tkinter, not a GUI test): {len(checks) - len(failed)}/{len(checks)} passed")
(ROOT / "evidence").mkdir(exist_ok=True)
(ROOT / "evidence" / "Optional_Inputs_Desktop_Logic.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
sys.exit(1 if failed else 0)
