"""Synthetic facts exercise search without migrating the corpus."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('search_facts_by_name', SCRIPTS / 'search_facts_by_name.py')
search = importlib.util.module_from_spec(spec)
spec.loader.exec_module(search)


class SearchFactsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.write('people.json', [
            {'id': 'known_arnold', 'name': 'Arnold von Rosenberg', 'titles': []},
            {'id': 'other_arnold', 'name': 'Arnold von Rosenberg', 'titles': []},
            {'id': 'eberhard_id', 'name': 'Eberhard von Rosenberg', 'titles': ['Ritter']},
            {'id': 'ritter_id', 'name': 'Konrad von Rosenberg', 'titles': ['Ritter']},
        ])
        self.write('places.json', [{'id': 'boxberg', 'variations': ['Boxberg', 'Bocksberg']}])
        (self.root / 'data/names.md').write_text('Arnold, Arnolt\nEberhard, Eberhardi\nRosenberg, Roßenberg\n')
        (self.root / 'data/nobiliary_particles.md').write_text('von\nv.\nde\n')

    def write(self, relative, value):
        path = self.root / 'data' / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False))
        return path

    def document(self, *facts, **extra):
        return {'date': '1395-04-12', 'entries': [{'source': 'Example charter', 'facts': list(facts), **extra}]}

    def run_search(self, query, direct=False):
        output = io.StringIO()
        with patch.object(search, 'ROOT', self.root), contextlib.redirect_stdout(output):
            search.main([query] + (['--direct'] if direct else []))
        return output.getvalue()

    def test_generic_subject_titles_status_and_body_are_searchable(self):
        self.write('documents/generic.json', self.document({
            'type': 'generic', 'person': 'known_arnold', 'personTitle': ['Ritter', 'zu Boxberg'],
            'personDeceased': True, 'content': 'held property at Boxberg.'}))
        for query in ('known_arnold', 'Arnolt', 'Boxberg'):
            output = self.run_search(query, direct=query == 'known_arnold')
            self.assertIn('Arnold von Rosenberg [known_arnold], Ritter, zu Boxberg (deceased) held property at Boxberg.', output)
        self.assertEqual('No matching facts found.\n', self.run_search('other_arnold', direct=True))

    def test_non_person_subject_is_searchable_without_person_reference(self):
        self.write('documents/castle.json', self.document({
            'type': 'generic', 'subject': 'Boxberg Castle', 'content': 'was attacked.'}))
        self.assertIn('Boxberg Castle was attacked.', self.run_search('Boxberg'))
        self.assertEqual('No matching facts found.\n', self.run_search('known_arnold', direct=True))

    def test_render_all_supported_types_and_title_lists(self):
        facts = [
            {'type': kind, 'person': 'known_arnold', 'personTitle': ['der Jüngere', 'Ritter'],
             'of': 'eberhard_id', 'ofTitle': ['Vogt zu Lauda'], **({'term': 'Vetter'} if kind == 'kin' else {})}
            for kind in ('parent', 'sibling', 'spouse', 'kin')
        ] + [{'type': 'title', 'person': 'known_arnold', 'personTitle': ['der Jüngere', 'zu Boxberg']}]
        self.write('documents/typed.json', self.document(*facts))
        output = self.run_search('known_arnold', direct=True)
        self.assertEqual(5, len(output.splitlines()))
        self.assertIn('[1395-04-12] Arnold von Rosenberg [known_arnold], der Jüngere, Ritter is parent of Eberhard von Rosenberg [eberhard_id], Vogt zu Lauda.', output)
        self.assertIn('is sibling of', output)
        self.assertIn('is spouse of', output)
        self.assertIn('(Vetter).', output)
        self.assertIn('Arnold von Rosenberg [known_arnold] is designated der Jüngere, zu Boxberg.', output)
        self.assertNotIn("['", output)

    def test_names_and_variants_find_id_fields_without_static_titles(self):
        self.write('documents/id.json', self.document({'type': 'title', 'person': 'known_arnold', 'personTitle': ['der Jüngere']}))
        for query in ('Arnold', 'Arnolt', 'Arnolt v. Roßenberg', 'Rosenberg'):
            with self.subTest(query=query):
                self.assertIn('Arnold von Rosenberg [known_arnold]', self.run_search(query))

    def test_direct_matches_exact_id_in_either_field_only(self):
        self.write('documents/typed.json', self.document(
            {'type': 'parent', 'person': 'eberhard_id', 'of': 'known_arnold'},
            {'type': 'title', 'person': 'Arnold von Rosenberg', 'personTitle': ['Name only']},
            {'type': 'title', 'person': 'other_arnold', 'personTitle': ['Other identity']},
            {'type': 'title', 'person': 'KNOWN_ARNOLD', 'personTitle': ['Wrong case']},
            {'type': 'title', 'person': '[known_arnold]', 'personTitle': ['Bracket literal']},
        ))
        output = self.run_search('known_arnold', direct=True)
        self.assertEqual(1, len(output.splitlines()))
        self.assertIn('is parent of Arnold von Rosenberg [known_arnold]', output)
        self.assertNotIn('Wrong case', output)
        self.assertNotIn('Bracket literal', output)

    def test_default_id_search_marks_unresolved_participant_beside_known_id(self):
        self.write('documents/typed.json', self.document(
            {'type': 'sibling', 'person': 'eberhard_id', 'of': 'Arnold von Rosenberg', 'ofTitle': ['der Jüngere']},
            {'type': 'title', 'person': 'Arnolt von Rosenberg', 'personTitle': ['zu Boxberg']},
            {'type': 'title', 'person': 'other_arnold', 'personTitle': ['Ritter']},
        ))
        output = self.run_search('known_arnold')
        self.assertIn('Arnold von Rosenberg [not recognised], der Jüngere', output)
        self.assertIn('Arnolt von Rosenberg [not recognised]', output)
        self.assertIn('Arnold von Rosenberg [other_arnold]', output)
        self.assertNotIn('[known_arnold]', output)

    def test_title_search_uses_fact_titles_not_ids_or_registry_titles(self):
        self.write('documents/titles.json', self.document(
            {'type': 'title', 'person': 'known_arnold', 'personTitle': ['Ritter']},
            {'type': 'title', 'person': 'ritter_id', 'personTitle': ['Edelknecht']},
            {'type': 'spouse', 'person': 'known_arnold', 'of': 'eberhard_id', 'ofTitle': ['Vogt zu Lauda']},
        ))
        output = self.run_search('Ritter')
        self.assertEqual(1, len(output.splitlines()))
        self.assertIn('[known_arnold]', output)
        self.assertNotIn('ritter_id', output)
        self.assertNotIn('Vogt', output)
        self.assertIn('Vogt zu Lauda', self.run_search('Vogt zu Lauda'))
        self.assertEqual('No matching facts found.\n', self.run_search('Unmentioned'))

    def test_place_aliases_find_titles_and_entry_metadata(self):
        self.write('documents/places.json', self.document(
            {'type': 'title', 'person': 'known_arnold', 'personTitle': ['zu Boxberg']},
        ))
        self.write('documents/metadata.json', self.document(
            {'type': 'spouse', 'person': 'known_arnold', 'of': 'Christina'}, place='Boxberg'))
        output = self.run_search('Bocksberg')
        self.assertEqual(2, len(output.splitlines()))
        self.assertIn('zu Boxberg', output)
        self.assertIn('is spouse of Christina', output)

    def test_document_dates_override_null_and_nested_traversal(self):
        self.write('documents/dates.json', {'date': '1395', 'research': [{'facts': [
            {'type': 'title', 'person': 'known_arnold', 'personTitle': ['Inherited']},
            {'type': 'title', 'person': 'known_arnold', 'personTitle': ['Override'], 'date': '1396-02'},
            {'type': 'title', 'person': 'known_arnold', 'personTitle': ['Unknown'], 'date': None},
        ]}, {'date': None, 'facts': [{'type': 'title', 'person': 'known_arnold', 'personTitle': ['Entry unknown']}]}]})
        lines = self.run_search('known_arnold', direct=True).splitlines()
        self.assertTrue(lines[0].startswith('[1395] '))
        self.assertTrue(lines[1].startswith('[1396-02] '))
        self.assertFalse(lines[2].startswith('['))
        self.assertFalse(lines[3].startswith('['))

    def test_books_and_notes_never_inherit_publication_or_entry_date(self):
        for directory in ('books', 'notes'):
            self.write(f'{directory}/dates.json', {'date': '1872', 'entries': [{'date': '1880', 'facts': [
                {'type': 'title', 'person': 'known_arnold', 'personTitle': ['Undated']},
                {'type': 'title', 'person': 'known_arnold', 'personTitle': ['Dated'], 'date': '1395'},
                {'text': 'Arnold von Rosenberg legacy undated'},
                {'text': 'Arnold von Rosenberg legacy dated', 'date': '1396'},
            ]}]})
        output = self.run_search('Arnold')
        self.assertNotIn('[1872]', output)
        self.assertNotIn('[1880]', output)
        self.assertEqual(2, output.count('[1395]'))
        self.assertNotIn('[1396]', output)

    def test_legacy_facts_are_ignored_and_runtime_seal_search_remains_available(self):
        self.write('documents/legacy.json', self.document(
            'Eberhard von Rosenberg [eberhard_id] witnessed a charter.',
            {'text': 'Arnold von Rosenberg sold property.', 'date': '1396'},
            img=[{'seals': [{'person': 'Arnold von Rosenberg'}, {'person': 'Arnold von Rosenberg'}, {'person': 'unknown'}]}],
        ))
        self.assertEqual('No matching facts found.\n', self.run_search('eberhard_id', direct=True))
        output = self.run_search('known_arnold')
        self.assertIn('The seal of Arnold von Rosenberg [not recognised] is under document Example charter.', output)
        self.assertEqual(1, output.count('The seal'))
        self.assertNotIn('sold property', output)
        self.assertEqual('No matching facts found.\n', self.run_search('known_arnold', direct=True))

    def test_cli_custom_data_dir_with_typed_facts(self):
        path = self.write('documents/cli.json', self.document({'type': 'title', 'person': 'vogt_zu_Lauda', 'personTitle': ['Ritter']}))
        result = subprocess.run([sys.executable, str(SCRIPTS / 'search_facts_by_name.py'), 'vogt_zu_Lauda', '--direct', '--data-dir', str(path.parent)], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('Eberhard von Rosenberg [vogt_zu_Lauda] is designated Ritter.', result.stdout)


if __name__ == '__main__':
    unittest.main()
