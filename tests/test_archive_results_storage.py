import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/archive_search'))
from search_results import ResultsStore


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts/archive_search' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ResultsStorageTests(unittest.TestCase):
    def test_reuse_and_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'results.json'
            store = ResultsStore('monasterium', path)
            with self.assertRaises(RuntimeError):
                store.exists('failed', lambda: (_ for _ in ()).throw(RuntimeError('error')))
            self.assertFalse(path.exists())
            self.assertTrue(store.exists('Rosinberg', lambda: True))
            self.assertFalse(store.exists('Rosenburgk', lambda: False))
            self.assertTrue(store.exists('Rosinberg', lambda: self.fail('Should use stored result')))
            self.assertEqual(json.loads(path.read_text())['queries'], {'Rosenburgk': False, 'Rosinberg': True})
            store.record('Rosinberg', False)
            self.assertFalse(json.loads(path.read_text())['queries']['Rosinberg'])

    def test_normal_search_skips_only_known_negative(self):
        for archive in ('monasterium', 'gda_bayern', 'regesta_imperii', 'landesarchiv_nrw', 'landesarchiv_bw', 'arcinsys_hessen'):
            for saved in (False, True, None):
                with self.subTest(archive=archive, saved=saved), tempfile.TemporaryDirectory() as directory:
                    m = load('search_' + archive)
                    path = Path(directory) / 'results.json'
                    if saved is not None:
                        ResultsStore(archive, path).record('Example name', saved)
                    args = ['search', 'Example name', '--list-only', '--results-file', str(path)]
                    if archive in ('monasterium', 'gda_bayern', 'regesta_imperii', 'landesarchiv_nrw'):
                        args += ['--cache-dir', str(Path(directory) / 'cache')]
                    with patch('sys.argv', args), patch.object(m.Client, 'search', side_effect=RuntimeError('archive reached')) as search, \
                         contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(m.main(), 0 if saved is False else 1)
                    self.assertEqual(search.call_count, 0 if saved is False else 1)

    def test_all_scripts_save_direct_searches_and_reuse_exists(self):
        for archive in ('monasterium', 'gda_bayern', 'regesta_imperii', 'landesarchiv_nrw', 'landesarchiv_bw', 'arcinsys_hessen'):
            for found in (False, True):
                with self.subTest(archive=archive, found=found), tempfile.TemporaryDirectory() as directory:
                    m = load('search_' + archive)
                    results = Path(directory) / 'results.json'
                    query = 'Example name'
                    args = ['search', query, '--list-only', '--results-file', str(results)]
                    if archive in ('monasterium', 'gda_bayern', 'regesta_imperii', 'landesarchiv_nrw'):
                        args += ['--cache-dir', str(Path(directory) / 'cache')]
                    if archive in ('monasterium', 'regesta_imperii', 'landesarchiv_nrw'):
                        rows = [] if not found else [{'url': 'https://example.test', 'title': '', 'nodeid': 'id'}]
                        response = (rows, int(found))
                    else:
                        row = {'url': 'https://example.test', 'title': 'Example', 'id': '1', 'signature': 'sig', 'date': ''}
                        response = iter([(row, 1)] if found else [])
                    with patch('sys.argv', args), patch.object(m.Client, 'search', return_value=response), \
                         patch.object(m, 'record_url', return_value=None, create=True), \
                         patch.object(m.Client, 'resolve', return_value='https://example.test', create=True), \
                         contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(m.main(), 0)
                    self.assertEqual(json.loads(results.read_text())['queries'][query], found)
                    args[2] = '--exists'
                    output = io.StringIO()
                    with patch('sys.argv', args), patch.object(m.Client, 'search', side_effect=AssertionError('search called')), \
                         patch.object(m.Client, 'exists', side_effect=AssertionError('search called'), create=True), \
                         contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(m.main(), 0)
                    self.assertEqual(output.getvalue().strip(), str(found).lower())


if __name__ == '__main__':
    unittest.main()
