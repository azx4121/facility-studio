"""Independently verify exact bilingual native menus and measured selector fit."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

PROFILES={'frozen1920':[1920,1080], 'small1024':[1024,768], 'suite1600':[1600,1200]}
PREFIX='test_actual_native_menu_and_rendered_selector_fit'
EXPECTED={f'{PREFIX}[{view}-{initial}]':(view,initial)
          for view in ('simple','workbench') for initial in ('en','zh-Hant')}
TOP={'en':['Facility Studio','File','Edit','Window','Help'],
     'zh-Hant':['Facility Studio','檔案','編輯','視窗','說明']}
CHILDREN={'en':[['About Facility Studio'],['Close window'],['Undo','Redo','Cut','Copy','Paste','Select all'],['Minimize'],['Verification purpose and scope']],
          'zh-Hant':[['關於 Facility Studio'],['關閉視窗'],['復原','重做','剪下','複製','貼上','全選'],['縮到最小'],['驗證用途與範圍']]}
CHOICES={'空調與熱負荷':'HVAC and room loads','全部工程分頁':'All engineering pages','基本模式':'Basic mode','進階模式':'Advanced mode'}


def require(condition,message):
    if not condition: raise ValueError(message)


def pairs(rows):
    result={}
    for key,value in rows:
        require(key not in result,'Duplicate JSON key');result[key]=value
    return result


def ints(value,count):
    return isinstance(value,list) and len(value)==count and all(type(v) is int for v in value)


def validate_menu_observation(observation, language):
    """Recompute native/Tk linkage; owner-drawn label content is Tk metadata."""
    require(isinstance(observation,dict) and set(observation)=={'native','tk_metadata','popup_pixels_verified'}
            and observation['popup_pixels_verified'] is False, 'Missing truthful native/Tk menu observation')
    native,meta=observation['native'],observation['tk_metadata']
    require(isinstance(native,dict) and isinstance(meta,dict), 'Missing raw menu facts')
    def integer(value,low=0,high=2**64-1):return type(value) is int and low<=value<=high
    require(integer(native.get('hwnd'),1) and integer(native.get('menu'),1), 'Missing real HWND/menu handle')
    attached=meta.get('attached_menu')
    require(isinstance(attached,str) and attached.startswith('.') and len(attached)>1
            and attached==meta.get('authored_menu'), 'Root-attached menu differs from authored menu')
    require(isinstance(meta.get('tk_version'),str) and meta['tk_version'].strip(), 'Missing observed Tk version')
    registered=meta.get('authored_submenus')
    require(isinstance(registered,list) and len(registered)==5
            and all(isinstance(p,str) and p.startswith(attached+'.') and len(p)>len(attached)+1 for p in registered)
            and len(set(registered))==5, 'Missing distinct authored submenu registration/order')
    tk_top=meta.get('top');os_top=native.get('top')
    require(isinstance(tk_top,list) and isinstance(os_top,list) and all(isinstance(r,dict) for r in tk_top+os_top),
            'Missing native/Tk top entries')
    offset=0
    if tk_top and tk_top[0].get('type')=='tearoff':
        require(set(tk_top[0])=={'index','type'} and integer(tk_top[0]['index'],0,0), 'Invalid master tearoff metadata')
        tk_top=tk_top[1:];offset=1
    require(len(tk_top)==len(os_top)==5, 'Native menubar count differs from authored cascades')
    ids,pointers,handles=set(),set(),set()
    for pos,(win,tk_entry) in enumerate(zip(os_top,tk_top)):
        require(integer(tk_entry.get('index'),pos+offset,pos+offset) and tk_entry.get('type')=='cascade'
                and tk_entry.get('state')=='normal', 'Wrong authored top entry type/order/state')
        require(tk_entry.get('label')==win.get('label')==win.get('native_text')==TOP[language][pos],
                'Exact Win32 top string differs from authored/expected language')
        require(integer(win.get('ftype'),0,0) and integer(win.get('state'),0,0)
                and integer(win.get('id'),0,0xffffffff) and integer(win.get('data')), 'Unknown native menubar type/state/data')
        handle=win.get('submenu')
        require(integer(handle,1) and integer(win.get('queried_submenu'),1)
                and handle==win['queried_submenu'] and handle not in handles, 'Invalid or mismatched GetSubMenu linkage')
        handles.add(handle)
        require(tk_entry.get('submenu')==registered[pos], 'Attached Tk submenu differs from registered order')
        os_children,tk_children=win.get('children'),tk_entry.get('children')
        require(isinstance(os_children,list) and isinstance(tk_children,list)
                and len(os_children)==len(tk_children)==len(CHILDREN[language][pos]), 'Native/Tk child count mismatch')
        for index,(item,entry) in enumerate(zip(os_children,tk_children)):
            require(isinstance(item,dict) and isinstance(entry,dict)
                    and integer(entry.get('index'),index,index) and entry.get('type')=='command',
                    'Unexpected child index/type; no separator/tearoff fallback')
            label=CHILDREN[language][pos][index]
            require(entry.get('label')==item.get('observed_label')==label
                    and isinstance(entry.get('command'),str) and entry['command'].strip(),
                    'Missing command callback or exact child label metadata')
            require(entry.get('state') in ('normal','disabled') and type(item.get('state')) is int
                    and item['state']==(3 if entry['state']=='disabled' else 0), 'Native/Tk command state mismatch')
            require(integer(item.get('submenu'),0,0) and integer(item.get('id'),1,0xfffffffe)
                    and item['id'] not in ids and integer(item.get('data')), 'Unknown child submenu/id/item data')
            ids.add(item['id'])
            if type(item.get('ftype')) is int and item['ftype']==0x100:
                require(item['data']>0 and item['data'] not in pointers, 'Missing or duplicate owner-draw item data')
                pointers.add(item['data'])
                require(item.get('native_text')=='' and item.get('label_source')=='tk.entrycget(-label);win32.MFT_OWNERDRAW',
                        'Owner-drawn labels must be classified as Tk metadata, not Win32 strings')
            else:
                require(integer(item.get('ftype'),0,0) and item.get('native_text')==label
                        and item.get('label_source')=='win32.GetMenuStringW',
                        'Unknown/empty menu type or unproven string-backed label')


def verify(receipt,profile):
    require(profile in PROFILES,'Unknown native profile')
    raw=receipt
    require(b'<!DOCTYPE' not in raw and b'<!ENTITY' not in raw,'Unsafe JUnit')
    root=ET.fromstring(raw);suites=list(root.iter('testsuite'));cases=list(root.iter('testcase'))
    require(len(suites)==1 and len(cases)==4 and {c.get('name') for c in cases}==set(EXPECTED),'Incomplete or duplicate native semantic cases')
    require(suites[0].get('tests')=='4' and all(suites[0].get(k)=='0' for k in ('errors','failures','skipped')),'JUnit aggregate mismatch')
    for case in cases:
        require(case.get('classname','').endswith('test_windows_english_startup_native'),'Wrong native semantic test module')
        require(not any(case.find(k) is not None for k in ('error','failure','skipped')),'Native semantic case failed or skipped')
        properties=case.findall('./properties/property[@name="native_language_fit"]')
        require(len(properties)==1,'Missing or duplicate semantic readout')
        rows=json.loads(properties[0].get('value'),object_pairs_hook=pairs)
        view,initial=EXPECTED[case.get('name')]
        require(isinstance(rows,list) and len(rows)==4,'Missing language-switch coverage')
        for row,language in zip(rows,[initial,'en','zh-Hant','en']):
            require(row.get('profile')==profile and row.get('screen_size')==PROFILES[profile]
                    and ints(row['screen_size'],2),'Wrong actual desktop dimensions')
            require(row.get('language')==language and row.get('top')==TOP[language]
                    and row.get('children')==CHILDREN[language],'Incorrect native menu language or command coverage')
            validate_menu_observation(row.get('menu_observation'),language)
            selectors=row.get('selectors')
            require(isinstance(selectors,list),'Missing selector evidence')
            if view=='simple':
                require(selectors==[],'Unexpected simple-view selectors')
                continue
            require(len(selectors)==4 and {s.get('canonical_choice') for s in selectors}==set(CHOICES),'Missing or duplicate selector choices')
            for s in selectors:
                choice=s['canonical_choice'];expected=CHOICES[choice] if language=='en' else choice
                require(s.get('text')==expected and s.get('visible') is True,'Wrong or hidden rendered selector')
                require(all(type(s.get(k)) is int and s[k]>0 for k in ('text_px','textarea_px','widget_px'))
                        and s['text_px']+2<=s['textarea_px']<=s['widget_px'],'Clipped selector text')
                bounds,size=s.get('client_bounds'),s.get('root_client_size')
                require(ints(bounds,4) and ints(size,2) and all(v>0 for v in size)
                        and 0<=bounds[0]<bounds[2]<=size[0] and 0<=bounds[1]<bounds[3]<=size[1]
                        and bounds[2]-bounds[0]==s['widget_px'],'Selector extends outside root client bounds')
    return dict(native_language_fit_cases=4,profile=profile,screen_size=PROFILES[profile],zero_skips=True,passed=True)


