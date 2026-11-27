"""Exercise web rebuilds through the real HTTP endpoint and Python engine."""

from itertools import count
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from family_graph.probability import DEFAULTS

spec = importlib.util.spec_from_file_location('family_tree_test_server', ROOT / 'docs/serve.py')
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)


class QuietHandler(viewer.ViewerHandler):
    def log_message(self, *args):
        pass


class FamilyTreeServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / 'scripts').symlink_to(ROOT / 'scripts', target_is_directory=True)
        self.write('data/names.md', 'Alex\nBea\n')
        self.write('data/nobiliary_particles.md', 'von\n')
        self.write('data/places.json', [])
        self.write('data/matching.json', DEFAULTS)
        self.write('data/people.json', [{'id': 'a', 'name': 'Alex'}, {'id': 'b', 'name': 'Bea'}])
        self.write('data/tree.json', {'views': ['facts', 'with-guesses'], 'configuration': {'searchLimit': 37}})
        self.write('data/documents/test.json', {'date': '1393', 'label': 'Franken', 'facts': [
            {'type': 'parent', 'person': 'a', 'of': 'b'},
        ]})
        self.root_patch = patch.object(viewer, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def write(self, path, value):
        path = self.root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value), encoding='utf-8')

    def post(self, value=None):
        return self.request('POST', '/api/rebuild-family-tree', value)

    def request(self, method, path, value=None):
        connection = HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        try:
            connection.request(method, path, body=json.dumps(value) if value is not None else None)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_rebuild_preserves_views_configuration_and_source_data(self):
        source = (self.root / 'data/documents/test.json').read_bytes()
        status, result = self.post()
        self.assertEqual((200, {'ok': True}), (status, result))
        people = json.loads((self.root / 'data/people.json').read_text())
        metadata = json.loads((self.root / 'data/tree.json').read_text())
        self.assertEqual(['with-guesses'], list(metadata['evidence']))
        self.assertEqual(37, metadata['configuration']['searchLimit'])
        self.assertEqual('b', metadata['evidence']['with-guesses']['relationships'][0]['of'])
        self.assertTrue(all(set(person) == {'id', 'name'} for person in people))
        self.assertEqual(source, (self.root / 'data/documents/test.json').read_bytes())
        before = (self.root / 'data/tree.json').read_bytes()
        registry = (self.root / 'data/people.json').read_bytes()
        self.assertEqual(200, self.post()[0])
        self.assertEqual(before, (self.root / 'data/tree.json').read_bytes())
        self.assertEqual(registry, (self.root / 'data/people.json').read_bytes())

    def test_soft_delete_excludes_documents_from_discovery_build_and_export(self):
        path = 'data/documents/test.json'
        archived = self.root / 'data/documents/deleted/test.json'
        source = (self.root / path).read_bytes()
        subprocess.run(['git', 'add', '--', path], cwd=self.root, check=True)
        subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.com',
                        'commit', '-qm', 'initial'], cwd=self.root, check=True)
        self.write('data/documents/unrelated.json', {'entries': []})
        status, result = self.post()
        self.assertEqual(200, status, result)
        self.assertEqual((200, {'ok': True}), self.request('POST', '/api/delete-document', {'path': path}))
        self.assertEqual(200, self.request('POST', '/api/delete-document', {'path': path})[0])
        self.assertEqual(source, archived.read_bytes())
        self.assertFalse((self.root / path).exists())
        staged = subprocess.run(['git', 'diff', '--cached', '--no-renames', '--name-only'], cwd=self.root,
                                capture_output=True, text=True, check=True).stdout.splitlines()
        self.assertEqual(['data/documents/deleted/test.json', path], staged)
        self.assertEqual((400, {'error': 'The document has been deleted'}),
                         self.request('POST', '/api/save-document', {'path': path, 'document': {'entries': []}}))
        status, files = self.request('GET', '/api/files')
        self.assertEqual(200, status)
        self.assertFalse(any(item['path'] == path or item['path'].startswith('data/documents/deleted/')
                             for item in files))
        # A corrupt archived record would fail the rebuild if the loader opened it.
        archived.write_text('{bad')
        status, result = self.post()
        self.assertEqual(200, status, result)
        metadata = json.loads((self.root / 'data/tree.json').read_text())
        self.assertNotIn(path, metadata['inputs'])
        self.assertNotIn('data/documents/deleted/test.json', metadata['inputs'])
        self.assertEqual([], metadata['evidence']['with-guesses']['relationships'])

    def test_facts_only_request_is_rejected(self):
        self.assertEqual(400, self.post({'includeGuesses': False})[0])

    def test_invalid_sources_return_failure_without_replacing_registry(self):
        before = (self.root / 'data/people.json').read_bytes()
        self.write('data/documents/test.json', '{bad')
        status, result = self.post()
        self.assertEqual(422, status)
        self.assertIn('test.json', result['error'])
        self.assertEqual(before, (self.root / 'data/people.json').read_bytes())

    def test_request_cannot_supply_commands_or_invalid_options(self):
        for request in ({'command': 'anything'}, {'searchLimit': -1}, {'includeGuesses': 'true'}, ['bad']):
            with self.subTest(request=request):
                self.assertEqual(400, self.post(request)[0])

    def test_invalid_saved_options_fall_back_to_rebuild_defaults(self):
        for metadata in ({'views': None}, {'views': 'facts'},
                         {'configuration': {'searchLimit': -1}},
                         {'configuration': {'searchLimit': 'bad'}},
                         {'configuration': {'searchLimit': True}}):
            with self.subTest(metadata=metadata):
                self.write('data/tree.json', metadata)
                status, result = self.post()
                self.assertEqual(200, status, result)
                tree = json.loads((self.root / 'data/tree.json').read_text())
                self.assertEqual(['with-guesses'], list(tree['evidence']))
                self.assertEqual(10000, tree['configuration']['searchLimit'])

    def test_timeout_is_reported_as_a_retryable_failure(self):
        # Use the real endpoint and process loop, with an elapsed deadline.
        with patch.object(viewer, 'time') as clock:
            clock.monotonic.side_effect = count(0, 3601)
            status, result = self.post()
        self.assertEqual(504, status)
        self.assertIn('retry', result['error'].lower())

    def test_inputs_changed_during_build_are_rebuilt_without_an_error(self):
        (self.root / 'scripts').unlink()
        self.write('scripts/rebuild_family_tree.py', """from pathlib import Path
import sys

attempts = Path('attempts')
count = int(attempts.read_text()) + 1 if attempts.exists() else 1
attempts.write_text(str(count))
sys.exit(75 if count == 1 or Path('always_changed').exists() else 0)
""")
        self.assertEqual(200, self.post()[0])
        self.assertEqual('2', (self.root / 'attempts').read_text())
        self.write('always_changed', '')
        self.assertEqual(422, self.post()[0])
        self.assertEqual('5', (self.root / 'attempts').read_text())

if __name__ == '__main__':
    unittest.main()
