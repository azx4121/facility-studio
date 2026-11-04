"""Independent-model and document/source-lock regressions for the reviewed defects.

Run each source tree in a separate process with FACILITY_TEST_PLATFORM. Tests
marked native require a real Tk display and never stand for EXE/App acceptance.
"""
import copy
import json
import os
from pathlib import Path
import sys
import tkinter
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = os.environ.get("FACILITY_TEST_PLATFORM", "windows")
sys.path.insert(0, str(ROOT / PLATFORM))
from facility_studio import design_basis, design_basis_ui, i18n
from facility_studio.ahu_desktop import AHUWindow
from facility_studio.ahu_engine import nm_calculate, nm_draft_inputs
from facility_studio.ahu_schema import NM_DEFAULTS, NM_FIELDS
from facility_studio.engineering_verification import compare_inputs
from facility_studio.schema import DEFAULTS


@pytest.fixture(autouse=True)
def isolated_language(monkeypatch, tmp_path):
    monkeypatch.setenv("FACILITY_STUDIO_PREFERENCES", str(tmp_path / "preferences.json"))
    i18n.set_language("zh-Hant", persist=False)
    yield
    i18n.set_language("zh-Hant", persist=False)


def test_imports_requested_source_platform():
    assert Path(design_basis_ui.__file__).resolve().is_relative_to(ROOT / PLATFORM)


@pytest.mark.parametrize("inactive_flow", ["65000", "abc", ""])
@pytest.mark.parametrize("inactive_basis", NM_FIELDS["flow_basis"]["limit"] + ["invalid draft"])
def test_seasonal_comparison_uses_each_seasons_supply_flow(inactive_flow, inactive_basis):
    import psychrolib
    values = dict(NM_DEFAULTS, target_mode="主案分季需求", summer_flow="18000", winter_flow="15000",
                  summer_sa_t="16", summer_sa_rh="85", winter_sa_t="20", winter_sa_rh="50",
                  flow=inactive_flow, flow_basis=inactive_basis)
    original = copy.deepcopy(values)
    compared = compare_inputs(values)
    engine = nm_calculate(values)
    for balance in compared["reference_balances"]:
        season = balance["season"]
        pressure = float(values["p"]) * 1000
        t, rh = float(values[season + "_sa_t"]), float(values[season + "_sa_rh"])
        w = psychrolib.GetHumRatioFromRelHum(t, rh / 100, pressure)
        expected = float(values[season + "_flow"]) / 3600 / psychrolib.GetMoistAirVolume(t, w, pressure)
        assert balance["psychrolib_mass_kg_s"] == pytest.approx(expected, rel=1e-12)
        # Production normalizes the rounded PsychroLib humidity coefficient.
        # 1e-7 relative allows only that documented molecular-ratio difference.
        assert balance["engine_mass_kg_s"] == pytest.approx(expected, rel=1e-7)
        assert abs(balance["reference_energy_residual_kw"]) < 1e-4
        assert abs(balance["reference_moisture_residual_kg_h"]) < 1e-4
        stages = [row for row in compared["comparison"] if row.get("season") == season and "stage" in row]
        assert len(stages) == 4
        for row in stages:
            assert row["reference_mass_kg_s"] == pytest.approx(expected, rel=1e-12)
            assert row["psychrolib_air_kw"] == pytest.approx(row["engine_air_kw"], rel=1e-7, abs=1e-7)
        assert engine[season]["mass"] == pytest.approx(expected, rel=1e-7)
    assert values == original
    assert compared["reference_balances"][0]["psychrolib_mass_kg_s"] != compared["reference_balances"][1]["psychrolib_mass_kg_s"]


@pytest.mark.parametrize("basis", NM_FIELDS["flow_basis"]["limit"])
def test_independent_comparison_retains_common_flow_basis(basis):
    values = dict(NM_DEFAULTS, flow="7200", flow_basis=basis)
    compared = compare_inputs(values)
    for balance in compared["reference_balances"]:
        assert balance["psychrolib_mass_kg_s"] == pytest.approx(balance["engine_mass_kg_s"], rel=1e-7)
        assert abs(balance["reference_energy_residual_kw"]) < 1e-4
        assert abs(balance["reference_moisture_residual_kg_h"]) < 1e-4


class Widget:
    def __init__(self, value=""):
        self.value = value
        self.options = {}
        self.after = Mock(return_value="job")
        self.after_cancel = Mock()
        self.title = Mock()
        self.show = Mock()

    def get(self, *args):
        return self.value

    def set(self, value):
        self.value = value

    def configure(self, **options):
        self.options.update(options)

    config = configure


@pytest.fixture
def ahu():
    ui = AHUWindow.__new__(AHUWindow)
    ui.vars = {key: Widget(value) for key, value in NM_DEFAULTS.items()}
    ui.vars["linked_main_hash"].set("CURRENT-BOUNDARY")
    ui.suspended = False
    ui.source_project_id = ui.owner_project_id = "synthetic-project"
    ui.ahu_id = "synthetic-ahu"
    ui.main_app = SimpleNamespace(
        project_id="synthetic-project", boundary_hash=lambda: "CURRENT-BOUNDARY",
        refresh_receipts=Mock(), refresh_session_status=Mock(),
        variables={key: Widget(value) for key, value in DEFAULTS.items()},
        snapshot=lambda: {"inputs": dict(DEFAULTS)}, apply_contribution=Mock(return_value=False),
    )
    ui.job = None
    ui.result = nm_calculate(dict(NM_DEFAULTS))
    for key in ("win", "export_button", "status", "banner", "summary", "link_button", "return_button", "link_info"):
        setattr(ui, key, Widget())
    ui.widgets = {}
    ui.clear_output = ui.visibility = ui.set_text = Mock()
    ui.calculate = Mock()
    ui.ensure = lambda: True
    ui.undo_inputs = None
    return ui


def assert_return_blocked(ui, monkeypatch):
    # Recalculation must not unlock a modified source snapshot.
    ui.result = nm_calculate(ui.snapshot())
    ui.refresh_link_status()
    assert ui.return_button.options["state"] == "disabled"
    assert "已過期" in ui.result["link_status"]
    errors = Mock()
    monkeypatch.setattr("facility_studio.ahu_desktop.messagebox.showerror", errors)
    ui.return_utilities()
    errors.assert_called_once()
    assert errors.call_args.args[0] == "來源快照已過期"
    ui.main_app.apply_contribution.assert_not_called()
    assert ui.source_project_id == "synthetic-project"
    assert ui.vars["linked_main_hash"].get() not in ("尚未連動", "CURRENT-BOUNDARY")


BOUNDARY_KEYS = ["target_mode", "p", "summer_t", "summer_rh", "winter_t", "winter_rh",
                 "sa_t", "sa_rh", "flow", "flow_basis", "summer_sa_t", "summer_sa_rh",
                 "winter_sa_t", "winter_sa_rh", "summer_flow", "winter_flow",
                 "c1_in", "c1_out", "c2_in", "c2_out"]


@pytest.mark.parametrize("key", BOUNDARY_KEYS)
@pytest.mark.parametrize("initial_link", ["CURRENT-BOUNDARY", "OLD-BOUNDARY"])
def test_boundary_edits_keep_source_and_block_return(ahu, monkeypatch, key, initial_link):
    ahu.vars["linked_main_hash"].set(initial_link)
    ahu.changed(key)
    assert_return_blocked(ahu, monkeypatch)
    marker = ahu.vars["linked_main_hash"].get()
    ahu.changed(key)
    assert ahu.vars["linked_main_hash"].get() == marker
    assert_return_blocked(ahu, monkeypatch)


@pytest.mark.parametrize("action,args", [("target_preset", (85,)), ("coil_preset", (False,)),
                                        ("coil_preset", (True,)), ("import_climate", ())])
def test_presets_and_climate_import_do_not_silently_make_independent(ahu, monkeypatch, action, args):
    getattr(ahu, action)(*args)
    assert_return_blocked(ahu, monkeypatch)


def test_modified_link_survives_document_roundtrip(ahu, monkeypatch, tmp_path):
    ahu.changed("c2_in")
    from facility_studio.schema import default_project
    from facility_studio.workspace_store import new_workspace, read_workspace
    workspace = new_workspace(default_project())
    workspace.update(project_id="synthetic-project", ahus=[ahu.document()])
    path = tmp_path / "edited-ahu-workspace.json"
    path.write_text(json.dumps(workspace), encoding="utf-8")
    doc = read_workspace(path)["ahus"][0]
    assert doc["source_project_id"] == "synthetic-project"
    loaded = nm_draft_inputs(doc["inputs"])
    ahu.vars = {key: Widget(value) for key, value in loaded.items()}
    ahu.source_project_id = doc["source_project_id"]
    assert_return_blocked(ahu, monkeypatch)


def test_rating_edits_keep_current_source_link(ahu):
    ahu.vars["h1_kw"].set("500")
    ahu.changed("h1_kw")
    assert ahu.vars["linked_main_hash"].get() == "CURRENT-BOUNDARY"
    assert ahu.source_project_id == "synthetic-project"


def test_unlinked_design_remains_independent_on_boundary_edit(ahu):
    ahu.vars["linked_main_hash"].set("尚未連動")
    ahu.source_project_id = ""
    ahu.changed("c2_in")
    assert ahu.vars["linked_main_hash"].get() == "尚未連動"
    assert ahu.source_project_id == ""


def test_independence_requires_explicit_confirmation_and_supports_undo(ahu, monkeypatch):
    ahu.changed("c2_in")
    stale = ahu.vars["linked_main_hash"].get()
    confirm = Mock(return_value=False)
    monkeypatch.setattr("facility_studio.ahu_desktop.messagebox.askokcancel", confirm)
    ahu.make_independent()
    assert ahu.vars["linked_main_hash"].get() == stale
    assert ahu.source_project_id == "synthetic-project"
    confirm.return_value = True
    ahu.make_independent()
    assert ahu.vars["linked_main_hash"].get() == "尚未連動"
    assert ahu.source_project_id == ""
    ahu.result = nm_calculate(ahu.snapshot())
    ahu.refresh_link_status()
    assert ahu.return_button.options["state"] == "normal"
    ahu.return_utilities()
    ahu.main_app.apply_contribution.assert_called_once()
    ahu.main_app.apply_contribution.reset_mock()
    ahu.undo_changes()
    assert ahu.vars["linked_main_hash"].get() == stale
    assert_return_blocked(ahu, monkeypatch)


def test_relink_explicitly_replaces_modified_marker(ahu, monkeypatch):
    from facility_studio import ahu_desktop
    updates = dict(target_mode="主案分季需求", summer_flow="18000", winter_flow="15000", linked_main_hash="CURRENT-BOUNDARY")
    ahu.changed("c2_in")
    ahu.main_app.ensure_result = lambda: True
    ahu.main_app.result = {}
    monkeypatch.setattr(ahu_desktop, "ahu_requirement_updates", lambda result: dict(updates))
    monkeypatch.setattr("tkinter.simpledialog.askfloat", lambda *a, **k: 50.)
    monkeypatch.setattr(ahu_desktop.messagebox, "askokcancel", lambda *a, **k: True)
    def apply(values):
        for key, value in values.items():
            ahu.vars[key].set(value)
    ahu.apply = apply
    ahu.link_requirements()
    assert ahu.vars["linked_main_hash"].get() == "CURRENT-BOUNDARY"
    assert ahu.source_project_id == "synthetic-project"
    assert float(ahu.vars["summer_flow"].get()) == 9000
    ahu.result = nm_calculate(ahu.snapshot())
    ahu.refresh_link_status()
    assert ahu.return_button.options["state"] == "normal"


STANDARD_TEXT = "ASHRAE 90.1｜2019｜6.5｜廠務空調｜業主規範"


def test_editable_standard_uses_native_text_not_report_translation():
    assert design_basis_ui.EditableText is tkinter.Text
    assert design_basis_ui.EditableText.insert is tkinter.Text.insert
    assert not hasattr(design_basis_ui.EditableText, "refresh_language")
    # Execute the actual native Text insertion method against a Tcl call sink.
    # This proves no display translation is applied, without claiming a window.
    widget = design_basis_ui.EditableText.__new__(design_basis_ui.EditableText)
    call = Mock()
    widget.tk, widget._w = SimpleNamespace(call=call), "standards"
    i18n.set_language("en", persist=False)
    widget.insert("1.0", STANDARD_TEXT)
    call.assert_called_once_with(("standards", "insert", "1.0", STANDARD_TEXT))


def test_standards_parser_and_revision_preserve_source_text_in_english(tmp_path):
    i18n.set_language("en", persist=False)
    ui = design_basis_ui.DesignReviewWindow.__new__(design_basis_ui.DesignReviewWindow)
    ui.data = design_basis.new_dossier()
    ui.variables = {key: Widget(value) for key, value in ui.data["basis"].items()}
    ui.standards, ui.exclusion, ui.current = Widget(STANDARD_TEXT), Widget(), "basis"
    ui.sync()
    before = copy.deepcopy(ui.data["standards"])
    path = design_basis.save_revision(ui.data, tmp_path)
    after = design_basis.load_revision(path)
    assert after["standards"] == before
    assert "｜".join(after["standards"][0].values()) == STANDARD_TEXT
    for language in ("zh-Hant", "en", "zh-Hant", "en"):
        i18n.set_language(language, persist=False)
        ui.sync()
        assert ui.data["standards"] == before


def test_native_english_reopen_switch_and_save_preserve_standards(tmp_path):
    try:
        root = tkinter.Tk()
    except tkinter.TclError as error:
        if os.environ.get("FACILITY_REQUIRE_DISPLAY") == "1":
            raise
        pytest.skip("Native Tk display unavailable: " + str(error))
    try:
        root.withdraw()
        i18n.set_language("en", persist=False)
        data = design_basis.new_dossier()
        data["standards"] = [dict(zip(("name", "edition", "clause", "scope", "source"), STANDARD_TEXT.split("｜")))]
        ui = design_basis_ui.DesignReviewWindow(root)
        ui.install(data, tmp_path)
        root.update()
        assert type(ui.standards) is tkinter.Text
        assert ui.standards.get("1.0", "end-1c") == STANDARD_TEXT
        for language in ("zh-Hant", "en", "zh-Hant", "en"):
            i18n.set_language(language, persist=False)
            root.update()
            assert ui.standards.get("1.0", "end-1c") == STANDARD_TEXT
            assert ui.win.title() == i18n.translate("Facility Studio｜設計依據與交付審查")
            assert not ui.dirty
        # Actual user typing, then another switch, must preserve the draft too.
        ui.standards.insert("end-1c", "-中文原文")
        root.update()
        i18n.set_language("zh-Hant", persist=False)
        root.update()
        assert ui.standards.get("1.0", "end-1c") == STANDARD_TEXT + "-中文原文"
        assert ui.dirty
        saved = ui.save()
        reloaded = design_basis.load_revision(saved)
        assert reloaded["standards"][0]["source"] == "業主規範-中文原文"
        ui.install(reloaded, tmp_path)
        root.update()
        assert ui.standards.get("1.0", "end-1c") == STANDARD_TEXT + "-中文原文"
        assert not ui.dirty
    finally:
        root.destroy()


def test_native_ahu_edit_return_relink_and_independence(monkeypatch, tmp_path):
    from facility_studio.desktop import DesktopApp
    from facility_studio.schema import FIELDS
    from facility_studio import ahu_desktop
    try:
        root = tkinter.Tk()
    except tkinter.TclError as error:
        if os.environ.get("FACILITY_REQUIRE_DISPLAY") == "1":
            raise
        pytest.skip("Native Tk display unavailable: " + str(error))
    try:
        root.withdraw()
        main = DesktopApp(root)
        main.variables["sys_type"].set(FIELDS["sys_type"]["options"][0])
        main.recalculate()
        ui = AHUWindow(root, main)
        monkeypatch.setattr("tkinter.simpledialog.askfloat", lambda *a, **k: 100.)
        monkeypatch.setattr(ahu_desktop.messagebox, "askokcancel", lambda *a, **k: True)
        ui.link_requirements()
        root.update()
        assert ui.vars["linked_main_hash"].get() == main.boundary_hash()
        assert ui.source_project_id == main.project_id
        assert ui.return_button.instate(["!disabled"])
        ui.vars["c2_in"].set("6")
        assert ui.result is None
        ui.calculate()
        root.update()
        assert ui.return_button.instate(["disabled"])
        errors, apply = Mock(), Mock(return_value=False)
        monkeypatch.setattr(ahu_desktop.messagebox, "showerror", errors)
        monkeypatch.setattr(main, "apply_contribution", apply)
        ui.return_utilities()
        errors.assert_called_once()
        apply.assert_not_called()
        monkeypatch.setattr(ahu_desktop.messagebox, "askokcancel", lambda *a, **k: False)
        ui.make_independent()
        assert ui.source_project_id == main.project_id
        assert ui.return_button.instate(["disabled"])
        monkeypatch.setattr(ahu_desktop.messagebox, "askokcancel", lambda *a, **k: True)
        ui.make_independent()
        assert ui.source_project_id == "" and ui.vars["linked_main_hash"].get() == "尚未連動"
        assert ui.return_button.instate(["!disabled"])
        ui.undo_changes()
        assert ui.source_project_id == main.project_id
        assert ui.return_button.instate(["disabled"])
        ui.link_requirements()
        assert ui.vars["linked_main_hash"].get() == main.boundary_hash()
        assert ui.return_button.instate(["!disabled"])
        apply.assert_not_called()
        ui.close(force=True)
    finally:
        root.destroy()


@pytest.mark.parametrize("text", [
    "規範每行一筆，以 ｜ 分隔：名稱｜版次｜條號｜適用範圍｜來源網址或文件編號",
    "每筆規範須填五個欄位，使用全形 ｜ 分隔",
])
def test_english_standard_instructions_keep_full_width_separator(text):
    rendered = i18n.translate(text, "en")
    assert "｜" in rendered
    assert "|" not in rendered
