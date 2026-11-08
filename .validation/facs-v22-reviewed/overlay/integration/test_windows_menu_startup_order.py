"""Headless contract: both Windows views attach menus before layout can map.

Execute the real constructor statements between geometry initialization and the
first layout/icon operation, without importing optional engineering/UI modules.
This guards ordering, not native Windows geometry or a frozen executable.
"""
import ast
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("filename,owner,method", [
    ("simple_desktop.py", "SimpleToolsApp", "__init__"),
    ("desktop.py", "DesktopApp", "_build_window"),
])
def test_native_menu_is_attached_before_first_layout_operation(monkeypatch, filename, owner, method):
    tree = ast.parse((ROOT / "windows/facility_studio" / filename).read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == owner)
    function = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == method)
    first = next(index for index, node in enumerate(function.body)
                 if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                 and isinstance(node.value.func, ast.Name)
                 and node.value.func.id == "initialize_main_window")
    # Stop at the first layout/icon statement. These can flush Tk's idle work
    # (icon hooks/sidebar measurements) and therefore map the native frame.
    last = next(index for index in range(first + 1, len(function.body))
                if isinstance(function.body[index], ast.Expr)
                and isinstance(function.body[index].value, ast.Call)
                and ((isinstance(function.body[index].value.func, ast.Name)
                      and function.body[index].value.func.id == "app_icon")
                     or (isinstance(function.body[index].value.func, ast.Attribute)
                         and function.body[index].value.func.attr == "columnconfigure")))
    events = []
    root = object()
    module = ModuleType("startup_order_fixture.sandbox_ui")
    module.install_menus = lambda candidate: events.append(("menus", candidate))
    package = ModuleType("startup_order_fixture")
    package.__path__ = []
    monkeypatch.setitem(__import__("sys").modules, package.__name__, package)
    monkeypatch.setitem(__import__("sys").modules, module.__name__, module)
    selected = ast.Module(body=function.body[first:last], type_ignores=[])
    exec(compile(selected, filename, "exec"), {
        "__package__": package.__name__, "root": root, "Theme": SimpleNamespace(scale=1),
        "initialize_main_window": lambda candidate, scale: events.append(("geometry", candidate)),
    })
    assert events == [("geometry", root), ("menus", root)]
    # No second late/deferred install can alter non-client geometry after Map.
    installs = [node for node in ast.walk(function) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == "install_menus"]
    assert len(installs) == 1


def test_desktop_constructor_does_not_defer_another_menu_install():
    tree = ast.parse((ROOT / "windows/facility_studio/desktop.py").read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DesktopApp")
    function = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "__init__")
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id == "install_menus" for node in ast.walk(function))


def test_workbench_title_is_set_after_early_menu_construction():
    tree = ast.parse((ROOT / "windows/facility_studio/desktop.py").read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DesktopApp")
    function = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "__init__")
    start = next(index for index, node in enumerate(function.body)
                 if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                 and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "_build_window")
    events = []
    root = SimpleNamespace(title=lambda value: events.append(("title", value)))
    owner = SimpleNamespace(_build_window=lambda candidate: events.append(("build", candidate)))
    selected = ast.Module(body=function.body[start:start+2], type_ignores=[])
    exec(compile(selected, "desktop.py", "exec"), {"self": owner, "root": root, "BUILD_VERSION": "test"})
    assert events == [("build", root), ("title", "廠務工程工作台 Vtest")]
