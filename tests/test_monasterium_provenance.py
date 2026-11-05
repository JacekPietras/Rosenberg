import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/archive_records'))
from archive_record_monasterium import EditionReferences, fallback_sources
from archive_record_monasterium_internal import create_record


class ProvenanceTests(unittest.TestCase):
    def test_explicit_host_only_and_deduplication(self):
        parser = EditionReferences()
        parser.feed('<a href="http://www.ingrossaturbuecher.de/fileadmin/image.jpg">Image</a>'
                    '<img src="https://ingrossaturbuecher.de/image.jpg">'
                    '<a href="https://www.ingrossaturbuecher.de.example.org/">Wrong host</a>')
        self.assertEqual(parser.sources, ['https://www.ingrossaturbuecher.de/'])
        parser = EditionReferences()
        parser.feed('www.ingrossaturbuecher.de <img src="144.mib010_075v.jpg">')
        self.assertEqual(parser.sources, [])

    def test_relative_graphic_inspects_monasterium_only(self):
        root = ET.fromstring('<cei><graphic url="144.mib010_075v.jpg"/></cei>')
        with patch('archive_record_monasterium.fetch_page', return_value=b'<img src="http://www.ingrossaturbuecher.de/fileadmin/image.jpg">') as fetch:
            self.assertEqual(fallback_sources(root, 'https://www.monasterium.net/charter'),
                             ['https://www.ingrossaturbuecher.de/'])
            fetch.assert_called_once_with('https://www.monasterium.net/charter')

    def test_cei_link_needs_no_html_request(self):
        root = ET.fromstring('<cei><ref target="https://www.ingrossaturbuecher.de/"/></cei>')
        with patch('archive_record_monasterium.fetch_page') as fetch:
            self.assertEqual(fallback_sources(root, 'monasterium'), ['https://www.ingrossaturbuecher.de/'])
            fetch.assert_not_called()

    def test_sources_added_to_fallback_idempotently(self):
        root = ET.fromstring('<cei><idno>StA Wü, MIB 10 fol. 075v</idno>'
                            '<issued><dateRange from="13780101" to="13831231"/></issued>'
                            '<abstract>Catalog text.</abstract></cei>')
        with tempfile.TemporaryDirectory() as tmp, patch('archive_record_monasterium_internal.REPOSITORY_ROOT', Path(tmp)):
            args = (root, 'https://www.monasterium.net/charter')
            sources = ['https://www.ingrossaturbuecher.de/']
            path, updated = create_record(*args, source_references=sources)
            before = path.read_text()
            self.assertEqual(create_record(*args, source_references=sources), (path, True))
            self.assertEqual(path.read_text(), before)
            entry = json.loads(before)['entries'][0]
            self.assertEqual(entry['source'], ['StA Wü, MIB 10 fol. 075v', *sources])
            self.assertEqual(entry['url'], args[1])


if __name__ == '__main__':
    unittest.main()
