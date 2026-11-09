"""Offline negative controls for exact-SHA branch activation. No network/writes outside fixtures."""
import copy
from contextlib import redirect_stdout
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import one_shot_guard as g
import publish_verified_windows as p
from test_publication import Fixture, FakeClient, encoded


class ActivationFixture:
    def __init__(self, root):
        self.root=root
        self.activation='a'*40
        self.publisher='f'*40
        self.lock={'publisher_commit':self.publisher,'private_run':{'workflow_id':111}}
        now=dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        lock_bytes=encoded(self.lock)
        review_bytes=encoded({'schema_version':2,'reviewer_role':'ai_assistant','fixture_only':True})
        self.invocation=dict(schema_version=1,repository=g.REPOSITORY,publisher_commit=self.publisher,
            operation='publish',lock_sha256=p.digest(lock_bytes),review_sha256=p.digest(review_bytes),
            prepared_at=now.isoformat(),expires_at=(now+dt.timedelta(hours=1)).isoformat(),
            nonce='b'*64,resume_release_id=None)
        for name,raw in {g.WORKFLOW:b'# synthetic activation workflow, not installed\n',
                        g.LOCK_FILE:lock_bytes,g.REVIEW_FILE:review_bytes,
                        g.INVOCATION_FILE:encoded(self.invocation)}.items():
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        branch=g.BRANCH_PREFIX+self.activation
        ref='refs/heads/'+branch
        self.environment={'GITHUB_REPOSITORY':g.REPOSITORY,'GITHUB_SHA':self.activation,
            'GITHUB_REF':ref,'GITHUB_EVENT_NAME':'push','GITHUB_RUN_ATTEMPT':'1',
            'GITHUB_JOB':'verify-same-bytes-2025', 'GITHUB_WORKSPACE':str(root),
            'GITHUB_WORKFLOW_REF':g.REPOSITORY+'/'+g.WORKFLOW+'@'+ref,
            'GITHUB_RUN_ID':'999','FACS_EXPECTED_PUBLISHER_COMMIT':self.publisher}
        self.commit_path='/commits/'+self.activation+'?per_page=100'
        self.ref_path='/git/ref/heads/'+branch
        self.run_path='/actions/runs/999'
        self.metadata={
            self.commit_path:dict(sha=self.activation,parents=[dict(sha=self.publisher)],files=[]),
            self.ref_path:dict(ref=ref,object=dict(type='commit',sha=self.activation)),
            self.run_path:dict(id=999,head_sha=self.activation,head_branch=branch,path=g.WORKFLOW,
                workflow_id=111,event='push',run_attempt=1,status='in_progress',conclusion=None,
                repository=dict(full_name=g.REPOSITORY),head_repository=dict(full_name=g.REPOSITORY)),
        }
        self.history_path='/actions/workflows/111/runs?head_sha='+self.activation+'&event=push&branch='+g.urllib.parse.quote(branch,safe='')+'&per_page=100&page=1'
        self.metadata[self.history_path]=dict(total_count=1,workflow_runs=[copy.deepcopy(self.metadata[self.run_path])])
        self.calls=[]
        self.refresh()

    def refresh(self):
        (self.root/g.INVOCATION_FILE).write_bytes(encoded(self.invocation))
        self.invocation_sha=p.digest((self.root/g.INVOCATION_FILE).read_bytes())
        self.metadata[self.commit_path]['files']=[dict(filename=name,
            status='modified' if name==g.WORKFLOW else 'added',sha=g.git_blob_sha((self.root/name).read_bytes()))
            for name in sorted(g.ALLOWED_CHANGED)]

    def get_json(self,path):
        self.calls.append(path)
        return copy.deepcopy(self.metadata[path])

    def git(self, workspace, *arguments):
        if arguments[0]=='rev-parse': return (self.activation+'\n').encode()
        if arguments[0]=='status': return b''
        raise AssertionError('Unexpected local Git command')

    def authorize(self,command='publish',release_id=None):
        with patch.dict(os.environ,self.environment,clear=True),patch.object(g,'git_read',side_effect=self.git):
            return g.authorize(self,self.lock,self.root/g.INVOCATION_FILE,self.invocation_sha,
                self.root/g.LOCK_FILE,self.root/g.REVIEW_FILE,command,release_id)


class OneShotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='activation-test-',dir=p.HERE)
        self.root=Path(self.temp.name)
        self.f=ActivationFixture(self.root)

    def tearDown(self): self.temp.cleanup()

    def reject(self):
        with self.assertRaises((ValueError,KeyError,TypeError)):
            self.f.authorize()

    def test_exact_first_push_context_is_read_only_and_accepted(self):
        self.assertEqual(self.f.authorize()['operation'],'publish')
        self.assertEqual(self.f.calls,[self.f.commit_path,self.f.ref_path,self.f.run_path,self.f.history_path])

    def test_pinned_branch_suffix_must_equal_activation_sha(self):
        self.f.environment['GITHUB_REF']='refs/heads/'+g.BRANCH_PREFIX+'c'*40
        self.reject()

    def test_original_validation_branch_cannot_use_fallback(self):
        self.f.environment['GITHUB_REF']='refs/heads/'+p.t.BRANCH
        self.reject()

    def test_main_cannot_use_fallback(self):
        self.f.environment['GITHUB_REF']='refs/heads/main'
        self.reject()

    def test_other_repository_rejected(self):
        self.f.environment['GITHUB_REPOSITORY']='other/repo'
        self.reject()

    def test_attempt_two_is_rejected_before_any_api_read(self):
        self.f.environment['GITHUB_RUN_ATTEMPT']='2'
        self.reject();self.assertEqual(self.f.calls,[])

    def test_live_rerun_attempt_rejected(self):
        self.f.metadata[self.f.run_path]['run_attempt']=2
        self.reject()

    def test_pull_request_event_rejected(self):
        self.f.environment['GITHUB_EVENT_NAME']='pull_request'
        self.reject()

    def test_other_workflow_rejected(self):
        self.f.environment['GITHUB_WORKFLOW_REF']=self.f.environment['GITHUB_WORKFLOW_REF'].replace('private-windows-handoff','other')
        self.reject()

    def test_other_job_rejected(self):
        self.f.environment['GITHUB_JOB']='some-other-writer'
        self.reject()

    def test_literal_publisher_pin_must_match_lock(self):
        self.f.environment['FACS_EXPECTED_PUBLISHER_COMMIT']='0'*40
        self.reject()

    def test_exact_single_reviewed_parent_required(self):
        self.f.metadata[self.f.commit_path]['parents']=[dict(sha='0'*40)]
        self.reject()

    def test_merge_parent_rejected(self):
        self.f.metadata[self.f.commit_path]['parents'].append(dict(sha='0'*40))
        self.reject()

    def test_publisher_code_change_rejected(self):
        self.f.metadata[self.f.commit_path]['files'].append(dict(filename=g.ROOT+'publish_verified_windows.py',status='modified',sha='0'*40))
        self.reject()

    def test_product_change_rejected(self):
        self.f.metadata[self.f.commit_path]['files'][0]['filename']='windows/facility_studio/window_geometry.py'
        self.reject()

    def test_wrong_committed_blob_rejected(self):
        self.f.metadata[self.f.commit_path]['files'][0]['sha']='0'*40
        self.reject()

    def test_renamed_file_rejected(self):
        self.f.metadata[self.f.commit_path]['files'][0]['previous_filename']='some-other-file'
        self.reject()

    def test_reused_old_invocation_file_rejected(self):
        row=next(r for r in self.f.metadata[self.f.commit_path]['files'] if r['filename']==g.INVOCATION_FILE)
        row['status']='modified'
        self.reject()

    def test_retired_or_moved_branch_rejected(self):
        self.f.metadata[self.f.ref_path]['object']['sha']='0'*40
        self.reject()

    def test_inactive_run_rejected(self):
        self.f.metadata[self.f.run_path].update(status='completed',conclusion='failure')
        self.reject()

    def test_unrelated_workflow_id_rejected(self):
        self.f.metadata[self.f.run_path]['workflow_id']=222
        self.reject()

    def test_fork_run_rejected(self):
        self.f.metadata[self.f.run_path]['head_repository']['full_name']='other/repo'
        self.reject()

    def test_expired_invocation_rejected(self):
        now=dt.datetime.now(dt.timezone.utc)
        self.f.invocation.update(prepared_at=(now-dt.timedelta(hours=2)).isoformat(),expires_at=(now-dt.timedelta(hours=1)).isoformat())
        self.f.refresh();self.reject()

    def test_excessive_persistent_lifetime_rejected(self):
        now=dt.datetime.now(dt.timezone.utc)
        self.f.invocation.update(expires_at=(now+dt.timedelta(days=2)).isoformat())
        self.f.refresh();self.reject()

    def test_wrong_operation_rejected(self):
        self.f.invocation['operation']='inspect';self.f.refresh();self.reject()

    def test_resume_id_cannot_be_injected_at_runtime(self):
        with self.assertRaises(ValueError): self.f.authorize(release_id=401)

    def test_explicit_inspected_resume_id_is_bound(self):
        self.f.invocation['resume_release_id']=402;self.f.refresh()
        self.assertEqual(self.f.authorize(release_id=402)['resume_release_id'],402)
        self.reject()

    def test_read_only_fetch_is_allowed_before_bound_publication(self):
        self.assertEqual(self.f.authorize(command='fetch-evidence')['operation'],'publish')

    def test_invocation_digest_mismatch_rejected(self):
        self.f.invocation_sha='0'*64
        self.reject()

    def test_locked_pixel_receipt_bytes_cannot_change(self):
        path=self.root/g.REVIEW_FILE;path.write_bytes(path.read_bytes()+b' ')
        self.reject()

    def test_wrong_local_head_rejected(self):
        self.f.git=lambda *args:b'0'*40+b'\n'
        self.reject()

    def test_dirty_local_checkout_rejected(self):
        self.f.git=lambda workspace,*args: (self.f.activation+'\n').encode() if args[0]=='rev-parse' else b' M publisher.py\n'
        self.reject()

    def test_second_distinct_first_attempt_push_is_rejected(self):
        old=copy.deepcopy(self.f.metadata[self.f.run_path])
        second=copy.deepcopy(old);second['id']=1000
        self.f.environment['GITHUB_RUN_ID']='1000'
        self.f.metadata['/actions/runs/1000']=second
        self.f.metadata[self.f.history_path]=dict(total_count=2,workflow_runs=[second,old])
        self.reject()

    def test_ambiguous_history_stops_even_original_run(self):
        self.f.metadata[self.f.history_path]['total_count']=2
        self.reject()

    def test_history_cannot_silently_select_other_run(self):
        self.f.metadata[self.f.history_path]['workflow_runs'][0]['id']=1000
        self.reject()

    def test_unknown_run_history_fails_closed(self):
        self.f.metadata[self.f.history_path]=dict(total_count=0,workflow_runs=[])
        self.reject()

    def test_crlf_converted_committed_bytes_are_rejected(self):
        path=self.root/g.WORKFLOW
        path.write_bytes(path.read_bytes().replace(b'\n',b'\r\n'))
        self.reject()

    def test_checkout_configures_exact_newlines_before_checkout(self):
        text=(p.HERE/'one-shot-publication.yml.template').read_text()
        block=text.split('      - uses: actions/checkout@',1)[1].split('      - uses:',1)[0]
        for value in ("GIT_CONFIG_COUNT: '2'",'GIT_CONFIG_KEY_0: core.autocrlf',"GIT_CONFIG_VALUE_0: 'false'",'GIT_CONFIG_KEY_1: core.eol','GIT_CONFIG_VALUE_1: lf'):
            self.assertIn(value,block)

    def test_job_environment_uses_no_unavailable_runner_context(self):
        text=(p.HERE/'one-shot-publication.yml.template').read_text()
        job_env=text.split('    env:\n',1)[1].split('    steps:\n',1)[0]
        self.assertNotRegex(job_env,r'\$\{\{[^}]*\brunner\s*\.')
        self.assertNotIn('FACS_RELEASE_EVIDENCE:',job_env)
        self.assertNotIn('GH_TOKEN:',job_env)

    def test_evidence_path_is_initialized_first_outside_clean_checkout_without_token(self):
        text=(p.HERE/'one-shot-publication.yml.template').read_text()
        steps=text.split('    steps:\n',1)[1]
        first_step=steps.split('      - ',2)[1]
        self.assertEqual(first_step,
            'name: Initialize runner-temp evidence path\n'
            '        shell: pwsh\n'
            '        run: |\n'
            '          "FACS_RELEASE_EVIDENCE=$env:RUNNER_TEMP/facs-final-evidence-$env:GITHUB_RUN_ID"'
            ' | Out-File -FilePath $env:GITHUB_ENV -Encoding utf8 -Append\n')
        self.assertNotIn('GH_TOKEN',first_step)
        self.assertNotIn('github.workspace',first_step)
        self.assertNotIn('GITHUB_WORKSPACE',first_step)
        self.assertLess(text.index('name: Initialize runner-temp evidence path'),text.index(' fetch-evidence '))

    def test_local_git_receives_no_tokens_and_does_not_lock_index(self):
        environment=dict(os.environ,GH_TOKEN='NEVER-PASS',GITHUB_TOKEN='NEVER-PASS',GIT_CONFIG_COUNT='1',ACTIONS_RUNTIME_TOKEN='NEVER-PASS')
        with patch.dict(os.environ,environment,clear=True),patch.object(g.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=b'clean')) as run:
            self.assertEqual(g.git_read(self.root,'status','--porcelain'),b'clean')
        args,kwargs=run.call_args
        self.assertIn('--no-optional-locks',args[0])
        self.assertFalse(any(k in kwargs['env'] for k in ('GH_TOKEN','GITHUB_TOKEN','ACTIONS_RUNTIME_TOKEN','GIT_CONFIG_COUNT')))

    def test_local_git_failure_does_not_leak_traceback_or_stderr(self):
        with patch.object(g.subprocess,'run',side_effect=g.subprocess.TimeoutExpired(['git','secret-string'],1)):
            with self.assertRaisesRegex(ValueError,'local activation checkout verification'):
                g.git_read(self.root,'status')

    def test_actual_ai_role_keeps_all_sixteen_review_images(self):
        directory=self.root/'fixture';directory.mkdir();fixture=Fixture(directory)
        fixture.review['reviewer_role']='ai_assistant'
        fixture.gate()
        fixture.review['captures'].pop()
        with self.assertRaises(p.GateError): fixture.gate()

    def test_human_role_is_honest_optional_alternative(self):
        directory=self.root/'fixture';directory.mkdir();fixture=Fixture(directory)
        fixture.review['reviewer_role']='human'
        fixture.gate()

    def test_old_human_only_schema_is_not_silently_accepted(self):
        directory=self.root/'fixture';directory.mkdir();fixture=Fixture(directory)
        fixture.review.update(schema_version=1,human_review_completed=True)
        with self.assertRaises(p.GateError): fixture.gate()

    def test_metadata_only_review_method_is_rejected(self):
        directory=self.root/'fixture';directory.mkdir();fixture=Fixture(directory)
        fixture.review['review_method']='metadata_only'
        with self.assertRaises(p.GateError): fixture.gate()

    def test_reauthorization_stops_before_release_creation(self):
        directory=self.root/'fixture';directory.mkdir();fixture=Fixture(directory)
        client=FakeClient(fixture)
        def stop(): raise p.GateError('Synthetic retired activation')
        with redirect_stdout(io.StringIO()),self.assertRaises(p.GateError):
            p.FinalRelease(fixture.lock,before_write=stop).create(client)
        self.assertFalse(any(m in {'POST','PATCH','DELETE'} for m,u,a in client.calls))

    def test_reauthorization_occurs_before_each_write(self):
        directory=self.root/'fixture';directory.mkdir();fixture=Fixture(directory)
        client=FakeClient(fixture);checks=[]
        with redirect_stdout(io.StringIO()):
            files=p.prepare_payloads(client,fixture.lock,fixture.gate(),directory/'payloads')
            final=p.FinalRelease(fixture.lock,before_write=lambda:checks.append(True))
            rid=final.create(client);assets=[final.upload(client,rid,file) for file in files]
            final.publish(client,rid,assets)
        self.assertEqual(len(checks),5)
        self.assertEqual(sum(m in {'POST','PATCH'} for m,u,a in client.calls),5)

    def test_local_renderer_emits_only_four_activation_changes(self):
        import prepare_one_shot as prepare
        directory=self.root/'fixture';directory.mkdir();fixture=Fixture(directory)
        lock=directory/'lock.json';review=directory/'review.json'
        lock.write_bytes(encoded(fixture.lock));review.write_bytes(encoded(fixture.review))
        with redirect_stdout(io.StringIO()):
            plan=prepare.prepare(lock,p.t.sha256(lock),review,p.t.sha256(review),directory,'publish',None,2,self.root/'prepared')
        self.assertEqual(set(plan['files']),g.ALLOWED_CHANGED)
        self.assertIsNone(plan['activation_commit']);self.assertIsNone(plan['activation_branch'])
        workflow=(self.root/'prepared'/'activation-files'/g.WORKFLOW).read_text()
        self.assertNotIn('REPLACE_',workflow)
        self.assertIn(fixture.lock['publisher_commit'],workflow)
        self.assertIn("github.run_attempt == 1",workflow)
        self.assertIn("format('refs/heads/validation/facs-v22-publish-{0}', github.sha)",workflow)

    def test_local_renderer_will_not_prepare_uninspected_candidate(self):
        import prepare_one_shot as prepare
        directory=self.root/'fixture';directory.mkdir();fixture=Fixture(directory)
        fixture.review['pixel_inspection_completed']=False
        lock=directory/'lock.json';review=directory/'review.json'
        lock.write_bytes(encoded(fixture.lock));review.write_bytes(encoded(fixture.review))
        with self.assertRaises(p.GateError):
            prepare.prepare(lock,p.t.sha256(lock),review,p.t.sha256(review),directory,'publish',None,2,self.root/'prepared')
        self.assertFalse((self.root/'prepared').exists())


if __name__=='__main__': unittest.main()
