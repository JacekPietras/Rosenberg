import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import search_landesarchiv_bw as search
import downloader_landesarchiv as downloader
import downloader_arcinsys_hessen as storage


def result_page(record_id, page):
    return f'''<div><article><table><tr><td title="Id: {record_id}, Onlinefreigabe: true"><b>Archive {record_id}</b></td></tr>
    <tr><td title="1400-01-01// Formulartyp 10028"><a href="../olf/struktur.php?bestand=123&amp;sprungId={record_id}">Findbuch</a></td></tr>
    </table></article></div><form name="uebergabe" action="ergebnis1a.php">
    <input name="treffer" value="2"><input name="trefferseite" value="{page}"></form>'''


class LandesarchivSearchTests(unittest.TestCase):
    def test_pagination_and_form(self):
        client = search.Client(1)
        with patch.object(client, 'request', side_effect=['home', result_page('11', 0), result_page('12', 1)]) as req:
            rows = list(client.search('Konrad von Rosenberg'))
        self.assertEqual([row['id'] for row, total in rows], ['11', '12'])
        self.assertEqual(rows[0][0]['bestand'], '123')
        self.assertIn(b'trefferseite=1', req.call_args.args[1])
        self.assertIn(b'%22Konrad+von+Rosenberg%22', req.call_args_list[1].args[1])

    def test_canonical_resolution(self):
        client = search.Client(1)
        with patch.object(client, 'request', return_value='<link rel="canonical" href="http://www.landesarchiv-bw.de/plink/?f=4-123">'):
            self.assertEqual(client.resolve({'id': '11', 'bestand': '123'}), 'https://www.landesarchiv-bw.de/plink/?f=4-123')

    def test_result_viewer_is_detected(self):
        page = search.SearchPage()
        page.feed(result_page('11', 0).replace('</table></article>',
            '<a href="javascript:open(\'../bild_zoom/zoom.php?id=11\')">Viewer</a></table></article>'))
        self.assertTrue(page.rows[0]['has_viewer'])

    def test_existing_record_gains_viewer_images(self):
        details = ('<table><tr><td>Bestellsignatur</td><td>Archive 11</td></tr>'
                   '<tr><td>Laufzeit</td><td>1400</td></tr><tr><td>Titel</td><td>Document text</td></tr></table>')
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, 'DOCUMENT_DIR', Path(directory)), \
                patch.object(downloader, 'DOCUMENT_DIR', Path(directory)), patch.object(downloader, 'fetch_page', return_value=details), \
                patch.object(downloader.time, 'sleep'), patch.object(downloader, 'read_viewer', return_value=('viewer', {}, ['page'], '123')), \
                patch.object(downloader, 'archive_image_urls', return_value=['https://archive/image']):
            url = 'https://www.landesarchiv-bw.de/plink/?f=4-123'
            path, _ = downloader.create_record(url, '11', '123', True)
            downloader.create_record(url, '11', '123', True, True, 1)
            downloader.create_record(url, '11', '123', True, True, 1)
            entry = json.loads(path.read_text())['entries'][0]
            self.assertEqual(entry['img'], [{'src': 'https://archive/image'}])
            self.assertEqual(entry['german'], 'Document text')

    def test_download_metadata_without_image_viewer(self):
        details = '''<table><tr><td>Bestellsignatur</td><td>Archive 11</td></tr>
        <tr><td>Laufzeit</td><td>1400</td></tr><tr><td>Titel</td><td>Document text</td></tr></table>'''
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, 'DOCUMENT_DIR', Path(directory)), \
                patch.object(downloader, 'DOCUMENT_DIR', Path(directory)), patch.object(downloader, 'fetch_page', return_value=details):
            path, existing = downloader.create_record('https://www.landesarchiv-bw.de/plink/?f=4-123', '11', '123', True)
            self.assertFalse(existing)
            self.assertEqual(json.loads(path.read_text())['entries'][0]['german'], 'Document text')
            self.assertEqual(downloader.create_record('https://www.landesarchiv-bw.de/plink/?f=4-123', '11', '123', True), (path, True))


if __name__ == '__main__':
    unittest.main()
