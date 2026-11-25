import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'archive_records'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from archive_record_storage import save_record, has_source, has_url, merge_text


class CatalogSectionMergeTests(unittest.TestCase):
    def test_preserves_new_catalog_sections(self):
        for section in ('Enthält u.a.: Details', 'Besiegelung/Beglaubigung: Friedrich',
                        'Enthält-/Darin-Vermerke: Darin: Details', 'Vermerke: Rückvermerk'):
            with self.subTest(section=section):
                self.assertEqual(merge_text('Text', f'Text\n\n{section}'), f'Text\n\n{section}')


class DownloaderStorageTests(unittest.TestCase):
    def test_deleted_records_still_match_and_reserve_their_filenames(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            original = {'date': '1341', 'entries': [{'source': 'Catalog citation',
                'url': 'https://example.org/record', 'german': 'Archived text'}]}
            path, _ = save_record(original, folder)
            archived = folder / 'deleted' / path.name
            archived.parent.mkdir()
            path.rename(archived)
            self.assertTrue(has_source(folder, 'Catalog citation'))
            self.assertTrue(has_url(folder, 'https://example.org/record'))
            self.assertEqual((archived, True), save_record(original, folder))
            related = {'date': '1341-01', 'entries': [{'source': 'Alternate citation', 'german': 'Archived text'}]}
            self.assertEqual((archived, True), save_record(related, folder))
            self.assertFalse(path.exists())
            distinct = {'date': '1341', 'entries': [{'source': 'Another document'}]}
            self.assertEqual((folder / '1341_2.json', False), save_record(distinct, folder))

    def test_shorter_citation_matches_without_adding_redundant_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            citation = 'StAN, Fürstentum Ansbach, Geheimes Archiv: Seckendorffische Dokumente, Urkunden 11'
            original = {'date': '1350-02-11', 'entries': [{'source': citation + ' (BayHStA, Personenselekt Cart. 399 Nr. 11)',
                        'german': 'Reviewed text'}]}
            path, _ = save_record(original, folder)
            incoming = {'date': '1350-02-11', 'entries': [{'source': citation, 'url': 'new-url', 'german': 'Different text'}]}
            self.assertEqual(save_record(incoming, folder), (path, True))
            entry = json.loads(path.read_text())['entries'][0]
            self.assertEqual(entry['source'], original['entries'][0]['source'])
            self.assertEqual(entry['url'], 'new-url')
            self.assertEqual(entry['german'], 'Reviewed text')
            distinct = {'date': '1350-02-11', 'entries': [{'source': citation + '0', 'german': 'Other text'}]}
            self.assertFalse(save_record(distinct, folder)[1])

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
