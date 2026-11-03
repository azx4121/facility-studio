"""User journeys for invalid/stale results, engineering warnings and mode interlocks."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ("windows" if sys.platform == "win32" else "macos")))
from facility_studio.engine import calculate
from facility_studio.industrial_theme import Theme
from facility_studio.localized_tk import tk
from facility_studio.schema import FIELDS, default_project
from facility_studio.simple_engines import calculate_tool
from facility_studio.simple_reports import tool_report
from facility_studio.simple_schema import defaults


@pytest.fixture
def simple(tmp_path, monkeypatch):
    from facility_studio.simple_desktop import SimpleToolsApp
    monkeypatch.setenv("FACILITY_STUDIO_PREFERENCES", str(tmp_path / "preferences.json"))
    root = tk.Tk()
    root.withdraw()
    app = SimpleToolsApp(root)
    try:
        yield root, app
    finally:
        root.destroy()


TOOL_FIELDS = [("electrical", "power"), ("duct", "flow"), ("gas", "flow"),
               ("lighting", "area"), ("water", "flow"), ("air", "temperature"),
               ("units", "value"), ("cleanroom", "room_rh"), ("heat_loads", "area"),
               ("pumps", "flow"), ("liquid", "flow"), ("vacuum", "vacuum_p")]


@pytest.mark.parametrize("tool,key", TOOL_FIELDS)
@pytest.mark.parametrize("invalid", ["nan", "inf", ""])
def test_all_simple_tools_reject_invalid_edits_and_stale_exports(simple, tmp_path, tool, key, invalid):
    root, app = simple
    app.show_tool(tool)
    page = app.active_page()
    page.calculate()
    assert page.result is not None, tool
    page.variables[key].set(invalid)
    assert page.result is None
    assert app.export_button.instate(["disabled"])
    root.clipboard_clear()
    root.clipboard_append("synthetic clipboard sentinel")
    assert not app.copy_result()
    assert root.clipboard_get() == "synthetic clipboard sentinel"
    for suffix in ("txt", "html"):
        target = tmp_path / ("must-not-export." + suffix)
        assert not app.export_result(target)
        assert not target.exists()
    assert page.banner.label.cget("background") == Theme.TONES["danger"][1]
    page.variables[key].set(defaults(tool)[key])
    page.calculate()
    assert page.result is not None and not app.export_button.instate(["disabled"])


@pytest.mark.parametrize("gas,risk", [("WF6", True), ("AsH3", None)])
def test_simple_phase_risk_and_unknown_are_visible_in_banner_and_report(simple, gas, risk):
    _, app = simple
    app.show_tool("gas")
    page = app.active_page()
    for key, value in {"gas": gas, "flow": "100", "velocity": "5", "temperature": "20", "pressure": "6", "pressure_unit": "bar(g)"}.items():
        page.variables[key].set(value)
    page.calculate()
    assert page.result is not None
    assert page.result["liquefaction_risk"] is risk
    assert page.result.get("warnings"), "Phase findings must not remain hidden metadata"
    assert page.status.cget("style") != "Simple.Good.TLabel"
    assert page.banner.label.cget("background") != Theme.TONES["success"][1]
    report = tool_report(page.result, page.data())
    assert all(w in report for w in page.result["warnings"])


@pytest.mark.parametrize("gas,expected", [("WF6", "未達"), ("AsH3", "待資料")])
def test_workbench_phase_findings_are_not_generic_later_stage_advice(gas, expected):
    p = default_project()
    p["inputs"].update(gas1_type=gas, gas1_q="100", gas1_v_mode="自訂流速",
                       gas1_velocity="5", gas_temp="20")
    result = calculate(p)
    findings = [x for x in result["quality"]["items"] if "相態" in x["name"]]
    assert findings and any(x["status"] == expected for x in findings)
    assert any("相態" in w or "液化" in w for w in result["warnings"])


def test_duct_pressure_failure_takes_precedence_over_general_reference_warning(simple):
    _, app = simple
    app.show_tool("duct")
    page = app.active_page()
    for key, value in {"check_path": "1", "pressure": "1", "length": "100", "equipment": "100"}.items():
        page.variables[key].set(value)
    page.calculate()
    assert page.result is not None
    assert page.result["rectangle"]["budget_sufficient"] is False
    assert "不足" in page.banner.label.cget("text")
    assert page.banner.label.cget("background") == Theme.TONES["danger"][1]
    assert "不足" in tool_report(page.result, page.data())


def test_deferred_quality_is_not_colored_as_passed():
    from facility_studio.quality import assessment
    from facility_studio.ui_common import quality_style
    for state, style in [("通過", "Good.TLabel"), ("待資料", "Warn.TLabel"),
                         ("待後續", "Warn.TLabel"), ("未達", "Error.TLabel")]:
        q = assessment([{"status": state}])
        assert quality_style(q) == style


def test_workbench_summary_shows_failure_before_missing_data():
    from facility_studio.quality import assessment
    from facility_studio.ui_common import quality_text
    q = assessment([{"name": "pending", "detail": "curve missing", "status": "待資料"},
                    {"name": "critical", "detail": "pressure failure", "status": "未達"}])
    assert "pressure failure" in quality_text(q)


def test_partial_workbench_does_not_hide_gas_phase_warning(tmp_path, monkeypatch):
    from facility_studio.desktop import DesktopApp
    monkeypatch.setenv("FACILITY_STUDIO_PREFERENCES", str(tmp_path / "preferences.json"))
    root = tk.Tk()
    root.withdraw()
    app = DesktopApp(root)
    try:
        for key, value in {"sys_type": FIELDS["sys_type"]["options"][0], "gas1_type": "WF6", "gas1_q": "100", "gas1_v_mode": "自訂流速",
                               "gas1_velocity": "5", "gas_temp": "20", "ffu_cmh": "invalid"}.items():
            app.variables[key].set(value)
        app.recalculate()
        assert app.result is None
        assert app.domain_results["gas"]["result"] is not None
        assert "相態" in app.result_labels[3].cget("text")
        assert app.result_labels[3].cget("style") == "Error.TLabel"
    finally:
        root.destroy()


def test_electrical_demand_outside_catalog_is_blocked_instead_of_reported_as_zero():
    from facility_studio.errors import ValidationError
    with pytest.raises(ValidationError):
        calculate_tool("electrical", dict(defaults("electrical"), power="100000"))


@pytest.mark.parametrize("action", ["export_result", "export_summary"])
def test_changes_during_save_dialog_cannot_export_old_simple_results(simple, tmp_path, monkeypatch, action):
    from facility_studio import simple_desktop
    _, app = simple
    app.show_tool("water")
    page = app.active_page()
    page.calculate()
    target = tmp_path / "must-not-export.html"
    def change_during_dialog(**kwargs):
        page.variables["flow"].set("nan")
        return str(target)
    monkeypatch.setattr(simple_desktop.filedialog, "asksaveasfilename", change_during_dialog)
    assert getattr(app, action)() is False
    assert not target.exists()


@pytest.mark.parametrize("tool,changes", [
    ("liquid", {"geometry": "指定外徑及管壁", "outer_mm": "16", "wall_mm": "2", "flow": "100"}),
    ("water", {"pipe_size": "15A (1/2\")", "flow": "100"}),
])
def test_high_velocity_warnings_are_consistent_on_screen_and_export(simple, tool, changes):
    _, app = simple
    app.show_tool(tool)
    page = app.active_page()
    for key, value in changes.items():
        page.variables[key].set(value)
    page.calculate()
    assert page.result is not None
    assert any("流速" in w or "水速" in w for w in page.result["warnings"])
    assert page.status.cget("style") != "Simple.Good.TLabel"
    assert all(w in tool_report(page.result, page.data()) for w in page.result["warnings"])


def test_workbench_mode_interlocks_and_failed_edit_block_all_export_paths(tmp_path, monkeypatch):
    from facility_studio import desktop
    from facility_studio.desktop import DesktopApp
    monkeypatch.setenv("FACILITY_STUDIO_PREFERENCES", str(tmp_path / "preferences.json"))
    root = tk.Tk()
    root.withdraw()
    app = DesktopApp(root)
    try:
        app.recalculate()
        assert app.result is not None
        app.variables["pre_mode"].set("單盤管（一般空調箱）")
        app.variables["sys_type"].set("AHU (OA+RA 混合)")
        app.interlocks()
        for key in ("ffu_cmh", "ffu_w", "dcc_airflow_cmh"):
            assert str(app.widgets[key].cget("state")) == "disabled"
        app.variables["ffu_cmh"].set("not applicable draft")
        app.recalculate()
        assert app.result is not None
        app.variables["sys_type"].set(FIELDS["sys_type"]["options"][0])
        app.interlocks()
        assert str(app.widgets["ffu_cmh"].cget("state")) != "disabled"
        app.recalculate()
        assert app.result is None and app.export_button.instate(["disabled"])
        calls = []
        monkeypatch.setattr(desktop.filedialog, "asksaveasfilename", lambda **kw: calls.append(kw) or str(tmp_path / "bad.txt"))
        root.clipboard_clear()
        root.clipboard_append("synthetic clipboard sentinel")
        for action in (app.export, app.export_audit, app.export_html, app.save_plot, app.copy_report):
            action()
        assert not calls and not (tmp_path / "bad.txt").exists()
        assert root.clipboard_get() == "synthetic clipboard sentinel"
        app.variables["ffu_cmh"].set(default_project()["inputs"]["ffu_cmh"])
        app.recalculate()
        assert app.result is not None
    finally:
        root.destroy()


@pytest.mark.parametrize('kind,action', [('main', 'export'), ('main', 'export_audit'),
    ('main', 'export_html'), ('main', 'save_plot'), ('ahu', 'export'), ('ahu', 'save_plot')])
def test_all_full_window_exports_recheck_snapshot_after_save_dialog(tmp_path, monkeypatch, kind, action):
    from facility_studio import ahu_desktop, desktop
    monkeypatch.setenv('FACILITY_STUDIO_PREFERENCES', str(tmp_path / 'prefs.json'))
    root = tk.Tk()
    root.withdraw()
    messages = []
    monkeypatch.setattr(desktop.messagebox, 'showerror', lambda *a, **kw: messages.append(a))
    monkeypatch.setattr(desktop.messagebox, 'showinfo', lambda *a, **kw: messages.append(a))
    monkeypatch.setattr(desktop.messagebox, 'showwarning', lambda *a, **kw: messages.append(a))
    try:
        app = desktop.DesktopApp(root) if kind == 'main' else ahu_desktop.AHUWindow(root)
        app.recalculate() if kind == 'main' else app.calculate()
        assert app.result is not None
        target = tmp_path / 'stale-export'
        def dialog(**kw):
            (app.variables['project_name'] if kind == 'main' else app.vars['name']).set('changed while selecting a file')
            return str(target)
        monkeypatch.setattr(desktop.filedialog, 'asksaveasfilename', dialog)
        getattr(app, action)()
        assert not target.exists(), 'a changed project must not export previous/null results'
        assert any('條件已變更' in str(m) for m in messages), messages
    finally:
        root.destroy()


def test_ahu_deferred_banner_and_inactive_field_reactivation(tmp_path, monkeypatch):
    from facility_studio.ahu_desktop import AHUWindow
    from facility_studio.ahu_schema import NM_DEFAULTS, NM_FIELDS
    from facility_studio.quality import assessment
    monkeypatch.setenv('FACILITY_STUDIO_PREFERENCES', str(tmp_path / 'prefs.json'))
    root = tk.Tk()
    root.withdraw()
    try:
        app = AHUWindow(root)
        app.calculate()
        assert app.result is not None
        app.result['quality'] = assessment([{"name": '待原廠確認', "detail": '合成顯示測試', "status": '待後續'}])
        app.refresh_link_status()
        assert app.banner.label.cget('background') == Theme.TONES['warning'][1]
        for season in ('summer', 'winter'):
            app.vars[season + '_c1_mode'].set('旁通')
        app.visibility()
        assert str(app.widgets['c1_in'].cget('state')) == 'disabled'
        app.vars['c1_in'].set('inactive draft')
        app.calculate()
        assert app.result is not None
        app.vars['summer_c1_mode'].set(next(v for v in NM_FIELDS['summer_c1_mode']['limit'] if v != '旁通'))
        app.calculate()
        assert app.result is None and app.export_button.instate(['disabled'])
        app.vars['c1_in'].set(NM_DEFAULTS['c1_in'])
        app.calculate()
        assert app.result is not None
    finally:
        root.destroy()


@pytest.mark.parametrize('invalid', ['nan', 'inf', '', '-1'])
def test_ahu_invalid_flow_disables_export_and_recovers(tmp_path, monkeypatch, invalid):
    from facility_studio import ahu_desktop
    from facility_studio.ahu_schema import NM_DEFAULTS
    monkeypatch.setenv('FACILITY_STUDIO_PREFERENCES', str(tmp_path / 'prefs.json'))
    root = tk.Tk()
    root.withdraw()
    try:
        app = ahu_desktop.AHUWindow(root)
        app.calculate()
        assert app.result is not None
        app.vars['flow'].set(invalid)
        app.calculate()
        assert app.result is None and app.export_button.instate(['disabled'])
        calls = []
        monkeypatch.setattr(ahu_desktop.filedialog, 'asksaveasfilename', lambda **kw: calls.append(kw))
        app.export()
        app.save_plot()
        assert not calls
        app.vars['flow'].set(NM_DEFAULTS['flow'])
        app.calculate()
        assert app.result is not None
    finally:
        root.destroy()


@pytest.mark.parametrize('state', ['wrong-owner', 'stale-boundary'])
def test_ahu_return_interlock_checks_callback_as_well_as_button(tmp_path, monkeypatch, state):
    from facility_studio import ahu_desktop, desktop
    monkeypatch.setenv('FACILITY_STUDIO_PREFERENCES', str(tmp_path / 'prefs.json'))
    root = tk.Tk()
    root.withdraw()
    try:
        main = desktop.DesktopApp(root)
        main.recalculate()
        app = ahu_desktop.AHUWindow(root, main_app=main)
        app.calculate()
        assert app.result is not None
        if state == 'wrong-owner':
            app.owner_project_id = 'a different synthetic project'
        else:
            app.source_project_id = main.project_id
            app.vars['linked_main_hash'].set('old synthetic boundary')
            app.calculate()
        app.refresh_link_status()
        assert app.return_button.instate(['disabled'])
        calls, errors = [], []
        monkeypatch.setattr(main, 'apply_contribution', lambda *a: calls.append(a))
        monkeypatch.setattr(ahu_desktop.messagebox, 'showerror', lambda *a, **kw: errors.append(a))
        app.return_utilities()
        assert errors and not calls
    finally:
        root.destroy()


def test_copy_or_export_does_not_hide_workbench_quality_warning(tmp_path, monkeypatch):
    from facility_studio import desktop
    from facility_studio.ui_common import quality_style
    monkeypatch.setenv('FACILITY_STUDIO_PREFERENCES', str(tmp_path / 'prefs.json'))
    root = tk.Tk()
    root.withdraw()
    try:
        app = desktop.DesktopApp(root)
        app.recalculate()
        expected = quality_style(app.result['quality'])
        assert expected != 'Good.TLabel'
        app.copy_report()
        assert app.status.cget('style') == expected
        monkeypatch.setattr(desktop.filedialog, 'asksaveasfilename', lambda **kw: str(tmp_path / 'review.txt'))
        app.export()
        assert (tmp_path / 'review.txt').exists()
        assert app.status.cget('style') == expected
        assert app.result['quality']['status'] in app.status.cget('text')
    finally:
        root.destroy()


@pytest.mark.parametrize('gas,velocity', [('N2', '100'), ('H2', '100'), ('SiH4', '20')])
def test_gas_custom_velocity_needs_visible_reference_review(simple, gas, velocity):
    _, app = simple
    app.show_tool('gas')
    page = app.active_page()
    page.variables['gas'].set(gas)
    page.variables['velocity'].set(velocity)
    page.variables['flow'].set('10000')
    page.calculate()
    assert page.result is not None
    assert any('流速' in w for w in page.result['warnings'])
    assert page.status.cget('style') != 'Simple.Good.TLabel'
    assert all(w in tool_report(page.result, page.data()) for w in page.result['warnings'])


@pytest.mark.parametrize('gas,velocity', [('N2', '100'), ('H2', '100'), ('SiH4', '20')])
def test_workbench_custom_velocity_is_pending_reference(gas, velocity):
    p = default_project()
    p['inputs'].update(gas1_type=gas, gas1_q='10000', gas1_v_mode='自訂流速', gas1_velocity=velocity)
    result = calculate(p)
    assert any('流速' in w for w in result['gas']['1']['warnings'])
    assert any('流速依據' in row['name'] and row['status'] == '待資料' for row in result['quality']['items'])


@pytest.mark.parametrize('tool,changes', [
    ('cleanroom', {'coverage_limit_pct': '1'}),
    ('cleanroom', {'oa_cmh': '30000'}),
    ('cleanroom', {'process_moisture': '100000'}),
    ('liquid', {'insulate': '1', 'heat_limit': '.01'}),
    ('water', {'insulate': '1', 'insulation_outer_mm': '48.3', 'heat_limit': '.01'}),
    ('vacuum', {'vacuum_p': '.00001', 'flow': '.001', 'diameter_mode': '指定內徑', 'inner_mm': '50'}),
    ('liquid', {'check_npsh': '1', 'suction_surface_kpa': '101.325', 'suction_level_m': '2',
                'suction_loss_kpa': '10', 'npshr_m': '100', 'npsh_margin_m': '1',
                'pump_curve_reference': '合成曲線', 'npsh_margin_reference': '合成裕度'}),
])
def test_known_simple_engine_failure_is_red_and_precedes_general_notes(simple, tool, changes):
    _, app = simple
    app.show_tool(tool)
    page = app.active_page()
    for key, value in changes.items():
        page.variables[key].set(value)
    page.calculate()
    assert page.result is not None
    assert page.result.get('failures'), 'Known infeasibility needs a structural failure flag'
    assert page.banner.label.cget('background') == Theme.TONES['danger'][1]
    assert page.banner.label.cget('text').startswith(page.result['failures'][0])
    assert all(w in tool_report(page.result, page.data()) for w in page.result['failures'])


def test_missing_pump_curve_is_pending_not_a_proven_physical_failure(simple):
    _, app = simple
    app.show_tool('liquid')
    page = app.active_page()
    for key, value in {'check_npsh': '1', 'suction_surface_kpa': '101.325', 'suction_level_m': '2',
                       'suction_loss_kpa': '10', 'npshr_m': '', 'npsh_margin_m': ''}.items():
        page.variables[key].set(value)
    page.calculate()
    assert page.result is not None
    assert not page.result.get('failures')
    assert page.banner.label.cget('background') == Theme.TONES['warning'][1]
