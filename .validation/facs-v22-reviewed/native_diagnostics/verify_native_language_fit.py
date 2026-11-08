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
