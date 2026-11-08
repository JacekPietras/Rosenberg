import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'archive_records'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'archive_search'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import search_landesarchiv_bw as search
import archive_record_landesarchiv_bw as downloader
import archive_record_arcinsys_hessen as storage


def result_page(record_id, page):
    return f'''<div><article><table><tr><td title="Id: {record_id}, Onlinefreigabe: true"><b>Archive {record_id}</b></td></tr>
    <tr><td title="1400-01-01// Formulartyp 10028"><a href="../olf/struktur.php?bestand=123&amp;sprungId={record_id}">Findbuch</a></td></tr>
    </table></article></div><form name="uebergabe" action="ergebnis1a.php">
    <input name="treffer" value="2"><input name="trefferseite" value="{page}"></form>'''


class LandesarchivSearchTests(unittest.TestCase):
    def test_day_first_german_catalogue_date_keeps_full_precision(self):
        self.assertEqual(downloader.iso_date('25. Apr. 1385'), '1385-04-25')
        self.assertEqual(downloader.iso_date('25. April 1385'), '1385-04-25')
        self.assertEqual(downloader.leading_title_date('1316 Juni 29 (an der heiligen Tag)'), '1316-06-29')
        self.assertEqual(downloader.leading_title_date('1408 Nov. 11 (sant Mertins tag)'), '1408-11-11')
        self.assertEqual(downloader.leading_title_date('[1575] Feb. 22 (Petri Cathedra)'), '1575-02-22')
        self.assertIsNone(downloader.leading_title_date('Hohenlohe gegen Hatzfeldt'))

    def test_precise_leading_title_date_overrides_year_only_catalogue_date(self):
        details = '''<table><tr><td>Bestellsignatur</td><td>Archive 11</td></tr>
        <tr><td>Laufzeit</td><td>1316</td></tr><tr><td>Titel</td><td>1316 Juni 29 - Konrad von Rosenberg</td></tr></table>'''
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, 'DOCUMENT_DIR', Path(directory)), \
                patch.object(downloader, 'DOCUMENT_DIR', Path(directory)), patch.object(downloader, 'fetch_page', return_value=details), \
                patch.object(downloader, 'verify_permalink', side_effect=lambda opener, url, aid: url):
            path, _ = downloader.create_record('https://www.landesarchiv-bw.de/plink/?f=4-123', '11', '123')
            self.assertEqual(path.name, '1316-06-29.json')
            self.assertEqual(json.loads(path.read_text())['date'], '1316-06-29')

    def test_darin_date_and_content_are_preserved(self):
        title = ('Rechtsstreit vor dem Reichskammergericht zwischen den Eigentumserben des verstorbenen '
                 'Konrad von Rosenberg als Klägern und Albrecht Christoph von Rosenberg als Lehenserbe '
                 'wegen einer der Pfarrei Waldmannshofen zustehenden Korngült von einem Gut zu Sechselbach.')
        darin = ('Darin: 1400 April 25 (Sonntag n. Ostern). Konrad von Weinsberg und seine Ehefrau Anna '
                 'geb. von Hohenlohe verkaufen für 120 fl. ihr Gut zu Sechselbach an die Pfarrei.')
        details = f'''<table><tr><td>Bestellsignatur</td><td>Archive 188</td></tr>
        <tr><td>Laufzeit</td><td>(1400,1582-1590) 1591-1594</td></tr>
        <tr><td>Titel</td><td>{title}</td></tr><tr><td>Enthält</td><td>{darin}</td></tr></table>'''
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, 'DOCUMENT_DIR', Path(directory)), \
                patch.object(downloader, 'DOCUMENT_DIR', Path(directory)), patch.object(downloader, 'fetch_page', return_value=details), \
                patch.object(downloader, 'verify_permalink', side_effect=lambda opener, url, aid: url):
            path, _ = downloader.create_record('https://www.landesarchiv-bw.de/plink/?f=4-188', '188', '123')
            record = json.loads(path.read_text())
            entry = record['entries'][0]
            self.assertEqual(record['date'], '1400-04-25')
            self.assertIn(title, entry['german'])
            self.assertIn(darin, entry['german'])

    def test_siegelbeschreibung_is_preserved_as_catalogue_metadata(self):
        description = 'Siegel des Ausstellers (fehlt) und der Zeugen: Conrad von Rosenberg und Wiprecht von Helmstadt.'
        details = f'''<table><tr><td>Bestellsignatur</td><td>Archive 4037151</td></tr>
        <tr><td>Laufzeit</td><td>1390 Juni 24</td></tr>
        <tr><td>Titel</td><td>Document text</td></tr>
        <tr><td>Siegelbeschreibung</td><td>{description}</td></tr></table>'''
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, 'DOCUMENT_DIR', Path(directory)), \
                patch.object(downloader, 'DOCUMENT_DIR', Path(directory)), patch.object(downloader, 'fetch_page', return_value=details), \
                patch.object(downloader, 'verify_permalink', side_effect=lambda opener, url, aid: url):
            path, _ = downloader.create_record('https://www.landesarchiv-bw.de/plink/?f=4-4037151')
            self.assertIn(f'Siegelbeschreibung: {description}', json.loads(path.read_text())['entries'][0]['german'])

    def test_existing_year_only_file_is_renamed_when_precise_date_is_found(self):
        for name in ('1418.json', '1418_3.json'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / name
                path.write_text(json.dumps({'date': '1418', 'entries': [{'source': 'Archive record'}]}))
                promoted = downloader.promote_existing_date(path, '1418-02-22')
                self.assertEqual(promoted.name, '1418-02-22.json')
                self.assertFalse(path.exists())
                self.assertEqual(json.loads(promoted.read_text())['date'], '1418-02-22')

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
                patch.object(downloader, 'verify_permalink', side_effect=lambda opener, url, aid: url), \
                patch.object(downloader.time, 'sleep'), patch.object(downloader, 'read_viewer', return_value=('viewer', {}, ['page'], '123')), \
                patch.object(downloader, 'image_urls', return_value=['https://archive/image']):
            url = 'https://www.landesarchiv-bw.de/plink/?f=4-123'
            path, _ = downloader.create_record(url, '11', '123')
            downloader.create_record(url, '11', '123', True, 1)
            downloader.create_record(url, '11', '123', True, 1)
            entry = json.loads(path.read_text())['entries'][0]
            self.assertEqual(entry['img'], [{'src': 'https://archive/image'}])
            self.assertIn('Document text', entry['german'])
            self.assertIn('Laufzeit: 1400', entry['german'])

    def test_download_metadata_without_image_viewer(self):
        details = '''<table><tr><td>Bestellsignatur</td><td>Archive 11</td></tr>
        <tr><td>Laufzeit</td><td>1400</td></tr><tr><td>Titel</td><td>Document text</td></tr></table>'''
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, 'DOCUMENT_DIR', Path(directory)), \
                patch.object(downloader, 'DOCUMENT_DIR', Path(directory)), patch.object(downloader, 'fetch_page', return_value=details), \
                patch.object(downloader, 'verify_permalink', side_effect=lambda opener, url, aid: url):
            path, existing = downloader.create_record('https://www.landesarchiv-bw.de/plink/?f=4-123', '11', '123')
            self.assertFalse(existing)
            self.assertIn('Document text', json.loads(path.read_text())['entries'][0]['german'])
            self.assertEqual(downloader.create_record('https://www.landesarchiv-bw.de/plink/?f=4-123', '11', '123'), (path, True))

    def test_permalink_without_viewer_creates_metadata_record_without_images(self):
        details = '''<table><tr><td>Bestellsignatur</td><td>Archive 11</td></tr>
        <tr><td>Laufzeit</td><td>25. Apr. 1385</td></tr><tr><td>Titel</td><td>Document text</td></tr></table>'''
        discovered = ('https://archive/details?id=11', '', {}, [], '')
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, 'DOCUMENT_DIR', Path(directory)), \
                patch.object(downloader, 'DOCUMENT_DIR', Path(directory)), \
                patch.object(downloader, 'discover_viewer', return_value=discovered), \
                patch.object(downloader, 'verify_permalink', side_effect=lambda opener, url, aid: url), \
                patch.object(downloader, 'fetch_page', return_value=details):
            path, existing = downloader.create_record('https://www.landesarchiv-bw.de/plink/?f=4-123')
            record = json.loads(path.read_text())
            self.assertFalse(existing)
            self.assertEqual(record['date'], '1385-04-25')
            self.assertNotIn('img', record['entries'][0])


if __name__ == '__main__':
    unittest.main()
