"""Portable top-level menu regression, not native rendering/ABI acceptance.

The installer, subscriber, i18n, tkinter.Menu Python API and application-menu
localizer are production code. Tcl menu widgets and AppKit storage are strict
in-memory doubles; Tcl's after/idle scheduler is real. No display is required.
Set FACILITY_TEST_PLATFORM to select each mirror; FACS_TOP_MENU_SOURCE permits
running this unchanged contract against a sealed baseline or mutation tree.
"""
import gc
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import weakref

import pytest
import tkinter as tk

ROOT = Path(os.environ.get('FACS_TOP_MENU_SOURCE', Path(__file__).resolve().parents[1]))
PLATFORM = os.environ.get('FACILITY_TEST_PLATFORM', 'macos')
sys.path.insert(0, str(ROOT / PLATFORM))
from facility_studio import i18n, sandbox_ui, sandbox_native_menu as native

ZH = ['Facility Studio', '檔案', '編輯', '視窗', '說明']
EN = ['Facility Studio', 'File', 'Edit', 'Window', 'Help']


class TclMenuRoot(tk.Misc):
    """Real Tcl event queue and tkinter.Menu, with only widget server doubled."""
    def __init__(self):
        self.interpreter = tk.Tcl()
        self.tk = self.interpreter.tk
        self.master = None
        self._w = '.'
        self.children = {}
        self.live = True
        self.handlers = []
        self.rows = {}
        self.paths = {}
        self.writes = []
        self.focus = None
        self.minimized = 0
        self.callback_errors = []
        self.tk.createcommand('menu', self.create_menu)
        self.tk.createcommand('winfo', self.winfo)
        self.tk.createcommand('destroy', self.delete_widget)
    def create_menu(self, path, *args):
        self.rows[path] = []
        self.paths[path] = dict(zip(args[::2], args[1::2]))
        self.tk.createcommand(path, lambda *args: self.dispatch(path, *args))
        return path
    def winfo(self, command, path):
        assert command == 'exists'
        return int(self.live and (path == '.' or path in self.rows))
    def delete_widget(self, path):
        self.rows.pop(path)
        self.paths.pop(path)
        self.tk.deletecommand(path)
        return ''
    def dispatch(self, path, command, *args):
        rows = self.rows[path]
        if command == 'add':
            kind, *options = args
            assert kind in ('command', 'cascade', 'separator')
            rows.append({'kind': kind, **dict(zip(options[::2], options[1::2]))})
            return ''
        if command == 'index':
            assert args == ('end',)
            return len(rows)-1 if rows else 'none'
        if command == 'type': return rows[int(args[0])]['kind']
        if command == 'entrycget': return rows[int(args[0])][args[1]]
        if command == 'entryconfigure':
            index, *options = args
            options = dict(zip(options[::2], options[1::2]))
            assert set(options) == {'-label'}, 'localization may write labels only'
            self.writes.append((path, int(index), options.copy()))
            rows[int(index)].update(options)
            return ''
        raise AssertionError((path, command, args))
    def title(self, text): self.caption = text
    def configure(self, **kwargs): self.configuration = kwargs
    def bind(self, event, callback, add=None):
        assert event == '<Destroy>' and add == '+'
        self.handlers.append(callback)
    def iconify(self): self.minimized += 1
    def focus_get(self): return self.focus
    def winfo_exists(self): return self.live
    def report_callback_exception(self, *args): self.callback_errors.append(args)
    def pump(self):
        self.tk.call('update', 'idletasks')
        assert not self.callback_errors, self.callback_errors
    def pending(self): return self.tk.splitlist(self.tk.call('after', 'info'))
    def destroy(self):
        for callback in self.handlers: callback(SimpleNamespace(widget=self))
        self.live = False
    def top(self): return self.rows[str(self._sandbox_menu)]
    def labels(self): return [row['-label'] for row in self.top() if row['kind']=='cascade']


class NativeStorage:
    def __init__(self, setting='Settings…', name='python'):
        self.rows = {i: {'title': text, 'action': object(), 'target': object(),
                         'key': str(i), 'modifiers': i, 'enabled': bool(i % 2)}
                     for i, text in enumerate(['About Facility Studio', '', setting,
                         'Services', 'Hide '+name, 'Hide Others', 'Show All', '', 'Quit '+name])}
        self.writes = []
    def items(self): return [(key, row['title']) for key, row in self.rows.items()]
    def rename(self, key, title):
        self.writes.append((key, title))
        self.rows[key]['title'] = title
    def titles(self): return [text for _, text in self.items()]


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(i18n, '_listeners', weakref.WeakSet())
    monkeypatch.setattr(i18n, '_language', 'zh-Hant')
    monkeypatch.setattr(i18n, '_initialized', True)
    monkeypatch.setattr(native, '_original_titles', {})
    monkeypatch.setattr(native, 'sys', SimpleNamespace(platform='darwin'))
    monkeypatch.setattr(sandbox_ui, 'sys', SimpleNamespace(platform='darwin'))
    monkeypatch.setenv('FACILITY_STUDIO_NATIVE_MENUS', '1')
    monkeypatch.delenv('FACILITY_STUDIO_SANDBOX', raising=False)
    roots = []
    def create(language='zh-Hant', setting='Settings…', name='python'):
        i18n.set_language(language, persist=False)
        root = TclMenuRoot()
        storage = NativeStorage(setting, name)
        monkeypatch.setattr(native, 'NativeApplicationMenu', lambda: storage)
        roots.append(root)
        sandbox_ui.install_menus(root)
        return root, storage
    yield create
    for root in roots:
        if root.live: root.destroy()
        for child in list(root.children.values()): child.destroy()
        for command in ('menu', 'winfo', 'destroy'): root.tk.deletecommand(command)


def flip(root, language):
    i18n.set_language(language, persist=False)
    root.pump()


def assert_route():
    assert PLATFORM in ('macos', 'windows')
    for module in (i18n, native, sandbox_ui):
        assert Path(module.__file__).resolve().parent == (ROOT / PLATFORM / 'facility_studio').resolve()


def test_exact_source_mirror(): assert_route()


@pytest.mark.parametrize('setting', ['Settings…', 'Settings...', 'Preferences…', 'Preferences...'])
@pytest.mark.parametrize('name', ['python', 'Facility Studio 5.7.3', '工程驗證沙盒'])
@pytest.mark.parametrize('initial', ['en', 'zh-Hant'])
def test_actual_installer_event_loop_and_appkit_localizer_chain(setup, initial, setting, name):
    root, storage = setup(initial, setting, name)
    original = storage.titles()
    non_titles = [{k:v for k,v in row.items() if k!='title'} for row in storage.rows.values()]
    top_nonlabels = [{k:v for k,v in row.items() if k!='-label'} for row in root.top()]
    submenu_rows = {path: [dict(row) for row in rows] for path, rows in root.rows.items()
                    if path != str(root._sandbox_menu)}
    for language in [initial, 'en', 'zh-Hant', 'en', 'zh-Hant'] * 3:
        flip(root, language)
        assert root.labels() == (EN if language=='en' else ZH)
        assert storage.titles() == (original if language=='en' else [native.translated_title(x) for x in original])
        assert [{k:v for k,v in row.items() if k!='title'} for row in storage.rows.values()] == non_titles
        assert [{k:v for k,v in row.items() if k!='-label'} for row in root.top()] == top_nonlabels
        assert {path: rows for path, rows in root.rows.items() if path != str(root._sandbox_menu)} == submenu_rows
        before = (list(root.writes), list(storage.writes))
        flip(root, language)
        root._sandbox_menu_language.refresh_language()
        root.pump()
        assert (root.writes, storage.writes) == before
    assert len(root.handlers)==1 and len(i18n._listeners)==1


def test_coalescing_reads_latest_language_and_rebuilt_menu(setup):
    root, storage = setup()
    root.pump()
    old_menu = root._sandbox_menu
    subscriber = root._sandbox_menu_language
    i18n.set_language('en', persist=False)
    old_rows = [dict(row) for row in root.top()]
    assert root.labels()==EN
    sandbox_ui.install_menus(root)
    newest = root._sandbox_menu
    assert newest is not old_menu and root._sandbox_menu_language is subscriber
    i18n.set_language('zh-Hant', persist=False)
    i18n.set_language('en', persist=False)
    assert len(root.pending())==1 and len(root.handlers)==1 and len(i18n._listeners)==1
    root.pump()
    assert root.labels()==EN
    assert root.rows[str(old_menu)]==old_rows
    assert 'Settings…' in storage.titles()
    old_menu.destroy()
    flip(root, 'zh-Hant')
    assert root.labels()==ZH


def test_identity_mapping_handles_reorder_duplicate_missing_and_unknown_nodes(setup):
    root, _ = setup()
    root.pump()
    rows = root.top()
    # Two unrelated entries deliberately use the same labels as authored nodes.
    custom = tk.Menu(root._sandbox_menu, tearoff=False)
    root._sandbox_menu.add_cascade(label='檔案', menu=custom)
    root._sandbox_menu.add_command(label='說明', command=lambda: None)
    root._sandbox_menu.add_separator()
    # Duplicate an owned cascade, rename it externally, and move all nodes.
    duplicate = dict(rows[2]); duplicate['-label']='Externally renamed'
    rows.append(duplicate)
    del rows[3]  # Missing Window cascade must not shift role identification.
    rows.reverse()
    flip(root, 'en')
    assert [row.get('-label') for row in rows] == ['Edit', None, '說明', '檔案', 'Help', 'Edit', 'File', 'Facility Studio']
    flip(root, 'zh-Hant')
    assert [row.get('-label') for row in rows] == ['編輯', None, '說明', '檔案', '說明', '編輯', '檔案', 'Facility Studio']
    # An empty live menu must be safe without manufacturing missing labels.
    rows.clear()
    flip(root, 'en')
    assert rows==[]


def test_missing_destroyed_menu_and_live_errors(setup, monkeypatch):
    root, storage = setup()
    root.pump()
    root._sandbox_menu.destroy()
    flip(root, 'en')
    assert 'Settings…' in storage.titles()
    sandbox_ui.install_menus(root)
    root.pump()
    # Live Tcl failures must remain visible, not become a misleading success.
    def fail(*args, **kwargs): raise tk.TclError('live menu failure')
    monkeypatch.setattr(root._sandbox_menu, 'entryconfigure', fail)
    with pytest.raises(tk.TclError, match='live menu failure'):
        i18n.set_language('zh-Hant', persist=False)
    assert not root.callback_errors


def test_root_owned_weak_listener_and_destroy_cancellation(setup):
    root, storage = setup()
    root.pump()
    listener = root._sandbox_menu_language
    assert listener.root() is root
    flip(root, 'en')
    i18n.set_language('zh-Hant', persist=False)
    assert len(root.pending())==1
    for callback in root.handlers: callback(SimpleNamespace(widget=object()))
    assert len(root.pending())==1
    before = (list(root.writes), list(storage.writes))
    root.destroy()
    assert not root.pending() and root._sandbox_menu_after is None
    flip(root, 'en')
    assert (root.writes, storage.writes)==before
    assert listener not in i18n._listeners
    ref = weakref.ref(listener)
    del root._sandbox_menu_language
    del listener
    gc.collect()
    assert ref() is None


def test_new_root_has_one_listener_without_old_root_writes(setup):
    first, first_native = setup()
    first.pump()
    first.destroy()
    before = (list(first.writes), list(first_native.writes))
    second, _ = setup('en')
    second.pump()
    assert second.labels()==EN and len(i18n._listeners)==1
    flip(second, 'zh-Hant')
    assert second.labels()==ZH and (first.writes, first_native.writes)==before


def test_new_native_items_dynamic_names_and_removed_cache(setup):
    root, storage = setup()
    root.pump()
    storage.rows[2]['title']='Preferences...'
    storage.rows[4]['title']='Hide New 工程 name'
    storage.rows[90]={'title':'Custom 中文 item'}
    del storage.rows[8]
    flip(root, 'en')
    assert root.labels()==EN and storage.rows[2]['title']=='Preferences...'
    assert storage.rows[4]['title']=='Hide New 工程 name' and 8 not in native._original_titles
    flip(root, 'zh-Hant')
    assert root.labels()==ZH and storage.rows[2]['title']=='偏好設定…'
    assert storage.rows[4]['title']=='隱藏 New 工程 name' and storage.rows[90]['title']=='Custom 中文 item'


@pytest.mark.parametrize('platform', ['win32', 'linux', 'freebsd'])
def test_non_darwin_behavior_and_catalog_unchanged(setup, monkeypatch, platform):
    monkeypatch.setattr(sandbox_ui, 'sys', SimpleNamespace(platform=platform))
    monkeypatch.setattr(native, 'sys', SimpleNamespace(platform=platform))
    root, storage = setup('en')
    original = storage.titles()
    # R6 deliberately enables Windows Tk labels in the Windows source mirror.
    # The macOS mirror's win32 fallback and all other non-Darwin fallbacks stay
    # Chinese and must not write labels or touch the Cocoa application menu.
    windows_labels = PLATFORM == 'windows' and platform == 'win32'
    for language in ['en', 'zh-Hant', 'en']:
        flip(root, language)
        expected = EN if windows_labels and language == 'en' else ZH
        assert root.labels() == expected and storage.titles() == original
    assert bool(root.writes) == windows_labels
    assert not storage.writes
    assert i18n.translate('說明', 'en')=='Description'



@pytest.mark.skipif(PLATFORM != 'windows', reason='Windows-only R6 Tk command contract')
@pytest.mark.parametrize('initial', ['en', 'zh-Hant'])
def test_windows_owned_commands_follow_language_without_native_writes(setup, monkeypatch, initial):
    monkeypatch.setattr(sandbox_ui, 'sys', SimpleNamespace(platform='win32'))
    monkeypatch.setattr(native, 'sys', SimpleNamespace(platform='win32'))
    root, storage = setup(initial)
    original_native = storage.titles()
    paths = [row['-menu'] for row in root.top()]
    # Literal independent oracle: do not derive expected labels from the
    # production registration map or the general Description translation.
    labels = {
        'en': [['About Facility Studio'], ['Close window'],
               ['Undo', 'Redo', 'Cut', 'Copy', 'Paste', 'Select all'],
               ['Minimize'], ['Verification purpose and scope']],
        'zh-Hant': [['關於 Facility Studio'], ['關閉視窗'],
                    ['復原', '重做', '剪下', '複製', '貼上', '全選'],
                    ['縮到最小'], ['驗證用途與範圍']],
    }
    nonlabels = {path: [{k: v for k, v in row.items() if k != '-label'}
                        for row in rows] for path, rows in root.rows.items()}
    for language in [initial, 'en', 'zh-Hant', 'en', 'zh-Hant'] * 2:
        flip(root, language)
        assert root.labels() == (EN if language == 'en' else ZH)
        assert [[row['-label'] for row in root.rows[path]] for path in paths] == labels[language]
        assert {path: [{k: v for k, v in row.items() if k != '-label'}
                       for row in rows] for path, rows in root.rows.items()} == nonlabels
        assert storage.titles() == original_native and not storage.writes
        before = list(root.writes)
        root._sandbox_menu_language.refresh_language()
        root.pump()
        assert root.writes == before
    assert i18n.translate('說明', 'en') == 'Description'


@pytest.mark.skipif(PLATFORM != 'windows', reason='Windows-only R6 Tk command contract')
def test_windows_command_identity_preserves_custom_entries_and_dispatch(setup, monkeypatch):
    monkeypatch.setattr(sandbox_ui, 'sys', SimpleNamespace(platform='win32'))
    monkeypatch.setattr(native, 'sys', SimpleNamespace(platform='win32'))
    root, storage = setup()
    root.pump()
    edit = root.nametowidget(root.top()[2]['-menu'])
    events = []
    root.focus = SimpleNamespace(event_generate=events.append)
    edit.add_command(label='復原', command=lambda: events.append('custom'), state='disabled')
    edit.add_separator()
    custom_menu = tk.Menu(edit, tearoff=False)
    edit.add_cascade(label='貼上', menu=custom_menu)
    rows = root.rows[str(edit)]
    duplicate = dict(rows[0])
    duplicate.update({'-label': 'Externally renamed', '-state': 'disabled', '-accelerator': 'Ctrl+Z'})
    rows.append(duplicate)
    del rows[1]  # Missing Redo must not shift command identity.
    rows.reverse()
    nonlabels = [{k: v for k, v in row.items() if k != '-label'} for row in rows]
    for language, expected in [
        ('en', ['Undo', '貼上', None, '復原', 'Select all', 'Paste', 'Copy', 'Cut', 'Undo']),
        ('zh-Hant', ['復原', '貼上', None, '復原', '全選', '貼上', '複製', '剪下', '復原']),
    ]:
        flip(root, language)
        assert [row.get('-label') for row in rows] == expected
        assert [{k: v for k, v in row.items() if k != '-label'} for row in rows] == nonlabels
        root.tk.call(rows[-1]['-command'])
        assert events[-1] == '<<Undo>>'
    assert events == ['<<Undo>>', '<<Undo>>'] and not storage.writes
    # Empty and destroyed registered submenus must not manufacture entries.
    rows.clear()
    flip(root, 'en')
    assert rows == []
    edit.destroy()
    flip(root, 'zh-Hant')
    assert root.labels() == ZH and not storage.writes


def test_disabled_feature_creates_no_menu_or_listener(monkeypatch):
    monkeypatch.delenv('FACILITY_STUDIO_NATIVE_MENUS', raising=False)
    monkeypatch.delenv('FACILITY_STUDIO_SANDBOX', raising=False)
    root = SimpleNamespace()
    sandbox_ui.install_menus(root)
    assert vars(root)=={}


def test_command_dispatch_and_shortcuts_survive_language_switch(setup):
    root, _ = setup()
    initial = {path: [dict(row) for row in rows] for path, rows in root.rows.items()}
    events = []
    focus = SimpleNamespace(event_generate=events.append)
    root.focus = focus
    for language in ['en', 'zh-Hant', 'en']:
        flip(root, language)
        file_menu, edit_menu, window_menu = [row['-menu'] for row in root.top()[1:4]]
        for row in root.rows[edit_menu]: root.tk.call(row['-command'])
        root.tk.call(root.rows[window_menu][0]['-command'])
        closed = []
        root.focus = SimpleNamespace(winfo_toplevel=lambda: SimpleNamespace(protocol=lambda _: '', destroy=lambda: closed.append(True)))
        root.tk.call(root.rows[file_menu][0]['-command'])
        assert closed==[True]
        root.focus = focus
    assert events==['<<Undo>>','<<Redo>>','<<Cut>>','<<Copy>>','<<Paste>>','<<SelectAll>>']*3
    assert root.minimized==3
    assert {path: rows for path, rows in root.rows.items() if path!=str(root._sandbox_menu)} == {path: rows for path, rows in initial.items() if path!=str(root._sandbox_menu)}


def test_deferred_tk_rebuild_precedes_native_title_restoration(setup, monkeypatch):
    """Conservative idle-rebuild model; not an observation of native Tk timing."""
    root, storage = setup()
    root.pump()
    original_dispatch = root.dispatch
    native_original = ['About Facility Studio', '', 'Settings…', 'Services',
                       'Hide python', 'Hide Others', 'Show All', '', 'Quit python']
    rebuilds = []
    def rebuild():
        rebuilds.append(True)
        for key, title in enumerate(native_original): storage.rows[key]['title'] = title
    def dispatch(path, command, *args):
        result = original_dispatch(path, command, *args)
        if command == 'entryconfigure':
            root.after_idle(rebuild)
        return result
    monkeypatch.setattr(root, 'dispatch', dispatch)
    for language in ['en', 'zh-Hant', 'en', 'zh-Hant']:
        flip(root, language)
        assert root.labels() == (EN if language=='en' else ZH)
        assert storage.titles() == (native_original if language=='en' else [native.translated_title(x) for x in native_original])
    assert len(rebuilds)==16
