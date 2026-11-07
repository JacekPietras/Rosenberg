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

    def test_title_and_zu_are_screened_and_combined(self):
        checked = []
        def exists(_self, query):
            checked.append(query)
            return query in ('Lauda', 'von Lauda', 'zu Lauda', 'des Lauda', 'vogt', 'advocatus', 'vogt zu Lauda')
        output = io.StringIO()
        with patch.object(module, 'surname_variants', return_value=['Lauda']), \
             patch.object(module, 'title_variants', return_value=['vogt', 'Voigt', 'advocatus']), \
             patch.object(module.Checker, 'exists', exists), \
             patch('sys.argv', ['check_variations.py', 'monasterium', 'vogt zu Lauda']), \
             contextlib.redirect_stdout(output):
            self.assertEqual(module.main(), 0)
        self.assertEqual(checked, ['Lauda', 'von Lauda', 'v Lauda', 'v. Lauda', 'von. Lauda', 'de Lauda',
                                   'zu Lauda', 'des Lauda', 'vogt', 'Voigt', 'advocatus',
                                   'vogt von Lauda', 'vogt zu Lauda', 'vogt des Lauda', 'vogt Lauda',
                                   'advocatus von Lauda', 'advocatus zu Lauda', 'advocatus des Lauda', 'advocatus Lauda'])
        self.assertEqual(output.getvalue().splitlines(),
                         ['vogt von Lauda\tfalse', 'vogt zu Lauda\ttrue', 'vogt des Lauda\tfalse', 'vogt Lauda\tfalse',
                          'advocatus von Lauda\tfalse', 'advocatus zu Lauda\tfalse', 'advocatus des Lauda\tfalse', 'advocatus Lauda\tfalse'])

    def test_given_name_with_zu_never_checks_zu_or_des(self):
        checked = []
        def exists(_self, query):
            checked.append(query)
            return query in ('Lauda', 'Eberhard')
        with patch.object(module, 'surname_variants', return_value=['Lauda']), \
             patch.object(module, 'name_variants', return_value=['Eberhard']), \
             patch.object(module.Checker, 'exists', exists), \
             patch('sys.argv', ['check_variations.py', 'monasterium', 'Eberhard zu Lauda']), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(module.main(), 0)
        self.assertNotIn('zu Lauda', checked)
        self.assertNotIn('des Lauda', checked)
        self.assertIn('von Lauda', checked)
        self.assertIn('Eberhard Lauda', checked)

    def test_multiword_title_variants(self):
        self.assertEqual(module.title_variants('der Rote', module.ROOT / 'data/titles.md'),
                         ['der Rote', 'Rufus'])

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
                                   'Eberhard de Rosinberg', 'Eberhard Rosinberg'])
        self.assertIn('Eberhard von Rosinberg\ttrue', output.getvalue())
        self.assertIn('Eberhard de Rosinberg\tfalse', output.getvalue())
        self.assertNotIn('Rosenburgk\t', output.getvalue())
        self.assertNotIn('Eberhard v Rosinberg', output.getvalue())

    def test_bare_surname_still_used_when_all_prefixes_absent(self):
        checked = []
        def exists(_self, query):
            checked.append(query)
            return query in ('Rosinberg', 'Eberhard')
        output = io.StringIO()
        with patch.object(module, 'surname_variants', return_value=['Rosinberg']), \
             patch.object(module, 'name_variants', return_value=['Eberhard']), \
             patch.object(module.Checker, 'exists', exists), \
             patch('sys.argv', ['check_variations.py', 'monasterium', 'Eberhard von Rosenberg']), \
             contextlib.redirect_stdout(output):
            self.assertEqual(module.main(), 0)
        self.assertEqual(checked, ['Rosinberg', 'von Rosinberg', 'v Rosinberg',
                                   'v. Rosinberg', 'von. Rosinberg', 'de Rosinberg',
                                   'Eberhard', 'Eberhard Rosinberg'])
        self.assertEqual(output.getvalue().strip(), 'Eberhard Rosinberg\tfalse')

    def test_absent_surnames_skip_all_names(self):
        with patch.object(module, 'surname_variants', return_value=['Absent']), \
             patch.object(module.Checker, 'exists', return_value=False) as check, \
             patch('sys.argv', ['check_variations.py', 'monasterium', 'Eberhard von Rosenberg']):
            self.assertEqual(module.main(), 0)
        check.assert_called_once_with('Absent')


if __name__ == '__main__':
    unittest.main()
