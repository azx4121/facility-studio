"""Offline path regressions; synthetic fixtures are not Windows acceptance."""
import copy
import tempfile
import unittest
from pathlib import Path
import publish_verified_windows as p
from test_publication import Fixture


class ExternalArtifactPathTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = Fixture(Path(self.temp.name))
        self.prefix = '0-facs-v22-evidence/external-frozen'
        self.files = self.fixture.files['private2022']
        self.data = p.t.parse_json(self.files[self.prefix + '/Frozen_External_Checks.json'])

    def tearDown(self):
        self.temp.cleanup()

    def gate(self, data=None):
        data = self.data if data is None else data
        files = self.files
        class Evidence:
            def json(self, name):
                return data
            def read(self, name):
                return files[name]
        return p.external_gate(Evidence(), self.prefix, self.fixture.lock['candidate']['sha256'], '2022')

    def test_slash_paths(self):
        self.assertEqual(len(self.gate()), 8)

    def test_native_single_backslash_inventory_and_capture_paths(self):
        for row in self.data['artifacts']:
            row['path'] = row['path'].replace('/', '\\')
        for row in self.data['screenshots']:
            row['screenshot'] = row['screenshot'].replace('/', '\\')
        self.assertEqual(len(self.gate()), 8)

    def test_mixed_separators(self):
        for row in self.data['artifacts']:
            row['path'] = row['path'].replace('/', '\\', 1)
        self.assertEqual(len(self.gate()), 8)

    def test_normalized_alias_collision(self):
        alias = dict(self.data['artifacts'][0])
        alias['path'] = alias['path'].replace('/', '\\')
        self.data['artifacts'].append(alias)
        with self.assertRaisesRegex(p.GateError, 'Duplicate external artifact paths'):
            self.gate()

    def test_invalid_relative_paths(self):
        for path in (None, 1, [], {}, '', '/x', '\\x', '\\\\server\\x', 'C:\\x', 'C:x',
                     'x:stream', '../x', 'x/../y', 'x\\..\\y', './x', 'x/./y', 'x\\.\\y',
                     'x//y', 'x\\\\y', 'x/\\y', 'x/', 'x\\', 'x\x00y', 'x\ny', 'x\ty', 'x\x7fy'):
            with self.subTest(path=path):
                data = copy.deepcopy(self.data)
                data['artifacts'].append(dict(path=path, bytes=1, sha256='0' * 64))
                with self.assertRaisesRegex(p.GateError, 'Unsafe'):
                    self.gate(data)

    def test_missing_inventory_capture_fails_explicitly(self):
        self.data['artifacts'].pop(0)
        with self.assertRaisesRegex(p.GateError, 'artifact is missing'):
            self.gate()

    def test_mismatched_inventory_digest(self):
        self.data['artifacts'][0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(p.GateError, 'Screenshot pixels differ'):
            self.gate()

    def test_mismatched_capture_digest(self):
        self.data['screenshots'][0]['screenshot_sha256'] = '0' * 64
        with self.assertRaisesRegex(p.GateError, 'Screenshot pixels differ'):
            self.gate()

    def test_mismatched_image_bytes(self):
        self.files[self.prefix + '/' + self.data['artifacts'][0]['path']] += b'changed'
        with self.assertRaisesRegex(p.GateError, 'Screenshot pixels differ'):
            self.gate()

    def test_mismatched_image_length(self):
        self.data['artifacts'][0]['bytes'] += 1
        with self.assertRaisesRegex(p.GateError, 'Screenshot pixels differ'):
            self.gate()
