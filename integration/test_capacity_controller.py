"""Real controller methods with display-only doubles, NOT native GUI acceptance."""
import copy
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / os.environ.get("FACILITY_TEST_PLATFORM", "windows")))
from facility_studio.capacity_planning_ui import CapacityPlanningWindow, RowDialog
from facility_studio import capacity_planning as m, capacity_planning_ui as ui
from facility_studio.design_workflow import capacity_source_binding
from facility_studio.session_controller import SessionController
from facility_studio.utils import project_hash
from test_capacity_planning import plan, row, ledger_workspace


class Var:
    def __init__(self, value=""):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


class Text:
    def __init__(self, text=""):
        self.text = text
    def configure(self, **kwargs):
        pass
    def delete(self, *args):
        self.text = ""
    def insert(self, index, value):
        self.text = str(value)
    def get(self, *args):
        return self.text


class Tree:
    def __init__(self):
        self.rows, self.selected = {}, []
    def get_children(self):
        return list(self.rows)
    def delete(self, *args):
        for key in args:
            self.rows.pop(key)
    def insert(self, *args, iid, values):
        self.rows[iid] = values
    def selection(self):
        return self.selected
    def selection_set(self, values):
        self.selected = values
    def exists(self, key):
        return key in self.rows


def controller(p=None):
    obj = CapacityPlanningWindow.__new__(CapacityPlanningWindow)
    workspace = ledger_workspace()
    obj.main = SimpleNamespace(children=[obj], session_snapshot=lambda: copy.deepcopy(workspace))
    obj.variables = {key: Var() for key in ("name", "scope", "additional_margin_pct", "margin_reason")}
    obj.confirmed, obj.status, obj.alt = Var(), Var(), Var()
    obj.output, obj.alt_combo = Text(), Text()
    obj.trees = {k: Tree() for k in ("demand", "capacity")}
    obj.win = SimpleNamespace(destroy=lambda: setattr(obj, "destroyed", True), winfo_exists=lambda: True)
    obj.destroyed = False
    obj.install(p or plan())
    return obj, workspace


def test_recalculate_save_export_and_source_stale(tmp_path):
    c, workspace = controller()
    original = copy.deepcopy(workspace)
    path = c.save(tmp_path / "plan.json")
    assert m.read_plan(path) == c.plan
    assert workspace == original
    c.plan["binding"] = capacity_source_binding(workspace)
    assert not c.refresh()["stale"]
    workspace["main"]["inputs"]["e_up_eq"] = "999"
    c.on_main_changed()
    assert "重新核對" in c.status.get()
    target = c.export(tmp_path / "report.txt")
    assert "來源過期或未核對" in target.read_text()
    assert "初篩容量足夠" not in target.read_text()


def test_invalid_new_input_clears_old_output_and_cannot_overwrite_export(tmp_path):
    c, _ = controller()
    assert "初篩容量足夠" in c.output.text
    c.variables["additional_margin_pct"].set("not numeric")
    output = tmp_path / "report.txt"
    output.write_text("previous artifact")
    with pytest.raises(ValueError):
        c.export(output)
    assert "初篩容量足夠" not in c.output.text
    assert c.result is None and output.read_text() == "previous artifact"


def test_same_id_update_and_duplicate_asset_never_show_old_result():
    c, _ = controller()
    c.commit_row("demand", "current", row("demand", "current", value=120))
    assert len(c.plan["demands"]) == 1
    assert c.result["alternatives"][0]["groups"][0]["cases"][0]["design_demand"] == 120
    duplicate = row("demand", "another", value=120)
    duplicate["asset_id"] = "current"
    with pytest.raises(ValueError):
        c.commit_row("demand", "another", duplicate)
    assert c.result is None and "初篩容量足夠" not in c.output.text


def test_cancel_close_new_import_preserves_unsaved_work(monkeypatch):
    c, _ = controller()
    c.variables["name"].set("unsaved")
    monkeypatch.setattr(ui.messagebox, "askyesno", lambda *args, **kwargs: False)
    assert c.close() is False and not c.destroyed
    c.new()
    assert c.plan["name"] == "unsaved"
    c.import_ledger()
    assert c.plan["name"] == "unsaved"
    assert not c.project_bound  # main-project switch retains independent draft
    monkeypatch.setattr(ui.messagebox, "askyesno", lambda *args, **kwargs: True)
    assert c.close() and c.destroyed and c not in c.main.children


def test_main_close_respects_capacity_draft_refusal():
    main = SimpleNamespace(children=[SimpleNamespace(independent_capacity_plan=True, may_close=lambda: False)])
    SessionController.close_workspace(main)  # returns before touching/destroying parent


def test_alternative_uses_explicit_selected_ids_and_preserves_data(monkeypatch):
    c, _ = controller()
    c.trees["demand"].selection_set(["current"])
    c.trees["capacity"].selection_set(["supply"])
    monkeypatch.setattr(ui.simpledialog, "askstring", lambda *a, **k: "Option A")
    c.add_alternative()
    assert c.plan["alternatives"][0]["demand_ids"] == ["current"]
    assert c.plan["alternatives"][0]["capacity_ids"] == ["supply"]
    assert len(c.result["alternatives"]) == 1


def test_manual_edit_of_source_records_new_provenance_requirement():
    c, _ = controller()
    c.plan["demands"][0]["source"]["fingerprint"] = "source-original-hash"
    changed = copy.deepcopy(c.plan["demands"][0])
    changed["values"]["summer"] = 110
    c.commit_row("demand", "current", changed)
    assert any("人工修改" in x for x in c.plan["demands"][0]["pending"])
    assert c.result["alternatives"][0]["groups"][0]["normal_status"] == "待資料／待覆核"


def test_row_dialog_unknown_and_case_name_collision(monkeypatch):
    r = row("demand", "source")
    r["values"] = {"name": 100}
    d = RowDialog.__new__(RowDialog)
    d.row, d.kind = r, "demand"
    d.variables = {("top", "name"): Var("user-supplied name"), ("values", "name"): Var("")}
    d.pending, d.notes = Text(), Text("literal 中文 user text")
    result = []
    d.commit = lambda kind, old, result_row: result.append(result_row)
    d.win = SimpleNamespace(destroy=lambda: None)
    d.save()
    assert result[0]["name"] == "user-supplied name"
    assert result[0]["values"]["name"] is None
    assert result[0]["notes"] == ["literal 中文 user text"]


def test_actual_ahu_changed_receipts_path_clears_stale_capacity_preview():
    from facility_studio.ahu_desktop import AHUWindow
    c, workspace = controller()
    c.plan["binding"] = capacity_source_binding(workspace)
    c.refresh()
    assert "初篩容量足夠" in c.output.text
    c.main.transfer_receipts = []
    c.main.result = None
    c.main.refresh_receipts = lambda: SessionController.refresh_receipts(c.main)
    c.main.refresh_session_status = lambda: None
    widget = SimpleNamespace(config=lambda **kw: None, configure=lambda **kw: None, show=lambda *a: None)
    ahu = SimpleNamespace(suspended=False, job=None, result=None, export_button=widget,
                          status=widget, banner=widget, widgets={}, summary=widget,
                          clear_output=lambda: None, visibility=lambda: None, calculate=lambda: None,
                          win=SimpleNamespace(after=lambda *a: "scheduled"), main_app=c.main)
    workspace["ahus"].append(dict(id="changed-ahu", inputs={"load": "changed"}))
    AHUWindow.changed(ahu, "fan_unit_kw")
    assert c.result is None and "初篩容量足夠" not in c.output.text
    assert c.refresh()["stale"]


def test_export_rechecks_sources_after_modal_dialog(monkeypatch, tmp_path):
    c, workspace = controller()
    c.plan["binding"] = capacity_source_binding(workspace)
    c.refresh()
    target = tmp_path / "race-report.txt"
    def choose(**kwargs):
        workspace["main"]["inputs"]["e_up_eq"] = "999"
        c.on_main_changed()
        return str(target)
    monkeypatch.setattr(ui.filedialog, "asksaveasfilename", choose)
    c.export()
    assert "來源過期或未核對" in target.read_text()
    assert "初篩容量足夠" not in target.read_text()


def test_save_rechecks_form_after_modal_dialog(monkeypatch, tmp_path):
    c, _ = controller()
    target = tmp_path / "latest-plan.json"
    def choose(**kwargs):
        c.variables["additional_margin_pct"].set("15")
        c.variables["margin_reason"].set("Latest change during dialog")
        return str(target)
    monkeypatch.setattr(ui.filedialog, "asksaveasfilename", choose)
    c.save()
    assert m.read_plan(target)["additional_margin_pct"] == 15


def test_display_tree_preserves_user_owned_identifiers_and_names():
    from facility_studio.i18n import translate
    p = plan()
    p["demands"][0].update(id="電力配線", name="計畫名稱", boundary="供水")
    c, _ = controller(p)
    values = c.trees["demand"].rows["電力配線"]
    assert [translate(v, "en") for v in (values[0], values[1], values[4])] == ["電力配線", "計畫名稱", "供水"]


def test_row_dialog_records_boolean_completeness_separately():
    d = RowDialog.__new__(RowDialog)
    d.row, d.kind = row("demand", "source"), "demand"
    d.variables = {("top", "demand_complete"): Var(False)}
    d.pending, d.notes = Text(), Text()
    results = []
    d.commit = lambda kind, old, result: results.append(result)
    d.win = SimpleNamespace(destroy=lambda: None)
    d.save()
    assert results[0]["demand_complete"] is False


def test_open_rechecks_unsaved_changes_after_modal_file_dialog(monkeypatch, tmp_path):
    c, _ = controller()
    replacement = plan()
    replacement["name"] = "Replacement plan"
    target = tmp_path / "replacement.json"
    target.write_text(json.dumps(replacement), encoding="utf-8")
    def choose(**kwargs):
        c.variables["name"].set("New unsaved draft during dialog")
        c.changed()
        return str(target)
    monkeypatch.setattr(ui.filedialog, "askopenfilename", choose)
    monkeypatch.setattr(ui.messagebox, "askyesno", lambda *a, **k: False)
    c.open()
    assert c.plan["name"] == "New unsaved draft during dialog"
    assert c.result is None
    assert c.plan["name"] != replacement["name"]


def test_visible_edit_invalidates_cached_result_immediately():
    c, _ = controller()
    assert c.result is not None
    c.variables["scope"].set("Changed scope")
    c.changed()
    assert c.result is None
    assert "初篩容量足夠" not in c.output.text


def test_plan_confirmation_is_invalidated_by_changed_basis_and_rows():
    c, _ = controller()
    assert c.confirmed.get() is True
    c.basis_changed("name")
    assert c.confirmed.get() is True
    for field in ("scope", "additional_margin_pct", "margin_reason"):
        c.confirmed.set(True)
        c.basis_changed(field)
        assert c.confirmed.get() is False
    c.confirmed.set(True)
    c.commit_row("demand", "current", row("demand", "current", value=120))
    assert c.plan["scope_confirmed"] is False
    assert c.result["alternatives"][0]["groups"][0]["normal_status"] == "待資料／待覆核"


def test_plan_confirmation_is_invalidated_by_alternatives_and_removal(monkeypatch):
    c, _ = controller()
    c.trees["demand"].selection_set(["current"])
    c.trees["capacity"].selection_set(["supply"])
    monkeypatch.setattr(ui.simpledialog, "askstring", lambda *a, **k: "Option A")
    monkeypatch.setattr(ui.messagebox, "askyesno", lambda *a, **k: True)
    c.add_alternative()
    assert c.plan["scope_confirmed"] is False
    c.confirmed.set(True)
    c.alt.set(c.plan["alternatives"][0]["id"])
    c.remove_alternative()
    assert c.plan["scope_confirmed"] is False
    c.confirmed.set(True)
    c.trees["demand"].selection_set(["current"])
    c.remove("demand")
    assert c.plan["scope_confirmed"] is False


def test_integer_margin_roundtrip_does_not_create_false_unsaved_edit(monkeypatch):
    p = plan()
    p.update(additional_margin_pct=10, margin_reason="Synthetic explicit margin")
    c, _ = controller(p)
    def unexpected_prompt(*args, **kwargs):
        raise AssertionError("Unchanged loaded plan should not prompt to discard")
    monkeypatch.setattr(ui.messagebox, "askyesno", unexpected_prompt)
    assert c.may_close()
