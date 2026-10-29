"""Checks for the proposed fact validator; all fixtures are synthetic."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/validate_facts.py'
spec = importlib.util.spec_from_file_location('validate_facts', SCRIPT)
facts = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = facts
spec.loader.exec_module(facts)


class FactValidatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')
        return path

    def check(self, value, relative='documents/test.json', strict=False):
        validator = facts.Validator(strict)
        validator.person_ids.add('known_id')
        validator.validate_file(self.write(relative, value))
        return validator

    def errors(self, validator):
        return [item for item in validator.diagnostics if item.severity == 'error']

    def document(self, *items, date='1395-04-12'):
        return {'date': date, 'entries': [{'facts': list(items)}]}

    def parent(self, **extra):
        return {'type': 'parent', 'person': 'known_id', 'of': 'Arnold von Rosenberg', **extra}

    def test_supported_types_and_flat_names_or_ids(self):
        items = [self.parent(type=kind) for kind in ('parent', 'sibling', 'spouse')]
        items += [self.parent(type='kin', term='Vetter'), {'type': 'title', 'person': 'known_id', 'personTitle': ['Ritter', 'der Ältere']}]
        validator = self.check(self.document(*items))
        self.assertEqual([], validator.diagnostics)
        self.assertEqual(5, validator.counts['typed'])

    def test_required_and_forbidden_fields(self):
        cases = [self.parent(type='father'), self.parent(type=[]),
                 {'type': 'parent', 'person': 'A'}, self.parent(person={'name': 'A'}),
                 self.parent(personId='known_id'), self.parent(type='kin'),
                 self.parent(type='kin', term=' '), {'type': 'title', 'person': 'A'},
                 self.parent(type='title', personTitle=['Ritter']),
                 self.parent(term='Vetter'), self.parent(of=' ')]
        for item in cases:
            with self.subTest(item=item):
                self.assertTrue(self.errors(self.check(self.document(item))))

    def test_title_arrays_not_scalar_null_empty_duplicate_or_nonstring(self):
        for value in ('Ritter', None, [], [''], ['Ritter', 'Ritter'], [17], [['Ritter']]):
            with self.subTest(value=value):
                self.assertTrue(self.errors(self.check(self.document(self.parent(personTitle=value)))))
        self.assertFalse(self.errors(self.check(self.document(self.parent(ofTitle=['Ritter'])))))

    def test_calendar_dates_and_iso_precision(self):
        for value in ('1395', '1395-02', '1396-02-29'):
            self.assertFalse(self.errors(self.check(self.document(self.parent(date=value)))))
        for value in ('0000', '1395-13', '1395-02-29', '1395-2', '1395-04-31', 1395, True, '1395/1396'):
            with self.subTest(value=value):
                self.assertTrue(self.errors(self.check(self.document(self.parent(date=value)))))

    def test_book_note_dates_explicit_even_with_enclosing_date(self):
        for relative in ('books/test.json', 'notes/nested/test.json'):
            self.assertTrue(self.errors(self.check(self.document(self.parent()), relative)))
            self.assertFalse(self.errors(self.check(self.document(self.parent(date='1395')), relative)))
        validator = self.check({'book': 'Example [1872]', 'date': '1872', 'facts': [self.parent()]}, 'elsewhere/book.json')
        self.assertTrue(self.errors(validator))

    def test_inherited_document_date_ranges_and_override(self):
        for value in ('1395/1396', '1395-1396', '1395-04-12--1395-04-15'):
            self.assertFalse(self.errors(self.check(self.document(self.parent(), date=value))))
        self.assertTrue(self.errors(self.check(self.document(self.parent(), date='1396/1395'))))
        self.assertTrue(self.errors(self.check({'facts': [self.parent()]})))
        self.assertFalse(self.errors(self.check(self.document(self.parent(date='1395'), date='bad metadata'))))
        self.assertFalse(self.errors(self.check({'date': '1395-1396', 'entries': [{'facts': ['Legacy']}]})))

    def test_null_dates_rejected_and_optional_dates_omitted(self):
        for relative in ('documents/test.json', 'books/test.json', 'notes/test.json'):
            for item in (self.parent(date=None), {'text': 'Example fact', 'date': None}):
                with self.subTest(relative=relative, item=item):
                    self.assertTrue(self.errors(self.check(self.document(item), relative)))
        self.assertTrue(self.errors(self.check(self.document(self.parent(), date=None))))
        self.assertFalse(self.errors(self.check(self.document(self.parent()))))
        self.assertFalse(self.errors(self.check(self.document({'text': 'Example fact'}))))

    def test_legacy_default_and_strict_migration(self):
        value = self.document('Old text', {'text': 'Other text', 'date': '1395'})
        self.assertEqual(1, len(self.errors(self.check(value, 'books/test.json'))))
        self.assertEqual(1, len(self.errors(self.check(value, 'books/test.json', strict=True))))
        self.assertFalse(self.errors(self.check(value, strict=True)))
        self.assertTrue(self.errors(self.check(self.document({'text': 'A', 'extra': 1}))))
        self.assertTrue(self.errors(self.check(self.document({'text': ' '}))))

    def test_nested_facts_and_bad_arrays(self):
        validator = self.check({'research': [{'facts': [self.parent(date='1395'), None]}]}, 'notes/test.json')
        self.assertEqual(2, validator.counts['facts'])
        self.assertIn('#/research/0/facts/1', self.errors(validator)[0].location)
        self.assertTrue(self.errors(self.check({'facts': 'bad'})))

    def test_generated_registry_metadata_is_not_source_facts(self):
        validator = self.check([{'name': 'Example', 'relationships': [], 'familyGraph': {
            'coverage': {'facts': {'unresolvedMentions': 0}},
        }}], 'people.json')
        self.assertFalse(validator.diagnostics)
        self.assertEqual(0, validator.counts['facts'])

    def test_guesses_use_fact_shapes_and_require_historical_dates(self):
        entry = {'guesses': [self.parent(date='1395'), {'date': '1395', 'text': 'A possible event'}]}
        validator = self.check({'book': 'Example', 'entries': [entry]}, 'books/test.json', strict=True)
        self.assertEqual([], validator.diagnostics)
        self.assertEqual(2, validator.counts['guesses'])
        self.assertEqual(0, validator.counts['facts'])

        entry['guesses'] = [self.parent(), {'date': '1395-02-29', 'text': 'Invalid date'}, 'Undated interpretation']
        validator = self.check({'book': 'Example', 'entries': [entry]}, 'books/test.json', strict=True)
        self.assertEqual(3, len(self.errors(validator)))
        self.assertEqual(0, len([d for d in validator.diagnostics if d.severity == 'warning']))

    def test_registry_duplicates_collisions_and_unmatched_id_warning(self):
        validator = facts.Validator()
        validator.load_people(self.write('people.json', [
            {'id': 'same', 'name': 'First'}, {'id': 'same', 'name': 'Second'},
            {'id': 'third', 'name': 'same'}]))
        self.assertEqual(2, len(self.errors(validator)))
        self.assertEqual([], self.check(self.document(self.parent(person='Arnold von Rosenberg'))).diagnostics)
        warning = self.check(self.document(self.parent(person='unknown_id'))).diagnostics[0]
        self.assertEqual('warning', warning.severity)

    def test_cli_exit_status_order_and_malformed_json(self):
        registry = self.write('people.json', [{'id': 'known_id', 'name': 'Known Person'}])
        first = self.write('documents/a.json', self.document(self.parent(type='father')))
        second = self.write('documents/b.json', self.document({'type': 'title', 'person': 'A'}))
        def run(paths):
            return subprocess.run([sys.executable, str(SCRIPT), '--people', str(registry), *map(str, paths)], capture_output=True, text=True)
        a, b = run([first, second]), run([second, first, first])
        self.assertEqual(1, a.returncode)
        self.assertEqual(a.stdout, b.stdout)
        self.assertIn('2 files, 2 facts', a.stdout)
        first.write_text('{broken')
        result = run([first])
        self.assertEqual(1, result.returncode)
        self.assertIn('cannot read JSON', result.stdout)
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(1, run([self.root / 'missing.json']).returncode)


if __name__ == '__main__':
    unittest.main()
