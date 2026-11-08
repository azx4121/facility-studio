"""Initial Windows dialog bounds; headless checks are not native GUI evidence.

Execute the unchanged production sizing statements with recording windows. The
native small-screen suite must still open and dismiss the actual dialogs without
moving them, because a size calculation cannot establish on-screen visibility.
"""
import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


SOURCE = Path(__file__).resolve().parents[1] / "windows" / "facility_studio"
SPEC = importlib.util.spec_from_file_location("dialog_window_geometry", SOURCE / "window_geometry.py")
geometry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(geometry)


class Window:
    def __init__(self, screen=(1920, 1080), scale=None):
        self.screen = screen
        self.geometry_calls = []
        self.minimum = None
        if scale is not None:
            self._facility_main_window_scale = scale

    def winfo_screenwidth(self):
        return self.screen[0]

    def winfo_screenheight(self):
        return self.screen[1]

    def configure(self, **kwargs):
        pass

    def title(self, value):
        pass

    def geometry(self, value):
        self.geometry_calls.append(value)

    def minsize(self, width, height):
        self.minimum = width, height


def production_body(dialog):
    filename = "feed_review_preview.py" if dialog == "review" else "fusion_settings.py"
    tree = ast.parse((SOURCE / filename).read_text(encoding="utf-8"))
    if dialog == "review":
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == "VerificationWindow")
        method = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                      and node.name == "__init__")
        return method.body
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name == "open_settings").body


def sizing_code(dialog):
    body = production_body(dialog)
    if dialog == "review":
        # Retain the actual embedded guard, rather than copying its condition.
        nodes = [next(node for node in body if isinstance(node, ast.If)
                      and ast.unparse(node.test) == "not self.embedded")]
    else:
        start = next(i for i, node in enumerate(body)
                     if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                     and ast.unparse(node.value.func) == "win.title")
        end = next(i for i, node in enumerate(body)
                   if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                   and ast.unparse(node.value.func) == "win.minsize")
        nodes = body[start:end + 1]
    return compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec")


def initialize(dialog, parent, win, embedded=False):
    context = {
        "parent": parent, "app": SimpleNamespace(root=parent), "win": win,
        "self": SimpleNamespace(win=win, embedded=embedded), "BUILD": "test",
        "client_size_limit": geometry.client_size_limit,
    }
    exec(sizing_code(dialog), context)


@pytest.mark.parametrize("dialog,desired,minimum", [
    ("review", (1120, 820), (720, 520)),
    ("settings", (840, 720), (720, 500)),
])
@pytest.mark.parametrize("screen,work_area,scale", [
    ((1024, 768), (1024, 728), 1.0),  # Actual Windows taskbar regression.
    ((1024, 768), (1024, 728), 1.5),
    ((3840, 2160), (1024, 728), 1.0),  # Parent on smaller second monitor.
    ((800, 600), (800, 560), 2.0),  # Minima must not undo the bound.
    ((1920, 1080), (1920, 1040), 1.0),  # Preserve original roomy size.
    ((1024, 768), None, None),  # Existing fallback, including unset scale.
])
def test_fresh_dialog_size_and_minimum_use_parent_work_area(
        monkeypatch, dialog, desired, minimum, screen, work_area, scale):
    parent, win = Window(screen, scale), Window()
    queried = []

    def current_work_area(root):
        queried.append(root)
        return work_area

    monkeypatch.setattr(geometry, "_windows_work_area", current_work_area)
    initialize(dialog, parent, win)
    area, factor = work_area or screen, scale if scale is not None else 1.0
    limit = (max(1, area[0] - round(60 * factor)),
             max(1, area[1] - round(100 * factor)))
    expected = tuple(min(value, bound) for value, bound in zip(desired, limit))
    assert win.geometry_calls == [f"{expected[0]}x{expected[1]}"]
    assert win.minimum == tuple(min(value, bound) for value, bound in zip(minimum, limit))
    assert all(value <= bound for value, bound in zip(win.minimum, expected))
    assert queried == [parent]
    assert parent.geometry_calls == [] and parent.minimum is None
    # Width/height only: no relocation or normalization of a user-owned window.
    assert "+" not in win.geometry_calls[0] and "-" not in win.geometry_calls[0]


def test_embedded_review_does_not_apply_dialog_geometry(monkeypatch):
    parent, host = Window(), Window()
    monkeypatch.setattr(geometry, "_windows_work_area", lambda root: pytest.fail(
        "Embedded review must not query or resize the containing window"))
    initialize("review", parent, host, embedded=True)
    assert host.geometry_calls == [] and host.minimum is None
    assert parent.geometry_calls == [] and parent.minimum is None


@pytest.mark.parametrize("dialog,notebook", [("review", "self.nb"), ("settings", "notebook")])
def test_dialog_footer_reserves_space_before_the_expanding_notebook(dialog, notebook):
    body = production_body(dialog)
    footer_pack = next(node for statement in body for node in ast.walk(statement)
                       if isinstance(node, ast.Call) and ast.unparse(node.func) == "footer.pack")
    options = {keyword.arg: keyword.value for keyword in footer_pack.keywords}
    assert ast.literal_eval(options["side"]) == "bottom"
    assert ast.unparse(options["before"]) == notebook
    assert ast.literal_eval(options["fill"]) == "x"
