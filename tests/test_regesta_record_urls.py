import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/archive_records'))
import archive_record_regesta_imperii as regesta


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


if __name__ == '__main__':
    unittest.main()
