"""Offline safeguards for narrowly scoped native crash-report collection."""
import importlib.util
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

SPEC = importlib.util.spec_from_file_location(
    'native_probe_under_test', Path(__file__).resolve().parents[1]/'macos/native_probe.py')
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class CrashPrivacy(unittest.TestCase):
    def test_only_this_process_and_app_after_launch_are_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports, retained, app = root/'reports', root/'retained', root/'Facility Studio.app'
            reports.mkdir()
            now = time.time()
            process = dict(name='continuous_dump25', pid=123, started_at=now-2, finished_at=now)
            def report(name, pid=123, path=None, captured=now-1, modified=now-1):
                target = reports/name
                payload = dict(pid=pid, procName='FacilityStudio',
                    procPath=path or str(app.resolve()/'Contents/MacOS/FacilityStudio'),
                    captureTime=datetime.fromtimestamp(captured, timezone.utc).isoformat(),
                    private_payload='Never upload a report failing any identity constraint.')
                target.write_text(json.dumps({'app_name': 'FacilityStudio'})+'\n'+json.dumps(payload))
                os.utime(target, (modified, modified))
                return target
            good = report('FacilityStudio_good.ips')
            # Reporter writes late, but its capture belongs to this process.
            delayed = dict(name='old_phase', pid=124, started_at=now-102, finished_at=now-100)
            report('FacilityStudio_delayed.ips', pid=124, captured=now-101, modified=now-1)
            report('Python_other_pid.ips', pid=999)
            report('FacilityStudio_other_app.ips', path=str(root/'Different.app/Contents/MacOS/FacilityStudio'))
            report('FacilityStudio_similar_prefix.ips', path=str(app)+'-unrelated/Contents/MacOS/FacilityStudio')
            report('FacilityStudio_old_capture.ips', captured=now-100)
            report('FacilityStudio_old_file.ips', modified=now-100)
            report('UnrelatedProcess.ips')
            (reports/'FacilityStudio_link.ips').symlink_to(good)
            saved = probe.collect_probe_crashes(reports, retained, [process, delayed], app)
            self.assertEqual(len(saved), 2)
            first = next(record for record in saved if record['identity']['pid'] == 123)
            self.assertEqual(first['phases'], ['continuous_dump25'])
            self.assertEqual(sorted(p.name for p in retained.iterdir()),
                ['ProbeCrash_123_FacilityStudio_good.ips', 'ProbeCrash_124_FacilityStudio_delayed.ips'])

    def test_incomplete_or_unparseable_report_is_not_uploaded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root/'reports'; reports.mkdir()
            now = time.time()
            process = dict(name='phase', pid=123, started_at=now-2, finished_at=now)
            (reports/'FacilityStudio_incomplete.ips').write_text('{"pid":123,"procPath":"x"}')
            (reports/'FacilityStudio_invalid.ips').write_text('not JSON')
            result = probe.collect_probe_crashes(reports, root/'out', [process], root/'App.app')
            self.assertEqual(result, [])
            self.assertFalse((root/'out').exists())

    def test_module_identity_and_bootstrap_constants_are_separate(self):
        self.assertEqual(probe.RELEASE_SHA256, 'aef324d08815257848e4b8080023611b41a4a88eb2cdd03e6ee1a71e5a983b65')
        self.assertIn('v5.5.4-beta.1/', probe.RELEASE_URL)
        self.assertEqual(probe.PROBE_RELEASE_SHA256, 'e7d0033a3d3256b530539a6bdaa7d7d670ff043828dd69a5166e5e9ba2b679c8')
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory)/'Facility Studio.app'
            source = app/'Contents/Resources/app/facility_studio/engine.py'
            source.parent.mkdir(parents=True)
            source.write_text('original module')
            baseline = probe.source_hashes(app)
            self.assertEqual(probe.source_hashes(app), baseline)
            source.write_text('unexpected mutation')
            self.assertNotEqual(probe.source_hashes(app), baseline)

    def test_faulting_native_thread_is_not_confused_with_sampled_main_thread(self):
        text = json.dumps({'app_name': 'FacilityStudio'})+'\n'+json.dumps({
            'faultingThread': 1,
            'threads': [
                {'name': 'main', 'frames': [{'symbol': 'Tcl_DoOneEvent', 'imageIndex': 0}]},
                {'name': 'watchdog', 'frames': [{'symbol': '_Py_DumpASCII', 'imageIndex': 1}]},
            ], 'usedImages': [{'name': 'Tcl'}, {'name': 'Python'}],
            'exception': {'type': 'EXC_BAD_ACCESS'},
        })
        summary = probe.faulting_thread_summary(text)
        self.assertEqual(summary['name'], 'watchdog')
        self.assertEqual(summary['frames'][0]['symbol'], '_Py_DumpASCII')
        self.assertEqual(summary['frames'][0]['image'], 'Python')

    def test_external_helper_requires_exact_path_pid_time_and_app_invocation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app, helper, reports, retained = root/'Facility Studio.app', root/'FacilityStudioProbe', root/'reports', root/'out'
            reports.mkdir()
            now = time.time()
            process = dict(name='external_probe', pid=234, started_at=now-2, finished_at=now,
                           diagnostic_executable=str(helper.resolve()), app_path=str(app.resolve()))
            def create(name, pid=234, path=None, captured=now-1):
                source = reports/name
                source.write_text(json.dumps(dict(pid=pid, procName='FacilityStudioProbe',
                    procPath=path or str(helper.resolve()),
                    captureTime=datetime.fromtimestamp(captured, timezone.utc).isoformat())))
            create('FacilityStudioProbe_good.ips')
            create('FacilityStudioProbe_neighbor.ips', path=str(helper.resolve())+'-neighbor')
            create('FacilityStudioProbe_fake_name.ips', path=str(root/'other/FacilityStudioProbe'))
            create('FacilityStudioProbe_wrong_pid.ips', pid=235)
            create('FacilityStudioProbe_old_capture.ips', captured=now-100)
            saved = probe.collect_probe_crashes(reports, retained, [process], app)
            self.assertEqual([row['file'] for row in saved], ['ProbeCrash_234_FacilityStudioProbe_good.ips'])
            wrong_app = dict(process, app_path=str(root/'unrelated.app'))
            self.assertEqual(probe.collect_probe_crashes(reports, root/'rejected', [wrong_app], app), [])

    def test_sample_header_requires_probe_pid_and_exact_helper_path(self):
        with tempfile.TemporaryDirectory() as directory:
            helper = Path(directory)/'FacilityStudioProbe'
            good = 'Process: FacilityStudioProbe [345]\nPath: '+str(helper)+'\nCall graph:\n'
            self.assertTrue(probe.sample_matches_process(good, 345, helper))
            self.assertFalse(probe.sample_matches_process(good, 346, helper))
            self.assertFalse(probe.sample_matches_process(good.replace(str(helper), str(helper)+'-neighbor'), 345, helper))
            self.assertFalse(probe.sample_matches_process('Process: FacilityStudioProbe [345]\nPath: /elsewhere/FacilityStudioProbe\n', 345, helper))
            self.assertFalse(probe.sample_matches_process('Call graph only, no reliable process identity', 345, helper))

    def test_sampler_retains_only_verified_header_and_skips_exited_process(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory); helper = output/'FacilityStudioProbe'
            process = SimpleNamespace(pid=345, poll=lambda: None)
            def native_sample(command, **options):
                self.assertEqual(command[:3], ['/usr/bin/sample', '345', '3'])
                self.assertEqual(options['timeout'], 8)
                Path(command[command.index('-file')+1]).write_text(
                    'Process: FacilityStudioProbe [345]\nPath: '+str(helper)+'\nCall graph:\n')
                return SimpleNamespace(returncode=0)
            with patch.object(probe, "native_process_executable", return_value=str(helper.resolve())), \
                 patch.object(probe.subprocess, 'run', side_effect=native_sample):
                result = probe.sample_probe_process(process, helper, output, 'owned')
            self.assertTrue(result['retained'])
            self.assertTrue((output/'owned_native_sample.txt').is_file())
            def wrong_sample(command, **options):
                Path(command[command.index('-file')+1]).write_text(
                    'Process: Unrelated [999]\nPath: /private/unrelated\nPrivate unrelated stack\n')
                return SimpleNamespace(returncode=0)
            with patch.object(probe, "native_process_executable", return_value=str(helper.resolve())), \
                 patch.object(probe.subprocess, 'run', side_effect=wrong_sample):
                result = probe.sample_probe_process(process, helper, output, 'rejected')
            self.assertFalse(result['retained'])
            self.assertFalse((output/'rejected_native_sample.txt').exists())
            self.assertFalse((output/'rejected_sample-candidate.tmp').exists())
            with patch.object(probe.subprocess, 'run') as run:
                result = probe.sample_probe_process(SimpleNamespace(pid=345, poll=lambda: 0), helper, output, 'exited')
                run.assert_not_called()
                self.assertFalse(result['attempted'])

    def test_sample_alias_requires_kernel_identity_before_and_after(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory); helper=output/'FacilityStudioProbe'; app=output/'Facility Studio.app'
            process=SimpleNamespace(pid=456, poll=lambda: None)
            alias=str(app.resolve()/'Contents/MacOS/FacilityStudio')
            def native_sample(command, **options):
                Path(command[command.index('-file')+1]).write_text(
                    'Process: FacilityStudio [456]\nPath: '+alias+'\nCall graph:\n')
                return SimpleNamespace(returncode=0)
            with patch.object(probe, "native_process_executable", return_value=str(helper.resolve())), \
                 patch.object(probe.subprocess,'run',side_effect=native_sample):
                result=probe.sample_probe_process(process,helper,output,'alias',app)
            self.assertTrue(result['retained'])
            self.assertEqual(result['header_path_category'],'original_launcher_alias')
            for label, identities in [('wrong_before',['/elsewhere/FacilityStudioProbe']),
                                       ('wrong_after',[str(helper.resolve()),'/elsewhere/FacilityStudioProbe'])]:
                with patch.object(probe, "native_process_executable",side_effect=identities), \
                     patch.object(probe.subprocess,'run',side_effect=native_sample):
                    result=probe.sample_probe_process(process,helper,output,label,app)
                self.assertFalse(result['retained'])
                self.assertFalse((output/(label+'_native_sample.txt')).exists())
            exits=iter([None,None,0])
            process=SimpleNamespace(pid=456,poll=lambda: next(exits))
            with patch.object(probe, "native_process_executable",return_value=str(helper.resolve())), \
                 patch.object(probe.subprocess,'run',side_effect=native_sample):
                result=probe.sample_probe_process(process,helper,output,'exited_after',app)
            self.assertFalse(result['retained'])

    def test_sample_redaction_categories_are_bounded(self):
        helper=Path('/owned/FacilityStudioProbe')
        for path in ('<redacted>','/Users/USER/*/FacilityStudioProbe'):
            header='Process: FacilityStudioProbe [789]\nPath: '+path+'\n'
            self.assertEqual(probe.sample_header_metadata(header,helper)['header_path_category'],'redacted')
        self.assertEqual(probe.sample_header_metadata(
            'Process: Other [789]\nPath: /elsewhere/Other\n',helper)['header_path_category'],'unmatched_external')


if __name__ == '__main__':
    unittest.main()
