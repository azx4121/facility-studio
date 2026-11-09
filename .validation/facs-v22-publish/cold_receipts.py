"""Independently validate cold real-entry observations; never execute the app."""
import json
import math
import re

PATHS = {'integration/entry.py', 'windows/facility_studio/cli.py',
         'windows/facility_studio/window_geometry.py',
         'windows/facility_studio/simple_desktop.py', 'windows/facility_studio/desktop.py'}
VIEWS = {'facility_studio.simple_desktop', 'facility_studio.desktop'}
CASE = re.compile(r'test_cold_real_entry_contains_untouched_native_window\[([0-3])-(simple|workbench)-(zh-Hant|en)\]')

def hashes(source):
    return {path: source['build_inputs_sha256'][path] if path.startswith('integration/')
            else source['product_source_sha256'][path.removeprefix('windows/')] for path in PATHS}

def validate_report(report, mode, language, expected_hashes, width, height, require):
    require(isinstance(report, dict) and report.get('mode') == mode and report.get('language') == language
        and report.get('passed') is True and report.get('stable') is True
        and report.get('probe_moves_or_resizes_window') is False
        and type(report.get('entry_exit')) is int and report['entry_exit'] == 0
        and report.get('errors') == [], 'Cold entry failed, was unstable, or probe altered placement.')
    imported = report.get('views_imported_when_tk_created', {})
    require(set(imported) == VIEWS and all(value is False for value in imported.values()),
            'Cold entry imported a view before creating Tk.')
    raw = report.get('source_sha256', {})
    require(isinstance(raw, dict) and all(isinstance(k,str) for k in raw), 'Invalid cold source hash inventory.')
    normalized = {key.replace('\\','/'): value for key,value in raw.items()}
    require(len(normalized) == len(raw) and normalized == expected_hashes,
            'Cold entry source hashes differ from independent final identity.')
    events = report.get('events', [])
    require(isinstance(events,list) and events and all(isinstance(e,dict) and 'error' not in e and isinstance(e.get('native'),dict) for e in events),
            'Cold entry has absent or failed native observations.')
    times = [e.get('elapsed') for e in events]
    require(all(type(t) in (int,float) and math.isfinite(t) and t >= 0 for t in times)
        and all(a <= b for a,b in zip(times,times[1:])), 'Invalid cold observation chronology.')
    require(any(e.get('event') == 'first_map' for e in events)
        and all(any(e.get('event') == kind and e.get('function') == '_place_initial_windows_window'
                    for e in events) for kind in ('call','return')), 'Cold entry mapping/placement observations missing.')
    samples=[e for e in events if e.get('event') == 'settled_sample'][-6:]
    settled=report.get('settled')
    require(isinstance(settled,dict) and len(samples)==6
        and all(e.get('native') == settled for e in samples)
        and samples[-1]['elapsed']-samples[0]['elapsed'] >= 0.5
        and all(a['elapsed'] < b['elapsed'] for a,b in zip(samples,samples[1:])),
            'Cold entry did not independently demonstrate six stable samples over half a second.')
    for key in ('hwnd','menu','dpi'):
        require(type(settled.get(key)) is int and settled[key]>0, 'Cold entry native window/menu/DPI missing.')
    require(type(settled.get('dwm_hresult')) is int and settled['dwm_hresult']==0
        and settled.get('state')=='normal' and isinstance(settled.get('title'),str) and settled['title'],
            'Cold entry has no normal visible DWM window.')
    for key in ('work','outer','visible','client'):
        rect=settled.get(key)
        require(isinstance(rect,list) and len(rect)==4 and all(type(v) is int for v in rect)
            and rect[0]<rect[2] and rect[1]<rect[3], 'Invalid cold native rectangle.')
    l,t,r,b=settled['work']
    require(0<=l<r<=width and 0<=t<b<=height, 'Cold work area differs from measured desktop.')
    require(report.get('containment') == {'outer':True,'visible':True,'client':True} and all(v is True for v in report['containment'].values()), 'Cold containment flag failed.')
    for key in ('outer','visible','client'):
        x,y,right,bottom=settled[key]
        require(l<=x<right<=r and t<=y<bottom<=b, 'Cold window escaped native work area.')
