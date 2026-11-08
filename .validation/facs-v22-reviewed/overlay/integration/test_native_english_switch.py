"""Portable regression: real localization/lifecycle code with no AppKit/Tk display.

Does not establish native rendering, ABI, dispatch or full English coverage.
Run separately for each FACILITY_TEST_PLATFORM. BASE_SOURCE enables v10 controls.
"""
import os
import sys
import weakref
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(os.environ.get('BASE_SOURCE', Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT / os.environ.get('FACILITY_TEST_PLATFORM', 'macos')))
from facility_studio import i18n, sandbox_native_menu as native, sandbox_ui, fusion_settings
from facility_studio import localized_tk, workspace_transition


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setattr(i18n, '_listeners', weakref.WeakSet())
    monkeypatch.setattr(i18n, '_language', 'zh-Hant')
    monkeypatch.setattr(i18n, '_initialized', True)
    if hasattr(native, '_original_titles'):
        monkeypatch.setattr(native, '_original_titles', {})


class Root:
    def __init__(self):
        self.live = True
        self.pending = {}
        self.sequence = 0
        self.bindings = []
        self.text = ''
    def title(self, text=None):
        if text is not None:
            self.text = text
        return self.text
    def winfo_exists(self): return self.live
    def configure(self, **kwargs): self.configuration = kwargs
    def after_idle(self, callback):
        self.sequence += 1
        self.pending[self.sequence] = callback
        return self.sequence
    def after_cancel(self, token): del self.pending[token]
    def bind(self, event, callback, add=None): self.bindings.append(callback)
    def iconify(self): pass
    def pump(self):
        callbacks = list(self.pending.values())
        self.pending.clear()
        for callback in callbacks: callback()
    def destroy(self):
        for callback in self.bindings: callback(SimpleNamespace(widget=self))
        self.live = False


class Menu:
    def __init__(self, *_args, **_kwargs): self.entries = []
    def add_command(self, **kwargs): self.entries.append(kwargs)
    def add_cascade(self, **kwargs): self.entries.append(kwargs)
    def winfo_exists(self): return True
    def index(self, index):
        assert index == 'end'
        return len(self.entries) - 1 if self.entries else None
    def type(self, index): return 'cascade' if 'menu' in self.entries[index] else 'command'
    def entrycget(self, index, key): return self.entries[index][key]
    def entryconfigure(self, index, **kwargs):
        assert set(kwargs) == {'label'}
        self.entries[index].update(kwargs)


class Native:
    def __init__(self, setting, name):
        self.entries = {index: dict(title=title, action=object(), target=object(),
                                    enabled=True, key='q', modifiers=3)
                        for index, title in enumerate([
                            'About '+name, '', setting, 'Services', 'Hide '+name,
                            'Hide Others', 'Show All', '', 'Quit '+name])}
        self.writes = []
    def items(self): return [(key, value['title']) for key, value in self.entries.items()]
    def rename(self, item, title):
        self.writes.append((item, title))
        self.entries[item]['title'] = title
    def titles(self): return [text for _, text in self.items()]


def setup(monkeypatch, setting='Settings…', name='Facility Studio 5.7.3 工程'):
    import tkinter
    menu = Native(setting, name)
    monkeypatch.setattr(native, 'NativeApplicationMenu', lambda: menu)
    monkeypatch.setattr(native, 'sys', SimpleNamespace(platform='darwin'))
    monkeypatch.setattr(tkinter, 'Menu', Menu)
    monkeypatch.setattr(sandbox_ui, 'sys', SimpleNamespace(platform='darwin'), raising=False)
    monkeypatch.setenv('FACILITY_STUDIO_NATIVE_MENUS', '1')
    root = Root()
    sandbox_ui.install_menus(root)
    return root, menu


@pytest.mark.parametrize('setting', ['Settings…', 'Settings...', 'Preferences…', 'Preferences...'])
@pytest.mark.parametrize('name', ['python', 'Facility Studio 5.7.3', '工程驗證沙盒', 'Settings & Preferences'])
def test_actual_install_language_switch_roundtrip(monkeypatch, setting, name):
    root, menu = setup(monkeypatch, setting, name)
    original = menu.titles()
    non_titles = [{k:v for k,v in entry.items() if k != 'title'} for entry in menu.entries.values()]
    for language in ['zh-Hant', 'en', 'zh-Hant', 'en', 'zh-Hant']:
        i18n.set_language(language, persist=False)
        root.pump()
        assert menu.titles() == ([native.translated_title(x) for x in original] if language == 'zh-Hant' else original)
        writes = list(menu.writes)
        root.pump()
        assert menu.writes == writes
        assert [{k:v for k,v in entry.items() if k != 'title'} for entry in menu.entries.values()] == non_titles


def test_reinstall_coalesces_and_destroy_cancels(monkeypatch):
    root, menu = setup(monkeypatch)
    sandbox_ui.install_menus(root)
    assert len(root.pending) == 1
    assert len(root.bindings) == 1
    root.pump()
    i18n.set_language('en', persist=False)
    i18n.set_language('zh-Hant', persist=False)
    i18n.set_language('en', persist=False)
    assert len(root.pending) == 1
    root.pump()
    assert 'Settings…' in menu.titles()
    i18n.set_language('zh-Hant', persist=False)
    assert len(root.pending) == 1
    root.destroy()
    assert root.pending == {}
    writes = list(menu.writes)
    i18n.set_language('en', persist=False)
    root.pump()
    assert writes == menu.writes


def test_native_replacement_external_rename_and_unknown_titles(monkeypatch):
    root, menu = setup(monkeypatch)
    root.pump()
    # Tk changed an item's app name and replaced Settings with Preferences.
    menu.entries[4]['title'] = 'Hide A different 工程 app'
    menu.entries[2]['title'] = 'Preferences...'
    menu.entries[90] = dict(title='Custom 中文 title')
    i18n.set_language('en', persist=False)
    root.pump()
    assert menu.entries[4]['title'] == 'Hide A different 工程 app'
    assert menu.entries[2]['title'] == 'Preferences...'
    i18n.set_language('zh-Hant', persist=False)
    root.pump()
    assert menu.entries[4]['title'] == '隱藏 A different 工程 app'
    assert menu.entries[90]['title'] == 'Custom 中文 title'
    del menu.entries[4]
    i18n.set_language('en', persist=False)
    root.pump()
    assert 4 not in native._original_titles


def test_english_startup_then_chinese(monkeypatch):
    i18n.set_language('en', persist=False)
    root, menu = setup(monkeypatch)
    original = menu.titles()
    root.pump()
    assert menu.titles() == original
    i18n.set_language('zh-Hant', persist=False)
    root.pump()
    assert menu.titles() == [native.translated_title(x) for x in original]


class StopAfterTitle(Exception): pass


def test_real_settings_creation_title_and_live_listener(monkeypatch):
    # Execute the actual open_settings entry and window title setup, stopping
    # before geometry/widget construction. Field/form/model paths are untouched.
    from facility_studio import window_geometry

    # Root below is a lifecycle double, not a display-backed Tk window.
    monkeypatch.setattr(window_geometry, '_windows_work_area', lambda root: (1024, 728))
    windows = []
    class Window(Root):
        def __init__(self, _root):
            super().__init__()
            windows.append(self)
        def geometry(self, _geometry): raise StopAfterTitle
    monkeypatch.setattr(localized_tk.tk, 'Toplevel', Window)
    monkeypatch.setattr(workspace_transition, 'require_editable', lambda app: None)
    monkeypatch.setattr(workspace_transition, 'token', lambda app: 1)
    app = SimpleNamespace(root=Root(), project_id='test')
    for language in ['zh-Hant', 'en', 'zh-Hant']:
        i18n.set_language(language, persist=False)
        with pytest.raises(StopAfterTitle): fusion_settings.open_settings(app)
        assert windows[-1].title() == i18n.translate('進階工程設定')
    for language in ['en', 'zh-Hant']:
        i18n.set_language(language, persist=False)
        assert all(win.title() == i18n.translate('進階工程設定') for win in windows)
    windows[0].destroy()
    previous = windows[0].title()
    i18n.set_language('en', persist=False)
    assert windows[0].title() == previous


def test_non_darwin_authored_about_label_preserved(monkeypatch):
    root, _ = setup(monkeypatch)
    monkeypatch.setattr(sandbox_ui, 'sys', SimpleNamespace(platform='win32'))
    sandbox_ui.install_menus(root)
    assert root._sandbox_menu.entries[0]['menu'].entries[0]['label'] == '關於 Facility Studio'


def test_native_about_has_restorable_authored_english_source(monkeypatch):
    root, _ = setup(monkeypatch)
    assert root._sandbox_menu.entries[0]['menu'].entries[0]['label'] == 'About Facility Studio'
