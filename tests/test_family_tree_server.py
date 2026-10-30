"""Exercise web rebuilds through the real HTTP endpoint and Python engine."""

from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
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
        self.root = Path(self.temp.name)
        (self.root / 'scripts').symlink_to(ROOT / 'scripts', target_is_directory=True)
        self.write('data/names.md', 'Alex\nBea\n')
        self.write('data/places.json', [])
        self.write('data/people.json', [{'id': 'a', 'name': 'Alex'}, {'id': 'b', 'name': 'Bea'}])
        self.write('data/tree.json', {'views': ['facts', 'with-guesses'], 'configuration': {'searchLimit': 37}})
        self.write('data/documents/test.json', {'date': '1393', 'facts': [
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
        connection = HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
        try:
            connection.request('POST', '/api/rebuild-family-tree',
                               body=json.dumps(value) if value is not None else None)
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
        self.assertEqual(['facts', 'with-guesses'], metadata['views'])
        self.assertEqual(37, metadata['configuration']['searchLimit'])
        self.assertEqual('b', metadata['evidence']['facts']['relationships'][0]['of'])
        self.assertTrue(all(set(person) == {'id', 'name'} for person in people))
        self.assertEqual(source, (self.root / 'data/documents/test.json').read_bytes())
        before = (self.root / 'data/tree.json').read_bytes()
        registry = (self.root / 'data/people.json').read_bytes()
        self.assertEqual(200, self.post()[0])
        self.assertEqual(before, (self.root / 'data/tree.json').read_bytes())
        self.assertEqual(registry, (self.root / 'data/people.json').read_bytes())

    def test_facts_only_request_does_not_add_a_guesses_view(self):
        self.assertEqual(200, self.post({'includeGuesses': False, 'searchLimit': 23})[0])
        tree = json.loads((self.root / 'data/tree.json').read_text())
        self.assertEqual(['facts'], tree['views'])
        self.assertEqual(23, tree['configuration']['searchLimit'])

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
                self.assertEqual(['facts', 'with-guesses'], tree['views'])
                self.assertEqual(10000, tree['configuration']['searchLimit'])

    def test_timeout_is_reported_as_a_retryable_failure(self):
        with patch.object(viewer.subprocess, 'run', side_effect=subprocess.TimeoutExpired('rebuild', 120)):
            self.assertEqual(504, self.post()[0])


if __name__ == '__main__':
    unittest.main()
