import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'archive_records'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from archive_record_storage import save_record, has_url, merge_text


class DownloaderStorageTests(unittest.TestCase):
    def test_existing_url_matches_when_citation_and_text_differ(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path, _ = save_record({'date': '1341', 'entries': [{'source': 'old citation',
                'url': 'same-url', 'german': 'Long reviewed text'}]}, folder)
            self.assertEqual(save_record({'date': '1341', 'entries': [{'source': 'new citation',
                'url': 'same-url', 'german': 'Short catalog text'}]}, folder), (path, True))
            entry = json.loads(path.read_text())['entries'][0]
            self.assertEqual(entry['source'], ['old citation', 'new citation'])
            self.assertEqual(entry['german'], 'Long reviewed text')

    def test_matching_ignores_special_sections_and_merges_without_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            original = {'date': '1342-04-23', 'entries': [{'source': 'GDA', 'url': 'old',
                'german': 'The charter text.\n\nSiegel: First seal',
                'english': 'Existing translation', 'facts': []}]}
            path, _ = save_record(original, folder)
            incoming = {'date': '1342-04-23', 'entries': [{'source': 'Monasterium', 'url': 'new',
                'german': 'The charter text. Aussteller: Ekkehart Empfänger: Abbey Siegel: First seal and second seal'}]}
            self.assertEqual(save_record(incoming, folder), (path, True))
            self.assertEqual(save_record(incoming, folder), (path, True))
            entry = json.loads(path.read_text())['entries'][0]
            self.assertEqual(entry['source'], ['GDA', 'Monasterium'])
            self.assertEqual(entry['url'], ['old', 'new'])
            self.assertEqual(entry['german'], 'The charter text.\n\nSiegel: First seal and second seal\n\nAussteller: Ekkehart\n\nEmpfänger: Abbey')
            self.assertEqual(entry['english'], 'Existing translation')
            self.assertEqual(len(list(folder.glob('*.json'))), 1)

    def test_distinct_special_parts_are_preserved(self):
        self.assertEqual(merge_text('Text\n\nSiegler: A', 'Text Siegler: B'),
                         'Text\n\nSiegler: A\n\nSiegler: B')
        self.assertEqual(merge_text('Text', 'Different text Aussteller: A'), 'Text')

    def test_existing_record_gains_images_and_missing_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = folder / '1400.json'
            original = {'date': '1400', 'entries': [{'source': ['other', 'archive'],
                'url': ['old'], 'german': 'reviewed', 'img': [{'src': 'old-image', 'tags': ['seal']}]}]}
            path.write_text(json.dumps(original))
            incoming = {'date': '1400', 'entries': [{'source': 'archive', 'url': 'new',
                'german': 'new text', 'latin': 'previously missing',
                'img': [{'src': 'old-image'}, {'src': 'new-image'}]}]}
            self.assertEqual(save_record(incoming, folder), (path, True))
            self.assertEqual(save_record(incoming, folder), (path, True))
            entry = json.loads(path.read_text())['entries'][0]
            self.assertEqual(entry['german'], 'reviewed')
            self.assertEqual(entry['latin'], 'previously missing')
            self.assertEqual(entry['url'], ['old', 'new'])
            self.assertEqual(entry['img'], [{'src': 'old-image', 'tags': ['seal']}, {'src': 'new-image'}])
            self.assertTrue(has_url(folder, 'new'))

    def test_transcribed_record_does_not_gain_catalog_text_as_transcription(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp); path = folder / '1400.json'
            path.write_text(json.dumps({'date': '1400', 'transcribed': True,
                'entries': [{'source': 'archive', 'latin': 'transcription'}]}))
            save_record({'date': '1400', 'entries': [{'source': 'archive', 'german': 'abstract'}]}, folder)
            self.assertNotIn('german', json.loads(path.read_text())['entries'][0])


if __name__ == '__main__':
    unittest.main()
