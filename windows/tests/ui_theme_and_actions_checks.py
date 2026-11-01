"""Theme contrast and button-action checks that run without a display.

The real Theme.apply runs against a recording stand-in for ttk.Style; option values are
resolved through ttk style inheritance ("Simple.Invalid.TEntry" -> "Invalid.TEntry" ->
"TEntry" -> ".") and checked against WCAG 2.1 contrast (text >= 4.5:1, component
boundaries >= 3:1). This proves the configured colours, not how Windows renders them.
"""

import ast
import json
import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class _Anything:
    def __init__(self, *a, **k):
        pass

    def __call__(self, *a, **k):
        return _Anything()

    def __getattr__(self, name):
        return _Anything()


def _used_names():
    names = set()
    for path in (ROOT / "facility_studio").glob("*.py"):
        names |= set(re.findall(r"\b(?:tk|ttk|tkfont|messagebox|filedialog)\.([A-Za-z_]\w*)", path.read_text(encoding="utf-8")))
    return sorted(names)


_NAMES = _used_names()


class _Stub(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Anything

    def __dir__(self):
        return _NAMES


try:  # use the real toolkit when present; otherwise a stand-in so the logic still runs
    import tkinter  # noqa: F401
except ImportError:
    for name in ("tkinter", "tkinter.ttk", "tkinter.messagebox", "tkinter.filedialog", "tkinter.font",
                 "tkinter.simpledialog", "tkinter.scrolledtext", "tkinter.colorchooser", "_tkinter"):
        sys.modules[name] = _Stub(name)
    sys.modules["tkinter"].ttk = sys.modules["tkinter.ttk"]
    sys.modules["tkinter"].TclError = type("TclError", (Exception,), {})

from facility_studio import industrial_theme  # noqa: E402
from facility_studio.industrial_theme import Theme  # noqa: E402

checks = []


def check(name, ok, detail=""):
    checks.append(dict(name=name, passed=bool(ok), detail=str(detail)[:240]))


def luminance(color):
    color = {"white": "#FFFFFF", "black": "#000000"}.get(color, color).lstrip("#")
    channels = [int(color[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class RecordingStyle:
    def __init__(self, root=None):
        self.conf, self.maps = {}, {}

    def theme_names(self):
        return ("clam", "default")

    def theme_use(self, name=None):
        return "clam"

    def configure(self, name, **options):
        self.conf.setdefault(name, {}).update(options)

    def map(self, name, **options):
        self.maps.setdefault(name, {}).update(options)

    def chain(self, name):
        parts = name.split(".")
        return [".".join(parts[i:]) for i in range(len(parts))] + ["."]

    def option(self, name, key):
        for style in self.chain(name):
            if key in self.conf.get(style, {}):
                return self.conf[style][key]
        return None

    def state(self, name, key, state):
        for style in self.chain(name):
            for states, value in self.maps.get(style, {}).get(key, []):
                if state in str(states).split():
                    return value
        return self.option(name, key)


class FakeTcl:
    """Records the Tk scaling calls; the display scaling variable is never set, so Theme.apply computes it."""

    def eval(self, script):
        return "0"

    def call(self, *args):
        return ""


class FakeRoot:
    tk = FakeTcl()

    def winfo_fpixels(self, value):
        return 96.0

    def configure(self, **k):
        pass


recorded = {}


def make_style(root=None):
    recorded["style"] = RecordingStyle(root)
    return recorded["style"]


industrial_theme.ttk.Style = make_style
industrial_theme.tkfont = types.SimpleNamespace(families=lambda root: ("Microsoft JhengHei UI", "Consolas"))
Theme.apply(FakeRoot())
st = recorded["style"]
BG, CARD, NAV = Theme.BG, Theme.CARD, Theme.NAV

# 1. Input fields are visible on both surfaces, also when focused, invalid or disabled.
for name in ("TEntry", "TCombobox"):
    face, border = st.option(name, "fieldbackground"), st.option(name, "bordercolor")
    width = st.option(name, "borderwidth")
    check(f"{name} has a border", width is not None and width >= 1, width)
    for surface, label in ((BG, "page"), (CARD, "card")):
        check(f"{name} boundary vs {label} >= 3:1", contrast(border, surface) >= 3, round(contrast(border, surface), 2))
    check(f"{name} text vs field >= 4.5:1", contrast(st.option(name, "foreground") or Theme.TEXT, face) >= 4.5)
    focus = st.state(name, "bordercolor", "focus")
    check(f"{name} focus outline vs page >= 3:1", contrast(focus, BG) >= 3, round(contrast(focus, BG), 2))
    check(f"{name} focus outline differs from idle border", focus != border, (focus, border))
    disabled_face = st.state(name, "fieldbackground", "disabled")
    check(f"{name} disabled field is distinguishable from an editable one", disabled_face != face, (disabled_face, face))
    check(f"{name} disabled text stays readable (>= 4.5:1)",
          contrast(st.state(name, "foreground", "disabled"), disabled_face) >= 4.5)
check("readonly combobox keeps the editable white face", st.state("TCombobox", "fieldbackground", "readonly") == st.option("TCombobox", "fieldbackground"))
for name in ("Invalid.TEntry", "Simple.Invalid.TEntry", "Invalid.TCombobox"):
    width, border = st.option(name, "borderwidth"), st.option(name, "bordercolor")
    check(f"{name} shows its red border (width >= 1, >= 3:1 vs page)",
          width is not None and width >= 1 and contrast(border, BG) >= 3, (width, border))

# 2. Buttons have a visible outline and distinct interaction states.
border = st.option("TButton", "bordercolor")
check("TButton has an outline", (st.option("TButton", "borderwidth") or 0) >= 1)
check("TButton outline vs page >= 3:1", contrast(border, BG) >= 3, round(contrast(border, BG), 2))
check("TButton text vs face >= 4.5:1", contrast(Theme.TEXT, st.option("TButton", "background")) >= 4.5)
hover, pressed = st.state("TButton", "background", "active"), st.state("TButton", "background", "pressed")
check("TButton hover and pressed differ from idle", len({hover, pressed, st.option("TButton", "background")}) == 3)
check("TButton keyboard focus is outlined", st.state("TButton", "bordercolor", "focus") == Theme.PRIMARY)
check("primary button text vs face >= 4.5:1", contrast("white", st.option("Primary.TButton", "background")) >= 4.5)

# 3. Secondary text.
check("side-panel hint text vs side panel >= 4.5:1",
      contrast(st.option("Simple.SideHint.TLabel", "foreground"), NAV) >= 4.5,
      round(contrast(st.option("Simple.SideHint.TLabel", "foreground"), NAV), 2))
check("muted text vs page >= 4.5:1", contrast(Theme.MUTED, BG) >= 4.5)

# 4. Reset asks first, only when inputs differ; it is placed apart from the import action.
from facility_studio import simple_desktop  # noqa: E402
from facility_studio.simple_schema import defaults  # noqa: E402


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def page(tool, changes=None):
    shell = simple_desktop.SimplePage.__new__(simple_desktop.SimplePage)
    values = dict(defaults(tool), **(changes or {}))
    shell.tool, shell.variables = tool, {k: Var(v) for k, v in values.items()}
    shell.winfo_toplevel = lambda: None
    shell.reset_calls = 0

    def fake_reset():
        shell.reset_calls += 1
    shell.reset = fake_reset
    return shell


asked = []


def answer(value):
    def ask(title, message, parent=None):
        asked.append((title, message))
        return value
    return ask


tool = next(iter(simple_desktop.TOOLS))
first_key = next(iter(defaults(tool)))
simple_desktop.messagebox.askokcancel = answer(False)
shell = page(tool)
asked.clear()
shell.confirm_reset()
check("reset with default values does not ask and resets", not asked and shell.reset_calls == 1)
shell = page(tool, {first_key: "__edited__"})
asked.clear()
shell.confirm_reset()
check("reset with edited inputs asks; Cancel keeps the inputs", len(asked) == 1 and shell.reset_calls == 0)
simple_desktop.messagebox.askokcancel = answer(True)
shell = page(tool, {first_key: "__edited__"})
shell.confirm_reset()
check("reset with edited inputs; OK resets", shell.reset_calls == 1)

# 5. Fixing a scenario snapshot asks before replacing an existing one.
from facility_studio import workspace_view  # noqa: E402


def workspace(existing):
    win = workspace_view.WorkspaceWindow.__new__(workspace_view.WorkspaceWindow)
    win.win = None
    win.main = types.SimpleNamespace(
        ensure_result=lambda: True, result={"value": "new"}, project_id="p1",
        comparisons=dict(existing), refresh_session_status=lambda: None)
    win.show_comparison = lambda: None
    return win


old = {"A": {"value": "old", "captured_at": "2026-10-30T00:00:00+00:00"}}
workspace_view.messagebox.askokcancel = answer(False)
w = workspace(old)
asked.clear()
w.capture("A")
check("replacing snapshot A asks; Cancel keeps the old snapshot", len(asked) == 1 and w.main.comparisons["A"]["value"] == "old")
workspace_view.messagebox.askokcancel = answer(True)
w = workspace(old)
w.capture("A")
check("replacing snapshot A; OK stores the new one", w.main.comparisons["A"]["value"] == "new")
w = workspace({})
asked.clear()
w.capture("B")
check("first snapshot B is stored without asking", not asked and w.main.comparisons["B"]["value"] == "new")


# 6. Placement: destructive buttons sit apart from the main action and use the confirming handler.
def buttons(path):
    tree = ast.parse((ROOT / "facility_studio" / path).read_text(encoding="utf-8"))
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "pack":
            call = node.func.value
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == "Button":
                kw = {k.arg: k.value for k in call.keywords}
                text = kw.get("text")
                if isinstance(text, ast.Constant):
                    side = {k.arg: k.value for k in node.keywords}.get("side")
                    found[text.value] = dict(side=side.value if isinstance(side, ast.Constant) else None,
                                             command=ast.unparse(kw.get("command")) if kw.get("command") else "")
    return found


simple = buttons("simple_desktop.py")
check("simple tools: 恢復預設 uses the confirming handler", simple.get("恢復預設", {}).get("command") == "self.confirm_reset", simple.get("恢復預設"))
check("simple tools: 恢復預設 sits on the opposite side from 帶入上游結果",
      simple.get("恢復預設", {}).get("side") == "right", simple.get("恢復預設"))
ledger = buttons("session_controller.py")
check("demand summary: adopting is on the left, removing on the right",
      ledger.get("主案採用選取水迴路", {}).get("side") == "left" and ledger.get("移除選取來源的需求", {}).get("side") == "right",
      {k: ledger.get(k) for k in ("主案採用選取水迴路", "移除選取來源的需求")})

failed = [c for c in checks if not c["passed"]]
(ROOT / "evidence").mkdir(exist_ok=True)
(ROOT / "evidence" / "UI_Theme_And_Actions_Checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
for c in failed:
    print("FAIL", c["name"], c["detail"])
print(f"UI theme and action checks (no display; colours and handlers only): {len(checks) - len(failed)}/{len(checks)} passed")
sys.exit(1 if failed else 0)
