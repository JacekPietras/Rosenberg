import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/archive_records'))
import archive_record_regesta_imperii as regesta
import search_regesta_imperii as search


PROVISIONAL_PATH = '/regesten/suche/result/nr/ri-prov-26b06a4e-034f-442e-b3a1-b59862e73109.html'
PROVISIONAL_URL = 'https://www.regesta-imperii.de/id/ri_prov_26b06a4e-034f-442e-b3a1-b59862e73109'


class RegestaRecordUrlTests(unittest.TestCase):
    def test_date_based_urls_canonicalize(self):
        canonical = 'https://www.regesta-imperii.de/id/1338-07-22_1_0_7_8_0_395_395'
        for url in (
            canonical,
            canonical + '?ignored=1#fragment',
            'https://www.regesta-imperii.de/regesten/7-8-0-ludwig/nr/1338-07-22_1_0_7_8_0_395_395.html',
            'https://www.regesta-imperii.de/regesten/suche/result/nr/1338-07-22-1-0-7-8-0-395-395.html',
        ):
            with self.subTest(url=url):
                self.assertEqual(regesta.canonical_url(url), canonical)
        with self.assertRaises(ValueError):
            regesta.canonical_url('https://www.regesta-imperii.de/id/not-a-record')

    def test_date_based_id_falls_back_to_html(self):
        url = 'https://www.regesta-imperii.de/id/1338-07-22_1_0_7_8_0_395_395'
        page = b'''<div id="head"><p class="departement"><strong>RI - citation</strong></p>
          <h3>1338 Juli 22, Frankfurt a. Main</h3><p class="actionlinks"></p></div>
          <div id="summary"><p>German abstract.</p></div>'''
        with patch.object(regesta, 'resolve_cei', side_effect=ValueError('no CEI')), \
             patch.object(regesta, 'fetch', return_value=(url, page)) as fetch, \
             patch('archive_record_storage.save_record', return_value=(Path('record.json'), False)) as save:
            regesta.create_record(url)
        fetch.assert_called_once_with(url)
        record = save.call_args.args[0]
        self.assertEqual(record['date'], '1338-07-22')
        self.assertEqual(record['place'], 'Frankfurt a. Main')
        self.assertEqual(record['entries'][0]['url'], url)
        self.assertEqual(record['entries'][0]['german'], 'German abstract.')

    def test_provisional_url_is_recovered_when_stale_cache_is_refreshed(self):
        query = '"von Rosenberg"'
        form = b'<form id="quicksearchform" action="/search"><input name="tx_hisodat_sources[__trustedProperties]" value="x"></form>'
        href = f'{PROVISIONAL_PATH}?tx_hisodat_sources%5Baction%5D=show&amp;cHash=example#rinav'
        page = f'Ihre Suche hat 1 Treffer ergeben <h4><a href="{href}">[1397 vor November 7]</a></h4>'.encode()
        stale_row = {'title': '[1397 vor November 7]',
                     'url': 'https://www.regesta-imperii.de/id/26b06a4e-034f-442e-b3a1-b59862e73109'}
        with tempfile.TemporaryDirectory() as directory, patch.object(regesta, 'request_url'):
            cache = Path(directory)
            cache_path = cache / (hashlib.sha256(query.encode()).hexdigest() + '.json')
            cache_path.write_text(json.dumps({'query': query, 'total': 1, 'rows': [stale_row]}))
            client = search.Client(15, cache)
            with patch.object(regesta, 'fetch', return_value=('', form)) as fetch, \
                 patch.object(client, 'post', return_value=page):
                self.assertEqual(client.search(query, 1, exists=True), ([], 1))
                fetch.assert_not_called()
                rows, total = client.search(query, None)
                self.assertEqual((rows, total), ([{**stale_row, 'url': PROVISIONAL_URL}], 1))
                self.assertEqual(client.search(query, None), (rows, total))
                fetch.assert_called_once()
        self.assertEqual(regesta.canonical_url(PROVISIONAL_URL), PROVISIONAL_URL)

    def test_provisional_record_uses_persistent_url_for_html_fallback(self):
        detail_url = 'https://www.regesta-imperii.de' + PROVISIONAL_PATH + '?cHash=example'
        page = b'''<div id="head"><p class="departement"><strong>Collection - Citation</strong></p>
          <h3>[1397 vor November 7]</h3><p class="actionlinks"></p></div>
          <div id="summary"><p>German abstract.</p></div>'''
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(regesta, 'DOCUMENT_DIR', Path(directory)), \
             patch.object(regesta, 'fetch', return_value=(detail_url, page)) as fetch:
            path, updated = regesta.create_record(detail_url)
            record = json.loads(path.read_text())
        self.assertEqual(fetch.call_args.args, (PROVISIONAL_URL,))
        self.assertFalse(updated)
        self.assertEqual(record['date'], '1397')
        self.assertEqual(record['entries'][0], {
            'source': 'Citation', 'url': PROVISIONAL_URL, 'german': 'German abstract.',
        })


if __name__ == '__main__':
    unittest.main()
