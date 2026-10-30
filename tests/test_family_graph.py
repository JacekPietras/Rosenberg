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
from family_graph.scoring import anchor_profiles
from family_graph.reconstruction import reconstruct


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
        self.write('data/matching.json', json.loads((Path(__file__).resolve().parents[1] / 'data/matching.json').read_text()))

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
        self.assertEqual(0, serialize(load_inputs(self.root, validate=False), [result])['coverage']['facts']['registryRelationships'])

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

    def test_guessed_cycle_cannot_block_identity_matching_in_another_family(self):
        inputs = self.family_context_inputs()
        self.write('data/people.json', inputs.people + [person('x', 'Xavier'), person('y', 'Yves')])
        self.write('data/documents/cycle.json', {'date': '1393', 'guesses': [relation('x', 'y'), relation('y', 'x')]})
        inputs = load_inputs(self.root, validate=False)
        result = build(inputs, include_guesses=True)
        decision = next(d for d in result.decisions.values() if d.mention.reference == 'Alex')
        self.assertEqual(('accepted', 'a'), (decision.status, decision.identity))
        self.assertFalse(decision.uses_guesses)
        self.assertTrue(result.conflicts)
        serialize(inputs, [build(inputs), result])

    def test_valid_guessed_bridge_between_conflicting_families_is_preserved(self):
        inputs = self.inputs([person(key) for key in ('a', 'b', 'c', 'd')],
                             [relation('a', 'b'), relation('c', 'd')],
                             [relation('b', 'a'), relation('d', 'c'), relation('b', 'c')])
        result = build(inputs, include_guesses=True)
        self.assertEqual({('a', 'b'), ('c', 'd'), ('b', 'c')},
                         {(e.person, e.of) for e in result.relationships})
        serialize(inputs, [build(inputs), result])

    def test_name_only_registry_records_have_distinct_internal_handles(self):
        result = build(self.inputs([{'name': 'Alex'}, {'name': 'Alex'}, person('b')], [relation('Alex', 'b')]))
        decision = next(d for d in result.decisions.values() if d.mention.reference == 'Alex')
        self.assertEqual({'@registry/0', '@registry/1'}, {c.identity for c in decision.candidates if c.identity.startswith('@registry/')})
        self.assertEqual(['@registry/0~', '@registry/0'], registry_keys([{'name': 'Alex'}, person('@registry/0', 'Bea')]))

    def test_empty_views_are_explicit_and_apply_is_idempotent(self):
        inputs = self.inputs(facts=[])
        output = serialize(inputs, [build(inputs), build(inputs, include_guesses=True)])
        self.assertEqual(['facts', 'with-guesses'], output['views'])
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
                    validate_generated(output, inputs.people, self.root)

    def test_source_pointers_and_assertion_fingerprints_are_validated(self):
        inputs = self.inputs(facts=[relation('a', 'b')])
        output = serialize(inputs, [build(inputs)])
        output['evidence']['facts']['sources'][0]['fingerprint'] = 'sha256:' + '0' * 64
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            validate_generated(output, inputs.people, self.root)

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

    def test_real_elisabeth_spouse_and_mother_attestations_form_one_identity(self):
        inputs = load_inputs(Path(__file__).resolve().parents[1])
        for include_guesses in (False, True):
            graph = build(inputs, include_guesses=include_guesses).evidence_graph
            nodes = [node for node in graph['nodes'] if node['name'] == 'Elisabeth von Erligheim']
            self.assertEqual(1, len(nodes))
            elisabeth = nodes[0]
            expected = {(a.source.path, a.source.pointer, m.field) for a in inputs.assertions
                        if include_guesses or a.source.kind == 'facts'
                        for m in a.mentions if m.reference == 'Elisabeth von Erligheim'}
            actual = {(m['source']['path'], m['source']['pointer'], m['field']) for m in elisabeth['mentions'] if m['field'] in {'person', 'of'}}
            self.assertEqual(expected, actual)
            relationships = {(edge['type'], edge['person'], edge['of']) for edge in graph['relationships']}
            self.assertIn(('parent', elisabeth['key'], 'arnold_boxberg'), relationships)
            self.assertIn(('parent', elisabeth['key'], 'eberhard_jagstberg'), relationships)
            self.assertTrue(any(edge['type'] == 'spouse' and {edge['person'], edge['of']} == {elisabeth['key'], 'vogt_zu_Lauda'}
                                for edge in graph['relationships']))
            self.assertNotEqual(elisabeth['key'], 'else_wife_of_arnold')
            membership = {(m['source']['path'], m['source']['pointer'], m['field']): node['key']
                          for node in graph['nodes'] for m in node['mentions'] if m['field'] in {'person', 'of'}}
            for first, second in [
                (('data/documents/1358-05-19.json', '/entries/0/facts/4'), ('data/documents/1364-03-10.json', '/entries/0/facts/5')),
                (('data/books/bauer_1872.json', '/entries/101/facts/0'), ('data/books/freiburger_dioecesan_archiv_1896_25.json', '/entries/52/facts/1')),
            ]:
                for field in ('person', 'of'):
                    self.assertEqual(membership[(*first, field)], membership[(*second, field)])
            self.assertTrue(all(node['identityProbability'] >= inputs.matching['mergeProbability'] for node in graph['nodes']))

    def test_unresolved_groups_are_alternatives_without_merging_nodes(self):
        result = build(self.inputs(facts=[relation('Alex', 'b'), relation('Alex', 'c')]))
        handles = [d.mention.handle for d in result.decisions.values() if d.mention.reference == 'Alex']
        self.assertEqual(2, len(set(handles)))
        self.assertTrue(any(set(handles) <= set(group) for group in result.provisional_groups.values()))
        self.assertEqual(2, len({edge.person for edge in result.relationships}))

    def test_source_people_are_exported_without_creating_registry_ids(self):
        inputs = self.inputs([person('unrelated', 'Unrelated')], [relation('Alex von North', 'Bea von South', 'spouse')])
        result = build(inputs)
        graph = result.evidence_graph
        self.assertEqual(2, len(graph['nodes']))
        self.assertEqual(1, len(graph['relationships']))
        self.assertTrue(all(node['key'].startswith('@evidence/') for node in graph['nodes']))
        output = serialize(inputs, [result])
        self.assertEqual(1, len(inputs.people))
        self.assertEqual(4, output['schema'])
        self.assertEqual(2, len(output['evidence']['facts']['nodes']))

    def test_repeated_family_pair_links_without_any_registry_anchor(self):
        self.inputs([person('unrelated', 'Unrelated')], [relation('Alex von North', 'Bea von South', 'spouse')])
        self.write('data/documents/other.json', {'date': '1394', 'source': 'different charter', 'facts': [relation('Alex von North', 'Bea von South', 'spouse')]})
        inputs = load_inputs(self.root, validate=False)
        graph = build(inputs).evidence_graph
        self.assertEqual(2, len(graph['nodes']))
        self.assertEqual(1, len(graph['relationships']))
        self.assertTrue(all(node['status'] == 'contextual' for node in graph['nodes']))
        self.assertTrue(all(d['identity'] == 'inferred' and len(d['sources']) >= 2 for d in graph['relationships'][0]['derivations']))
        serialize(inputs, [build(inputs)])

    def test_name_only_cross_source_occurrences_remain_separate(self):
        self.inputs([person('unrelated', 'Unrelated')], [relation('Alex', 'Bea')])
        self.write('data/documents/other.json', {'date': '1394', 'facts': [relation('Alex', 'Bea')]})
        graph = build(load_inputs(self.root, validate=False)).evidence_graph
        self.assertEqual(4, len(graph['nodes']))
        self.assertEqual(2, len(graph['relationships']))

    def test_source_family_keeps_one_parent_across_its_explicit_children(self):
        inputs = self.inputs([person('unrelated', 'Unrelated')], [relation('Alex', 'Bea'), relation('Alex', 'Chris'), relation('Alex', 'Dora', 'spouse')])
        graph = build(inputs).evidence_graph
        self.assertEqual(4, len(graph['nodes']))
        self.assertEqual(2, len([edge for edge in graph['relationships'] if edge['type'] == 'parent']))
        self.assertEqual(1, len([node for node in graph['nodes'] if node['name'] == 'Alex']))

    def test_coparent_context_links_identity_without_inventing_relationships(self):
        self.inputs(facts=[relation('Bea von South', 'a', 'spouse')])
        self.write('data/documents/parents.json', {'date': '1394', 'facts': [relation('Bea von South', 'c'), relation('a', 'c')]})
        graph = build(load_inputs(self.root, validate=False)).evidence_graph
        self.assertEqual(1, len([node for node in graph['nodes'] if node['name'] == 'Bea von South']))
        self.assertEqual(3, len(graph['relationships']))
        self.assertEqual(2, len([edge for edge in graph['relationships'] if edge['type'] == 'parent']))

    def test_contextual_name_variants_require_matching_family_context(self):
        self.inputs(facts=[relation('Anne von South', 'a', 'spouse')])
        self.write('data/documents/variant.json', {'date': '1394', 'facts': [relation('Anna von South', 'a', 'spouse')]})
        graph = build(load_inputs(self.root, validate=False)).evidence_graph
        self.assertEqual(1, len([node for node in graph['nodes'] if not node.get('registry')]))
        self.assertEqual(1, len(graph['relationships']))
        self.write('data/documents/variant.json', {'date': '1394', 'facts': [relation('Anna von West', 'a', 'spouse')]})
        graph = build(load_inputs(self.root, validate=False)).evidence_graph
        self.assertEqual(2, len([node for node in graph['nodes'] if not node.get('registry')]))

    def test_source_graph_guesses_have_separate_views_and_dependencies(self):
        inputs = self.inputs([person('unrelated', 'Unrelated')], [relation('Alex von North', 'Bea von South', 'spouse')], [relation('Alex von North', 'Bea von South', 'spouse')])
        facts = build(inputs)
        guessed = build(inputs, include_guesses=True)
        self.assertTrue(all(not d['usesGuesses'] for e in facts.evidence_graph['relationships'] for d in e['derivations']))
        self.assertTrue(any(d['usesGuesses'] for e in guessed.evidence_graph['relationships'] for d in e['derivations']))
        self.assertEqual(facts.evidence_graph, build(inputs).evidence_graph)
        serialize(inputs, [facts, guessed])

    def test_reconstructed_graph_validates_participant_assignments(self):
        inputs = self.inputs([person('unrelated', 'Unrelated')], [relation('Alex', 'Bea')])
        output = serialize(inputs, [build(inputs)])
        graph = output['evidence']['facts']
        graph['relationships'][0]['person'], graph['relationships'][0]['of'] = graph['relationships'][0]['of'], graph['relationships'][0]['person']
        with self.assertRaisesRegex(ValueError, 'supporting participant'):
            validate_generated(output, inputs.people, self.root)

    def test_reconstructed_kin_term_must_match_its_source(self):
        inputs = self.inputs(facts=[relation('a', 'b', 'kin', term='Vetter')])
        output = serialize(inputs, [build(inputs)])
        output['evidence']['facts']['relationships'][0]['term'] = 'Schwager'
        with self.assertRaisesRegex(ValueError, 'supporting participant'):
            validate_generated(output, inputs.people, self.root)

    def test_source_graph_never_merges_distinct_namesake_anchors(self):
        inputs = self.inputs([person('a', 'Alex von North'), person('other', 'Alex von North')], [relation('a', 'Bea von South', 'spouse'), relation('other', 'Bea von South', 'spouse'), relation('Alex von North', 'Bea von South', 'spouse')])
        graph = build(inputs).evidence_graph
        self.assertEqual({'a', 'other'}, {node['registry'] for node in graph['nodes'] if node.get('registry')})
        self.assertTrue(any(not node.get('registry') and node['name'] == 'Alex von North' for node in graph['nodes']))

    def test_general_book_citation_does_not_turn_equal_assertions_into_one_event(self):
        self.inputs([person('unrelated', 'Unrelated')])
        document = {'date': '1393', 'source': 'General book [1872]', 'facts': [relation('Alex', 'Bea')]}
        self.write('data/documents/first.json', document)
        self.write('data/documents/second.json', document)
        graph = build(load_inputs(self.root, validate=False)).evidence_graph
        self.assertEqual(4, len(graph['nodes']))
        self.assertEqual(2, len(graph['relationships']))

    def test_joint_source_constraints_do_not_choose_an_arbitrary_identity_merge(self):
        inputs = self.inputs([person('unrelated', 'Unrelated')], [relation('Alex', 'Bea'), relation('Bea', 'Alex')])
        graph = build(inputs).evidence_graph
        self.assertEqual(4, len(graph['nodes']))
        self.assertEqual(2, len(graph['relationships']))
        self.assertFalse(graph['links'])

    def test_legacy_guessed_registry_resolution_cannot_bypass_probability_weights(self):
        inputs = self.family_context_inputs(guessed=True)
        result = build(inputs, include_guesses=True)
        # The preceding diagnostic resolver accepts this legacy score. The
        # actual source graph must still apply the weaker guessed evidence.
        self.assertTrue(any(d.identity == 'a' and d.uses_guesses for d in result.decisions.values()))
        graph = result.evidence_graph
        self.assertTrue(any(node['name'] == 'Alex' and not node.get('registry') for node in graph['nodes']))
        self.assertTrue(any(c['usesGuesses'] and c['status'] != 'merged' for c in graph['comparisons']))

    def test_apply_writes_only_tree_and_preserves_the_confirmed_registry(self):
        inputs = self.inputs(facts=[relation('a', 'b')])
        before = (self.root / 'data/people.json').read_bytes()
        tree = serialize(inputs, [build(inputs)])
        output = apply(inputs, tree)
        self.assertEqual(before, (self.root / 'data/people.json').read_bytes())
        self.assertEqual(output, (self.root / 'data/tree.json').read_bytes())
        self.assertNotIn('data/tree.json', tree['inputs'])
        self.assertTrue(all(set(person) == {'id', 'name'} for person in json.loads(before)))

    def test_intervening_tree_edit_prevents_overwriting_it(self):
        inputs = self.inputs(facts=[relation('a', 'b')])
        tree = serialize(inputs, [build(inputs)])
        self.write('data/tree.json', {'changed': 'by another editor'})
        with self.assertRaisesRegex(ValueError, 'changed'):
            apply(inputs, tree)
        self.assertEqual({'changed': 'by another editor'}, json.loads((self.root / 'data/tree.json').read_text()))

    def test_invalid_generated_tree_can_be_rebuilt_without_using_it_as_evidence(self):
        self.inputs(facts=[relation('a', 'b')])
        self.write('data/tree.json', '{invalid')
        inputs = load_inputs(self.root)
        tree = serialize(inputs, [build(inputs)])
        apply(inputs, tree)
        self.assertEqual(4, json.loads((self.root / 'data/tree.json').read_text())['schema'])

    def test_confirmed_registry_rejects_computation_fields(self):
        self.inputs()
        self.write('data/people.json', [person('a', 'Alex', relationships=[])])
        with self.assertRaisesRegex(ValueError, 'only id and name'):
            load_inputs(self.root)


if __name__ == '__main__':
    unittest.main()
