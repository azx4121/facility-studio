"""Offline owner-stage controls only. Never authorizes a real owner UI or upload."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import publish_verified_windows as p
import one_shot_guard as g
from test_publication import Fixture, FakeClient
from test_one_shot import ActivationFixture

class OwnerStageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.f=Fixture(self.root);self.c=FakeClient(self.f)
        self.final=p.FinalRelease(self.f.lock);self.guard=Mock();self.final.before_write=self.guard
        self.c.releases[402]=dict(id=402,draft=True,tag_name=self.final.tag,target_commitish=self.final.commit,
            name=self.final.name,body=self.final.body,prerelease=False,published_at=None,
            html_url=p.WEB+'/releases/tag/untagged-402')
        self.files=p.prepare_payloads(self.c,self.f.lock,self.f.gate(),self.root/'payload')
        self.check=Mock(side_effect=self.f.gate)
    def writes(self):
        return [(m,u) for m,u,a in self.c.calls if m in {'POST','PATCH','DELETE','PUT'}]
    def stage(self,rid=402):return self.final.stage_existing(self.c,rid,self.files,self.check)
    def test_only_three_asset_posts_and_ready_receipt(self):
        private=copy.deepcopy(self.c.releases[401]);result=self.stage()
        self.assertEqual(result['status'],'READY_FOR_OWNER_UI_PUBLICATION');self.assertFalse(result['published'])
        self.assertTrue(self.c.releases[402]['draft']);self.assertEqual(private,self.c.releases[401])
        self.assertEqual(len(self.writes()),3)
        self.assertTrue(all(m=='POST' and u.startswith(p.UPLOADS+'/releases/402/assets?') for m,u in self.writes()))
        self.assertGreaterEqual(self.guard.call_count,5);self.assertEqual(self.check.call_count,2)
    def test_missing_invalid_and_private_id(self):
        for rid in (None,0,-1,True,'402',401):
            with self.subTest(rid=rid),self.assertRaises((p.GateError,ValueError,TypeError)):self.stage(rid)
        self.assertEqual(self.writes(),[])
    def test_no_guard_rejected(self):
        self.final.before_write=None
        with self.assertRaises(p.GateError):self.stage()
        self.assertEqual(self.writes(),[])
    def test_metadata_mutations_rejected_before_writes(self):
        good=copy.deepcopy(self.c.releases[402])
        for key,value in dict(id=999,draft=False,tag_name='other',target_commitish='0'*40,name='other',body='other',prerelease=True,published_at='now').items():
            self.c.releases[402]=dict(good,**{key:value})
            with self.subTest(key=key),self.assertRaises(p.GateError):self.stage()
        self.assertEqual(self.writes(),[])
    def test_wrong_tag_target(self):
        self.c.tag_sha='0'*40
        with self.assertRaises(p.GateError):self.stage()
        self.assertEqual(self.writes(),[])
    def test_bad_existing_asset_blocks_all_uploads(self):
        self.c.add_asset(900,402,self.files[-1].name,b'wrong')
        with self.assertRaises(p.GateError):self.stage()
        self.assertEqual(self.writes(),[])
    def test_existing_asset_bad_readback_blocks_first_upload(self):
        path=self.files[-1];row=self.c.add_asset(900,402,path.name,path.read_bytes())
        rid,data,metadata=self.c.asset_data[900];self.c.asset_data[900]=(rid,b'corrupt',metadata)
        with self.assertRaises(p.GateError):self.stage()
        self.assertEqual(self.writes(),[])
    def test_unknown_existing_asset_blocks_all_uploads(self):
        self.c.add_asset(900,402,'unknown.txt',b'wrong')
        with self.assertRaises(p.GateError):self.stage()
        self.assertEqual(self.writes(),[])
    def test_existing_identical_assets_no_duplicate_uploads(self):
        for i,path in enumerate(self.files):self.c.add_asset(900+i,402,path.name,path.read_bytes())
        self.stage();self.assertEqual(self.writes(),[])
    def test_guard_failure_before_second_upload_stops(self):
        self.guard.side_effect=[None,None,p.GateError('expired')]
        with self.assertRaises(p.GateError):self.stage()
        self.assertEqual(len(self.writes()),1)
    def test_uncertain_upload_never_retry_or_publish(self):
        self.c.uncertain='upload'
        with self.assertRaises(p.GateError):self.stage()
        self.assertEqual(len(self.writes()),1);self.assertTrue(self.c.releases[402]['draft'])
    def test_changed_evidence_after_upload_no_ready_receipt(self):
        self.check.side_effect=[None,p.GateError('changed')]
        with self.assertRaises(p.GateError):self.stage()
        self.assertEqual(len(self.writes()),3);self.assertTrue(self.c.releases[402]['draft'])
    def test_failed_online_gate_prevents_upload(self):
        self.c.metadata['/actions/runs/303']['conclusion']='failure'
        with self.assertRaises(p.GateError):self.stage()
        self.assertEqual(self.writes(),[])
    def test_private_candidate_public_prevents_upload(self):
        self.c.releases[401]['draft']=False
        with self.assertRaises(p.GateError):self.stage()
        self.assertEqual(self.writes(),[])

class OwnerInvocationTests(unittest.TestCase):
    def test_positive_id_mandatory_and_exact(self):
        with tempfile.TemporaryDirectory() as folder:
            f=ActivationFixture(Path(folder));v=f.invocation;v['operation']='stage-existing'
            for value in (None,0,-1,True,'402'):
                v['resume_release_id']=value
                with self.subTest(value=value),self.assertRaises(ValueError):g.validate_invocation(v,f.lock,'stage-existing',value)
            v['resume_release_id']=402;g.validate_invocation(v,f.lock,'stage-existing',402)
            with self.assertRaises(ValueError):g.validate_invocation(v,f.lock,'stage-existing',403)
            with self.assertRaises(ValueError):g.validate_invocation(v,f.lock,'publish',402)
    def test_main_requires_one_shot_without_network(self):
        with patch.object(p,'pinned_json',return_value={'candidate':{'release_id':401}}),patch.object(p,'validate_lock',side_effect=lambda x:x),patch.object(p,'FinalRelease'),patch.object(p.t,'Client') as client:
            for rid in ('0','401','402'):
                with self.subTest(rid=rid),self.assertRaises(p.GateError):
                    p.main(['stage-existing','--lock','x','--lock-sha256','a'*64,'--release-id',rid])
            client.assert_not_called()
    def test_stage_existing_exact_context_and_negative_mutations(self):
        changes=[
            lambda f:f.environment.update(GITHUB_RUN_ATTEMPT='2'),
            lambda f:f.environment.update(GITHUB_REF='refs/heads/main'),
            lambda f:f.environment.update(GITHUB_EVENT_NAME='pull_request'),
            lambda f:f.environment.update(GITHUB_REPOSITORY='other/repo'),
            lambda f:f.environment.update(GITHUB_JOB='other'),
            lambda f:f.environment.update(FACS_EXPECTED_PUBLISHER_COMMIT='0'*40),
            lambda f:f.metadata[f.commit_path].update(parents=[dict(sha='0'*40)]),
            lambda f:f.metadata[f.commit_path]['files'].append(dict(filename='evil.py',status='added',sha='0'*40)),
            lambda f:f.metadata[f.ref_path]['object'].update(sha='0'*40),
            lambda f:f.metadata[f.run_path].update(run_attempt=2),
            lambda f:f.metadata[f.history_path].update(total_count=2),
            lambda f:f.invocation.update(expires_at='2000-01-01T00:00:00+00:00'),
        ]
        for change in [None]+changes:
            with tempfile.TemporaryDirectory() as folder:
                f=ActivationFixture(Path(folder));f.invocation.update(operation='stage-existing',resume_release_id=402);f.refresh()
                if change is None:self.assertEqual(f.authorize('stage-existing',402)['operation'],'stage-existing')
                else:
                    change(f)
                    if f.invocation['expires_at'].startswith('2000'):f.refresh()
                    with self.subTest(change=change),self.assertRaises((ValueError,KeyError,TypeError)):f.authorize('stage-existing',402)

class SafeInspectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.f=Fixture(Path(self.tmp.name));self.c=FakeClient(self.f);self.final=p.FinalRelease(self.f.lock)
    def capture(self,release_id=402):
        import io
        from contextlib import redirect_stdout
        output=io.StringIO()
        with redirect_stdout(output):self.final.inspect(self.c,release_id)
        return output.getvalue()
    def test_malicious_metadata_never_echoed(self):
        import json
        secret='SENSITIVE_SERVER_VALUE_TOKEN_URL'
        self.c.releases[402]=dict(id=402,draft=secret,tag_name=secret)
        self.c.asset_data[900]=(402,b'',dict(id=secret,name=secret,state=secret,size=secret))
        result=self.capture();self.assertNotIn(secret,result)
        row=json.loads(result)['releases'][0]
        self.assertEqual(row,dict(id=402,draft=None,tag='unknown',assets=[dict(id=None,name='unknown',state='unknown',bytes=None)]))
    def test_unbounded_boolean_and_nested_values_redacted(self):
        for value in (True,-1,0,2**100,{'secret':'never_echo'},['never_echo'],'never_echo'):
            self.c.releases[402]=dict(id=value,draft=value,tag_name=value)
            out=self.capture();self.assertNotIn('never_echo',out)
            self.assertFalse(any('/assets' in u for m,u,a in self.c.calls))
    def test_wrong_metadata_id_does_not_follow_other_release(self):
        self.c.releases[402]=dict(id=999,draft=True,tag_name=self.final.tag)
        self.capture();self.assertFalse(any('/999/assets' in u for m,u,a in self.c.calls))
    def test_valid_scoped_values_preserved(self):
        import json
        self.c.releases[402]=dict(id=402,draft=True,tag_name=self.final.tag)
        self.c.asset_data[900]=(402,b'',dict(id=900,name=p.EXE,state='uploaded',size=100))
        row=json.loads(self.capture())['releases'][0]
        self.assertEqual(row['tag'],self.final.tag);self.assertEqual(row['assets'][0]['bytes'],100)
    def test_uncertain_upload_hostile_inspection_still_stops_once(self):
        import io
        from contextlib import redirect_stdout
        path=Path(self.tmp.name)/p.EXE;path.write_bytes(b'fixture')
        # Use an otherwise valid scoped draft until the server rejects the upload.
        self.c.releases[402]=dict(id=402,draft=True,tag_name=self.final.tag,target_commitish=self.final.commit,
            name=self.final.name,body=self.final.body,prerelease=False,published_at=None,html_url=p.WEB+'/releases/tag/untagged-402')
        original=self.c.request
        def request(method,url,**kwargs):
            if method=='POST':
                self.c.calls.append((method,url,True));self.c.releases[402]['tag_name']='secret_never_echo'
                self.c.asset_data[900]=(402,b'',dict(id='secret_never_echo',name='secret_never_echo',state='secret_never_echo',size='secret_never_echo'))
                raise p.GateError('Synthetic uncertain')
            return original(method,url,**kwargs)
        self.c.request=request;output=io.StringIO()
        with redirect_stdout(output),self.assertRaises(p.GateError):self.final.upload(self.c,402,path)
        self.assertNotIn('secret_never_echo',output.getvalue())
        self.assertEqual(sum(m=='POST' for m,u,a in self.c.calls),1)
