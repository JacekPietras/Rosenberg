import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS / 'archive_records'))
sys.path.insert(0, str(SCRIPTS / 'archive_search'))
from archive_record_gda_resolver import resolve
from archive_record_gda_bayern import RecordFields, create_record, field_values, iso_date, seal_sections


class ResolverTests(unittest.TestCase):
    def test_search_url_is_added_to_existing_permalink_with_different_date_and_citation(self):
        search_url = 'https://www.gda.bayern.de/gvl/archive.xhtml?id=Vz++++++search-id&parent_id='
        permalink = 'https://www.gda.bayern.de/gvl/document/762e2c8d-0916-4308-a2bd-cdebfb3bd436'
        page = ('<td data-label="Bestellsignatur">StAN, new shelfmark</td>'
                '<td data-label="Laufzeit">1454 Dezember 20</td>'
                '<td data-label="Betreff">Catalogue description.</td>')
        with tempfile.TemporaryDirectory() as tmp:
            documents = Path(tmp)
            old = documents / '1454.json'
            old.write_text(json.dumps({'date': '1454', 'entries': [{
                'source': 'StAN, old shelfmark', 'url': permalink,
                'english': 'Preserved translation.'}]}))
            with patch('archive_record_gda_bayern.DOCUMENT_DIR', documents), \
                 patch('archive_record_gda_bayern.fetch', side_effect=[page + permalink, page]), \
                 patch('archive_record_gda_bayern.image_urls', return_value=[]):
                self.assertEqual(create_record(search_url), (old, True))
            entry = json.loads(old.read_text())['entries'][0]
            self.assertEqual(entry['url'], [permalink, search_url])
            self.assertEqual(entry['english'], 'Preserved translation.')
            self.assertEqual(len(list(documents.glob('*.json'))), 1)
            from archive_record_storage import has_url
            self.assertTrue(has_url(documents, search_url))

    def test_import_saves_records_with_undated_or_missing_laufzeit(self):
        url = 'https://www.gda.bayern.de/gvl/archive.xhtml?id=example'
        permalink = 'https://www.gda.bayern.de/gvl/document/762e2c8d-0916-4308-a2bd-cdebfb3bd436'
        values = ('o.D.', 'o. D.', 'ohne Datum', '[]', '[Hinweis: Feld bitte leer lassen]', '', None)
        for value in values:
            with self.subTest(laufzeit=value), tempfile.TemporaryDirectory() as tmp:
                page = ('<td data-label="Bestellsignatur">StAN, Akten 337/fol. 229 - 231</td>'
                        '<td data-label="Betreff">Schadensliste des Zaisolph von Rosenberg.</td>')
                if value is not None:
                    page += f'<td data-label="Laufzeit">{value}</td>'
                with patch('archive_record_gda_bayern.DOCUMENT_DIR', Path(tmp)), \
                     patch('archive_record_gda_bayern.fetch', side_effect=[page + permalink, page] * 2):
                    path, updated = create_record(url)
                    self.assertFalse(updated)
                    self.assertEqual(create_record(url), (path, True))
                self.assertEqual(path.name, '9999.json')
                record = json.loads(path.read_text())
                self.assertEqual(record['date'], '9999')
                self.assertEqual(record['entries'], [{
                    'source': 'StAN, Akten 337/fol. 229 - 231',
                    'url': [permalink, url],
                    'german': 'Schadensliste des Zaisolph von Rosenberg.',
                }])

    def test_undated_handling_still_rejects_unrecognized_date_labels(self):
        with self.assertRaisesRegex(ValueError, 'Could not determine the document date'):
            iso_date('fehlerhafte Datumsangabe')

    def test_seal_section_excludes_other_description_fields(self):
        description = ('Beschreibstoff: Pergament\nSiegler bzw. Siegel: S 1: Bischof, besch.\n'
                       'S 2: Konrad von Rosenberg, fehlt\nMaße: 20 cm')
        self.assertEqual(seal_sections(description),
                         ['Siegler bzw. Siegel: S 1: Bischof, besch.\nS 2: Konrad von Rosenberg, fehlt'])
        self.assertEqual(seal_sections('Beschreibstoff: Pergament'), [])

    def test_import_includes_duplicate_seal_section_only_once(self):
        url = 'https://www.gda.bayern.de/gvl/document/6e42910b-9ede-45ce-8f68-9068ba1d1875'
        description = 'Beschreibstoff: Pergament\nSiegler bzw. Siegel: S 1: Bischof\nS 2: Konrad, fehlt\nMaße: 20 cm'
        page = ('<td data-label="Laufzeit">1454 Dezember 20</td>'
                '<td data-label="Bestellsignatur">StAWü, Urkunde</td>'
                '<td data-label="Betreff">Inhalt</td>'
                + 2 * f'<td data-label="Äußere Beschreibung">{description}</td>')
        with patch('archive_record_gda_bayern.fetch', return_value=page), \
             patch('archive_record_gda_bayern.image_urls', return_value=[]), \
             patch('archive_record_storage.save_record', return_value=(Path('record.json'), False)) as save:
            create_record(url)
        self.assertEqual(save.call_args.args[0]['entries'][0]['german'],
                         'Inhalt\n\nSiegler bzw. Siegel: S 1: Bischof\nS 2: Konrad, fehlt')

    def test_mobile_fields_and_german_date(self):
        fields = RecordFields()
        fields.feed('<td data-label="Laufzeit">1341 Mai <span>12</span></td>'
                    '<td data-label="Laufzeit">1341 Mai 12</td>')
        self.assertEqual(list(dict.fromkeys(field_values(fields, 'Laufzeit'))), ['1341 Mai 12'])
        self.assertEqual(iso_date(field_values(fields, 'Laufzeit')[0]), '1341-05-12')

    def test_import_includes_catalog_notes_with_field_labels(self):
        url = 'https://www.gda.bayern.de/gvl/document/c42e1677-acf0-4b5a-98eb-bc09812e2f61'
        page = ('<td data-label="Laufzeit">1660</td>'
                '<td data-label="Bestellsignatur">StAWü, Akten</td>'
                '<td data-label="Betreff">Inhalt</td>'
                + 2 * '<td data-label="Enthält-/Darin-Vermerke">Darin: Abschrift</td>'
                + 2 * '<td data-label="Vermerke">Rückvermerk</td>')
        with patch('archive_record_gda_bayern.fetch', return_value=page), \
             patch('archive_record_gda_bayern.image_urls', return_value=[]), \
             patch('archive_record_storage.save_record', return_value=(Path('record.json'), False)) as save:
            create_record(url)
        self.assertEqual(save.call_args.args[0]['entries'][0]['german'],
                         'Inhalt\n\nEnthält-/Darin-Vermerke: Darin: Abschrift\n\nVermerke: Rückvermerk')

    def test_import_includes_separate_sealing_field_once(self):
        url = 'https://www.gda.bayern.de/gvl/document/1dc4f41a-126d-4b5a-98c3-c02f6bb16ac8'
        page = ('<td data-label="Laufzeit">1521 Februar 6</td>'
                '<td data-label="Bestellsignatur">StAWü, Urkunde</td>'
                '<td data-label="Betreff">Inhalt</td>'
                + 2 * '<td data-label="Besiegelung/Beglaubigung:">Friedrich von Rosenberg, fehlt</td>')
        with patch('archive_record_gda_bayern.fetch', return_value=page), \
             patch('archive_record_gda_bayern.image_urls', return_value=[]), \
             patch('archive_record_storage.save_record', return_value=(Path('record.json'), False)) as save:
            create_record(url)
        self.assertEqual(save.call_args.args[0]['entries'][0]['german'],
                         'Inhalt\n\nBesiegelung/Beglaubigung: Friedrich von Rosenberg, fehlt')

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

    def test_numeric_shelfmark_uses_collection_name(self):
        root = ET.fromstring('<cei><archIdentifier><archFond>Jesuitenorden, Kolleg St. Paul Regensburg Urkunden</archFond>'
                             '<idno>813</idno></archIdentifier><issued><date value="13580207"/></issued></cei>')
        with patch('search_gda_bayern.Client') as client:
            client.return_value.search.return_value = []
            self.assertIsNone(resolve('DE-BayHStA', 'JesuitenordenKollegStPaulRegensburg', 'shelfmark', '13580207', root))
            client.return_value.search.assert_called_once_with('Jesuitenorden Kolleg St. Paul Regensburg Urkunden 813')

    def test_numeric_shelfmark_without_collection_is_not_searched(self):
        root = ET.fromstring('<cei><archIdentifier><idno>813</idno></archIdentifier>'
                             '<issued><date value="13580207"/></issued></cei>')
        with patch('search_gda_bayern.Client') as client:
            self.assertIsNone(resolve('DE-BayHStA', 'fonds', 'shelfmark', '13580207', root))
            client.return_value.search.assert_not_called()

    def test_range_record_does_not_guess_catalog_item(self):
        root = self.root()
        root.find('issued').clear()
        ET.SubElement(root.find('issued'), 'dateRange', {'from': '13780101', 'to': '13831231'})
        with patch('search_gda_bayern.Client') as client:
            self.assertIsNone(resolve('DE-StAW', 'MIB10', 'folio075v', '', root))
            client.return_value.search.assert_not_called()


if __name__ == '__main__':
    unittest.main()
