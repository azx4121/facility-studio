"""Cross-repair B/undo interactions, not native UI acceptance.

Real production session/transition/storage methods and Tcl variables. Reuses
reviewed fixture presentation doubles; native-menu/window doubles test callback
semantics only, not AppKit/Tk rendering, action dispatch or packaged binaries.
"""
import copy
import os
from pathlib import Path
import sys
from unittest.mock import Mock
import weakref

import pytest

ROOT = Path(os.environ.get('FACILITY_SOURCE_TREE', Path(__file__).resolve().parents[1])).resolve()
PLATFORM = os.environ.get('FACILITY_TEST_PLATFORM', 'macos')
assert PLATFORM in ('macos', 'windows')
sys.path[:0] = [str(ROOT / 'integration'), str(ROOT / PLATFORM)]
import test_workspace_repair_interactions as workspace
import test_demand_view_lifecycle as ledger
import test_native_english_switch as language
from facility_studio import ahu_desktop, i18n, fusion_settings, localized_tk, window_geometry
from facility_studio import session_controller as controller, workspace_transition
from facility_studio.workspace_store import read_workspace

isolate = workspace.isolate
base_app_factory = workspace.base_app_factory
app_factory = workspace.app_factory


@pytest.fixture(autouse=True)
def localization_isolation(monkeypatch):
    monkeypatch.setattr(i18n, '_listeners', weakref.WeakSet())
    monkeypatch.setattr(i18n, '_initialized', True)
    monkeypatch.setattr(i18n, '_language', 'zh-Hant')
    monkeypatch.setattr(language.native, '_original_titles', {})


def presentations(app, monkeypatch):
    root, menu = language.setup(monkeypatch)
    windows = []

    class Settings(language.Root):
        def __init__(self, parent):
            super().__init__()
            windows.append(self)
        def geometry(self, value):
            raise language.StopAfterTitle

    # Real construction path with actual editability/token guards, stopping at
    # geometry. Does not open the form or claim Save/Cancel widget validation.
    with monkeypatch.context() as patch:
        patch.setattr(localized_tk.tk, 'Toplevel', Settings)
        # app.root owns Tcl variables only, with no Tk winfo/native HWND.
        patch.setattr(window_geometry, '_windows_work_area', lambda root: (1024, 728))
        with pytest.raises(language.StopAfterTitle):
            fusion_settings.open_settings(app)
    return root, menu, windows[0]


def flip(root, menu, settings, code):
    i18n.set_language(code, persist=False)
    root.pump()
    assert menu.entries[2]['title'] == ('Settings…' if code == 'en' else '設定…')
    assert settings.title() == ('Advanced engineering settings' if code == 'en' else '進階工程設定')


def owner_controls(child):
    child.return_button = Mock()
    child.link_button = Mock()
    child.link_info = Mock()
    child.ensure = Mock(side_effect=AssertionError('refusal/stale callback calculated'))


def test_requested_production_mirror():
    for module in (ahu_desktop, controller, fusion_settings, language.native):
        assert Path(module.__file__).resolve().is_relative_to(ROOT / PLATFORM)


@pytest.mark.parametrize('phase', ['current', 'transition', 'restoring', 'degraded'])
def test_language_and_readonly_callbacks_preserve_canonical_undo_and_drafts(
        app_factory, monkeypatch, tmp_path, phase):
    app = app_factory()
    old = workspace.seed_old(app, raw='unfinished')
    root, menu, settings = presentations(app, monkeypatch)
    view = ledger.view(app)
    if phase == 'degraded':
        incoming = workspace.incoming(app, raw='nan')
        with monkeypatch.context() as patch:
            patch.setattr(app, 'notify_children', Mock(side_effect=RuntimeError('injected observer failure')))
            with pytest.raises(RuntimeError):
                app.apply_workspace(incoming)
        view = ledger.view(app)  # A current-generation read-only observer.
    elif phase == 'transition':
        app._workspace_transition = True
    elif phase == 'restoring':
        app._restoring_snapshot = True
    # Wrong ownership excludes a live child from snapshots by design. Establish
    # the comparison only after that explicit fixture change.
    old.owner_project_id = 'different-owner'
    owner_controls(old)
    before = workspace.state(app)
    draft = old.vars['flow'].get()
    old_undo = copy.deepcopy(old.undo_inputs)
    errors = Mock()
    monkeypatch.setattr(ahu_desktop.messagebox, 'showerror', errors)
    for code in ('en', 'zh-Hant', 'en'):
        flip(root, menu, settings, code)
        app.refresh_demand_views()
        old.refresh_link_status()
        old.return_utilities()
        assert workspace.state(app) == before
        assert old.vars['flow'].get() == draft and old.undo_inputs == old_undo
    assert view.refresh.call_count == 3
    assert errors.call_count == (3 if phase == 'current' else 0)
    if phase == 'current':
        old.return_button.configure.assert_called_with(state='disabled')
        old.link_button.configure.assert_called_with(state='disabled')
    old.ensure.assert_not_called()
    app._workspace_transition = app._restoring_snapshot = False
    if phase == 'degraded':
        assert app.retry_workspace_presentation()
    output = tmp_path / 'after-readonly.json'
    assert app.save_workspace(output)
    assert read_workspace(output) == before['workspace']
    root.destroy()


@pytest.mark.parametrize('degraded', [False, True])
def test_live_owner_feedback_then_switch_retires_callbacks_without_replacing_new_drafts(
        app_factory, monkeypatch, tmp_path, degraded):
    app = app_factory()
    old = workspace.seed_old(app)
    owner_controls(old)
    root, menu, settings = presentations(app, monkeypatch)
    old.owner_project_id = 'wrong-owner'
    errors = Mock()
    monkeypatch.setattr(ahu_desktop.messagebox, 'showerror', errors)
    old.refresh_link_status(); old.return_utilities()
    assert errors.call_count == 1
    old.return_button.configure.assert_called_with(state='disabled')
    incoming = workspace.incoming(app, raw='nan', same_id=True)
    if degraded:
        with monkeypatch.context() as patch:
            patch.setattr(app, 'notify_children', Mock(side_effect=RuntimeError('injected switch observer')))
            with pytest.raises(RuntimeError):
                app.apply_workspace(incoming)
    else:
        app.apply_workspace(incoming)
    assert old not in app.children and old._workspace_detached
    for stage in ('after-switch', 'after-retry'):
        before = workspace.state(app)
        for code in ('en', 'zh-Hant'):
            flip(root, menu, settings, code)
            old.refresh_link_status(); old.return_utilities(); old.undo_changes()
            app.refresh_demand_views(); app.undo_preset()
            assert workspace.state(app) == before
            assert app.session_snapshot() == incoming
            assert errors.call_count == 1
        output = tmp_path / (stage + '.json')
        assert app.save_workspace(output) and read_workspace(output) == incoming
        if degraded and stage == 'after-switch':
            assert app.retry_workspace_presentation()
    old.ensure.assert_not_called()
    root.destroy()


@pytest.mark.parametrize('lost_binding', [False, True])
def test_external_ledger_destroy_reopen_language_reimport_and_real_undo(
        app_factory, monkeypatch, tmp_path, lost_binding):
    app = app_factory()
    project, initial_ledger, entry = ledger.legacy_example('W')
    monkeypatch.setattr(controller.messagebox, 'askyesnocancel', lambda *a, **k: True)
    monkeypatch.setattr(ledger.workspace_view.messagebox, 'askokcancel', lambda *a, **k: True)
    app.suspended = True
    for key, value in project['inputs'].items():
        app.variables[key].set(value)
    app.suspended = False
    # Real contribution/reimport and undo, with invalid inactive draft evidence.
    app.variables['process_latent_kw'].set('unfinished')
    app.field_drafts['upw_res'] = {'source': '使用者輸入', 'note': 'Synthetic dormant draft', 'value': '17.2000'}
    root, menu, settings = presentations(app, monkeypatch)
    stale = ledger.view(app)
    stale.refresh.side_effect = AssertionError('externally destroyed ledger refreshed')
    if lost_binding:
        stale.win.handlers.clear()
    stale.win.destroy()
    live = ledger.view(app)  # Production wrapper for reopened presentation.
    observed = []

    def readonly_refresh():
        before = workspace.state(app)
        flip(root, menu, settings, 'en')
        flip(root, menu, settings, 'zh-Hant')
        observed.append(bool(getattr(app, '_restoring_snapshot', False)))
        assert workspace.state(app) == before

    live.refresh.side_effect = readonly_refresh
    before = copy.deepcopy(app.session_snapshot())
    assert app.apply_contribution(entry)
    assert entry['id'] in app.demand_ledger['entries']
    assert stale not in app.children and live in app.children
    app.undo_preset()
    assert app.session_snapshot() == before
    assert True in observed, 'read-only refresh must run during actual undo'
    stale.close(); stale.close(force=True)
    assert stale not in app.children and stale.win.destroy_calls == 1
    stale.refresh.assert_not_called()
    assert live in app.children and live.win.alive
    assert app.apply_contribution(entry)  # Reimport after undo must remain usable.
    assert stale not in app.children
    output = tmp_path / 'after-reimport.json'
    assert app.save_workspace(output)
    assert read_workspace(output) == app.session_snapshot()
    root.destroy()
