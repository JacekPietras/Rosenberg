import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS / 'archive_records'))
sys.path.insert(0, str(SCRIPTS / 'archive_search'))
from archive_record_gda_resolver import resolve
from archive_record_gda_bayern import RecordFields, field_values, iso_date


class ResolverTests(unittest.TestCase):
    def test_mobile_fields_and_german_date(self):
        fields = RecordFields()
        fields.feed('<td data-label="Laufzeit">1341 Mai <span>12</span></td>'
                    '<td data-label="Laufzeit">1341 Mai 12</td>')
        self.assertEqual(list(dict.fromkeys(field_values(fields, 'Laufzeit'))), ['1341 Mai 12'])
        self.assertEqual(iso_date(field_values(fields, 'Laufzeit')[0]), '1341-05-12')

    def root(self):
        return ET.fromstring('<cei><archIdentifier>Staatsarchiv Würzburg'
            '<idno>Kloster Urkunden 1341 Mai 12</idno>'
            '<altIdentifier>Würzburger Urkunden 4667</altIdentifier></archIdentifier>'
            '<issued><date value="13410512"/></issued></cei>')

    def test_date_identifier_resolves_by_verified_old_shelfmark(self):
        url = 'https://www.gda.bayern.de/gvl/archive.xhtml?id=example'
        page = '<table><td data-label="Bestellsignatur">StAWü, Kloster Urkunden 228</td>' \
               '<td data-label="Laufzeit">12.5.1341</td>' \
               '<td data-label="Altsignatur">Würzburger Urkunden 4667</td></table>'
        with patch('search_gda_bayern.Client') as client, patch('archive_record_gda_resolver.fetch', return_value=page):
            client.return_value.search.return_value = [(dict(url=url), 1)]
            self.assertEqual(resolve('DE-StAW', 'HimmelspfortenOCist', 'Urkunden_1341_Mai_12', '13410512', self.root()), url)
            client.return_value.search.assert_called_once_with('Würzburger Urkunden 4667')

    def test_wrong_archive_or_date_is_not_routed(self):
        for citation, date in [('StAM, Kloster', '12.5.1341'), ('StAW, Kloster', '13.5.1341')]:
            page = f'<td data-label="Bestellsignatur">{citation}</td><td data-label="Laufzeit">{date}</td><td data-label="Altsignatur">Würzburger Urkunden 4667</td>'
            with patch('search_gda_bayern.Client') as client, patch('archive_record_gda_resolver.fetch', return_value=page):
                client.return_value.search.return_value = [(dict(url='https://www.gda.bayern.de/gvl/archive.xhtml?id=x'), 1)]
                self.assertIsNone(resolve('DE-StAW', 'HimmelspfortenOCist', 'Urkunden_1341_Mai_12', '13410512', self.root()))

    def test_range_record_does_not_guess_catalog_item(self):
        root = self.root()
        root.find('issued').clear()
        ET.SubElement(root.find('issued'), 'dateRange', {'from': '13780101', 'to': '13831231'})
        with patch('search_gda_bayern.Client') as client:
            self.assertIsNone(resolve('DE-StAW', 'MIB10', 'folio075v', '', root))
            client.return_value.search.assert_not_called()


if __name__ == '__main__':
    unittest.main()
