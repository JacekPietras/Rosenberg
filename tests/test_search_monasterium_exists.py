import contextlib
import importlib.util
import io
import json
import tempfile
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/archive_search/search_monasterium.py'
spec = importlib.util.spec_from_file_location('search_monasterium', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ExistenceTests(unittest.TestCase):
    def test_one_request_for_positive_and_negative_results(self):
        pages = [
            b'<div class="hits">Hits 1 to 10 of 123</div>',
            b'<form id="search-form"></form>Sorry, no results were found for your search.',
        ]
        with tempfile.TemporaryDirectory() as directory:
            client = module.Client(15, Path(directory))
            with patch.object(client, 'wait'), patch.object(module, 'urlopen', side_effect=[io.BytesIO(page) for page in pages]) as fetch:
                self.assertTrue(client.exists('Rosinberg'))
                self.assertFalse(client.exists('Rosenburgk'))
                self.assertEqual(fetch.call_count, 2)

    def test_complete_search_cache_avoids_request(self):
        with tempfile.TemporaryDirectory() as directory:
            client = module.Client(15, Path(directory))
            key = module.hashlib.sha256(b'and-quoted-v1\0Rosinberg').hexdigest()
            (Path(directory) / (key + '.json')).write_text(json.dumps({
                'query': 'Rosinberg', 'total': 1, 'rows': [{'url': 'example'}],
            }))
            with patch.object(module, 'urlopen') as fetch:
                self.assertTrue(client.exists('Rosinberg'))
                fetch.assert_not_called()

    def test_full_search_fetches_all_pages_and_caches_complete_results(self):
        pages = [
            b'<div class="hits">Hits 1 to 1 of 2</div><a href="/mom/a/b/charter">First</a>',
            b'<div class="hits">Hits 2 to 2 of 2</div><a href="/mom/a/c/charter">Second</a>',
        ]
        with tempfile.TemporaryDirectory() as directory:
            client = module.Client(15, Path(directory))
            with patch.object(client, 'wait'), patch.object(module, 'urlopen', side_effect=[io.BytesIO(page) for page in pages]) as fetch:
                rows, total = client.search('von Rosenberg', None)
            self.assertEqual(total, 2)
            self.assertEqual([row['title'] for row in rows], ['First', 'Second'])
            self.assertEqual([parse_qs(urlsplit(call.args[0].full_url).query)['block'][0]
                              for call in fetch.call_args_list], ['1', '2'])
            cached = json.loads(next(Path(directory).glob('*.json')).read_text())
            self.assertEqual(cached['rows'], rows)
            self.assertEqual(cached['total'], 2)

    def test_dotted_normal_search_is_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            args = ['search', 'Eberhard von. Rosenberg', '--cache-dir', directory,
                    '--results-file', str(Path(directory) / 'results.json')]
            with patch.object(sys, 'argv', args), patch.object(module.Client, 'search') as search, \
                 contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(module.main(), 0)
            search.assert_not_called()
            self.assertFalse((Path(directory) / 'results.json').exists())

    def test_dotted_exists_reuses_undotted_result(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'results.json'
            path.write_text(json.dumps({'archive': 'monasterium', 'queries': {'v Rosinberg': True}}))
            args = ['search', 'v. Rosinberg', '--exists', '--cache-dir', directory,
                    '--results-file', str(path)]
            output = io.StringIO()
            with patch.object(sys, 'argv', args), patch.object(module.Client, 'exists') as exists, \
                 contextlib.redirect_stdout(output):
                self.assertEqual(module.main(), 0)
            exists.assert_not_called()
            self.assertEqual(output.getvalue().strip(), 'true')

    def test_http_500_does_not_store_a_negative_result(self):
        for exists_mode in (True, False):
            with self.subTest(exists=exists_mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                results = root / 'results.json'
                args = ['search', 'Eberhardi de Rosenperg', '--cache-dir', str(root / 'cache'),
                        '--results-file', str(results)]
                if exists_mode:
                    args.append('--exists')
                error = HTTPError('https://www.monasterium.net/mom/search', 500, 'Internal Server Error', {}, None)
                with patch.object(sys, 'argv', args), patch.object(module.Client, 'wait'), \
                     patch.object(module, 'urlopen', side_effect=error), \
                     contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(module.main(), 75)
                self.assertFalse(results.exists())
                self.assertEqual(list((root / 'cache').glob('*.json')), [])

    def test_unrecognized_page_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            client = module.Client(15, Path(directory))
            with patch.object(client, 'wait'), patch.object(module, 'urlopen', return_value=io.BytesIO(b'blocked')):
                with self.assertRaises(ValueError):
                    client.exists('Rosinberg')


if __name__ == '__main__':
    unittest.main()
