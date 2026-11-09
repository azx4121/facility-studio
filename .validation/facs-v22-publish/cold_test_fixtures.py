"""Synthetic observations only; not native evidence."""
import copy
import json
import xml.etree.ElementTree as ET
import cold_receipts

def report(source,width,height,mode='simple',language='en'):
    native=dict(hwnd=10,menu=20,dpi=96,dwm_hresult=0,state='normal',title='Synthetic',
        outer=[10,10,800,600],visible=[10,10,800,600],client=[20,40,790,590],work=[0,0,width,height-40])
    events=[dict(event='first_map',elapsed=0),dict(event='call',function='_place_initial_windows_window',elapsed=.1),
        dict(event='return',function='_place_initial_windows_window',elapsed=.2)]
    for event in events:event['native']=copy.deepcopy(native)
    events += [dict(event='settled_sample',elapsed=1+i*.2,native=copy.deepcopy(native)) for i in range(6)]
    return dict(mode=mode,language=language,passed=True,stable=True,probe_moves_or_resizes_window=False,
        entry_exit=0,errors=[],views_imported_when_tk_created={k:False for k in cold_receipts.VIEWS},
        source_sha256=cold_receipts.hashes(source),events=events,settled=native,
        containment={'outer':True,'visible':True,'client':True})

def xml(source,width,height):
    top=ET.Element('testsuites');suite=ET.SubElement(top,'testsuite',tests='16',skipped='0',failures='0',errors='0')
    for launch in range(4):
        for mode in ('simple','workbench'):
            for language in ('en','zh-Hant'):
                case=ET.SubElement(suite,'testcase',classname='integration.test_windows_cold_startup',
                    name=f'test_cold_real_entry_contains_untouched_native_window[{launch}-{mode}-{language}]')
                properties=ET.SubElement(case,'properties')
                ET.SubElement(properties,'property',name='cold_startup_readout',value=json.dumps(report(source,width,height,mode,language)))
    return ET.tostring(top)

def add(result,source,display_builder,prefix=''):
    for w,h in ((1920,1080),(1024,768)):
        result[f'{prefix}cold-startup-placement-{w}-{h}.xml']=xml(source,w,h)
        display=display_builder(w,h)
        display['command']=['python','-B','-m','pytest','D:/source/integration/test_windows_cold_startup.py','-k','cold_real_entry','--capture=sys']
        result[f'{prefix}cold-startup-display-{w}-{h}.json']=display
