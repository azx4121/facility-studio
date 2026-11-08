"""Independent v12 contracts: real Tcl + tkinter.Menu, no Tk display/AppKit ABI.
No author test helper is imported. The Tcl widget server is separately authored.
"""
import copy
import gc
import inspect
import os
from pathlib import Path
import random
import sys
from types import SimpleNamespace as NS
import weakref
import tkinter as tk
import pytest

HERE=Path(__file__).resolve().parent
SOURCE=Path(os.environ.get('FACILITY_SOURCE_TREE',Path(__file__).resolve().parents[1])).resolve()
PLATFORM=os.environ.get('FACILITY_TEST_PLATFORM','macos')
sys.path.insert(0,str(SOURCE/PLATFORM))
from facility_studio import sandbox_ui as ui, sandbox_native_menu as native, i18n
EN=['Facility Studio','File','Edit','Window','Help']
ZH=['Facility Studio','檔案','編輯','視窗','說明']

class Root(tk.Tk):
    def __init__(self,tearoff):
        super().__init__(useTk=False)
        self.tk.call('source',str(HERE/'independent_top_menu_server.tcl'))
        self.tk.setvar('audit::default_tearoff',int(tearoff))
        self.alive=True;self.handlers=[];self.errors=[];self.focus=None
        self.minimize_count=0;self.close_command='';self.configuration={}
    def title(self,text): self.caption=text
    def configure(self,**kw): self.configuration.update(kw)
    def bind(self,event,callback,add=None):
        assert (event,add)==('<Destroy>','+')
        self.handlers.append(callback)
    def winfo_exists(self):return self.alive
    def focus_get(self):return self.focus
    def iconify(self):self.minimize_count+=1
    def protocol(self,name):assert name=='WM_DELETE_WINDOW';return self.close_command
    def report_callback_exception(self,*args):self.errors.append(args)
    def pending(self):return self.tk.splitlist(self.tk.call('after','info'))
    def pump(self,check=True):
        self.tk.call('update','idletasks')
        if check:assert not self.errors,self.errors
    def destroy(self):
        if not self.alive:return
        for callback in self.handlers:callback(NS(widget=self))
        self.alive=False
    def release(self):
        self.destroy()
        for child in list(self.children.values()):child.destroy()
        for command in list(self._tclCommands or ()):
            try:self.deletecommand(command)
            except tk.TclError:pass
    def rows(self,path=None):
        path=str(path or self._sandbox_menu)
        result=[]
        for row in self.tk.splitlist(self.tk.call('dict','get',self.tk.getvar('audit::widgets'),path,'rows')):
            pairs=self.tk.splitlist(row);result.append(dict(zip(pairs[::2],pairs[1::2])))
        return result
    def labels(self):return [r['-label'] for r in self.rows() if r['kind']=='cascade']
    def writes(self):return self.tk.splitlist(self.tk.getvar('audit::writes'))
    def clear_writes(self):self.tk.setvar('audit::writes',())

class Storage:
    def __init__(self,titles=None):
        if titles is None:titles=['About Engineer 工程','Settings...','Services','Hide Engineer 工程','Hide Others','Show All','Quit Engineer 工程','Custom 中文']
        self.rows={100+n:dict(title=text,action=object(),target=object(),key=str(n),modifiers=n,enabled=n%2==0) for n,text in enumerate(titles)}
        self.writes=[];self.before_rename=None
    def items(self):return [(key,row['title']) for key,row in self.rows.items()]
    def rename(self,key,text):
        if self.before_rename:self.before_rename()
        self.writes.append((key,text));self.rows[key]['title']=text
    def titles(self):return [row['title'] for row in self.rows.values()]

@pytest.fixture
def setup(monkeypatch):
    roots=[]
    monkeypatch.setattr(ui,'sys',NS(platform='darwin'))
    monkeypatch.setattr(native,'sys',NS(platform='darwin'))
    monkeypatch.setattr(i18n,'_language','zh-Hant')
    monkeypatch.setattr(i18n,'_initialized',True)
    monkeypatch.setattr(i18n,'_listeners',weakref.WeakSet())
    monkeypatch.setattr(native,'_original_titles',{})
    monkeypatch.setenv('FACILITY_STUDIO_NATIVE_MENUS','1')
    monkeypatch.delenv('FACILITY_STUDIO_SANDBOX',raising=False)
    def make(tearoff=True,language='zh-Hant',titles=None):
        i18n.set_language(language,persist=False)
        root=Root(tearoff);roots.append(root)
        store=Storage(titles)
        monkeypatch.setattr(native,'NativeApplicationMenu',lambda:store)
        ui.install_menus(root)
        return root,store
    yield make
    for root in roots:root.release()

def flip(root,language):i18n.set_language(language,persist=False);root.pump()
def owned_submenus(root):return [root.nametowidget(r['-menu']) for r in root.rows() if r['kind']=='cascade'][1:]
def nonlabels(root):return [{k:v for k,v in r.items() if k!='-label'} for r in root.rows()]


def test_actual_module_and_tk_api_provenance():
    for module in (ui,native,i18n):assert Path(module.__file__).resolve().parent==SOURCE/PLATFORM/'facility_studio'
    assert str(inspect.signature(tk.Menu.entryconfigure))=='(self, index, cnf=None, **kw)'
    assert str(inspect.signature(tk.Menu.entrycget))=='(self, index, option)'
    assert str(inspect.signature(tk.Menu.index))=='(self, index)'
    assert str(inspect.signature(tk.Menu.type))=='(self, index)'

@pytest.mark.parametrize('tearoff',[False,True])
@pytest.mark.parametrize('initial',['zh-Hant','en'])
def test_install_roundtrip_tearoff_offsets_and_title_only(setup,tearoff,initial):
    root,store=setup(tearoff,initial)
    assert isinstance(root._sandbox_menu,tk.Menu)
    assert root._sandbox_menu.index('end')==(5 if tearoff else 4)
    if tearoff:assert root._sandbox_menu.type(0)=='tearoff'
    before=nonlabels(root);submenus={str(s):copy.deepcopy(root.rows(s)) for s in owned_submenus(root)}
    native_non_titles={key:{k:v for k,v in row.items() if k!='title'} for key,row in store.rows.items()}
    original=store.titles()
    for lang in [initial,'en','zh-Hant','en']*6:
        flip(root,lang)
        assert root.labels()==(EN if lang=='en' else ZH)
        assert nonlabels(root)==before
        assert {str(s):root.rows(s) for s in owned_submenus(root)}==submenus
        assert store.titles()==(original if lang=='en' else [native.translated_title(t) for t in original])
        assert {key:{k:v for k,v in row.items() if k!='title'} for key,row in store.rows.items()}==native_non_titles
        for write in root.writes():
            args=root.tk.splitlist(root.tk.splitlist(write)[2]);assert len(args)==2 and args[0]=='-label'
    root.clear_writes();store.writes.clear()
    ui._localize_top_menus(root,i18n.language());native.localize_application_menu(i18n.language())
    assert not root.writes() and not store.writes


def test_roles_follow_menu_identity_after_reorder_insertion_and_removal(setup):
    root,_=setup();root.pump();menu=root._sandbox_menu
    roles=owned_submenus(root);before={str(s):root.rows(s) for s in roles}
    menu.delete(0,'end')
    outsider=tk.Menu(menu,tearoff=False)
    menu.add_cascade(label='檔案',menu=outsider,underline=2,state='disabled',accelerator='Ctrl+F')
    menu.add_command(label='說明',command=lambda:None)
    menu.add_separator()
    sequence=[roles[3],roles[0],roles[1],roles[1]]
    for submenu in sequence:menu.add_cascade(label='externally changed',menu=submenu,underline=1)
    notlabels=nonlabels(root)
    flip(root,'en')
    assert root.labels()==['檔案','Help','File','Edit','Edit']
    assert root.rows()[1]['-label']=='說明'
    assert nonlabels(root)==notlabels
    flip(root,'zh-Hant')
    assert root.labels()==['檔案','說明','檔案','編輯','編輯']
    assert {str(s):root.rows(s) for s in roles}==before
    menu.delete(0,'end');assert menu.index('end') is None
    flip(root,'en');assert root.rows()==[]


def test_many_random_reordered_roles_keep_custom_nodes(setup):
    root,_=setup(False);root.pump();menu=root._sandbox_menu;roles=owned_submenus(root)
    custom=tk.Menu(menu,tearoff=False);rng=random.Random(57312)
    for n in range(24):
        menu.delete(0,'end');order=list(range(4))+[4,5];rng.shuffle(order)
        for role in order:
            if role<4:menu.add_cascade(label='untrusted label',menu=roles[role])
            elif role==4:menu.add_cascade(label='說明',menu=custom)
            else:menu.add_command(label='檔案',command=lambda:None)
        lang='en' if n%2==0 else 'zh-Hant';flip(root,lang)
        expected=[(EN if lang=='en' else ZH)[r+1] if r<4 else ('說明' if r==4 else '檔案') for r in order]
        assert [r['-label'] for r in root.rows()]==expected


def test_rebuild_before_idle_targets_new_menu_and_latest_language(setup):
    root,store=setup();root.pump();old=root._sandbox_menu;listener=root._sandbox_menu_language
    i18n.set_language('en',persist=False);rows=root.rows(old);ui.install_menus(root)
    newest=root._sandbox_menu
    assert newest is not old and root._sandbox_menu_language is listener
    for lang in ['zh-Hant','en','zh-Hant','en']:i18n.set_language(lang,persist=False)
    assert len(root.pending())==1 and len(root.handlers)==1 and len(i18n._listeners)==1
    root.pump();assert root.labels()==EN and root.rows(old)==rows
    old.destroy();flip(root,'zh-Hant');assert root.labels()==ZH
    assert root.configuration['menu'] is newest


def test_callback_resolves_language_at_execution_not_registration(setup):
    root,store=setup();root.pump()
    i18n.set_language('en',persist=False)
    assert root.labels()==EN
    # Isolates the native callback's execution-time read. Directly mutating this
    # private global is not a public language change and does not notify Tk.
    i18n._language='zh-Hant'
    root.pump();assert store.rows[101]['title']=='設定…'
    i18n.set_language('en',persist=False);root.pump()
    assert root.labels()==EN and store.rows[101]['title']=='Settings...'



def test_tk_cascades_update_before_appkit_localizer(setup):
    root,store=setup();root.pump()
    observations=[]
    store.before_rename=lambda:observations.append(root.labels())
    flip(root,'en');assert observations and all(x==EN for x in observations)


def test_destroyed_menu_still_allows_appkit_update_and_reinstall(setup):
    root,store=setup();root.pump();root._sandbox_menu.destroy()
    flip(root,'en');assert 'Settings...' in store.titles()
    ui.install_menus(root);root.pump();assert root.labels()==EN


def test_live_tcl_error_is_not_silently_passed(setup):
    root,store=setup();root.pump();menu=root._sandbox_menu;before=store.titles()
    # Replace only the actual Tcl widget entryconfigure operation with an error.
    path=str(menu);root.tk.call('rename',path,path+'_real')
    root.tk.eval(f'proc {path} {{args}} {{ if {{[lindex $args 0] eq "entryconfigure"}} {{error "injected live Tk failure"}}; return [uplevel 1 [linsert $args 0 {path}_real]] }}')
    with pytest.raises(tk.TclError,match='injected live Tk failure'):
        i18n.set_language('en',persist=False)
    assert not root.errors
    assert root._sandbox_menu_after is None and store.titles()==before
    root.tk.call('rename',path,'');root.tk.call('rename',path+'_real',path)
    root.errors.clear();root._sandbox_menu_language.refresh_language();root.pump();assert root.labels()==EN


def test_root_destroy_cancels_only_own_event_and_prunes_listener(setup):
    root,store=setup();root.pump();listener=root._sandbox_menu_language
    assert listener.root() is root
    i18n.set_language('en',persist=False);assert len(root.pending())==1
    for fn in root.handlers:fn(NS(widget=object()))
    assert len(root.pending())==1
    old=(root.writes(),list(store.writes));root.destroy()
    assert root.pending()==() and root._sandbox_menu_after is None
    i18n.set_language('zh-Hant',persist=False);root.pump()
    assert (root.writes(),store.writes)==old and listener not in i18n._listeners
    ref=weakref.ref(listener);del root._sandbox_menu_language;del listener;gc.collect();assert ref() is None


def test_new_root_after_old_destroy_has_one_listener(setup):
    root,store=setup();root.pump();root.destroy();before=root.writes()
    second,_=setup(language='en');second.pump();assert second.labels()==EN
    assert len(i18n._listeners)==1
    flip(second,'zh-Hant');assert second.labels()==ZH and root.writes()==before


def test_command_callbacks_and_registered_close_protocol_preserved(setup):
    root,_=setup(False);root.pump();files,edits,windows,helps=owned_submenus(root)
    events=[];close_calls=[]
    close_id=root.register(lambda:close_calls.append('protocol'))
    root.close_command=close_id
    for lang in ['en','zh-Hant','en']:
        flip(root,lang)
        root.focus=NS(event_generate=events.append)
        for ix in range(edits.index('end')+1):edits.invoke(ix)
        windows.invoke(0)
        root.focus=None;files.invoke(0)
    assert events==['<<Undo>>','<<Redo>>','<<Cut>>','<<Copy>>','<<Paste>>','<<SelectAll>>']*3
    assert close_calls==['protocol']*3 and root.minimize_count==3
    destroyed=[];root.focus=NS(winfo_toplevel=lambda:NS(protocol=lambda name:'',destroy=lambda:destroyed.append(True)))
    files.invoke(0);assert destroyed==[True]

@pytest.mark.parametrize('platform',['linux','win32'])
def test_non_darwin_platform_label_contract(setup,monkeypatch,platform):
    monkeypatch.setattr(ui,'sys',NS(platform=platform));monkeypatch.setattr(native,'sys',NS(platform=platform))
    root,store=setup(language='en');before=store.titles()
    localized = PLATFORM == 'windows' and platform == 'win32'
    for lang in ['en','zh-Hant','en']:
        flip(root,lang)
        assert root.labels()==(EN if localized and lang=='en' else ZH)
    assert not store.writes and store.titles()==before
    if not localized:assert not root.writes()
    assert root.rows(root.nametowidget(root.rows()[1]['-menu']))[0]['-label']==('About Facility Studio' if localized else '關於 Facility Studio')
    assert i18n.translate('說明','en')=='Description'


def test_disabled_feature_is_inert(monkeypatch):
    monkeypatch.delenv('FACILITY_STUDIO_NATIVE_MENUS',raising=False);monkeypatch.delenv('FACILITY_STUDIO_SANDBOX',raising=False)
    root=NS();ui.install_menus(root);assert vars(root)=={}


def test_preexisting_appkit_localization_external_changes_and_new_items(setup):
    root,store=setup();root.pump()
    assert store.rows[101]['title']=='設定…'
    store.rows[101]['title']='Preferences…';store.rows[103]['title']='Hide Renamed 工程'
    store.rows[250]=dict(title='About Newly added',action=object(),key='x')
    del store.rows[106]
    flip(root,'en');assert root.labels()==EN and store.rows[101]['title']=='Preferences…'
    assert store.rows[103]['title']=='Hide Renamed 工程' and 106 not in native._original_titles
    flip(root,'zh-Hant');assert store.rows[250]['title']=='關於 Newly added'
    flip(root,'en');assert store.rows[250]['title']=='About Newly added'


def test_uncached_chinese_appkit_titles_not_guessed(setup):
    # Existing v11 contract: without known original titles, do not guess/rewrite.
    original=['設定…','關於 外部程式','Custom 中文']
    root,store=setup(language='en',titles=original);root.pump()
    assert root.labels()==EN and store.titles()==original
    flip(root,'zh-Hant');flip(root,'en');assert store.titles()==original


def test_conservative_deferred_native_rebuild_orders_before_restoration(setup):
    """Synthetic stronger model only; not proof Aqua rebuilds on label writes."""
    root,store=setup();root.pump()
    originals=['About Engineer 工程','Settings...','Services','Hide Engineer 工程','Hide Others','Show All','Quit Engineer 工程','Custom 中文']
    rebuilt=[]
    def trigger():
        def rebuild():
            rebuilt.append(True)
            for row,text in zip(store.rows.values(),originals):row['title']=text
        root.after_idle(rebuild)
    command=root.register(trigger)
    root.tk.call('rename','audit::dispatch','audit::dispatch_actual')
    root.tk.eval('proc audit::dispatch {path op args} { set result [audit::dispatch_actual $path $op {*}$args]; if {$op eq "entryconfigure" && [llength $args] > 1} { '+command+' }; return $result }')
    for lang in ['en','zh-Hant','en','zh-Hant']:
        flip(root,lang)
        assert rebuilt
        assert root.labels()==(EN if lang=='en' else ZH)
        assert store.titles()==(originals if lang=='en' else [native.translated_title(x) for x in originals])


def test_subscriber_does_not_retain_root_without_scheduled_work():
    class MinimalRoot:
        def winfo_exists(self):return True
    root=MinimalRoot();ref=weakref.ref(root);listener=ui._NativeMenuLanguage(root)
    del root;gc.collect()
    assert ref() is None and listener.root() is None and not listener.winfo_exists()
    listener.refresh_language()


@pytest.mark.skipif(PLATFORM != "windows", reason="Windows source correction")
@pytest.mark.parametrize("initial", ["en", "zh-Hant"])
@pytest.mark.parametrize("tearoff", [True, False])
def test_windows_authored_commands_roundtrip_keep_actions_and_disabled(setup, monkeypatch, initial, tearoff):
    monkeypatch.setattr(ui, "sys", NS(platform="win32"))
    monkeypatch.setattr(native, "sys", NS(platform="win32"))
    root, store = setup(tearoff, initial)
    menus = [root.nametowidget(r['-menu']) for r in root.rows() if r['kind']=='cascade']
    expected_en = [["About Facility Studio"], ["Close window"],
                   ["Undo", "Redo", "Cut", "Copy", "Paste", "Select all"],
                   ["Minimize"], ["Verification purpose and scope"]]
    expected_zh = [["關於 Facility Studio"], ["關閉視窗"],
                   ["復原", "重做", "剪下", "複製", "貼上", "全選"],
                   ["縮到最小"], ["驗證用途與範圍"]]
    # Disable a real authored action and add an identically labelled outsider.
    edits = menus[2]
    edits.entryconfigure(0, state="disabled", accelerator="Ctrl+Z")
    calls = []
    edits.add_command(label="復原", command=lambda: calls.append("custom"))
    prior = [[{k:str(v) for k,v in row.items() if k!='-label'} for row in root.rows(m)] for m in menus]
    for lang in [initial, "en", "zh-Hant", "en"]:
        flip(root, lang)
        expected = copy.deepcopy(expected_en if lang=='en' else expected_zh)
        expected[2].append("復原")
        assert [[r['-label'] for r in root.rows(m)] for m in menus] == expected
        assert [[{k:str(v) for k,v in row.items() if k!='-label'} for row in root.rows(m)] for m in menus] == prior
        assert root.labels() == (EN if lang=='en' else ZH)
        root.focus = NS(event_generate=calls.append)
        edits.invoke(0)  # Disabled Undo must remain inert after translation.
        edits.invoke(1)
        edits.invoke(6)
    assert calls == ["<<Redo>>", "custom"] * 4
    assert not store.writes  # No AppKit access on Windows.
    root.clear_writes()
    ui._localize_top_menus(root, i18n.language())
    assert not root.writes()


@pytest.mark.skipif(PLATFORM != "windows", reason="Windows source correction")
def test_windows_disabled_native_menu_feature_is_inert(monkeypatch):
    monkeypatch.setattr(ui, "sys", NS(platform="win32"))
    monkeypatch.delenv("FACILITY_STUDIO_NATIVE_MENUS", raising=False)
    monkeypatch.delenv("FACILITY_STUDIO_SANDBOX", raising=False)
    root = NS()
    ui.install_menus(root)
    assert vars(root) == {}
