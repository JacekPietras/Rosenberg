import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'archive_records'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'archive_search'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import search_arcinsys_hessen as search
import archive_record_arcinsys_hessen as downloader


class SearchTests(unittest.TestCase):
    def test_dotted_datierung_keeps_day_month_and_year(self):
        self.assertEqual(downloader.iso_date('31.08.1444'), '1444-08-31')

    def test_year_only_record_is_promoted_to_full_arcinsys_date(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '1444.json'
            path.write_text(json.dumps({'date': '1444', 'entries': [{'source': 'Archive record'}]}))
            promoted = downloader.promote_existing_date(path, '1444-08-31')
            self.assertEqual(promoted.name, '1444-08-31.json')
            self.assertFalse(path.exists())
            self.assertEqual(json.loads(promoted.read_text())['date'], '1444-08-31')

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

    def test_existing_text_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '1400.json'
            original = {'date': '1400', 'entries': [{'source': 'signature', 'german': 'reviewed'}]}
            path.write_text(json.dumps(original))
            incoming = {'date': '1400', 'entries': [{'source': 'signature', 'german': 'new'}]}
            with patch.object(downloader, 'DOCUMENT_DIR', Path(directory)):
                result, existing = downloader.save_record(incoming)
            self.assertTrue(existing)
            self.assertEqual(result, path)
            self.assertEqual(json.loads(path.read_text()), original)

    def test_matching_text_merges_citations_across_fields_and_dates(self):
        for field in ('german', 'latin', 'summary'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / '1399.json'
                original = {'date': '1399', 'entries': [{'source': 'old', 'url': 'old-url',
                    field: 'The same   text', 'english': 'Keep this translation'}]}
                path.write_text(json.dumps(original))
                incoming = {'date': '1400', 'entries': [{'source': 'new', 'url': 'new-url',
                    'german': 'The same text'}]}
                with patch.object(downloader, 'DOCUMENT_DIR', Path(directory)):
                    result, matched = downloader.save_record(incoming)
                    self.assertEqual(downloader.save_record(incoming), (path, True))
                self.assertTrue(matched)
                self.assertEqual(result, path)
                entry = json.loads(path.read_text())['entries'][0]
                self.assertEqual(entry['source'], ['old', 'new'])
                self.assertEqual(entry['url'], ['old-url', 'new-url'])
                self.assertEqual(entry['english'], 'Keep this translation')
                self.assertEqual(entry[field], 'The same   text')

    def test_existing_source_in_list_is_matched(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '1400.json'
            original = {'date': '1400', 'entries': [{'source': ['first', 'second'],
                'url': ['first-url', 'second-url'], 'german': 'Reviewed text'}]}
            path.write_text(json.dumps(original))
            incoming = {'date': '1400', 'entries': [{'source': 'second',
                'url': 'second-url', 'german': 'Different text'}]}
            with patch.object(downloader, 'DOCUMENT_DIR', Path(directory)):
                result, matched = downloader.save_record(incoming)
            self.assertEqual((result, matched), (path, True))
            self.assertEqual(json.loads(path.read_text()), original)
            self.assertEqual(list(Path(directory).glob('*.json')), [path])

    def test_empty_text_does_not_merge(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '1400.json'
            path.write_text(json.dumps({'date': '1400', 'entries': [{'source': 'old', 'german': ''}]}))
            incoming = {'date': '1400', 'entries': [{'source': 'new', 'german': ''}]}
            with patch.object(downloader, 'DOCUMENT_DIR', Path(directory)):
                result, matched = downloader.save_record(incoming)
            self.assertFalse(matched)
            self.assertNotEqual(result, path)

    def test_non_archival_result_has_no_download_url(self):
        self.assertIsNone(search.record_url({'columnKeyActions': [{'key': 'rowActionKeyShowItem',
            'detailId': 1, 'additionalParameters': {'itemPrefix': 'b'}}]}))


if __name__ == '__main__':
    unittest.main()
