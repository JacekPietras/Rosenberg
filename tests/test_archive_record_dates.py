import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/archive_records'))

import archive_record_arcinsys_hessen as hessen
import archive_record_gda_bayern as bayern
import archive_record_landesarchiv_bw as bw
import archive_record_nrw as nrw
from archive_record_dates import parse_catalogue_date


class CatalogueDateTests(unittest.TestCase):
    def test_common_dates(self):
        examples = {'[158...]': '158X', '[15..]': '15XX', '25. Apr. 1385': '1385-04-25',
                    '1316 Juni 29': '1316-06-29', '31.08.1444': '1444-08-31',
                    '[15]43 Februar 15': '1543-02-15', '15[43] Februar': '1543-02',
                    '[1543]': '1543',
                    'frühes 17. Jh.': '1601-1700', '(16. Jh.)': '1501-1600'}
        for value, expected in examples.items():
            with self.subTest(value=value):
                self.assertEqual(parse_catalogue_date(value), expected)

    def test_importers_share_century_and_uncertain_year_handling(self):
        for parse in (hessen.iso_date, bayern.iso_date, bw.iso_date, nrw.normalize_date):
            with self.subTest(importer=parse.__module__):
                self.assertEqual(parse('(16. Jh.)'), '1501-1600')
                self.assertEqual(parse('[158...]'), '158X')

    def test_rejects_invalid_and_missing_dates(self):
        for value in ('31.02.1444', 'unbekannt', '15. April'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_catalogue_date(value)


if __name__ == '__main__':
    unittest.main()
