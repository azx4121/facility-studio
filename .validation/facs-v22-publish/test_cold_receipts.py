"""Negative controls for cold receipt requirements. Entirely synthetic/offline."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import publish_verified_windows as p
import cold_receipts as c
import cold_test_fixtures as fixture
from test_publication import Fixture, FakeClient

class ColdReports(unittest.TestCase):
    def setUp(self):
        self.source=p.t.parse_json((p.HERE/'trusted-source-manifest.json').read_bytes())
        self.report=fixture.report(self.source,1920,1080)
    def gate(self):c.validate_report(self.report,'simple','en',c.hashes(self.source),1920,1080,p.require)
    def reject(self,mutation):
        mutation(self.report)
        with self.assertRaises((p.GateError,KeyError,TypeError,ValueError)):self.gate()
    def test_valid(self):self.gate()
    def test_native_backslash_hash_keys(self):
        self.report['source_sha256']={k.replace('/','\\'):v for k,v in self.report['source_sha256'].items()};self.gate()
    def test_missing_pass(self):self.reject(lambda r:r.pop('passed'))
    def test_wrong_language(self):self.reject(lambda r:r.update(language='zh-Hant'))
    def test_wrong_mode(self):self.reject(lambda r:r.update(mode='workbench'))
    def test_boolean_exit(self):self.reject(lambda r:r.update(entry_exit=False))
    def test_nonzero_exit(self):self.reject(lambda r:r.update(entry_exit=1))
    def test_probe_repair(self):self.reject(lambda r:r.update(probe_moves_or_resizes_window=True))
    def test_warm_import(self):self.reject(lambda r:r['views_imported_when_tk_created'].update({'facility_studio.desktop':True}))
    def test_missing_import_inventory(self):self.reject(lambda r:r['views_imported_when_tk_created'].clear())
    def test_hash_changed(self):self.reject(lambda r:r['source_sha256'].update({'integration/entry.py':'0'*64}))
    def test_duplicate_normalized_hash(self):self.reject(lambda r:r['source_sha256'].update({'integration\\entry.py':r['source_sha256']['integration/entry.py']}))
    def test_missing_hash(self):self.reject(lambda r:r['source_sha256'].pop('integration/entry.py'))
    def test_error(self):self.reject(lambda r:r['errors'].append('failure'))
    def test_event_error(self):self.reject(lambda r:r['events'][0].update(error='failure'))
    def test_missing_first_map(self):self.reject(lambda r:r['events'].pop(0))
    def test_missing_placement_return(self):self.reject(lambda r:r['events'].pop(2))
    def test_missing_stable_sample(self):self.reject(lambda r:r['events'].pop())
    def test_samples_disagree(self):self.reject(lambda r:r['events'][-1]['native'].update(menu=30))
    def test_nan_time(self):self.reject(lambda r:r['events'][-1].update(elapsed=float('nan')))
    def test_short_duration(self):self.reject(lambda r:[e.update(elapsed=1+i*.01) for i,e in enumerate(r['events'][-6:])])
    def test_boolean_time(self):self.reject(lambda r:r['events'][0].update(elapsed=False))
    def test_unstable(self):self.reject(lambda r:r.update(stable=False))
    def test_false_containment(self):self.reject(lambda r:r['containment'].update(outer=False))
    def test_escaped_rectangle_recomputed(self):
        self.report['settled']['outer'][3]=1093
        for e in self.report['events'][-6:]:e['native']=copy.deepcopy(self.report['settled'])
        with self.assertRaises(p.GateError):self.gate()
    def test_native_fields(self):
        for field,value in [('hwnd',0),('menu',False),('dpi',0),('dwm_hresult',1),('state','withdrawn'),('title',''),('outer',[1,2,1,2]),('work',[0,0,1921,1080])]:
            with self.subTest(field=field):
                self.report=fixture.report(self.source,1920,1080);self.report['settled'][field]=value
                for e in self.report['events'][-6:]:e['native']=copy.deepcopy(self.report['settled'])
                with self.assertRaises(p.GateError):self.gate()

class ColdArchives(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.f=Fixture(Path(self.tmp.name))
    def tearDown(self):self.tmp.cleanup()
    def mutate_xml(self,mutator,role='source',version='2022',width=1920,height=1080):
        prefix='' if role=='source' else '0-facs-v22-evidence/prebuild-'
        name=f'{prefix}cold-startup-placement-{width}-{height}.xml'
        tree=ET.fromstring(self.f.files[role+version][name]);mutator(tree)
        self.f.files[role+version][name]=ET.tostring(tree);self.f.zip(role,version)
    def fails(self):
        with self.assertRaises((p.GateError,KeyError,TypeError,ValueError)):self.f.gate()
    def test_missing_every_required_cold_archive_member(self):
        for role,version in [('source','2022'),('source','2025'),('private','2022')]:
            for width,height in [(1920,1080),(1024,768)]:
                for kind in ['placement','display']:
                    with self.subTest(role=role,version=version,size=width,kind=kind):
                        prefix='' if role=='source' else '0-facs-v22-evidence/prebuild-'
                        ext='xml' if kind=='placement' else 'json';name=f'{prefix}cold-startup-{kind}-{width}-{height}.{ext}'
                        old=self.f.files[role+version].pop(name);self.f.zip(role,version);self.fails()
                        self.f.files[role+version][name]=old;self.f.zip(role,version)
    def test_missing_readout(self):self.mutate_xml(lambda t:t.find('.//properties').clear());self.fails()
    def test_duplicate_readout(self):
        self.mutate_xml(lambda t:t.find('.//properties').append(copy.deepcopy(t.find('.//property'))));self.fails()
    def test_wrong_case_name(self):self.mutate_xml(lambda t:t.find('.//testcase').set('name','test_native_untouched_warm'));self.fails()
    def test_wrong_display_target(self):
        self.f.change('source','2022','cold-startup-display-1920-1080.json',lambda r:r.update(command=['python','test_windows_startup_placement.py','-k','native_untouched','--capture=sys']));self.fails()
    def test_skipped_cold_case(self):self.mutate_xml(lambda t:ET.SubElement(t.find('.//testcase'),'skipped'));self.fails()
    def test_failed_cold_report(self):
        def mutate(t):
            prop=t.find('.//property');r=json.loads(prop.get('value'));r['passed']=False;prop.set('value',json.dumps(r))
        self.mutate_xml(mutate);self.fails()
    def test_readout_workarea_must_match_measured_display(self):
        self.f.change('source','2022','cold-startup-display-1920-1080.json',lambda r:r['after'].update(work_area=[0,0,1920,1030]));self.fails()
    def test_no_cold_readout_bypasses_exact_frozen_requirement(self):
        self.f.change('private','2025','1-facs-v22-independent-2025/Independent_Windows_2025.json',lambda r:r.update(passed=False));self.fails()
    def test_live_cold_step_missing_or_skipped(self):
        for role,version in [('source','2022'),('source','2025'),('private','2022')]:
            for mutation in ('missing','skipped'):
                with self.subTest(role=role,version=version,mutation=mutation):
                    client=FakeClient(self.f);job=client.metadata['/actions/jobs/'+str(self.f.lock[role+'_run']['jobs'][version]['id'])]
                    name=next(name for name in (p.SOURCE_STEPS if role=='source' else p.PRIVATE_STEPS['2022']) if 'cold real-entry' in name.lower())
                    if mutation=='missing':job['steps']=[s for s in job['steps'] if s['name']!=name]
                    else:next(s for s in job['steps'] if s['name']==name).update(conclusion='skipped')
                    with self.assertRaises(p.GateError):p.online_gate(client,self.f.lock)
    def test_live_warm_cold_full_order(self):
        for role,version in [('source','2022'),('source','2025'),('private','2022')]:
            for number in (0,999):
                with self.subTest(role=role,version=version,number=number):
                    client=FakeClient(self.f);job=client.metadata['/actions/jobs/'+str(self.f.lock[role+'_run']['jobs'][version]['id'])]
                    name=next(name for name in (p.SOURCE_STEPS if role=='source' else p.PRIVATE_STEPS['2022']) if 'cold real-entry' in name.lower())
                    next(s for s in job['steps'] if s['name']==name)['number']=number
                    with self.assertRaises(p.GateError):p.online_gate(client,self.f.lock)
