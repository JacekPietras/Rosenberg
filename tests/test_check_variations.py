import contextlib
import importlib.util
import io
import tempfile
import subprocess
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
            return query in ('Rosinberg', 'Eberhard', 'Eberhard von Rosinberg')
        output = io.StringIO()
        with patch.object(module, 'surname_variants', return_value=['Rosenburgk', 'Rosinberg']), \
             patch.object(module, 'name_variants', return_value=['Eberhard', 'Everhard']), \
             patch.object(module.Checker, 'exists', exists), \
             patch('sys.argv', ['check_variations.py', 'monasterium', 'Eberhard von Rosenberg']), \
             contextlib.redirect_stdout(output):
            self.assertEqual(module.main(), 0)
        self.assertEqual(checked[:4], ['Rosenburgk', 'Rosinberg', 'Eberhard', 'Everhard'])
        self.assertEqual(len(checked), 9)
        self.assertIn('Eberhard von Rosinberg\ttrue', output.getvalue())
        self.assertIn('Eberhard de Rosinberg\tfalse', output.getvalue())
        self.assertNotIn('Rosenburgk\t', output.getvalue())

    def test_persistent_cache_separates_archives_and_stores_both_answers(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / 'checks.sqlite3'
            with patch.object(module.subprocess, 'run', side_effect=[
                subprocess.CompletedProcess([], 0, 'true\n'),
                subprocess.CompletedProcess([], 0, 'false\n'),
                subprocess.CompletedProcess([], 0, 'false\n'),
            ]) as run:
                first = module.Checker('monasterium', results_cache=cache)
                self.assertTrue(first.exists('Rosinberg'))
                self.assertFalse(first.exists('Rosenburgk'))
                second = module.Checker('monasterium', results_cache=cache)
                self.assertTrue(second.exists('Rosinberg'))
                self.assertFalse(second.exists('Rosenburgk'))
                other = module.Checker('regesta_imperii', results_cache=cache)
                self.assertFalse(other.exists('Rosinberg'))
                self.assertEqual(run.call_count, 3)

    def test_failures_are_not_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / 'checks.sqlite3'
            with patch.object(module.subprocess, 'run', side_effect=[
                subprocess.CompletedProcess([], 1, ''),
                subprocess.CompletedProcess([], 0, 'unexpected'),
                subprocess.CompletedProcess([], 0, 'true\n'),
            ]) as run:
                for _ in range(2):
                    with self.assertRaises(RuntimeError):
                        module.Checker('monasterium', results_cache=cache).exists('Rosinberg')
                self.assertTrue(module.Checker('monasterium', results_cache=cache).exists('Rosinberg'))
                self.assertEqual(run.call_count, 3)

    def test_absent_surnames_skip_all_names(self):
        with patch.object(module, 'surname_variants', return_value=['Absent']), \
             patch.object(module.Checker, 'exists', return_value=False) as check, \
             patch('sys.argv', ['check_variations.py', 'monasterium', 'Eberhard von Rosenberg']):
            self.assertEqual(module.main(), 0)
        check.assert_called_once_with('Absent')


if __name__ == '__main__':
    unittest.main()
