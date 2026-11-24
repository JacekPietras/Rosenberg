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
