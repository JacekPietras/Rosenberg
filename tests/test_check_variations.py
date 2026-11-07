import contextlib
import importlib.util
import io
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/archive_search/check_variations.py'
spec = importlib.util.spec_from_file_location('check_variations', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class VariationChecks(unittest.TestCase):
    def test_actual_variant_sources_preserve_distinct_spellings(self):
        self.assertIn('Eberhardi', module.name_variants('Eberhard', module.ROOT / 'data/names.md'))
        surnames = module.surname_variants('Rosenberg', module.ROOT / 'data/places.json')
        self.assertIn('Rosinberg', surnames)
        self.assertIn('Rosenburgk', surnames)
        self.assertIn('Roßenberg', surnames)
        self.assertIn('Rossenberg', surnames)

    def test_screening_and_full_queries(self):
        checked = []
        def exists(_self, query):
            checked.append(query)
            return query in ('Rosinberg', 'von Rosinberg', 'de Rosinberg', 'Eberhard', 'Eberhard von Rosinberg')
        output = io.StringIO()
        with patch.object(module, 'surname_variants', return_value=['Rosenburgk', 'Rosinberg']), \
             patch.object(module, 'name_variants', return_value=['Eberhard', 'Everhard']), \
             patch.object(module.Checker, 'exists', exists), \
             patch('sys.argv', ['check_variations.py', 'monasterium', 'Eberhard von Rosenberg']), \
             contextlib.redirect_stdout(output):
            self.assertEqual(module.main(), 0)
        self.assertEqual(checked, ['Rosenburgk', 'Rosinberg', 'von Rosinberg', 'v Rosinberg',
                                   'v. Rosinberg', 'von. Rosinberg', 'de Rosinberg',
                                   'Eberhard', 'Everhard', 'Eberhard von Rosinberg',
                                   'Eberhard de Rosinberg'])
        self.assertIn('Eberhard von Rosinberg\ttrue', output.getvalue())
        self.assertIn('Eberhard de Rosinberg\tfalse', output.getvalue())
        self.assertNotIn('Rosenburgk\t', output.getvalue())
        self.assertNotIn('Eberhard v Rosinberg', output.getvalue())

    def test_no_prefixed_surname_skips_given_names(self):
        checked = []
        def exists(_self, query):
            checked.append(query)
            return query == 'Rosinberg'
        with patch.object(module, 'surname_variants', return_value=['Rosinberg']), \
             patch.object(module.Checker, 'exists', exists), \
             patch('sys.argv', ['check_variations.py', 'monasterium', 'Eberhard von Rosenberg']):
            self.assertEqual(module.main(), 0)
        self.assertEqual(checked, ['Rosinberg', 'von Rosinberg', 'v Rosinberg',
                                   'v. Rosinberg', 'von. Rosinberg', 'de Rosinberg'])

    def test_absent_surnames_skip_all_names(self):
        with patch.object(module, 'surname_variants', return_value=['Absent']), \
             patch.object(module.Checker, 'exists', return_value=False) as check, \
             patch('sys.argv', ['check_variations.py', 'monasterium', 'Eberhard von Rosenberg']):
            self.assertEqual(module.main(), 0)
        check.assert_called_once_with('Absent')


if __name__ == '__main__':
    unittest.main()
