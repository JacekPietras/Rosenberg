import contextlib
import importlib.util
import io
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

    def test_title_and_zu_are_screened_and_combined(self):
        checked = []
        def exists(_self, query):
            checked.append(query)
            return query in ('Lauda', 'von Lauda', 'zu Lauda', 'des Lauda', 'vogt', 'advocatus', 'vogt zu Lauda')
        output = io.StringIO()
        with patch.object(module, 'surname_variants', return_value=['Lauda']), \
             patch.object(module, 'title_variants', return_value=['vogt', 'Voigt', 'advocatus']), \
             patch.object(module.Checker, 'exists', exists), \
             patch.object(module.Checker, 'run') as search, \
             patch('sys.argv', ['check_variations.py', 'monasterium', 'vogt zu Lauda']), \
             contextlib.redirect_stdout(output):
            self.assertEqual(module.main(), 0)
        self.assertEqual(checked, ['Lauda', 'von Lauda', 'v Lauda', 'v. Lauda', 'von. Lauda', 'de Lauda',
                                   'zu Lauda', 'des Lauda', 'vogt', 'Voigt', 'advocatus'])
        self.assertEqual([c.args[0] for c in search.call_args_list],
                         ['vogt von Lauda', 'vogt zu Lauda', 'vogt des Lauda', 'vogt Lauda',
                          'advocatus von Lauda', 'advocatus zu Lauda', 'advocatus des Lauda', 'advocatus Lauda'])

    def test_given_name_with_zu_never_checks_zu_or_des(self):
        checked = []
        def exists(_self, query):
            checked.append(query)
            return query in ('Lauda', 'Eberhard')
        with patch.object(module, 'surname_variants', return_value=['Lauda']), \
             patch.object(module, 'name_variants', return_value=['Eberhard']), \
             patch.object(module.Checker, 'exists', exists), \
             patch.object(module.Checker, 'run') as search, \
             patch('sys.argv', ['check_variations.py', 'monasterium', 'Eberhard zu Lauda']), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(module.main(), 0)
        self.assertNotIn('zu Lauda', checked)
        self.assertNotIn('des Lauda', checked)
        self.assertIn('von Lauda', checked)
        search.assert_called_once_with('Eberhard Lauda')

    def test_place_without_given_name_searches_surviving_variations(self):
        checked = []
        def exists(_self, query):
            checked.append(query)
            return query in ('Rosenberg', 'Rosinberg', 'von Rosenberg', 'de Rosinberg')
        with patch.object(module, 'surname_variants', return_value=['Rosenberg', 'Rosinberg']), \
             patch.object(module.Checker, 'exists', exists), \
             patch.object(module.Checker, 'run') as search, \
             patch('sys.argv', ['check_variations.py', 'monasterium', 'von Rosenberg']):
            self.assertEqual(module.main(), 0)
        self.assertIn('v. Rosenberg', checked)
        self.assertIn('von. Rosinberg', checked)
        self.assertEqual([call.args[0] for call in search.call_args_list],
                         ['von Rosenberg', 'Rosenberg', 'de Rosinberg', 'Rosinberg'])

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
             patch.object(module.Checker, 'run') as search, \
             patch('sys.argv', ['check_variations.py', 'monasterium', 'Eberhard von Rosenberg']), \
             contextlib.redirect_stdout(output):
            self.assertEqual(module.main(), 0)
        self.assertEqual(checked, ['Rosenburgk', 'Rosinberg', 'von Rosinberg', 'v Rosinberg',
                                   'v. Rosinberg', 'von. Rosinberg', 'de Rosinberg',
                                   'Eberhard', 'Everhard'])
        self.assertEqual([c.args[0] for c in search.call_args_list],
                         ['Eberhard von Rosinberg', 'Eberhard de Rosinberg', 'Eberhard Rosinberg'])

    def test_bare_surname_still_used_when_all_prefixes_absent(self):
        checked = []
        def exists(_self, query):
            checked.append(query)
            return query in ('Rosinberg', 'Eberhard')
        output = io.StringIO()
        with patch.object(module, 'surname_variants', return_value=['Rosinberg']), \
             patch.object(module, 'name_variants', return_value=['Eberhard']), \
             patch.object(module.Checker, 'exists', exists), \
             patch.object(module.Checker, 'run') as search, \
             patch('sys.argv', ['check_variations.py', 'monasterium', 'Eberhard von Rosenberg']), \
             contextlib.redirect_stdout(output):
            self.assertEqual(module.main(), 0)
        self.assertEqual(checked, ['Rosinberg', 'von Rosinberg', 'v Rosinberg',
                                   'v. Rosinberg', 'von. Rosinberg', 'de Rosinberg',
                                   'Eberhard'])
        search.assert_called_once_with('Eberhard Rosinberg')

    def test_normal_search_calls_script_without_exists_and_stops_on_failure(self):
        checker = module.Checker('monasterium', results_file=Path('/tmp/test-results.json'))
        with patch.object(module.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            checker.run('Eberhard von Rosinberg')
        command = run.call_args.args[0]
        self.assertNotIn('--exists', command)
        self.assertIn('--skip-existing', command)
        self.assertIn('Eberhard von Rosinberg', command)
        self.assertIn('--results-file', command)
        with patch.object(module.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)):
            with self.assertRaises(RuntimeError):
                checker.run('Eberhard Rosinberg')

    def test_http_500_continues_following_final_queries(self):
        def exists(_self, query):
            return query in ('Rosinberg', 'von Rosinberg', 'Eberhard')
        def run(checker, query):
            if query == 'Eberhard von Rosinberg':
                checker.failed.append(query)
        with patch.object(module, 'surname_variants', return_value=['Rosinberg']), \
             patch.object(module, 'name_variants', return_value=['Eberhard']), \
             patch.object(module.Checker, 'exists', exists), \
             patch.object(module.Checker, 'run', autospec=True, side_effect=run) as search, \
             patch('sys.argv', ['check_variations.py', 'monasterium', 'Eberhard von Rosenberg']), \
             contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(module.main(), 1)
        self.assertEqual([call.args[1] for call in search.call_args_list],
                         ['Eberhard von Rosinberg', 'Eberhard Rosinberg'])
        self.assertIn('Eberhard von Rosinberg', errors.getvalue())

    def test_http_500_screening_remains_possible(self):
        checker = module.Checker('monasterium')
        with patch.object(module.subprocess, 'run', return_value=subprocess.CompletedProcess([], 75, '')), \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertTrue(checker.exists('Rosinberg'))
        self.assertEqual(checker.failed, ['Rosinberg'])

    def test_absent_surnames_skip_all_names(self):
        with patch.object(module, 'surname_variants', return_value=['Absent']), \
             patch.object(module.Checker, 'exists', return_value=False) as check, \
             patch('sys.argv', ['check_variations.py', 'monasterium', 'Eberhard von Rosenberg']):
            self.assertEqual(module.main(), 0)
        check.assert_called_once_with('Absent')


if __name__ == '__main__':
    unittest.main()
