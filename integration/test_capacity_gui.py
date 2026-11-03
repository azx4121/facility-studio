"""Actual Tk tests. Skipped only when this executor has no usable display."""
import copy
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / os.environ.get("FACILITY_TEST_PLATFORM", "windows")))
from facility_studio.localized_tk import tk
from facility_studio.capacity_planning_ui import CapacityPlanningWindow
from test_capacity_planning import plan, row, ledger_workspace


@pytest.fixture
def app():
    try:
        root = tk.Tk()
    except tk.TclError as error:
        if os.environ.get("FACILITY_REQUIRE_DISPLAY") == "1":
            raise
        pytest.skip("Native Tk display unavailable: " + str(error))
    root.withdraw()
    workspace = ledger_workspace()
    main = SimpleNamespace(root=root, children=[], session_snapshot=lambda: copy.deepcopy(workspace))
    window = CapacityPlanningWindow(root, main)
    try:
        yield window, workspace
    finally:
        root.destroy()


def test_real_widgets_save_export_edit_cancel_and_stale(app, tmp_path):
    window, workspace = app
    window.install(plan())
    window.win.update()
    assert "初篩容量足夠" in window.output.get("1.0", "end")
    window.trees["demand"].selection_set("current")
    dialog = window.edit("demand")
    dialog.variables["values", "summer"].set("160")
    dialog.save()
    window.win.update()
    assert window.plan["demands"][0]["values"]["summer"] == 160
    before = copy.deepcopy(window.plan)
    dialog = window.edit("demand")
    dialog.variables["values", "summer"].set("999")
    dialog.win.destroy()  # cancel leaves original record unchanged
    assert window.plan == before
    path = window.save(tmp_path / "plan.json")
    assert path.is_file()
    assert window.export(tmp_path / "report.txt").is_file()
    window.import_ledger()
    workspace["main"]["inputs"]["project_name"] = "different project revision"
    assert window.refresh()["stale"]


def test_real_window_small_geometry_and_english_editable_notes(app):
    from facility_studio import i18n
    window, _ = app
    window.win.geometry("960x700")
    window.win.update()
    def walk(parent):
        for child in parent.winfo_children():
            yield child
            yield from walk(child)
    for widget in walk(window.win):
        if widget.winfo_class() == "TButton" and widget.winfo_ismapped():
            assert widget.winfo_rootx() + widget.winfo_width() <= window.win.winfo_rootx() + window.win.winfo_width()
    window.install(plan())
    window.trees["demand"].selection_set("current")
    i18n.set_language("en", persist=False)
    try:
        dialog = window.edit("demand")
        assert "Capacity" in window.win.title()
        assert dialog.win.title() == "Edit demand"
        assert dialog.variables["top", "demand_complete"].get() is True
        dialog.notes.insert("1.0", "原始使用者中文：不可改寫")
        i18n.set_language("zh-Hant", persist=False)
        assert dialog.notes.get("1.0", "end-1c") == "原始使用者中文：不可改寫"
        dialog.win.destroy()
    finally:
        i18n.set_language("zh-Hant", persist=False)
