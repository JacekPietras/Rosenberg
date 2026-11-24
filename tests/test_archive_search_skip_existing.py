import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/archive_search'))
sys.path.insert(0, str(ROOT / 'scripts/archive_records'))

from search_results import ResultsStore
import search_arcinsys_hessen as hessen
import search_gda_bayern as bayern
import search_landesarchiv_nrw as nrw
import search_monasterium as monasterium
import search_regesta_imperii as regesta


class SkipExistingTests(unittest.TestCase):
    def test_bavarian_result_without_citation_requires_corroborating_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'record.json').write_text(json.dumps({'date': '1363-03-27', 'entries': [{
                'source': 'BayHStA, Hochstift Regensburg Urkunden 491/a',
                'german': 'Beginning of charter. S: Cunrad von Rosenberg, Viztum von Amberg. End.'}]}))
            row = {'title': '491/a - Charter', 'date': '1363 März 27',
                   'provenance': 'Hochstift Regensburg',
                   'description': 'S: Cunrad von Rosenberg, Viztum von Amberg.'}
            self.assertTrue(bayern.has_existing_description(root, row))
            for field, wrong in [('date', '1363 März 28'), ('provenance', 'Other archive'),
                                 ('title', '492 - Charter'), ('description', 'A different description that is sufficiently long')]:
                self.assertFalse(bayern.has_existing_description(root, {**row, field: wrong}))

    def test_bavarian_full_citation_skips_different_result_title_and_url(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            documents = root / 'data/documents'
            documents.mkdir(parents=True)
            (documents / 'record.json').write_text(json.dumps({'entries': [{
                'source': 'BayHStA, Hochstift Regensburg Urkunden 491/a',
                'url': 'https://www.gda.bayern.de/gvl/document/stable'}]}))
            row = {'title': '491/a - Vlrich [von Ettenstatt]',
                   'citation': 'BayHStA, Hochstift Regensburg Urkunden 491/a',
                   'url': 'https://www.gda.bayern.de/gvl/archive.xhtml?id=other'}
            with patch.object(bayern, 'ResultsStore', side_effect=lambda archive: ResultsStore(archive, root / 'results.json')), \
                    patch.object(bayern, 'ROOT', root), patch.object(bayern.Client, 'search', return_value=iter([(row, 1)])), \
                    patch.object(sys, 'argv', ['search', 'von Rosenberg', '--skip-existing', '--cache-dir', str(root / 'cache')]), \
                    patch('subprocess.run') as run:
                self.assertEqual(bayern.main(), 0)
                run.assert_not_called()

    def test_citations_skip_import_for_each_search(self):
        signature = 'D Nr. 456, Verweisung'
        cases = [
            (hessen, {'columnKeySignatur': signature, 'columnKeyActions': [
                {'key': 'rowActionKeyShowItem', 'detailId': '123', 'additionalParameters': {'itemPrefix': 'v'}}]}, True),
            (bayern, {'title': signature, 'url': 'https://www.gda.bayern.de/gvl/archive.xhtml?id=123'}, True),
            (nrw, {'signatur': signature, 'nodeid': 'VERZEICHNUNGSEINHEIT-123'}, False),
            (monasterium, {'title': signature, 'url': 'https://www.monasterium.net/mom/a/b/charter'}, False),
            (regesta, {'title': signature, 'url': 'https://www.regesta-imperii.de/regesten/suche/result/nr/123'}, False),
        ]
        for module, row, iterator in cases:
            with self.subTest(search=module.__name__), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                documents = root / 'data/documents'
                documents.mkdir(parents=True)
                (documents / 'record.json').write_text(json.dumps({'entries': [
                    {'source': 'Generallandesarchiv Karlsruhe {D Nr. 456, Verweisung}'}]}))
                result = iter([(row, 1)]) if iterator else ([row], 1)
                argv = ['search', 'Rosenberg', '--skip-existing']
                if module in (bayern, nrw, monasterium, regesta):
                    argv += ['--cache-dir', str(root / 'cache')]
                with patch.object(module, 'ResultsStore', side_effect=lambda archive: ResultsStore(archive, root / 'results.json')), \
                        patch.object(module, 'ROOT', root), patch.object(module.Client, 'search', return_value=result), \
                        patch.object(sys, 'argv', argv), patch('subprocess.run') as run:
                    if module in (nrw, regesta):
                        importer = module.nrw if module is nrw else module.ri
                        with patch.object(importer, 'create_record') as create:
                            self.assertEqual(module.main(), 0)
                            create.assert_not_called()
                    else:
                        self.assertEqual(module.main(), 0)
                    run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
