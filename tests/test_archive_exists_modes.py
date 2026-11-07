import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts/archive_search' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExistsModes(unittest.TestCase):
    def test_arcinsys_stops_before_tree_request(self):
        m = load('search_arcinsys_hessen')
        client = m.Client(1)
        pages = [('', '<form id="simpleSearchForm"><input name="executionId" value="1"></form>'),
                 ('', '<meta name="_csrf" content="x"><div data-query-table-data-url="table"></div>')]
        with patch.object(client, 'request', side_effect=pages) as request:
            self.assertIsNotNone(next(client.search('"name"', exists=True), None))
            self.assertEqual(request.call_count, 2)
        with patch.object(client, 'request', side_effect=[pages[0], ('', 'Your search returned no results')]):
            self.assertIsNone(next(client.search('"name"', exists=True), None))

    def test_bw_returns_first_page_count(self):
        m = load('search_landesarchiv_bw')
        client = m.Client(1)
        for count in (0, 500):
            with self.subTest(count=count), patch.object(client, 'request', side_effect=['', f'<form name="uebergabe"><input name="treffer" value="{count}"></form>']) as request:
                self.assertEqual(next(client.search('name', exists=True)), (None, count))
                self.assertEqual(request.call_count, 2)

    def test_gda_accepts_partial_results_without_creating_raw_cache(self):
        m = load('search_gda_bayern')
        with tempfile.TemporaryDirectory() as directory:
            client = m.Client(15, directory)
            form = '<script nonce="abc"></script><form id="searchForm"><input name="jakarta.faces.ViewState" value="x"></form>'
            with patch.object(client, 'request', side_effect=[form, 'response']), patch.object(m, 'parse_response', return_value=([], 500, {})):
                self.assertEqual(next(client.search('name', exists=True)), (None, 500))
            self.assertEqual(list(Path(directory).glob('*.xml')), [])

    def test_nrw_uses_one_result_page(self):
        m = load('search_landesarchiv_nrw')
        with tempfile.TemporaryDirectory() as directory:
            client = m.Client(15, Path(directory))
            with patch.object(m.nrw, 'fetch', return_value=('', json.dumps({'hits': 500, 'searchResult': []}).encode())) as fetch:
                self.assertEqual(client.search('name', 1, exists=True), ([], 500))
                self.assertIn('size=1', fetch.call_args.args[0])
                self.assertEqual(fetch.call_count, 1)

    def test_regesta_stops_after_first_results_page(self):
        m = load('search_regesta_imperii')
        with tempfile.TemporaryDirectory() as directory:
            client = m.Client(15, Path(directory))
            form = b'<form id="quicksearchform" action="/search"><input name="tx_hisodat_sources[__trustedProperties]" value="x"></form>'
            with patch.object(m.ri, 'fetch', return_value=('', form)) as fetch, patch.object(client, 'post', return_value=b'Ihre Suche hat 500 Treffer ergeben'):
                self.assertEqual(client.search('name', 1, exists=True), ([], 500))
                self.assertEqual(fetch.call_count, 1)


if __name__ == '__main__':
    unittest.main()
