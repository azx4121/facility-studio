"""Offline R6 negatives: process image completeness, native controls, semantic fit."""
import copy,json,tempfile,unittest,ntpath
from pathlib import Path
import xml.etree.ElementTree as ET
import publish_verified_windows as p
import process_receipts as pr
import r6_test_fixtures as r6
from test_publication import Fixture,FakeClient

class ProcessAudit(unittest.TestCase):
    def setUp(self):self.row=r6.launch(p.EXE)
    def gate(self):pr.record(self.row,p.EXE,p.require)
    def reject(self,mutate):
        mutate(self.row)
        with self.assertRaises((p.GateError,KeyError,TypeError,ValueError)):self.gate()
    def test_valid_same_exe_bootloader_children(self):self.gate()
    def test_case_and_separator_normalized(self):
        for image in self.row['process_image_audit']['images']:image['image']=image['image'].upper().replace('/','\\')
        self.gate()
    def test_foreign_python_image(self):self.reject(lambda r:r['process_image_audit']['images'][1].update(image='C:/Python/python.exe'))
    def test_different_same_named_exe(self):self.reject(lambda r:r['process_image_audit']['images'][1].update(image='C:/elsewhere/'+p.EXE))
    def test_relative_image(self):self.reject(lambda r:r['process_image_audit']['images'][0].update(image=p.EXE))
    def test_drive_relative_image(self):self.reject(lambda r:r['process_image_audit']['images'][0].update(image='C:'+p.EXE))
    def test_root_relative_image(self):self.reject(lambda r:r['process_image_audit']['images'][0].update(image='/synthetic/'+p.EXE))
    def test_wrong_command(self):self.reject(lambda r:r.update(command=['C:/Python/python.exe']))
    def test_no_command(self):self.reject(lambda r:r.pop('command'))
    def test_no_audit(self):self.reject(lambda r:r.pop('process_image_audit'))
    def test_no_image(self):self.reject(lambda r:r['process_image_audit']['images'].clear())
    def test_duplicate_pid(self):self.reject(lambda r:r['process_image_audit']['images'][1].update(pid=1))
    def test_boolean_pid(self):self.reject(lambda r:r['process_image_audit']['images'][0].update(pid=True))
    def test_zero_pid(self):self.reject(lambda r:r['process_image_audit']['images'][0].update(pid=0))
    def test_missing_process_coverage(self):self.reject(lambda r:r['process_image_audit'].update(total_job_processes=3))
    def test_missing_handle_coverage(self):self.reject(lambda r:r['process_image_audit'].update(retained_process_handles=3))
    def test_boolean_count(self):self.reject(lambda r:r['process_image_audit'].update(total_job_processes=True))
    def test_disabled_audit(self):self.reject(lambda r:r['process_image_audit'].update(required=False))
    def test_failed_audit(self):self.reject(lambda r:r['process_image_audit'].update(passed=False))
    def test_query_error(self):self.reject(lambda r:r['process_image_audit'].update(errors=['QueryFullProcessImageNameW failed']))
    def test_obsolete_or_false_policies(self):
        for field,value in [('launch_path_policy','normal'),('external_python_absence_claimed',True),('standalone_process_image_audit_required',False),('standalone_process_image_audit_passed',False),('installation_performed',True),('external_python_removed_from_path',True),('external_python_removed_from_child_path',True),('external_python_removed_from_tested_launch_path',True)]:
            with self.subTest(field=field):
                data=r6.policies();data[field]=value
                with self.assertRaises(p.GateError):pr.summary(data,p.require)
    def test_system_launcher_is_allowed_and_reported(self):pr.launch_preflight(r6.preflight(),p.require)
    def test_host_scan_cannot_claim_absence(self):
        for field,value in [('machine_python_absence_claimed',True),('absolute_path_execution_blocked',True),('process_execution_policy_enforced',True),('unsafe_path_entries',['.']),('path_and_implicit_directory_scan_passed',True),('path_entries',['C:/Windows/System32','.'])]:
            with self.subTest(field=field):
                data=r6.preflight();data[field]=value
                with self.assertRaises(p.GateError):pr.launch_preflight(data,p.require)

class R6Archives(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.f=Fixture(Path(self.tmp.name))
    def tearDown(self):self.tmp.cleanup()
    def fails(self):
        with self.assertRaises((p.GateError,ValueError,TypeError,KeyError)):self.f.gate()
    def xml(self,role,version,name,mutate):
        tree=ET.fromstring(self.f.files[role+version][name]);mutate(tree)
        self.f.files[role+version][name]=ET.tostring(tree);self.f.zip(role,version)
    def property(self,tree,name,mutate):
        prop=tree.find('.//property[@name="'+name+'"]');value=json.loads(prop.get('value'));mutate(value);prop.set('value',json.dumps(value))
    def private_name(self,version,suffix):return ('1-evidence/' if version=='2022' else '1-facs-v22-independent-2025/')+suffix
    def external_name(self,version):return ('0-facs-v22-evidence/' if version=='2022' else '1-facs-v22-independent-2025/')+'external-frozen/Frozen_External_Checks.json'
    def test_each_builtin_command_and_capture_requires_audit(self):
        # Exhaustive entries on each host, exercising per-record validation directly.
        for version in ['2022','2025']:
            frozen=json.loads(self.f.files['private'+version][self.private_name(version,'single-exe/Single_EXE_Verification.json')]);ext=json.loads(self.f.files['private'+version][self.external_name(version)])
            rows=frozen['records']+ext['commands']+[x['process'] for x in ext['screenshots']]
            self.assertEqual(len(rows),130)
            for index,row in enumerate(rows):
                with self.subTest(version=version,index=index):
                    expected_name=ntpath.basename(row['command'][0])
                    pr.record(row,expected_name,p.require)
                    row.pop('process_image_audit')
                    with self.assertRaises(p.GateError):pr.record(row,expected_name,p.require)
    def test_builtin_missing_audit_blocks_publication(self):
        self.f.change('private','2022',self.private_name('2022','single-exe/Single_EXE_Verification.json'),lambda r:r['records'][0].pop('process_image_audit'));self.fails()
    def test_expected_refusal_requires_audit(self):
        self.f.change('private','2025',self.external_name('2025'),lambda r:next(x for x in r['commands'] if x['expected_exit']==2).pop('process_image_audit'));self.fails()
    def test_capture_requires_audit(self):
        self.f.change('private','2025',self.external_name('2025'),lambda r:r['screenshots'][0]['process'].pop('process_image_audit'));self.fails()
    def test_consumer_must_have_actually_launched(self):
        self.f.change('private','2025','1-facs-v22-independent-2025/Independent_Windows_2025.json',lambda r:r.update(application_launch_attempted=False));self.fails()
    def test_missing_native_preflight_on_every_host(self):
        for role,version in [('source','2022'),('source','2025'),('private','2022'),('private','2025')]:
            for filename in ['process-image-preflight.xml','python-launch-preflight.json']:
                with self.subTest(role=role,version=version,filename=filename):
                    name=('' if role=='source' else '0-facs-v22-evidence/')+filename
                    old=self.f.files[role+version].pop(name);self.f.zip(role,version);self.fails()
                    self.f.files[role+version][name]=old;self.f.zip(role,version)
    def test_native_control_query_failure_not_real_foreign_negative(self):
        def change(tree):
            props=tree.findall('.//property');r=json.loads(props[1].get('value'));r['process_image_audit']['errors']=['QueryFullProcessImageNameW failed'];props[1].set('value',json.dumps(r))
        self.xml('source','2022','process-image-preflight.xml',change);self.fails()
    def test_native_positive_missing_child(self):
        self.xml('private','2025','0-facs-v22-evidence/process-image-preflight.xml',lambda t:self.property(t,'process_image_preflight',lambda r:r['process_image_audit']['images'].pop()));self.fails()
    def test_skipped_synthetic_preflight(self):
        self.xml('source','2025','process-image-preflight.xml',lambda t:ET.SubElement(t.find('.//testcase'),'skipped'));self.fails()
    def test_missing_semantic_every_resolution_and_host(self):
        for role,version in [('source','2022'),('source','2025'),('private','2022')]:
            for w,h in [(1920,1080),(1024,768)]:
                for tail in [f'native-language-fit-{w}-{h}.xml',f'native-language-fit-display-{w}-{h}.json']:
                    with self.subTest(role=role,version=version,tail=tail):
                        name=('' if role=='source' else '0-facs-v22-evidence/prebuild-')+tail
                        old=self.f.files[role+version].pop(name);self.f.zip(role,version);self.fails()
                        self.f.files[role+version][name]=old;self.f.zip(role,version)
    def test_wrong_language_menu(self):
        self.xml('source','2022','native-language-fit-1920-1080.xml',lambda t:self.property(t,'native_language_fit',lambda r:r[0].update(top=['Wrong'])));self.fails()
    def test_wrong_actual_semantic_resolution(self):
        self.xml('source','2022','native-language-fit-1920-1080.xml',lambda t:self.property(t,'native_language_fit',lambda r:r[0].update(screen_size=[1600,1200])));self.fails()
    def test_selector_vertical_clip(self):
        def change(tree):
            prop=tree.findall('.//property')[2];rows=json.loads(prop.get('value'));rows[0]['selectors'][0]['client_bounds']=[10,590,110,620];prop.set('value',json.dumps(rows))
        self.xml('source','2022','native-language-fit-1920-1080.xml',change);self.fails()
    def test_live_preflight_and_semantic_order(self):
        for role,version in [('source','2022'),('source','2025'),('private','2022'),('private','2025')]:
            with self.subTest(role=role,version=version):
                c=FakeClient(self.f);job=c.metadata['/actions/jobs/'+str(self.f.lock[role+'_run']['jobs'][version]['id'])]
                first=next(s for s in job['steps'] if s['number']==1);first['number']=999
                with self.assertRaises(p.GateError):p.online_gate(c,self.f.lock)
    def test_public_note_truthful_scope(self):
        note=p.release_note(self.f.lock)
        self.assertIn('Python was installed for the test controllers',note)
        self.assertIn('not a Python-free-host test',note)
        self.assertIn('same copied EXE',note)
    def test_producer_prerename_builtin_name_is_required(self):
        name=self.private_name('2022','single-exe/Single_EXE_Verification.json')
        data=json.loads(self.f.files['private2022'][name])
        self.assertTrue(all(r['command'][0].endswith('/Facility Studio 5.7.3.exe') for r in data['records']))
        self.f.gate()
        data['records'][0].update(r6.launch(p.EXE));self.f.files['private2022'][name]=json.dumps(data).encode();self.f.zip('private','2022');self.fails()
    def test_consumer_cannot_use_producer_prerename_name(self):
        name=self.private_name('2025','single-exe/Single_EXE_Verification.json')
        self.f.change('private','2025',name,lambda r:r['records'][0].update(r6.launch('Facility Studio 5.7.3.exe')));self.fails()
    def test_synthetic_base_executable_must_match_command(self):
        self.xml('source','2022','process-image-preflight.xml',lambda t:self.property(t,'process_image_preflight',lambda r:r.update(synthetic_base_executable='C:/wrong/python.exe')));self.fails()
    def test_missing_synthetic_controller_metadata(self):
        self.xml('private','2025','0-facs-v22-evidence/process-image-preflight.xml',lambda t:self.property(t,'process_image_preflight',lambda r:r.pop('synthetic_controller_executable')));self.fails()

class R7OwnerDrawObservation(unittest.TestCase):
    def setUp(self):self.observation=r6.menu_observation('en')
    def gate(self):p.semantic_receipts.validate_menu_observation(self.observation,'en')
    def test_owner_draw_both_languages_with_or_without_master_tearoff(self):
        for language in ('en','zh-Hant'):
            for tearoff in (True,False):p.semantic_receipts.validate_menu_observation(r6.menu_observation(language,tearoff),language)
    def test_explicit_string_backed_disabled_command(self):
        item=self.observation['native']['top'][0]['children'][0]
        item.update(ftype=0,state=3,data=0,native_text='About Facility Studio',label_source='win32.GetMenuStringW')
        self.observation['tk_metadata']['top'][1]['children'][0]['state']='disabled';self.gate()
    def test_corrupt_native_tk_linkage_rejected(self):
        mutations={
          'absent_observation':lambda o:o.clear(),
          'popup_pixel_overclaim':lambda o:o.update(popup_pixels_verified=True),
          'no_hwnd':lambda o:o['native'].update(hwnd=0),
          'boolean_hwnd':lambda o:o['native'].update(hwnd=True),
          'no_menu':lambda o:o['native'].update(menu=0),
          'foreign_root_attachment':lambda o:o['tk_metadata'].update(attached_menu='.foreign'),
          'empty_root_attachment':lambda o:o['tk_metadata'].update(attached_menu='',authored_menu=''),
          'no_tk_version':lambda o:o['tk_metadata'].pop('tk_version'),
          'extra_registered_menu':lambda o:o['tk_metadata']['authored_submenus'].append('.menu.extra'),
          'missing_registered_menu':lambda o:o['tk_metadata']['authored_submenus'].pop(),
          'duplicate_registered_menu':lambda o:o['tk_metadata']['authored_submenus'].__setitem__(1,'.menu.0'),
          'foreign_submenu_tree':lambda o:o['tk_metadata']['authored_submenus'].__setitem__(0,'.other.0'),
          'wrong_registered_order':lambda o:o['tk_metadata']['authored_submenus'].reverse(),
          'extra_tearoff':lambda o:o['tk_metadata']['top'].insert(1,dict(index=1,type='tearoff')),
          'boolean_tearoff_index':lambda o:o['tk_metadata']['top'][0].update(index=False),
          'wrong_top_count':lambda o:o['native']['top'].pop(),
          'wrong_tk_top_count':lambda o:o['tk_metadata']['top'].pop(),
          'wrong_top_index':lambda o:o['tk_metadata']['top'][1].update(index=2),
          'wrong_top_type':lambda o:o['tk_metadata']['top'][1].update(type='command'),
          'top_disabled':lambda o:o['tk_metadata']['top'][1].update(state='disabled'),
          'empty_win32_top':lambda o:o['native']['top'][0].update(native_text=''),
          'top_native_text_label_disagree':lambda o:o['native']['top'][0].update(native_text='Other'),
          'wrong_top_language':lambda o:o['native']['top'][0].update(label='Other',native_text='Other'),
          'ownerdraw_top_not_string':lambda o:o['native']['top'][0].update(ftype=0x100),
          'unknown_top_state':lambda o:o['native']['top'][0].update(state=1),
          'boolean_top_state':lambda o:o['native']['top'][0].update(state=False),
          'missing_submenu_handle':lambda o:o['native']['top'][0].update(submenu=0,queried_submenu=0),
          'mismatched_getsubmenu':lambda o:o['native']['top'][0].update(queried_submenu=999),
          'duplicate_native_submenu':lambda o:o['native']['top'][1].update(submenu=300,queried_submenu=300),
          'foreign_tk_submenu':lambda o:o['tk_metadata']['top'][1].update(submenu='.foreign'),
          'child_count':lambda o:o['native']['top'][0]['children'].clear(),
          'child_wrong_index':lambda o:o['tk_metadata']['top'][1]['children'][0].update(index=1),
          'child_separator':lambda o:o['tk_metadata']['top'][1]['children'][0].update(type='separator'),
          'empty_callback':lambda o:o['tk_metadata']['top'][1]['children'][0].update(command=''),
          'empty_tk_label':lambda o:o['tk_metadata']['top'][1]['children'][0].update(label=''),
          'wrong_tk_label':lambda o:o['tk_metadata']['top'][1]['children'][0].update(label='Wrong'),
          'unknown_tk_state':lambda o:o['tk_metadata']['top'][1]['children'][0].update(state='active'),
          'native_tk_state_mismatch':lambda o:o['native']['top'][0]['children'][0].update(state=3),
          'foreign_child_submenu':lambda o:o['native']['top'][0]['children'][0].update(submenu=999),
          'zero_native_id':lambda o:o['native']['top'][0]['children'][0].update(id=0),
          'boolean_native_id':lambda o:o['native']['top'][0]['children'][0].update(id=True),
          'sentinel_native_id':lambda o:o['native']['top'][0]['children'][0].update(id=0xffffffff),
          'duplicate_native_id':lambda o:o['native']['top'][1]['children'][0].update(id=1),
          'zero_ownerdraw_data':lambda o:o['native']['top'][0]['children'][0].update(data=0),
          'boolean_ownerdraw_data':lambda o:o['native']['top'][0]['children'][0].update(data=True),
          'duplicate_ownerdraw_data':lambda o:o['native']['top'][1]['children'][0].update(data=1001),
          'unknown_native_type':lambda o:o['native']['top'][0]['children'][0].update(ftype=4),
          'native_separator':lambda o:o['native']['top'][0]['children'][0].update(ftype=0x900),
          'ownerdraw_unclassified_text':lambda o:o['native']['top'][0]['children'][0].update(native_text='Unexpected'),
          'ownerdraw_false_native_label_source':lambda o:o['native']['top'][0]['children'][0].update(label_source='win32.GetMenuStringW'),
          'wrong_observed_label':lambda o:o['native']['top'][0]['children'][0].update(observed_label='Wrong'),
          'empty_string_backed':lambda o:o['native']['top'][0]['children'][0].update(ftype=0,label_source='win32.GetMenuStringW'),
        }
        for name,mutate in mutations.items():
            with self.subTest(name=name):
                self.observation=r6.menu_observation('en');mutate(self.observation)
                with self.assertRaises((ValueError,TypeError,KeyError)):self.gate()

class R7Archives(unittest.TestCase):
    setUp=R6Archives.setUp
    tearDown=R6Archives.tearDown
    fails=R6Archives.fails
    xml=R6Archives.xml
    property=R6Archives.property
    def test_menu_observation_absent_fails_real_archive_gate(self):
        self.xml('source','2022','native-language-fit-1920-1080.xml',lambda t:self.property(t,'native_language_fit',lambda r:r[0].pop('menu_observation')));self.fails()
    def test_native_top_string_disagreement_fails_archive_gate(self):
        self.xml('private','2022','0-facs-v22-evidence/prebuild-native-language-fit-1024-768.xml',lambda t:self.property(t,'native_language_fit',lambda r:r[0]['menu_observation']['native']['top'][0].update(native_text='Wrong')));self.fails()
    def test_live_semantic_must_precede_cold(self):
        for role,version in [('source','2022'),('source','2025'),('private','2022')]:
            c=FakeClient(self.f);job=c.metadata['/actions/jobs/'+str(self.f.lock[role+'_run']['jobs'][version]['id'])]
            semantic,cold=(p.SOURCE_STEPS[1:3] if role=='source' else p.PRIVATE_STEPS['2022'][1:3])
            self.assertIn('bilingual',semantic);self.assertIn('cold',cold.lower())
            a=next(s for s in job['steps'] if s['name']==semantic);b=next(s for s in job['steps'] if s['name']==cold);a['number'],b['number']=b['number'],a['number']
            with self.assertRaises(p.GateError):p.online_gate(c,self.f.lock)
    def test_popup_scope_note_is_explicit(self):
        note=p.release_note(self.f.lock)
        self.assertIn('not popup pixel proof',note)
        self.assertIn('Tk label metadata',note)
