"""Independent source-level regression contracts. No native GUI evidence.
Set FACS_AUDIT_SOURCE to a source tree (macos package selected by default).
"""
import copy
import os
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import tkinter
import pytest

ROOT = Path(os.environ.get('FACS_AUDIT_SOURCE', Path(__file__).resolve().parents[1])).resolve()
sys.path.insert(0, str(ROOT / os.environ.get('FACILITY_TEST_PLATFORM', 'macos')))
from facility_studio import ahu_desktop, session_controller as sc, sandbox_native_menu as menu, i18n

@pytest.fixture(autouse=True)
def isolated_localization(monkeypatch):
    import weakref
    monkeypatch.setattr(i18n, '_listeners', weakref.WeakSet())
    monkeypatch.setattr(i18n, '_language', 'zh-Hant')
    monkeypatch.setattr(i18n, '_initialized', True)
    if hasattr(menu, '_original_titles'):
        monkeypatch.setattr(menu, '_original_titles', {})


class Window:
    def __init__(self): self.live = True; self.destroys = 0
    def winfo_exists(self): return self.live
    def destroy(self):
        if not self.live: raise tkinter.TclError('invalid command name')
        self.live = False; self.destroys += 1
    def protocol(self, *args): pass
    def bind(self, *args, **kwargs): pass

class Widget:
    def __init__(self): self.state = 'normal'; self.calls = []
    def configure(self, **kw):
        self.calls.append(kw)
        self.state = kw.get('state', self.state)
    config = configure


def ahu_case():
    main = NS(project_id='current', _workspace_generation=7, children=[], ahu_documents={'kept':{'inputs':{'flow':42}}}, demand_ledger={'entries':[{'source':'kept'}]}, transfer_receipts=[{'before':True}])
    child = ahu_desktop.AHUWindow.__new__(ahu_desktop.AHUWindow)
    child.main_app = main; child.owner_project_id = 'wrong'; child.owner_generation=7
    child.win = Window(); child.return_button=Widget(); child.link_button=Widget(); child.link_info=Widget()
    child.result={'preserve':True}; child.ensure=lambda: True
    main.children.append(child)
    return main, child


def data(main): return copy.deepcopy((main.ahu_documents, main.demand_ledger, main.transfer_receipts))


def test_live_wrong_owner_disables_and_reports_without_data_changes(monkeypatch):
    main, child = ahu_case(); before=data(main); result=copy.deepcopy(child.result)
    errors=[]; monkeypatch.setattr(ahu_desktop.messagebox, 'showerror', lambda *a, **kw: errors.append((a,kw)))
    child.refresh_link_status()
    assert child.return_button.state == 'disabled'
    child.return_utilities()
    assert len(errors)==1
    assert data(main)==before and child.result==result


@pytest.mark.parametrize('state',['retired','stale','closed','unregistered','transition','restoring','degraded'])
def test_inactive_wrong_owner_callbacks_silent_and_inert(monkeypatch,state):
    main, child=ahu_case()
    if state=='retired': child._workspace_detached=True
    elif state=='stale': child.owner_generation=6
    elif state=='closed': child.win.live=False
    elif state=='unregistered': main.children=[]
    elif state=='transition': main._workspace_transition=True
    elif state=='restoring': main._restoring_snapshot=True
    elif state=='degraded': main._workspace_main={'inputs':{}}
    before=data(main); errors=[]
    monkeypatch.setattr(ahu_desktop.messagebox,'showerror',lambda *a, **kw: errors.append(a))
    child.ensure=lambda: pytest.fail('inactive child attempted calculation')
    child.refresh_link_status(); child.return_utilities()
    assert not errors and data(main)==before


def ledger_case():
    owner=NS(project_id='a', _workspace_generation=4, children=[], demand_ledger={'entries':[{'source':'untouched'}]}, undo_stack=[{'old':'ledger'}])
    win=Window(); child=sc.DemandLedgerWindow(owner,win)
    return owner,win,child


def test_dead_ledger_pruned_live_neighbor_refreshed_and_data_untouched():
    owner,win,child=ledger_case(); child.refresh=lambda: pytest.fail('dead view refreshed')
    live=sc.DemandLedgerWindow(owner,Window()); seen=[]; live.refresh=lambda: seen.append('live')
    before=copy.deepcopy((owner.demand_ledger,owner.undo_stack)); win.destroy()
    sc.SessionController.refresh_demand_views(owner)
    assert child not in owner.children and live in owner.children and seen==['live']
    assert (owner.demand_ledger,owner.undo_stack)==before


def test_live_ledger_tclerror_not_swallowed():
    owner,win,child=ledger_case()
    def fail(): raise tkinter.TclError('live rendering failure')
    child.refresh=fail
    with pytest.raises(tkinter.TclError,match='live rendering failure'):
        sc.SessionController.refresh_demand_views(owner)
    assert child in owner.children and win.live


def test_ledger_close_idempotent_after_external_destroy():
    owner,win,child=ledger_case(); before=copy.deepcopy(owner.demand_ledger)
    win.destroy(); child.close(); child.close(force=True)
    assert child not in owner.children and win.destroys==1 and owner.demand_ledger==before


def test_native_menu_language_reversal_preserves_dynamic_names(monkeypatch):
    labels=['About Facility Studio','','Settings…','Services','Hide 工程 python','Hide Others','Show All','Quit 工程 python','Custom item']
    rows=dict(enumerate(labels)); actions={key:object() for key in rows}; identities=dict(actions)
    class Native:
        def items(self): return list(rows.items())
        def rename(self,item,title): rows[item]=title
    monkeypatch.setattr(menu.sys,'platform','darwin'); monkeypatch.setattr(menu,'NativeApplicationMenu',Native)
    for language,expected in [('zh-Hant','設定…'),('en','Settings…'),('zh-Hant','設定…'),('en','Settings…')]:
        i18n.set_language(language,persist=False); call_localizer(language)
        assert rows[2]==expected
        assert rows[4]==('隱藏 工程 python' if language=='zh-Hant' else 'Hide 工程 python')
        assert rows[7]==('結束 工程 python' if language=='zh-Hant' else 'Quit 工程 python')
        assert rows[8]=='Custom item' and actions==identities


def test_actual_settings_construction_title_path_translates_and_switches(monkeypatch):
    """Execute unchanged construction prefix with native window boundaries replaced.
    Stops after title assignment; does not claim actual native dialog rendering.
    """
    import ast
    import inspect
    from facility_studio import fusion_settings, localized_tk, window_geometry
    tree=ast.parse(inspect.getsource(fusion_settings.open_settings))
    function=tree.body[0]
    stop=next(i for i,node in enumerate(function.body) if isinstance(node,ast.Expr)
              and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute)
              and node.value.func.attr=='geometry')
    function.body=function.body[:stop]+[ast.Return(value=ast.Name(id='win',ctx=ast.Load()))]
    ast.fix_missing_locations(tree)
    scope=dict(fusion_settings.__dict__)
    exec(compile(tree,'<actual settings construction prefix>','exec'),scope)
    class TitleWindow(Window):
        def __init__(self,root): super().__init__(); self.text=''
        def title(self,text=None):
            if text is not None:self.text=text
            return self.text
    monkeypatch.setattr(localized_tk.tk,'Toplevel',TitleWindow)
    # The title-only parent is not a Tk window; use explicit headless bounds.
    monkeypatch.setattr(window_geometry,'_windows_work_area',lambda root: (1024,728))
    app=NS(root=None,project_id='project',_workspace_generation=0)
    i18n.set_language('en',persist=False)
    win=scope['open_settings'](app)
    assert win.title()=='Advanced engineering settings'
    i18n.set_language('zh-Hant',persist=False)
    assert win.title()=='進階工程設定'
    i18n.set_language('en',persist=False)
    assert win.title()=='Advanced engineering settings'


def call_localizer(language):
    import inspect
    if 'language' in inspect.signature(menu.localize_application_menu).parameters:
        menu.localize_application_menu(language)
    else:
        menu.localize_application_menu()


def test_native_cache_rebuild_external_rename_and_default_contract(monkeypatch):
    rows={110:'Settings...',120:'Hide Old App',130:'Services'}
    class Native:
        def items(self): return list(rows.items())
        def rename(self,item,title): rows[item]=title
    monkeypatch.setattr(menu.sys,'platform','darwin'); monkeypatch.setattr(menu,'NativeApplicationMenu',Native)
    if hasattr(menu,'_original_titles'):menu._original_titles.clear()
    i18n.set_language('en',persist=False)
    menu.localize_application_menu()  # historical no-argument contract is Chinese
    assert rows=={110:'設定…',120:'隱藏 Old App',130:'服務'}
    call_localizer('zh-Hant'); call_localizer('zh-Hant')
    rows[120]='Hide Replacement App'  # native external update of dynamic app name
    call_localizer('zh-Hant'); call_localizer('en')
    assert rows=={110:'Settings...',120:'Hide Replacement App',130:'Services'}
    del rows[110]; call_localizer('zh-Hant')
    rows[110]='Preferences…'  # recycled address after absent item was observed
    call_localizer('zh-Hant'); assert rows[110]=='偏好設定…'
    call_localizer('en'); assert rows[110]=='Preferences…'
    rows.clear(); rows.update({110:'Quit New App',999:'Custom item'})
    call_localizer('zh-Hant');call_localizer('en')
    assert rows=={110:'Quit New App',999:'Custom item'}


def test_real_menu_installer_coalesces_latest_language_and_retires_root(monkeypatch):
    """Actual installer/subscriber, strict event-loop double; no native dispatch."""
    import weakref
    from facility_studio import sandbox_ui
    monkeypatch.setattr(i18n,'_listeners',weakref.WeakSet())
    monkeypatch.setattr(i18n,'_language','zh-Hant')
    monkeypatch.setattr(i18n,'_initialized',True)
    class Root(Window):
        def __init__(self): super().__init__();self.pending={};self.seq=0;self.handlers=[]
        def title(self,text):pass
        def configure(self,**kw):pass
        def bind(self,event,callback,**kw):self.handlers.append(callback)
        def iconify(self):pass
        def after_idle(self,callback):self.seq+=1;self.pending[self.seq]=callback;return self.seq
        def after_cancel(self,token):del self.pending[token]
        def pump(self):
            work=list(self.pending.values());self.pending.clear()
            for callback in work:callback()
    class Menu:
        def __init__(self,*a,**kw):self.rows=[]
        def add_command(self,**kw):self.rows.append(kw)
        def add_cascade(self,**kw):self.rows.append(kw)
        def winfo_exists(self):return True
        def index(self,index):
            assert index=='end'
            return len(self.rows)-1 if self.rows else None
        def type(self,index):return 'cascade' if 'menu' in self.rows[index] else 'command'
        def entrycget(self,index,key):return self.rows[index][key]
        def entryconfigure(self,index,**kw):
            assert set(kw)=={'label'}
            self.rows[index].update(kw)
    calls=[]
    monkeypatch.setattr(tkinter,'Menu',Menu)
    monkeypatch.setattr(menu,'localize_application_menu',lambda language='zh-Hant':calls.append(language))
    monkeypatch.setenv('FACILITY_STUDIO_NATIVE_MENUS','1')
    root=Root();sandbox_ui.install_menus(root);sandbox_ui.install_menus(root)
    assert len(root.pending)==1 and len(root.handlers)==1
    i18n.set_language('en',persist=False);i18n.set_language('zh-Hant',persist=False);i18n.set_language('en',persist=False)
    assert len(root.pending)==1
    root.pump();assert calls==['en']
    i18n.set_language('en',persist=False);assert not root.pending
    i18n.set_language('zh-Hant',persist=False);assert len(root.pending)==1
    # A descendant Destroy must not cancel the root's work.
    root.handlers[0](NS(widget=Window()));assert len(root.pending)==1
    listener=getattr(root,'_sandbox_menu_language',None)
    root.handlers[0](NS(widget=root));root.live=False
    assert not root.pending and root._sandbox_menu_after is None
    i18n.set_language('en',persist=False)
    assert listener not in i18n._listeners and not root.pending and calls==['en']
