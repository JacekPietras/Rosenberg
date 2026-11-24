import json
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'archive_records'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'archive_search'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from search_results import ResultsStore
import search_landesarchiv_bw as search
import archive_record_landesarchiv_bw as downloader
import archive_record_arcinsys_hessen as storage


def result_page(record_id, page):
    return f'''<div><article><table><tr><td title="Id: {record_id}, Onlinefreigabe: true"><b>Archive {record_id}</b></td></tr>
    <tr><td title="1400-01-01// Formulartyp 10028"><a href="../olf/struktur.php?bestand=123&amp;sprungId={record_id}">Findbuch</a></td></tr>
    </table></article></div><form name="uebergabe" action="ergebnis1a.php">
    <input name="treffer" value="2"><input name="bisTreffer" value="{page + 1}">
    <input name="trefferseite" value="{page}"></form>'''


class LandesarchivSearchTests(unittest.TestCase):
    def test_specialized_catalogue_forms_without_title_are_imported(self):
        cases = [
            ('1869', [('Person', 'Dietz, Johann'), ('Gegenstand', 'Missbrauch des geistlichen Amtes'),
                      ('Mitbeklagte/r', 'Thöne, Pfarrverweser von Rosenberg')]),
            ('1845', [('Kläger/-in', 'Hirschmüller, Xaver von Rosenberg'), ('Gegenstand', 'Forderung'),
                      ('Beklagte-/r', 'Pahl, Karl')]),
            ('', [('Name', 'von Rosenberg, Joachim Friedrich'), ('Geburtsdatum', '16. September 1899'),
                  ('Bemerkungen', 'Ausgeschieden am: 10.07.1942')]),
        ]
        for date, fields in cases:
            with self.subTest(fields=fields), tempfile.TemporaryDirectory() as directory:
                rows = [('Bestellsignatur', 'Archive 11'), ('Laufzeit', date), *fields]
                details = '<table>' + ''.join(f'<tr><td>{key}</td><td>{value}</td></tr>' for key, value in rows) + '</table>'
                with patch.object(downloader, 'DOCUMENT_DIR', Path(directory)), \
                        patch.object(downloader, 'fetch_page', return_value=details), \
                        patch.object(downloader, 'verify_permalink', side_effect=lambda opener, url, aid, *args: url):
                    path, _ = downloader.create_record('https://www.landesarchiv-bw.de/plink/?f=4-123', '11', '123')
                record = json.loads(path.read_text())
                self.assertEqual(record['date'], date or '9999')
                for label, value in fields:
                    self.assertIn(f'{label}: {value}', record['entries'][0]['german'])
                if date:
                    self.assertIn(f'Laufzeit: {date}', record['entries'][0]['german'])

    def test_partial_year_is_saved_with_unknown_digit(self):
        details = ('<table><tr><td>Bestellsignatur</td><td>Archive 11</td></tr>'
                   '<tr><td>Laufzeit</td><td>[158...]</td></tr><tr><td>Titel</td><td>Document</td></tr></table>')
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, 'DOCUMENT_DIR', Path(directory)), \
                patch.object(downloader, 'DOCUMENT_DIR', Path(directory)), patch.object(downloader, 'fetch_page', return_value=details), \
                patch.object(downloader, 'verify_permalink', side_effect=lambda opener, url, aid, *args: url):
            path, _ = downloader.create_record('https://www.landesarchiv-bw.de/plink/?f=4-123', '11', '123')
            self.assertEqual(path.name, '158X.json')
            self.assertEqual(json.loads(path.read_text())['date'], '158X')

    def test_permalink_redirect_to_requested_catalogue_record_is_verified(self):
        url = 'https://www.landesarchiv-bw.de/plink/?f=4-5466304'
        redirect = 'https://www2.landesarchiv-bw.de/ofs21/olf/struktur.php?bestand=10798&sprungId=13356277'
        with patch.object(downloader, 'fetch', return_value=(redirect, '<html></html>')):
            self.assertEqual(downloader.verify_permalink(None, url, '4-5466304', '13356277'), url)
            with self.assertRaises(ValueError):
                downloader.verify_permalink(None, url, '4-5466304', '13356278')

    def test_importer_tries_alternate_permalink_from_catalogue_page(self):
        details = ('<table><tr><td>Bestellsignatur</td><td>Archive 11</td></tr>'
                   '<tr><td>Permalink</td><td>http://www.landesarchiv-bw.de/plink/?f=4-456</td></tr>'
                   '<tr><td>Titel</td><td>Document</td></tr></table>')
        def verify(opener, url, aid, *args):
            if aid == '4-123':
                raise ValueError('incorrect redirect')
            return url
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, 'DOCUMENT_DIR', Path(directory)), \
                patch.object(downloader, 'DOCUMENT_DIR', Path(directory)), patch.object(downloader, 'fetch_page', return_value=details), \
                patch.object(downloader, 'verify_permalink', side_effect=verify):
            path, _ = downloader.create_record('https://www.landesarchiv-bw.de/plink/?f=4-123', '11', '123')
            self.assertEqual(json.loads(path.read_text())['entries'][0]['url'], 'https://www.landesarchiv-bw.de/plink/?f=4-456')

    def test_missing_date_uses_placeholder_and_keeps_viewer(self):
        details = '<table><tr><td>Bestellsignatur</td><td>Archive 11</td></tr><tr><td>Titel</td><td>Jörg von Rosenberg</td></tr></table>'
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, 'DOCUMENT_DIR', Path(directory)), \
                patch.object(downloader, 'DOCUMENT_DIR', Path(directory)), patch.object(downloader, 'fetch_page', return_value=details), \
                patch.object(downloader, 'verify_permalink', side_effect=lambda opener, url, aid, *args: url), \
                patch.object(downloader, 'read_viewer', return_value=('https://example.org/', {}, ['page'], '123')) as viewer, \
                patch.object(downloader, 'image_urls', return_value=['https://example.org/image.jpg']), \
                patch.object(downloader.time, 'sleep'):
            path, _ = downloader.create_record('https://www.landesarchiv-bw.de/plink/?f=4-123', '11', '123', has_viewer=True)
            record = json.loads(path.read_text())
            self.assertEqual(record['date'], '9999')
            self.assertEqual(record['entries'][0]['source'], 'Archive 11')
            self.assertEqual(record['entries'][0]['german'], 'Jörg von Rosenberg')
            self.assertEqual(record['entries'][0]['img'][0]['src'], 'https://example.org/image.jpg')
            viewer.assert_called_once()

    def test_search_stops_after_two_consecutive_download_failures(self):
        rows = [{'id': str(i), 'signature': f'Archive {i}', 'bestand': '123', 'date': '', 'has_viewer': False}
                for i in range(3)]
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(search.Client, 'search', return_value=iter((row, 3) for row in rows)), \
                patch.object(search.Client, 'resolve', return_value='https://www.landesarchiv-bw.de/plink/?f=4-123'), \
                patch.object(search.Client, 'wait'), patch.object(search.subprocess, 'run') as run, \
                patch.object(search, 'ResultsStore', side_effect=lambda archive: ResultsStore(archive, Path(directory) / 'results.json')), \
                patch.object(sys, 'argv', ['search', 'Rosenberg']):
            run.return_value.returncode = 1
            self.assertEqual(search.main(), 1)
            self.assertEqual(run.call_count, 2)

    def test_existing_citations_normalize_wrapping_but_distinguish_verweisung(self):
        sources = [
            'D Nr. 456, Verweisung',
            'D Nr. 456 Verweisung',
            'Generallandesarchiv Karlsruhe {D Nr. 456, Verweisung}',
            'Generallandesarchiv Karlsruhe {D Nr. 456 Verweisung}',
            'Generallandesarchiv Karlsruhe D Nr. 456 Verweisung',
            'Generallandesarchiv Karlsruhe D Nr. 456',
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for source in sources:
                with self.subTest(source=source):
                    (path / 'test.json').write_text(json.dumps({'entries': [{'source': ['unrelated', source]}]}))
                    suffix = ', Verweisung' if ', Verweisung' in source else ' Verweisung' if ' Verweisung' in source else ''
                    for candidate in ('', ', Verweisung', ' Verweisung'):
                        wanted = 'D Nr. 456' + candidate
                        expected = candidate == suffix and (len(wanted) >= 12 or source == wanted)
                        self.assertEqual(search.has_source(path, wanted), expected)
                    self.assertFalse(search.has_source(path, 'D Nr. 457'))
                    self.assertFalse(search.has_source(path, ''))

    def test_citation_substring_requires_twelve_normalized_characters(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'test.json').write_text(json.dumps({'entries': [{'source': 'Archive {123456789012}'}]}))
            self.assertFalse(search.has_source(path, '12345678901'))
            self.assertTrue(search.has_source(path, '123456789012'))
            (path / 'test.json').write_text(json.dumps({'entries': [{'source': '{12345678901}'}]}))
            self.assertTrue(search.has_source(path, '12345678901'))

    def test_skip_existing_checks_citation_and_urls_before_resolving(self):
        rows = [
            {'id': '11', 'signature': 'Known citation', 'bestand': '123'},
            {'id': '22', 'signature': 'Different citation', 'bestand': '123'},
            {'id': '33', 'signature': 'Another citation', 'bestand': '123'},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            documents = root / 'data/documents'
            documents.mkdir(parents=True)
            (documents / 'test.json').write_text(json.dumps({'entries': [
                {'source': ['Other', 'Known citation']},
                {'url': ['https://example.org/', 'http://www.landesarchiv-bw.de/plink/?f=4-22']},
                {'url': 'https://www2.landesarchiv-bw.de/ofs21/olf/druckansicht.php?bestand=123&id_titlaufn=33'},
            ]}))
            with patch.object(search, 'ROOT', root), patch.object(search.Client, 'search', return_value=iter((row, 3) for row in rows)), \
                    patch.object(search.Client, 'resolve') as resolve, patch.object(search.subprocess, 'run') as run, \
                    patch.object(search, 'ResultsStore', side_effect=lambda archive: ResultsStore(archive, Path(directory) / 'results.json')), \
                patch.object(sys, 'argv', ['search', 'Rosenberg', '--skip-existing']):
                self.assertEqual(search.main(), 0)
                resolve.assert_not_called()
                run.assert_not_called()

    def test_result_url_requires_exact_catalogue_id(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'test.json').write_text(json.dumps({'entries': [
                {'url': 'https://www.landesarchiv-bw.de/plink/?f=4-122'},
                {'url': 'https://example.org/plink/?f=4-22'},
                {'url': 'https://www.landesarchiv-bw.de/plink/?f=4-22-1'},
            ]}))
            self.assertFalse(search.has_result_url(path, '22'))

    def test_catalogue_line_breaks_are_preserved_without_splitting_inline_text(self):
        details = downloader.CatalogDetails()
        details.feed('<table><tr><td>Titel</td><td>Datum<br>Urfehde.<br/>Sr.: Jörg\n von '
                     '<b>Rosenberg</b><br>Ausf. Pap.</td></tr></table>')
        self.assertEqual(details.fields['titel'], 'Datum\nUrfehde.\nSr.: Jörg von Rosenberg\nAusf. Pap.')

    def test_day_first_german_catalogue_date_keeps_full_precision(self):
        self.assertEqual(downloader.iso_date('[158...]'), '158X')
        self.assertEqual(downloader.iso_date('[15..]'), '15XX')
        self.assertEqual(downloader.iso_date('158?'), '158X')
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
                patch.object(downloader, 'verify_permalink', side_effect=lambda opener, url, aid, *args: url):
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
                patch.object(downloader, 'verify_permalink', side_effect=lambda opener, url, aid, *args: url):
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
                patch.object(downloader, 'verify_permalink', side_effect=lambda opener, url, aid, *args: url):
            path, _ = downloader.create_record('https://www.landesarchiv-bw.de/plink/?f=4-4037151')
            self.assertIn(f'Siegelbeschreibung: {description}', json.loads(path.read_text())['entries'][0]['german'])

    def test_zeugen_are_preserved_as_catalogue_metadata(self):
        witnesses = 'Hans von Ingelheim, Hans von Rosenberg und Philipp von Bettendorff'
        details = f'''<table><tr><td>Bestellsignatur</td><td>Archive 11</td></tr>
        <tr><td>Laufzeit</td><td>1500 März 21</td></tr>
        <tr><td>Titel</td><td>Document text</td></tr>
        <tr><td>Zeugen</td><td>{witnesses}</td></tr></table>'''
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, 'DOCUMENT_DIR', Path(directory)), \
                patch.object(downloader, 'DOCUMENT_DIR', Path(directory)), patch.object(downloader, 'fetch_page', return_value=details), \
                patch.object(downloader, 'verify_permalink', side_effect=lambda opener, url, aid, *args: url):
            path, _ = downloader.create_record('https://www.landesarchiv-bw.de/plink/?f=4-123', '11', '123')
            self.assertIn(f'Zeugen: {witnesses}', json.loads(path.read_text())['entries'][0]['german'])

    def test_vermerke_are_preserved_as_catalogue_metadata(self):
        notes = 'Dabei ein Transfix vom gleichen Tag.'
        details = f'''<table><tr><td>Bestellsignatur</td><td>Archive 11</td></tr>
        <tr><td>Laufzeit</td><td>1468 Juli 12</td></tr>
        <tr><td>Titel</td><td>Document text</td></tr>
        <tr><td>Vermerke</td><td>{notes}</td></tr></table>'''
        with tempfile.TemporaryDirectory() as directory, patch.object(storage, 'DOCUMENT_DIR', Path(directory)), \
                patch.object(downloader, 'DOCUMENT_DIR', Path(directory)), patch.object(downloader, 'fetch_page', return_value=details), \
                patch.object(downloader, 'verify_permalink', side_effect=lambda opener, url, aid, *args: url):
            path, _ = downloader.create_record('https://www.landesarchiv-bw.de/plink/?f=4-123', '11', '123')
            self.assertIn(f'Vermerke: {notes}', json.loads(path.read_text())['entries'][0]['german'])

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
        output = io.StringIO()
        with patch.object(client, 'request', side_effect=['home', result_page('11', 0), result_page('12', 1)]) as req, \
                patch.object(sys, 'stderr', output):
            rows = list(client.search('Konrad von Rosenberg'))
        self.assertEqual([row['id'] for row, total in rows], ['11', '12'])
        self.assertEqual(rows[0][0]['bestand'], '123')
        self.assertIn(b'trefferseite=1', req.call_args.args[1])
        self.assertIn(b'%22Konrad+von+Rosenberg%22', req.call_args_list[1].args[1])
        self.assertIn('Catalogue page 1: results through 1 of 2', output.getvalue())
        self.assertIn('Catalogue page 2: results through 2 of 2', output.getvalue())

    def test_pagination_ends_at_advertised_range_with_fewer_visible_rows(self):
        client = search.Client(1)
        first = result_page('11', 0).replace('value="2"', 'value="60"').replace('name="bisTreffer" value="1"', 'name="bisTreffer" value="30"')
        last = result_page('12', 1).replace('value="2"', 'value="60"').replace('name="bisTreffer" value="2"', 'name="bisTreffer" value="60"')
        with patch.object(client, 'request', side_effect=['home', first, last]) as req:
            rows = list(client.search('Rosenberg'))
        self.assertEqual([row['id'] for row, _ in rows], ['11', '12'])
        self.assertEqual(req.call_count, 3)

    def test_skip_pages_jumps_to_requested_page(self):
        client = search.Client(1)
        first = result_page('11', 0).replace('value="2"', 'value="90"').replace('name="bisTreffer" value="1"', 'name="bisTreffer" value="30"')
        last = result_page('33', 2).replace('value="2"', 'value="90"').replace('name="bisTreffer" value="3"', 'name="bisTreffer" value="90"')
        with patch.object(client, 'request', side_effect=['home', first, last]) as req:
            rows = list(client.search('Rosenberg', skip_pages=2))
        self.assertEqual([row['id'] for row, _ in rows], ['33'])
        self.assertEqual(client.current_page, 3)
        self.assertIn(b'trefferseite=2', req.call_args.args[1])

    def test_empty_intermediate_page_is_an_error(self):
        client = search.Client(1)
        empty = result_page('11', 0).split('<form', 1)[1]
        with patch.object(client, 'request', side_effect=['home', '<form' + empty]):
            with self.assertRaisesRegex(ValueError, 'empty page'):
                list(client.search('Rosenberg'))

    def test_resume_at_last_result_does_not_save_a_false_negative(self):
        row = {'id': '11', 'signature': 'Archive 11'}
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory) / 'results.json'
            with patch.object(search.Client, 'search', return_value=iter([(row, 1)])), \
                    patch.object(search, 'ResultsStore', side_effect=lambda archive: ResultsStore(archive, Path(directory) / 'results.json')), \
                patch.object(sys, 'argv', ['search', 'Rosenberg', '--resume-after-result-id', '11']):
                self.assertEqual(search.main(), 0)
            self.assertTrue(json.loads(results.read_text())['queries']['Rosenberg'])

    def test_canonical_resolution(self):
        client = search.Client(1)
        with patch.object(client, 'request', return_value='<link rel="canonical" href="http://www.landesarchiv-bw.de/plink/?f=4-123">'):
            self.assertEqual(client.resolve({'id': '11', 'bestand': '123'}), 'https://www.landesarchiv-bw.de/plink/?f=4-123')

    def test_missing_collection_is_recovered_from_detail_page(self):
        client = search.Client(1)
        row = {'id': '8472160', 'bestand': None}
        page = ('<link rel="canonical" href="https://www.landesarchiv-bw.de/plink/?f=7-43244">'
                "<a href=\"javascript:oeffner('../olf/struktur.php?bestand=53073&amp;sprungId=8472160')\">Record</a>")
        with patch.object(client, 'request', return_value=page):
            self.assertEqual(client.resolve(row), 'https://www.landesarchiv-bw.de/plink/?f=7-43244')
        self.assertEqual(row['bestand'], '53073')

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
                patch.object(downloader, 'verify_permalink', side_effect=lambda opener, url, aid, *args: url), \
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
                patch.object(downloader, 'verify_permalink', side_effect=lambda opener, url, aid, *args: url):
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
                patch.object(downloader, 'verify_permalink', side_effect=lambda opener, url, aid, *args: url), \
                patch.object(downloader, 'fetch_page', return_value=details):
            path, existing = downloader.create_record('https://www.landesarchiv-bw.de/plink/?f=4-123')
            record = json.loads(path.read_text())
            self.assertFalse(existing)
            self.assertEqual(record['date'], '1385-04-25')
            self.assertNotIn('img', record['entries'][0])


if __name__ == '__main__':
    unittest.main()
