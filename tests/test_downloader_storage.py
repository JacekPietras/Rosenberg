import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from downloader_storage import save_record, has_url


class DownloaderStorageTests(unittest.TestCase):
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
