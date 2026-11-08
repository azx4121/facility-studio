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


def verify_menu_observation(observation,language):
    """Validate native structure plus honestly classified Tk ownerdraw labels."""
    require(isinstance(observation,dict) and observation.get('popup_pixels_verified') is False,
            'Menu metadata is not popup pixel evidence')
    native,metadata=observation.get('native'),observation.get('tk_metadata')
    require(isinstance(native,dict) and isinstance(metadata,dict),'Missing native/Tk menu observations')
    for key in ('hwnd','menu'):
        require(type(native.get(key)) is int and native[key]>0,'Invalid native menu/window handle')
    authored=metadata.get('authored_menu')
    require(isinstance(authored,str) and authored.startswith('.') and authored!='.'
            and metadata.get('attached_menu')==authored,'Observed menu is not the authored root-attached menu')
    version=metadata.get('tk_version')
    require(isinstance(version,str) and version and all(part.isdigit() for part in version.split('.')),
            'Missing Tk runtime version')
    submenus=metadata.get('authored_submenus')
    require(isinstance(submenus,list) and len(submenus)==5 and len(set(submenus))==5
            and all(isinstance(p,str) and p.startswith(authored+'.') for p in submenus),
            'Invalid authored submenu registration')
    os_top,tk_top=native.get('top'),metadata.get('top')
    require(isinstance(os_top,list) and isinstance(tk_top,list),'Missing menu item observations')
    offset=0
    if tk_top and tk_top[0].get('type')=='tearoff':
        require(type(tk_top[0].get('index')) is int and tk_top[0]['index']==0,'Unexpected tearoff index')
        tk_top=tk_top[1:];offset=1
    require(len(os_top)==len(tk_top)==5,'Incomplete native/Tk menubar counts')
    ids,pointers,handles=set(),set(),set()
    def numeric(item):
        require(isinstance(item,dict) and all(type(item.get(k)) is int and item[k]>=0
                for k in ('ftype','state','id','submenu','data')),'Invalid native menu item metadata')
    for position,(item,entry) in enumerate(zip(os_top,tk_top)):
        numeric(item)
        require(isinstance(entry,dict) and type(entry.get('index')) is int
                and entry['index']==position+offset and entry.get('type')=='cascade'
                and entry.get('state')=='normal','Invalid Tk cascade position/state')
        require(item.get('native_text')==item.get('label')==entry.get('label')==TOP[language][position],
                'Top menu native text does not match observed label')
        require(item['ftype']==0 and item['state']==0,'Top menu is not a normal native string item')
        handle=item['submenu']
        require(handle>0 and type(item.get('queried_submenu')) is int and handle==item['queried_submenu']
                and handle not in handles and handle!=native['menu'],'Invalid native popup linkage')
        handles.add(handle)
        require(entry.get('submenu')==submenus[position],'Tk submenu registration order mismatch')
        children,tk_children=item.get('children'),entry.get('children')
        expected=CHILDREN[language][position]
        require(isinstance(children,list) and isinstance(tk_children,list)
                and len(children)==len(tk_children)==len(expected),'Incomplete native/Tk popup counts')
        for index,(child,tk_child) in enumerate(zip(children,tk_children)):
            numeric(child)
            require(isinstance(tk_child,dict) and type(tk_child.get('index')) is int
                    and tk_child['index']==index and tk_child.get('type')=='command'
                    and isinstance(tk_child.get('command'),str) and tk_child['command']
                    and tk_child.get('label')==expected[index],'Unexpected Tcl popup command/label')
            state=tk_child.get('state')
            require(state in ('normal','disabled') and child['state']==(3 if state=='disabled' else 0)
                    and child['submenu']==0,'Popup state or submenu mismatch')
            require(0<child['id']<0xffffffff and child['id'] not in ids,'Invalid or duplicate native command ID')
            ids.add(child['id'])
            if child['ftype']==0x100:
                require(child['data']>0 and child['data'] not in pointers and child.get('native_text')==''
                        and child.get('label_source')=='tk.entrycget(-label);win32.MFT_OWNERDRAW',
                        'Invalid ownerdraw item or dishonest label source')
                pointers.add(child['data'])
            else:
                require(child['ftype']==0 and child.get('native_text')==expected[index]
                        and child.get('label_source')=='win32.GetMenuStringW','Unclassified popup representation')
            require(child.get('observed_label')==expected[index],'Popup observed label mismatch')
    return True


def verify(receipt,profile):
    require(profile in PROFILES,'Unknown native profile')
    raw=Path(receipt).read_bytes()
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
            verify_menu_observation(row.get('menu_observation'),language)
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


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('receipt',type=Path);parser.add_argument('--profile',choices=PROFILES,required=True);args=parser.parse_args()
    print(json.dumps(verify(args.receipt,args.profile)))
