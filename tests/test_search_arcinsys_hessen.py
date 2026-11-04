import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import search_arcinsys_hessen as search
import downloader_arcinsys_hessen as downloader


class SearchTests(unittest.TestCase):
    def test_pagination_and_record_links(self):
        form = '<form id="simpleSearchForm"><input name="executionId" value="abc"></form>'
        result = ('<meta name="_csrf" content="token">'
                  '<div data-query-table-data-url="/table?x=1" '
                  'data-tree-data-url="/tree?x=1"></div>')
        row = lambda i: {'DT_RowId': 'v' + str(i), 'columnKeyActions': [
            {'key': 'rowActionKeyShowItem', 'detailId': i, 'additionalParameters': {'itemPrefix': 'v'}}]}
        responses = [('', form), ('', result), ('', '[{"id":"root"}]'),
                     ('', json.dumps({'data': [row(i) for i in range(100)], 'recordsFiltered': 101})),
                     ('', json.dumps({'data': [row(100)], 'recordsFiltered': 101}))]
        client = search.Client(1)
        with patch.object(client, 'request', side_effect=responses) as request:
            rows = list(client.search('Rosenberg'))
        self.assertEqual(len(rows), 101)
        self.assertEqual(rows[-1][1], 101)
        self.assertIn('archivalDescriptionId=100', search.record_url(rows[-1][0]))
        state = json.loads(__import__('urllib.parse', fromlist=['parse_qs']).parse_qs(request.call_args.args[1].decode())['tableStateJson'][0])
        self.assertEqual(state['start'], 100)

    def test_skip_existing_preserves_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '1400.json'
            original = {'date': '1400', 'entries': [{'source': 'signature', 'german': 'reviewed'}]}
            path.write_text(json.dumps(original))
            incoming = {'date': '1400', 'entries': [{'source': 'signature', 'german': 'new'}]}
            with patch.object(downloader, 'DOCUMENT_DIR', Path(directory)):
                result, existing = downloader.save_record(incoming, skip_existing=True)
            self.assertTrue(existing)
            self.assertEqual(result, path)
            self.assertEqual(json.loads(path.read_text()), original)

    def test_non_archival_result_has_no_download_url(self):
        self.assertIsNone(search.record_url({'columnKeyActions': [{'key': 'rowActionKeyShowItem',
            'detailId': 1, 'additionalParameters': {'itemPrefix': 'b'}}]}))


if __name__ == '__main__':
    unittest.main()
