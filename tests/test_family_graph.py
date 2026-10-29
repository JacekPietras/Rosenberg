"""Logical boundary tests; the old registry tree is never a genealogy oracle."""

from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from family_graph import build, load_inputs
from family_graph.constraints import cycle_nodes
from family_graph.dates import date_bounds, death_interval, inherited_date_bounds
from family_graph.export import apply, serialize, validate_generated
from family_graph.model import fingerprint, registry_keys
from family_graph.names import Names
from family_graph.policy import OfficeRule
from family_graph.sources import input_manifest, walk_assertions
from family_graph.scoring import place_patterns, places_for


def person(identity, name=None, **extra):
    return {'id': identity, 'name': name or identity + ' name', **extra}


def snapshot(result):
    return {'view': result.view, 'relationships': [asdict(edge) for edge in result.relationships],
            'decisions': [(key, decision.status, decision.identity, decision.method, decision.uses_guesses,
                           [asdict(candidate) for candidate in decision.candidates]) for key, decision in result.decisions.items()],
            'conflicts': result.conflicts}


def relation(left, right, kind='parent', **extra):
    return {'type': kind, 'person': left, 'of': right, **extra}


class FamilyGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write('data/names.md', 'Konrad, Conradus\nKunz, Cunz // never expand to Konrad\nEberhard, Eberhardi\nMünch, Mönch\n')
        self.write('data/places.json', [])

    def write(self, path, value):
        path = self.root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False), encoding='utf-8')

    def inputs(self, people=None, facts=None, guesses=None):
        self.write('data/people.json', people or [person('a', 'Alex'), person('b', 'Bea'), person('c', 'Chris')])
        if facts is not None or guesses is not None:
            self.write('data/documents/test.json', {'date': '1393', 'entries': [{'source': 'charter 1', 'facts': facts or [], 'guesses': guesses or []}]})
        return load_inputs(self.root, validate=False)

    def test_exact_ids_and_old_relationship_independence(self):
        inputs = self.inputs(facts=[relation('a', 'b'), relation('A', 'b')])
        first = build(inputs)
        self.assertEqual(1, len([edge for edge in first.relationships if edge.person == 'a']))
        inputs.people[0].update(wife='c', children=['b'], died='1000', titles=['Wrong'])
        second = build(inputs)
        self.assertEqual(snapshot(first), snapshot(second))
        self.assertTrue(any(d.mention.reference == 'A' and d.status == 'unresolved' for d in second.decisions.values()))

    def test_unique_name_is_still_unresolved_and_id_wording_means_nothing(self):
        result = build(self.inputs([person('son_of_a', 'Alex'), person('b', 'Bea')], [relation('Alex', 'b')]))
        self.assertTrue(any(d.status == 'unresolved' for d in result.decisions.values()))
        self.assertEqual(1, result.omitted)
        self.assertEqual([], serialize(load_inputs(self.root, validate=False), [result])[0]['relationships'])

    def test_recursive_sources_and_no_publication_inheritance(self):
        self.inputs()
        self.write('data/images/nested/test.json', {'date': '1390-1394', 'research': [{'date': '1392/1393', 'facts': [relation('a', 'b')]}]})
        inputs = load_inputs(self.root, validate=False)
        self.assertEqual('1392/1393', inputs.assertions[0].historical_date)
        self.assertEqual('/research/0/facts/0', inputs.assertions[0].source.pointer)
        self.write('data/books/deep/book.json', {'book': 'Published', 'date': '1900', 'entries': [{'date': '1400', 'facts': [relation('a', 'b')]}]})
        with self.assertRaisesRegex(ValueError, 'historical date'):
            load_inputs(self.root, validate=False)

    def test_malformed_input_is_fatal(self):
        self.inputs()
        self.write('data/notes/bad.json', '{bad')
        with self.assertRaisesRegex(ValueError, 'bad.json'):
            load_inputs(self.root, validate=False)

    def test_partial_dates_and_exclusive_death_bounds(self):
        self.assertEqual('1400-02-28', date_bounds('1400-02')[1].isoformat())
        self.assertEqual('1404-02-29', date_bounds('1404-02')[1].isoformat())
        for spelling in ('1393-1394', '1393/1394', '1393--1394'):
            self.assertEqual(('1393-01-01', '1394-12-31'), tuple(d.isoformat() for d in inherited_date_bounds(spelling)))
        inputs = self.inputs(facts=[{'type': 'death', 'person': 'a', 'diedBefore': '1394'}])
        self.assertEqual('1393-12-31', death_interval(inputs.assertions[0].mentions[0])[1].isoformat())

    def test_posthumous_mentions_do_not_prove_life(self):
        result = build(self.inputs(facts=[{'type': 'death', 'person': 'a', 'diedOn': '1387'}, relation('a', 'b', 'spouse', personDeceased=True), {'type': 'title', 'person': 'a', 'personTitle': ['Ritter']}]))
        self.assertFalse(result.conflicts)
        self.assertEqual('anchored', result.relationships[0].derivations[0]['identity'])

    def test_conflicting_factual_deaths_block_affected_edges(self):
        result = build(self.inputs(facts=[{'type': 'death', 'person': 'a', 'diedOn': '1387'}, {'type': 'death', 'person': 'a', 'diedOn': '1388'}, relation('a', 'b'), relation('b', 'c')]))
        self.assertEqual([('b', 'c')], [(edge.person, edge.of) for edge in result.relationships])
        self.assertTrue(result.conflicts)

    def test_no_spouse_or_sibling_closure_and_kin_terms_survive(self):
        result = build(self.inputs(facts=[relation('a', 'b', 'spouse'), relation('a', 'c'), relation('b', 'c', 'sibling'), relation('a', 'b', 'kin', term='Vetter')]))
        self.assertEqual(4, len(result.relationships))
        self.assertEqual(['Vetter'], [edge.term for edge in result.relationships if edge.type == 'kin'])
        self.assertFalse(any(edge.type == 'parent' and edge.person == 'b' for edge in result.relationships))

    def test_names_preserve_family_and_kunz_boundaries(self):
        names = Names((self.root / 'data/names.md').read_text(), [])
        self.assertEqual(names.key('Conradus de Rosenberg'), names.key('Konrad von Rosenberg'))
        self.assertNotEqual(names.key('Kunz von Rosenberg'), names.key('Konrad von Rosenberg'))
        self.assertNotEqual(names.key('Eberhard Münch von Rosenberg'), names.key('Eberhard von Rosenberg'))
        self.assertNotIn('never', names.key('Cunz von Rosenberg'))

    def test_reviewed_scoped_office_rule_cannot_merge_anchors(self):
        inputs = self.inputs([person('lauda', 'Eberhard von Rosenberg'), person('durn', 'Eberhard von Rosenberg'), person('b')],
            [{'type': 'title', 'person': 'lauda', 'personTitle': ['Vogt zu Lauda']}, relation('Eberhard von Rosenberg', 'b', personTitle=['Vogt zu Lauda'])])
        rule = OfficeRule('Eberhard von Rosenberg', 'Vogt zu Lauda', 'lauda', '1393', '1393', 'data/documents/test.json', '/entries/0/facts/0')
        result = build(inputs, rules=[rule])
        decision = next(d for d in result.decisions.values() if d.mention.reference == 'Eberhard von Rosenberg')
        self.assertEqual(('lauda', 'reviewed'), (decision.identity, decision.method))
        self.assertTrue(next(c for c in decision.candidates if c.identity == 'durn').exclusions)
        result = build(inputs, rules=[OfficeRule(**{**rule.__dict__, 'end': '1392'})])
        self.assertTrue(any(d.status == 'unresolved' for d in result.decisions.values()))

    def family_context_inputs(self, guessed=False):
        inputs = self.inputs([person('a', 'Alex'), person('other_a', 'Alex'), person('b', 'Bea')], [relation('Alex', 'b', 'spouse')])
        self.write('data/documents/independent.json', {'date': '1390', 'entries': [{'source': 'charter 2', 'guesses' if guessed else 'facts': [relation('a', 'b', 'spouse')]}]})
        return load_inputs(self.root, validate=False)

    def test_independent_grounded_relative_identifies_with_dependencies(self):
        result = build(self.family_context_inputs())
        decision = next(d for d in result.decisions.values() if d.mention.reference == 'Alex')
        self.assertEqual(('a', 'inferred'), (decision.identity, decision.method))
        self.assertEqual('data/documents/independent.json', decision.sources[0].path)

    def test_guess_dependent_identity_is_separate_from_facts(self):
        inputs = self.family_context_inputs(guessed=True)
        facts = build(inputs)
        guessed = build(inputs, include_guesses=True)
        self.assertEqual(snapshot(facts), snapshot(build(inputs)))
        self.assertTrue(any(d.mention.reference == 'Alex' and d.status == 'unresolved' for d in facts.decisions.values()))
        self.assertTrue(any(d.mention.reference == 'Alex' and d.identity == 'a' and d.uses_guesses for d in guessed.decisions.values()))
        self.assertTrue(all(d['usesGuesses'] for edge in guessed.relationships for d in edge.derivations))

    def test_search_limit_leaves_supported_match_unresolved(self):
        result = build(self.family_context_inputs(), search_limit=1)
        self.assertTrue(any('search limit' in d.reason and d.status == 'unresolved' for d in result.decisions.values()))

    def test_circular_family_evidence_cannot_identify_either_endpoint(self):
        result = build(self.inputs(facts=[relation('Alex', 'Bea', 'spouse'), relation('Alex', 'Bea', 'sibling')]))
        self.assertTrue(all(d.status == 'unresolved' for d in result.decisions.values()))

    def test_duplicate_titles_do_not_multiply_scores(self):
        inputs = self.inputs(facts=[{'type': 'title', 'person': 'Alex', 'personTitle': ['Ritter']}])
        self.write('data/documents/copies.json', {'date': '1393', 'entries': [{'facts': [{'type': 'title', 'person': 'a', 'personTitle': ['Ritter']}] * 15}]})
        result = build(load_inputs(self.root, validate=False))
        decision = next(d for d in result.decisions.values() if d.mention.reference == 'Alex')
        self.assertEqual(.25, next(c for c in decision.candidates if c.identity == 'a').score)
        self.assertEqual('unresolved', decision.status)

    def test_identical_objects_at_different_dates_remain_distinct(self):
        doc = {'entries': [{'source': 'same general citation', 'date': '1390', 'facts': [relation('Alex', 'b')]}, {'source': 'same general citation', 'date': '1400', 'facts': [relation('Alex', 'b')]}]}
        assertions = [assertion for _, assertion in walk_assertions(doc, 'data/documents/test.json')]
        self.assertNotEqual(assertions[0].event_key, assertions[1].event_key)
        self.assertNotEqual(assertions[0].mentions[0].handle, assertions[1].mentions[0].handle)

    def test_factual_cycles_block_but_repeated_ancestry_is_allowed(self):
        result = build(self.inputs(facts=[relation('a', 'b'), relation('b', 'a')]))
        self.assertTrue(result.conflicts)
        self.assertEqual([], result.relationships)
        self.assertEqual(set(), cycle_nodes([('a', 'b'), ('a', 'c'), ('b', 'd'), ('c', 'd')]))

    def test_incompatible_guesses_do_not_flatten_into_a_cycle(self):
        inputs = self.inputs(facts=[relation('a', 'b')], guesses=[relation('b', 'a')])
        result = build(inputs, include_guesses=True)
        self.assertTrue(result.conflicts)
        self.assertEqual([('a', 'b')], [(edge.person, edge.of) for edge in result.relationships])
        self.assertTrue(result.alternatives)
        serialize(inputs, [build(inputs), result])

    def test_name_only_registry_records_have_distinct_internal_handles(self):
        result = build(self.inputs([{'name': 'Alex'}, {'name': 'Alex'}, person('b')], [relation('Alex', 'b')]))
        decision = next(d for d in result.decisions.values() if d.mention.reference == 'Alex')
        self.assertEqual({'@registry/0', '@registry/1'}, {c.identity for c in decision.candidates if c.identity.startswith('@registry/')})
        self.assertEqual(['@registry/0~', '@registry/0'], registry_keys([{'name': 'Alex'}, person('@registry/0', 'Bea')]))

    def test_empty_views_are_explicit_and_apply_is_idempotent(self):
        inputs = self.inputs(facts=[])
        output = serialize(inputs, [build(inputs), build(inputs, include_guesses=True)])
        self.assertEqual(['facts', 'with-guesses'], output[0]['familyGraph']['views'])
        first = apply(inputs, output)
        second_inputs = load_inputs(self.root, validate=False)
        second_output = serialize(second_inputs, [build(second_inputs), build(second_inputs, include_guesses=True)])
        self.assertEqual(first, apply(second_inputs, second_output))

    def test_apply_rejects_intervening_registry_changes(self):
        inputs = self.inputs(facts=[relation('a', 'b')])
        output = serialize(inputs, [build(inputs)])
        self.write('data/people.json', [*inputs.people, person('new')])
        with self.assertRaisesRegex(ValueError, 'stale|changed'):
            apply(inputs, output)

    def test_inherited_context_added_sources_and_name_inputs_invalidate_build(self):
        for kind in ('context', 'source', 'names'):
            with self.subTest(kind=kind):
                inputs = self.inputs(facts=[relation('a', 'b')])
                output = serialize(inputs, [build(inputs)])
                if kind == 'context':
                    self.write('data/documents/test.json', {'date': '1400', 'facts': [relation('a', 'b')]})
                elif kind == 'source':
                    self.write('data/documents/new.json', {'date': '1400', 'facts': []})
                else:
                    self.write('data/names.md', 'Alex, Alexander')
                with self.assertRaisesRegex(ValueError, 'stale'):
                    validate_generated(output, self.root)

    def test_source_pointers_and_assertion_fingerprints_are_validated(self):
        inputs = self.inputs(facts=[relation('a', 'b')])
        output = serialize(inputs, [build(inputs)])
        output[0]['relationships'][0]['derivations'][0]['sources'][0]['fingerprint'] = 'sha256:' + '0' * 64
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            validate_generated(output, self.root)

    def test_numeric_fingerprints_are_cross_runtime_and_type_sensitive(self):
        self.assertEqual(fingerprint({'x': 1}), fingerprint({'x': 1.0}))
        self.assertNotEqual(fingerprint({'x': True}), fingerprint({'x': 1}))

    def test_rank_and_age_changes_and_missing_titles_are_neutral(self):
        self.inputs(facts=[{'type': 'title', 'person': 'Alex', 'personTitle': ['der Ältere', 'Ritter']}])
        self.write('data/documents/early.json', {'date': '1385', 'facts': [{'type': 'title', 'person': 'a', 'personTitle': ['der Jüngere', 'Edelknecht']}]})
        result = build(load_inputs(self.root, validate=False))
        candidate = next(c for d in result.decisions.values() if d.mention.reference == 'Alex' for c in d.candidates if c.identity == 'a')
        self.assertFalse(candidate.exclusions)
        self.assertEqual(0, candidate.score)

    def test_place_ambiguity_and_surname_geography_supply_no_support(self):
        inputs = self.inputs(facts=[relation('a', 'b')])
        mention = inputs.assertions[0].mentions[0]
        mention.assertion.context['place'] = 'Essingen'
        patterns = place_patterns([{'id': 'one', 'variations': ['Essingen']}, {'id': 'two', 'variations': ['Essingen']}])
        self.assertEqual(set(), places_for(mention, patterns))
        mention.assertion.context['place'] = ''
        mention.reference = 'Alex von Essingen'
        self.assertEqual(set(), places_for(mention, patterns))

    def test_real_posthumous_source_and_independently_anchored_parentage(self):
        root = Path(__file__).resolve().parents[1]
        inputs = load_inputs(root)
        result = build(inputs)
        death_mentions = [d for d in result.decisions.values() if d.mention.assertion.source.path == 'data/documents/1393-06-23_2.json' and d.mention.reference == 'vogt_zu_Lauda']
        self.assertTrue(death_mentions)
        self.assertTrue(all(d.identity == 'vogt_zu_Lauda' and d.method == 'anchored' for d in death_mentions))
        self.assertFalse(result.conflicts)
        edges = [(e.person, e.of) for e in result.relationships if e.type == 'parent']
        self.assertIn(('vogt_zu_Lauda', 'arnold_boxberg'), edges)
        self.assertIn(('vogt_zu_Durn', 'engelhard_son_of_vogt_zu_Durn'), edges)
        self.assertTrue(any(d.method == 'reviewed' for d in result.decisions.values()))

    def test_unresolved_groups_are_alternatives_without_merging_nodes(self):
        result = build(self.inputs(facts=[relation('Alex', 'b'), relation('Alex', 'c')]))
        handles = [d.mention.handle for d in result.decisions.values() if d.mention.reference == 'Alex']
        self.assertEqual(2, len(set(handles)))
        self.assertTrue(any(set(handles) <= set(group) for group in result.provisional_groups.values()))
        self.assertEqual(2, len({edge.person for edge in result.relationships}))


if __name__ == '__main__':
    unittest.main()
