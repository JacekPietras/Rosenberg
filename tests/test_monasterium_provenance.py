import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/archive_records'))
from archive_record_monasterium import CharterImages, EditionReferences, fallback_sources, create_record as download_record
from archive_record_monasterium_internal import create_record


class ProvenanceTests(unittest.TestCase):
    def test_image_filenames_match_url_encoded_viewer_links(self):
        parser = CharterImages(['K.._~Zwettl._~StAZ__12291219v.jpg', 'K.._~Zwettl._~StAZ__12291219.jpg'])
        parser.feed('<a class="imageLink" data-url="http://images.monasterium.net/pics/166/K.._%7EZwettl._%7EStAZ__12291219v.jpg"></a>'
                    '<a class="imageLink" data-url="http://images.monasterium.net/pics/166/K.._%7EZwettl._%7EStAZ__12291219.jpg"></a>'
                    '<a class="imageLink" data-url="http://images.monasterium.net/pics/166/other.jpg"></a>')
        self.assertEqual(parser.images, [
            'https://images.monasterium.net/pics/166/K.._%7EZwettl._%7EStAZ__12291219v.jpg',
            'https://images.monasterium.net/pics/166/K.._%7EZwettl._%7EStAZ__12291219.jpg',
        ])

    def test_explicit_host_only_and_deduplication(self):
        parser = EditionReferences()
        parser.feed('<a href="http://www.ingrossaturbuecher.de/fileadmin/image.jpg">Image</a>'
                    '<img src="https://ingrossaturbuecher.de/image.jpg">'
                    '<a href="https://www.ingrossaturbuecher.de.example.org/">Wrong host</a>')
        self.assertEqual(parser.sources, [])
        parser = EditionReferences()
        parser.feed('www.ingrossaturbuecher.de <img src="144.mib010_075v.jpg">')
        self.assertEqual(parser.sources, [])

    def test_relative_graphic_inspects_monasterium_only(self):
        root = ET.fromstring('<cei><graphic url="144.mib010_075v.jpg"/></cei>')
        with patch('archive_record_monasterium.fetch_page', return_value=b'<img src="http://www.ingrossaturbuecher.de/fileadmin/image.jpg">') as fetch:
            self.assertEqual(fallback_sources(root, 'https://www.monasterium.net/charter'),
                             [])
            fetch.assert_called_once_with('https://www.monasterium.net/charter')

    def test_cei_link_needs_no_html_request(self):
        root = ET.fromstring('<cei><ref target="https://www.ingrossaturbuecher.de/id/source/123"/></cei>')
        with patch('archive_record_monasterium.fetch_page') as fetch:
            self.assertEqual(fallback_sources(root, 'monasterium'), ['https://www.ingrossaturbuecher.de/id/source/123'])
            fetch.assert_not_called()

    def test_equal_range_and_relative_images(self):
        root = ET.fromstring('<cei><idno>Example</idno><issued><dateRange from="13840515" to="13840515"/></issued><abstract>Text</abstract><graphic url="broken.jpg"/></cei>')
        with tempfile.TemporaryDirectory() as tmp, patch('archive_record_monasterium_internal.REPOSITORY_ROOT', Path(tmp)):
            path, _ = create_record(root, 'https://www.monasterium.net/charter')
            document = json.loads(path.read_text())
            self.assertEqual(path.name, '1384-05-15.json')
            self.assertEqual(document['date'], '1384-05-15')
            self.assertNotIn('img', document['entries'][0])

    def test_day_range_preserves_both_endpoints(self):
        root = ET.fromstring('<cei><idno>Example</idno><issued><dateRange from="13320908" to="13320915"/></issued><abstract>Text</abstract></cei>')
        with tempfile.TemporaryDirectory() as tmp, patch('archive_record_monasterium_internal.REPOSITORY_ROOT', Path(tmp)):
            path, _ = create_record(root, 'https://www.monasterium.net/charter')
            self.assertEqual(json.loads(path.read_text())['date'], '1332-09-08/1332-09-15')

    def test_empty_metadata_is_reported_as_unavailable(self):
        url = 'https://www.monasterium.net/mom/CZ-NA/AZK-Koruna/1332_IX_08-15/charter'
        with patch('archive_record_monasterium.fetch_cei', return_value=b'<atom:null xmlns:atom="http://www.w3.org/2005/Atom"/>'), \
             patch('archive_record_monasterium.fetch_page', return_value=b'<div id="error-content">Temporary error</div>'):
            with self.assertRaisesRegex(ValueError, 'returned no metadata'):
                download_record(url)

    def test_explicit_missing_charter_has_distinct_exit_status(self):
        url = 'https://www.monasterium.net/mom/CZ-NA/AZK-Koruna/1332_IX_08-15/charter'
        with patch('sys.argv', ['downloader', url]), \
             patch('archive_record_monasterium.fetch_cei', return_value=b'<atom:null xmlns:atom="http://www.w3.org/2005/Atom"/>'), \
             patch('archive_record_monasterium.fetch_page', return_value=b'<div id="error-content"><div>Charter not found<span>: </span></div></div>'), \
             patch('archive_record_monasterium.create_internal_record') as save:
            from archive_record_monasterium import main
            self.assertEqual(main(), 76)
            save.assert_not_called()

    def test_collection_explicit_date_and_citation(self):
        root = ET.fromstring('<cei><bibl>Book, p. 127</bibl><idno>LXXXIII.</idno><issued><date value="99999999"/></issued><abstract>Charter. 1340. Jan. 2.</abstract></cei>')
        with tempfile.TemporaryDirectory() as tmp, patch('archive_record_monasterium_internal.REPOSITORY_ROOT', Path(tmp)):
            path, _ = create_record(root, 'https://www.monasterium.net/charter')
            document = json.loads(path.read_text())
            self.assertEqual(document['date'], '1340-01-02')
            self.assertEqual(document['entries'][0]['source'], 'Book, p. 127, LXXXIII.')

    def test_unknown_date_with_explicit_german_date_at_start(self):
        root = ET.fromstring('<cei><idno>CIII.</idno><issued><date value="99999999"/></issued>'
                             '<abstract>1354. 4. Jänner. Abt Albert bestätigt die Urkunde.</abstract></cei>')
        with tempfile.TemporaryDirectory() as tmp, patch('archive_record_monasterium_internal.REPOSITORY_ROOT', Path(tmp)):
            path, _ = create_record(root, 'https://www.monasterium.net/charter')
            self.assertEqual(json.loads(path.read_text())['date'], '1354-01-04')

    def test_unknown_date_does_not_use_later_date_from_prose(self):
        root = ET.fromstring('<cei><idno>CIII.</idno><issued><date value="99999999"/></issued>'
                             '<abstract>A document mentioning 1354. 4. Jänner. in its text.</abstract></cei>')
        with self.assertRaisesRegex(ValueError, 'without an explicit date'):
            create_record(root, 'https://www.monasterium.net/charter')

    def test_sources_added_to_fallback_idempotently(self):
        root = ET.fromstring('<cei><idno>StA Wü, MIB 10 fol. 075v</idno>'
                            '<issued><dateRange from="13780101" to="13831231"/></issued>'
                            '<abstract>Catalog text.</abstract></cei>')
        with tempfile.TemporaryDirectory() as tmp, patch('archive_record_monasterium_internal.REPOSITORY_ROOT', Path(tmp)):
            args = (root, 'https://www.monasterium.net/charter')
            sources = ['https://www.ingrossaturbuecher.de/id/source/123']
            path, updated = create_record(*args, source_references=sources)
            before = path.read_text()
            self.assertEqual(create_record(*args, source_references=sources), (path, True))
            self.assertEqual(path.read_text(), before)
            entry = json.loads(before)['entries'][0]
            self.assertEqual(entry['source'], ['StA Wü, MIB 10 fol. 075v', *sources])
            self.assertEqual(entry['url'], [args[1], *sources])
            self.assertEqual(json.loads(before)['date'], '1378-1383')
            self.assertEqual(path.name, '1378.json')


if __name__ == '__main__':
    unittest.main()
