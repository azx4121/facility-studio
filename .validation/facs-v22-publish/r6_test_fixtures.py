"""Synthetic R6 evidence. Never a native product or GUI attestation."""
import json
import xml.etree.ElementTree as ET
import semantic_receipts as semantic

def audit(image,count=2):
    return dict(required=True,passed=True,errors=[],total_job_processes=count,retained_process_handles=count,
        images=[dict(pid=i+1,image=image) for i in range(count)])
def launch(exe):
    image='C:/synthetic/'+exe
    return dict(command=[image],process_image_audit=audit(image))
def policies():
    return dict(launch_path_policy='windows-system-directories-only',external_python_absence_claimed=False,
        standalone_process_image_audit_required=True,standalone_process_image_audit_passed=True,installation_performed=False)
def preflight():
    return dict(schema_version=1,path_entries=['C:/Windows/System32','C:/Windows'],launch_path='C:/Windows/System32;C:/Windows',
        controller_python='C:/Python/python.exe',controller_python_version='3.12 synthetic',
        unsafe_path_entries=[],absolute_path_execution_blocked=False,machine_python_absence_claimed=False,
        process_execution_policy_enforced=False,controller_which={n:None for n in ('python.exe','python3.exe','py.exe')},
        reachable_candidates=[dict(origin='launch_path',name='py.exe',path='C:/Windows/py.exe')],
        path_and_implicit_directory_scan_passed=False)
def process_xml():
    root=ET.Element('testsuites');suite=ET.SubElement(root,'testsuite',tests='2',errors='0',failures='0',skipped='0')
    for foreign in (False,True):
        image='C:/Python/python.exe';a=audit(image)
        if foreign:
            a['passed']=False;a['images'][1]['image']='C:/Windows/System32/cmd.exe';a['errors']=['Unexpected external process image: C:/Windows/System32/cmd.exe']
        row=dict(schema_version=1,synthetic_controller_executable='C:/venv/python.exe',synthetic_base_executable=image,expected='denied' if foreign else 'allowed',passed=True,command=[image],process_image_audit=a)
        c=ET.SubElement(suite,'testcase',classname='integration.test_standalone_process_images',name=f'test_native_child_identity[{foreign}]')
        ET.SubElement(ET.SubElement(c,'properties'),'property',name='process_image_preflight',value=json.dumps(row))
    return ET.tostring(root)
def menu_observation(language,tearoff=True):
    native=dict(hwnd=100,menu=200,top=[])
    meta=dict(attached_menu='.menu',authored_menu='.menu',authored_submenus=['.menu.'+str(i) for i in range(5)],
        top=[dict(index=0,type='tearoff')] if tearoff else [],tk_version='8.6.15')
    identity=1
    for pos,label in enumerate(semantic.TOP[language]):
        win=dict(ftype=0,state=0,id=0,data=0,label=label,native_text=label,submenu=300+pos,queried_submenu=300+pos,children=[])
        tk=dict(index=pos+int(tearoff),type='cascade',state='normal',label=label,submenu=meta['authored_submenus'][pos],children=[])
        for index,child in enumerate(semantic.CHILDREN[language][pos]):
            win['children'].append(dict(ftype=0x100,state=0,id=identity,data=1000+identity,submenu=0,native_text='',
                observed_label=child,label_source='tk.entrycget(-label);win32.MFT_OWNERDRAW'))
            tk['children'].append(dict(index=index,type='command',state='normal',label=child,command='callback'+str(identity)))
            identity+=1
        native['top'].append(win);meta['top'].append(tk)
    return dict(native=native,tk_metadata=meta,popup_pixels_verified=False)

def semantic_xml(w,h):
    profile='frozen1920' if w==1920 else 'small1024'
    root=ET.Element('testsuites');suite=ET.SubElement(root,'testsuite',tests='4',errors='0',failures='0',skipped='0')
    for name,(view,initial) in semantic.EXPECTED.items():
        rows=[]
        for language in [initial,'en','zh-Hant','en']:
            selectors=[]
            if view=='workbench':
                for choice,text in semantic.CHOICES.items():
                    selectors.append(dict(canonical_choice=choice,text=text if language=='en' else choice,visible=True,
                        text_px=80,textarea_px=90,widget_px=100,client_bounds=[10,10,110,40],root_client_size=[800,600]))
            rows.append(dict(profile=profile,screen_size=[w,h],language=language,top=semantic.TOP[language],children=semantic.CHILDREN[language],menu_observation=menu_observation(language),selectors=selectors))
        c=ET.SubElement(suite,'testcase',classname='integration.test_windows_english_startup_native',name=name)
        ET.SubElement(ET.SubElement(c,'properties'),'property',name='native_language_fit',value=json.dumps(rows))
    return ET.tostring(root)
def enrich(files,role,version,exe,display_builder):
    files=dict(files);prefix='' if role=='source' else '0-facs-v22-evidence/'
    files[prefix+'process-image-preflight.xml']=process_xml()
    files[prefix+'python-launch-preflight.json']=json.dumps(preflight()).encode()
    if role=='source' or version=='2022':
        semantic_prefix=prefix+('prebuild-' if role=='private' else '')
        for w,h in [(1920,1080),(1024,768)]:
            files[f'{semantic_prefix}native-language-fit-{w}-{h}.xml']=semantic_xml(w,h)
            display=display_builder(w,h);display['command']=['python','-B','-m','pytest','D:/source/integration/test_windows_english_startup_native.py','--capture=sys']
            files[f'{semantic_prefix}native-language-fit-display-{w}-{h}.json']=json.dumps(display).encode()
    for name,raw in list(files.items()):
        if name.endswith(('Single_EXE_Verification.json','Frozen_External_Checks.json','Independent_Windows_2025.json')):
            data=json.loads(raw);data.update(policies())
            for field in ('external_python_removed_from_path','external_python_removed_from_child_path','external_python_removed_from_tested_launch_path'):data.pop(field,None)
            for record in data.get('records',[])+data.get('commands',[]):
                record.update(launch('Facility Studio 5.7.3.exe' if version=='2022' and name.endswith('Single_EXE_Verification.json') else exe))
            for capture in data.get('screenshots',[]):capture['process'].update(launch(exe))
            if name.endswith('Independent_Windows_2025.json'):data.update(python_launch_preflight=preflight(),python_installed_on_controller=True,application_launch_attempted=True)
            files[name]=json.dumps(data).encode()
    return files
