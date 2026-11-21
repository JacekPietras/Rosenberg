"""Logical boundary tests; the old registry tree is never a genealogy oracle."""

from dataclasses import asdict
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from family_graph import build, load_inputs
from family_graph.constraints import cycle_nodes
from family_graph.dates import date_bounds, death_interval, inherited_date_bounds
from family_graph.export import apply, pack_evidence, serialize, unpack_evidence, validate_generated
from family_graph.model import fingerprint, registry_keys
from family_graph.names import Names
from family_graph.probability import DEFAULTS
from family_graph.policy import OfficeRule
from family_graph.sources import input_manifest, walk_assertions
from family_graph.scoring import places_for
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
        self.write('data/names.md', '# Men\n\nArnold\nEberhard, Eberhardi\nKonrad, Conradus\nKunz, Cunz // never expand to Konrad\n\n'
                                    '# Women\n\nElisabeth\nJutta\n\n# Other\n\nMünch, Mönch\n')
        self.write('data/places.json', [])
        self.write('data/nobiliary_particles.md', 'von')
        self.write('data/matching.json', DEFAULTS)

    def write(self, path, value):
        path = self.root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False), encoding='utf-8')

    def inputs(self, people=None, facts=None, guesses=None):
        self.write('data/people.json', people or [person('a', 'Alex'), person('b', 'Bea'), person('c', 'Chris')])
        if facts is not None or guesses is not None:
            self.write('data/documents/test.json', {'date': '1393', 'entries': [{'source': 'charter 1', 'facts': facts or [], 'guesses': guesses or []}]})
        return load_inputs(self.root, validate=False)

    def test_multiple_name_components_use_variants(self):
        names = Names('# Men\nLudwig\nMönch, Münch\nFriedrich\nZaisolph, Zeisolf\n', [])
        self.assertEqual(names.key('Ludwig Münch von Rosenberg'), names.key('Ludwig Mönch von Rosenberg'))
        self.assertEqual(names.key('Friedrich Zeisolf von Rosenberg'), names.key('Friedrich Zaisolph von Rosenberg'))
        self.assertNotEqual(names.key('Ludwig Mönch von Rosenberg'), names.key('Ludwig von Rosenberg'))

    def test_generic_facts_and_guesses_preserve_subject_metadata_without_edges(self):
        fact = {'type': 'generic', 'person': 'a', 'personTitle': ['Ritter', 'zu Boxberg'],
                'personDeceased': True, 'content': 'Held property at Boxberg.'}
        inputs = self.inputs(facts=[fact], guesses=[{**fact, 'person': 'Unresolved name'}])
        self.assertEqual(2, len(inputs.assertions))
        for assertion in inputs.assertions:
            self.assertEqual(1, len(assertion.mentions))
            self.assertEqual(('Ritter', 'zu Boxberg'), assertion.mentions[0].titles)
            self.assertTrue(assertion.mentions[0].deceased)
        self.assertEqual([], build(inputs).relationships)

    def test_titles_normalized_on_ingestion_and_deduplicated_in_tree(self):
        self.write('data/titles-office.md', 'Vizedom, Vicedom, Vitzthum\nRitter, miles\nder Rote, Rufus\n')
        facts = [
            {'type': 'parent', 'person': 'a', 'of': 'b', 'personTitle': ['Vicedom zu Amberg', 'miles', 'Rufus']},
            {'type': 'title', 'person': 'a', 'personTitle': ['Vitzthum in Amberg', 'Ritter', 'der Rote']},
            {'type': 'title', 'person': 'a', 'personTitle': ['Vitzthum zu Heidelberg']},
        ]
        inputs = self.inputs(facts=facts)
        self.assertEqual(('Vizedom zu Amberg', 'Ritter', 'der Rote'), inputs.assertions[0].mentions[0].titles)
        self.assertEqual(facts[0], inputs.assertions[0].original)
        node = next(n for n in build(inputs).evidence_graph['nodes'] if n.get('registry') == 'a')
        self.assertEqual(['Ritter', 'Vizedom zu Amberg', 'Vizedom zu Heidelberg', 'der Rote'], node['titles'])

    def test_non_person_subjects_do_not_create_person_mentions(self):
        fact = {'type': 'generic', 'subject': 'The von Rosenberg family',
                'content': 'held Boxberg Castle.'}
        inputs = self.inputs(facts=[fact], guesses=[fact])
        self.assertEqual(2, len(inputs.assertions))
        self.assertTrue(all(not assertion.mentions for assertion in inputs.assertions))
        self.assertEqual([], build(inputs).relationships)

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

    def test_marked_posthumous_mentions_are_compatible_and_unmarked_ones_are_reported(self):
        death = {'type': 'death', 'person': 'a', 'diedOn': '1387'}
        result = build(self.inputs(facts=[death, relation('a', 'b', 'spouse', personDeceased=True), {'type': 'title', 'person': 'a', 'personTitle': ['Ritter'], 'personDeceased': True}]))
        self.assertFalse(result.conflicts)
        self.assertEqual('anchored', result.relationships[0].derivations[0]['identity'])
        result = build(self.inputs(facts=[death, relation('a', 'b', 'spouse', personDeceased=True), {'type': 'title', 'person': 'a', 'personTitle': ['Ritter']}]))
        self.assertEqual(['unmarked mention after recorded death or impossible age'], [c['reason'] for c in result.conflicts])
        self.assertEqual('anchored', result.relationships[0].derivations[0]['identity'])

    def test_earlier_generic_fact_date_controls_chronology(self):
        death = {'type': 'death', 'person': 'a', 'diedOn': '1387'}
        earlier = {'type': 'generic', 'person': 'a', 'date': '1369-08-27', 'content': 'issued a ruling.'}
        inputs = self.inputs(facts=[death, earlier])
        self.assertEqual('1369-08-27', inputs.assertions[1].historical_date)
        self.assertFalse(build(inputs).conflicts)
        del earlier['date']
        self.assertTrue(build(self.inputs(facts=[death, earlier])).conflicts)

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
        self.assertEqual({'facts', 'with-guesses'}, set(output['evidence']))
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

    def test_python_script_changes_do_not_invalidate_tree(self):
        self.write('scripts/family_graph/graph.py', 'original')
        inputs = self.inputs(facts=[relation('a', 'b')])
        output = serialize(inputs, [build(inputs, include_guesses=True)])
        self.assertTrue(all(path.endswith(('.json', '.md')) for path in output['inputs']))
        self.write('scripts/family_graph/graph.py', 'changed')
        validate_generated(output, inputs.people, self.root)
        self.assertEqual(inputs.manifest, input_manifest(self.root))

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

    def test_places_come_from_the_entry_mention_and_a_death_mention(self):
        inputs = self.inputs(facts=[relation('a', 'b')])
        mention = inputs.assertions[0].mentions[0]
        self.assertEqual(set(), places_for(mention))
        mention.assertion.context['places'] = ('essingen',)
        self.assertEqual({('context', 'essingen')}, places_for(mention))
        mention.assertion.original.update({'type': 'death', 'mention': [{'person': 'Alex'}, {'place': 'north'}]})
        self.assertEqual({('context', 'essingen'), ('death-context', 'north')}, places_for(mention))

    def test_posthumous_parent_and_independent_family_survive_export(self):
        inputs = self.inputs([person(x) for x in ('father', 'son', 'parent2', 'child2')], [
            {'type': 'death', 'person': 'father', 'diedOn': '1390'},
            relation('father', 'son', personDeceased=True), relation('parent2', 'child2')])
        result = build(inputs)
        self.assertFalse(result.conflicts)
        graph = serialize(inputs, [result])['evidence']['facts']
        self.assertEqual({('father', 'son'), ('parent2', 'child2')},
                         {(e['person'], e['of']) for e in graph['relationships']})

    def test_same_named_brothers_with_opposite_ranks_stay_distinct(self):
        name = 'Konrad von North'
        def brother(rank):
            return relation(name, 'a', 'sibling', personTitle=[rank])
        self.inputs(facts=[brother('Ritter'), brother('Edelknecht')])
        self.write('data/documents/confirmation.json', {'date': '1394', 'facts': [brother('Ritter')]})
        inputs = load_inputs(self.root, validate=False)
        nodes = serialize(inputs, [build(inputs)])['evidence']['facts']['nodes']
        self.assertEqual({('Ritter',): 2, ('Edelknecht',): 1},
                         {tuple(n['titles']): len(n['mentions']) for n in nodes if n['name'] == name})

    def test_same_name_with_different_titles_in_one_document_never_merge(self):
        name = 'Eberhard von North'
        def brother(*titles):
            return relation(name, 'a', 'sibling', **({'personTitle': list(titles)} if titles else {}))
        self.inputs(facts=[brother('Vogt zu Dürn'), brother('genannt von Zimmern'), brother(), brother('genannt von Zimmern')])
        inputs = load_inputs(self.root, validate=False)
        nodes = serialize(inputs, [build(inputs)])['evidence']['facts']['nodes']
        self.assertEqual({('Vogt zu Dürn',): 1, ('genannt von Zimmern',): 2, (): 1},
                         {tuple(n['titles']): len(n['mentions']) for n in nodes if n['name'] == name})

    def test_unanchored_spouse_and_mother_across_sources(self):
        name = 'Elisabeth von North'
        self.inputs(facts=[relation(name, 'a', 'spouse'), relation(name, 'b')])
        self.write('data/documents/second.json', {'date': '1394', 'facts': [relation(name, 'a', 'spouse')],
                                                  'guesses': [relation(name, 'c')]})
        inputs = load_inputs(self.root, validate=False)
        for guesses in (False, True):
            graph = unpack_evidence(serialize(inputs, [build(inputs, guesses)])['evidence']['with-guesses' if guesses else 'facts'])
            mother, = [n for n in graph['nodes'] if n['name'] == name]
            self.assertNotIn('registry', mother)
            self.assertEqual(3 + guesses, len(mother['mentions']))
            self.assertEqual({'b', 'c'} if guesses else {'b'},
                             {e['of'] for e in graph['relationships'] if e['type'] == 'parent' and e['person'] == mother['key']})

    def test_opposite_kin_assertions_keep_direction_through_export(self):
        self.write('data/kinship.md', 'patruus: PS | S | exact')
        inputs = self.inputs(facts=[relation('c', 'a', 'kin', term='patruus'), relation('a', 'c', 'kin', term='patruus')])
        result = build(inputs)
        tree = serialize(inputs, [result])
        edges = tree['evidence']['facts']['relationships']
        self.assertEqual({('c', 'a'), ('a', 'c')}, {(e['person'], e['of']) for e in edges})
        self.assertEqual(2, len(result.relationships))
        edges.pop()
        edges[0]['of'], edges[0]['person'] = edges[0]['person'], edges[0]['of']
        with self.assertRaises(ValueError):
            validate_generated(tree, inputs.people, self.root)

    def test_kin_exclusion_applies_before_same_section_merge(self):
        self.write('data/kinship.md', 'Vetter: PS SC PSC | S | narrow')
        name = 'Konrad von North'
        for relative, expected in [('a', 2), ('b', 1)]:
            inputs = self.inputs(facts=[relation(name, 'a', 'kin', term='Vetter'), relation(name, relative, 'sibling')])
            nodes = serialize(inputs, [build(inputs)])['evidence']['facts']['nodes']
            self.assertEqual(expected, sum(n['name'] == name for n in nodes))

    def test_unrelated_generation_conflict_preserves_other_merges(self):
        inputs = self.inputs(facts=[relation('a', 'b'), relation('a', 'b', 'sibling'),
                                    relation('Konrad von North', 'c'), relation('Konrad von North', 'c')])
        result = build(inputs)
        self.assertIn({'reason': 'inconsistent anchored generations', 'identities': ['a', 'b']}, result.conflicts)
        nodes = serialize(inputs, [result])['evidence']['facts']['nodes']
        merged, = [n for n in nodes if n['name'] == 'Konrad von North']
        self.assertEqual(2, len(merged['mentions']))

    def test_document_birth_name_is_counted_once_and_attached_to_context(self):
        self.write('data/places.json', [{'id': place.lower(), 'variations': [place]} for place in ('North', 'South', 'Hill')])
        self.write('data/nobiliary_particles.md', 'von')
        self.inputs(facts=[relation('Elisabeth von South', 'b'),
                           {'type': 'generic', 'person': 'Elisabeth von South',
                            'content': 'held Hill with Konrad von North and Arnold von South.'}])
        path = self.root / 'data/documents/test.json'
        document = json.loads(path.read_text())
        document['entries'][0]['mention'] = [{'person': 'Arnold von South'}, {'person': 'Elisabeth von South'},
                                             {'person': 'Konrad von North'}, {'place': 'hill'}]
        path.write_text(json.dumps(document))
        phrase = 'Elisabeth von North, née von South'
        self.write('data/documents/prose.json', {'date': '1394', 'place': 'Hill', 'entries': [
            {'english': f'{phrase} held Hill with Konrad von North and Arnold von South. {phrase} witnessed.',
             'mention': [{'person': 'Arnold von South'}, {'person': 'Elisabeth von South'}, {'person': 'Konrad von North'},
                         {'place': 'hill'}]}]})
        inputs = load_inputs(self.root, validate=False)
        result = build(inputs)
        tree = serialize(inputs, [result])
        counts = tree['matchingBackground']['facts']['counts']
        self.assertEqual(4, counts['elisabeth von south'])
        self.assertNotIn('elisabeth von north', counts)
        graph = unpack_evidence(tree['evidence']['facts'])
        elisabeth, = [n for n in graph['nodes'] if n['name'] == 'Elisabeth von South']
        english = [m for m in elisabeth['mentions'] if m['source']['pointer'].endswith('/mention')]
        self.assertEqual(['Elisabeth von South'], [m['reference'] for m in english])
        self.assertEqual(1, len(graph['relationships']))

    def test_incomplete_passage_search_never_commits_first_grouping(self):
        name = 'Konrad von North'
        facts = [relation(name, endpoint, 'spouse', personTitle=titles)
                 for endpoint, titles in [('a', ['Ritter']), ('b', ['Edelknecht']), ('c', [])]]
        inputs = self.inputs(facts=facts)
        for limit in ('PASSAGE_SEARCH_LIMIT', 'PASSAGE_PARTITION_LIMIT'):
            with self.subTest(limit=limit), patch('family_graph.reconstruction.' + limit, 1):
                result = build(inputs)
                serialize(inputs, [result])
                self.assertFalse(any(link['reason'] == 'repeated participant within one dated source passage'
                                     for link in result.evidence_graph['links']))

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
        self.assertNotIn('schema', output)
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

    def inferred_parents(self, facts):
        inputs = self.inputs([person('unrelated', 'Unrelated')], facts)
        result = build(inputs)
        graph = result.evidence_graph
        named = {node['key']: node['name'] for node in graph['nodes']}
        return inputs, result, [(named[e['person']], named[e['of']], e['derivations']) for e in graph['relationships']
                                if e['type'] == 'parent' and any('inference' in d for d in e['derivations'])]

    def test_same_surname_sibling_shares_recorded_father(self):
        inputs, result, inferred = self.inferred_parents([relation('Eberhard von North', 'Ulrich von North'),
                                                          relation('Ulrich von North', 'Kunz von North', 'sibling'),
                                                          relation('Ulrich von North', 'Bea von South', 'sibling')])
        self.assertEqual([('Eberhard von North', 'Kunz von North')], [(left, right) for left, right, _ in inferred])
        self.assertEqual([{'sibling'}], [{d['inference'] for d in derivations} for _, _, derivations in inferred])
        self.assertGreaterEqual(len(inferred[0][2][0]['sources']), 2)
        serialize(inputs, [result])

    def test_sibling_with_a_different_recorded_father_gets_no_inferred_father(self):
        _, _, inferred = self.inferred_parents([relation('Eberhard von North', 'Ulrich von North'),
                                                relation('Arnold von North', 'Kunz von North'),
                                                relation('Ulrich von North', 'Kunz von North', 'sibling')])
        self.assertEqual([], inferred)

    def test_same_surname_mother_is_not_inherited_by_sibling(self):
        _, _, inferred = self.inferred_parents([relation('Elisabeth von North', 'Ulrich von North'),
                                                relation('Ulrich von North', 'Kunz von North', 'sibling')])
        self.assertEqual([], inferred)

    def test_names_md_headers_give_genders(self):
        names = Names((self.root / 'data/names.md').read_text(), [])
        self.assertEqual(['man', 'man', 'woman', None, None],
                         [names.gender(names.key(value)) for value in ('Eberhardi von North', 'Cunz', 'Jutta', 'Münch', 'Alex')])

    def one_document_children(self, facts):
        self.inputs([person('unrelated', 'Unrelated')], facts)
        graph = build(load_inputs(self.root, validate=False)).evidence_graph
        return [node for node in graph['nodes'] if node['name'] == 'Hans von North']

    def test_different_recorded_fathers_keep_children_apart(self):
        self.assertEqual(2, len(self.one_document_children([relation('Eberhard von North', 'Hans von North'),
                                                            relation('Arnold von North', 'Hans von North')])))

    def test_different_recorded_mothers_keep_children_apart(self):
        self.assertEqual(2, len(self.one_document_children([relation('Elisabeth von South', 'Hans von North'),
                                                            relation('Jutta von West', 'Hans von North')])))

    def test_same_named_fathers_and_a_father_with_a_mother_do_not_block(self):
        self.assertEqual(1, len(self.one_document_children([relation('Eberhard von North', 'Hans von North'),
                                                            relation('Eberhard von North', 'Hans von North'),
                                                            relation('Elisabeth von South', 'Hans von North')])))

    def test_inherited_and_recorded_fathers_never_give_one_person_two_fathers(self):
        self.inputs([person('unrelated', 'Unrelated')], [relation('Eberhard von North', 'Ulrich von North'),
                                                         relation('Ulrich von North', 'Hans von North', 'sibling')])
        self.write('data/documents/other.json', {'date': '1394', 'facts': [relation('Arnold von North', 'Hans von North'),
                                                                          relation('Ulrich von North', 'Hans von North', 'sibling')]})
        graph = build(load_inputs(self.root, validate=False)).evidence_graph
        named = {node['key']: node['name'] for node in graph['nodes']}
        fathers = {}
        for edge in graph['relationships']:
            if edge['type'] == 'parent':
                fathers.setdefault(edge['of'], set()).add(named[edge['person']])
        self.assertTrue(all(len(values) == 1 for values in fathers.values()), fathers)

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

    def test_pass_zero_kinship_variants_share_one_relationship(self):
        self.write('data/kinship.md', 'Schwager, swager, Schwägerin: SpS SSp SpSSp | blood | narrow\n')
        facts = [relation('a', 'b', 'kin', term=term)
                 for term in ('swager', 'Schwager', 'Schwägerin')]
        inputs = self.inputs(facts=facts)
        output = serialize(inputs, [build(inputs)])
        edges = output['evidence']['facts']['relationships']
        self.assertEqual(1, len(edges))
        self.assertEqual('Schwager', edges[0]['term'])
        self.assertEqual(3, len(edges[0]['derivations']))
        self.assertEqual(['swager', 'Schwager', 'Schwägerin'], [fact['term'] for fact in facts])

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
        self.inputs([person('a', 'Alex'), person('other_a', 'Alex'), person('b', 'Bea')], [relation('Alex', 'b', 'spouse')])
        self.write('data/books/independent.json', {'entries': [{'guesses': [{**relation('a', 'b', 'spouse'), 'date': '1390'}]}]})
        result = build(load_inputs(self.root, validate=False), include_guesses=True)
        # The preceding diagnostic resolver accepts this legacy score. The
        # actual source graph must still apply the weaker guessed evidence.
        self.assertTrue(any(d.identity == 'a' and d.uses_guesses for d in result.decisions.values()))
        graph = result.evidence_graph
        # The source graph joins them by its own rule (two same-named spouses of
        # b), and the join keeps its dependency on the guess.
        link = next(link for link in graph['links'] if link['reason'] == 'same-named relatives of one identity')
        self.assertTrue(any('/guesses/' in ref['pointer'] for ref in link['sources']))

    def test_apply_writes_only_tree_and_preserves_the_confirmed_registry(self):
        inputs = self.inputs(facts=[relation('a', 'b')])
        before = (self.root / 'data/people.json').read_bytes()
        tree = serialize(inputs, [build(inputs)])
        output = apply(inputs, tree)
        self.assertEqual(before, (self.root / 'data/people.json').read_bytes())
        self.assertEqual(output, (self.root / 'data/tree.json').read_bytes())
        self.assertNotIn('data/tree.json', tree['inputs'])
        self.assertTrue(all(set(person) == {'id', 'name'} for person in json.loads(before)))

    def test_apply_commits_only_merged_and_ambiguous_comparisons_and_caches_the_rest(self):
        inputs = self.inputs(facts=[relation('a', 'b')])
        tree = serialize(inputs, [build(inputs)])
        view = next(iter(tree['evidence']))
        graph = tree['evidence'][view]
        prior = json.loads((self.root / 'data/matching.json').read_text())['priorProbability']
        template = {'person': graph['nodes'][0]['key'], 'candidate': graph['nodes'][1]['key'], 'probability': prior,
                    'logOdds': math.log(prior / (1 - prior)), 'features': [], 'usesGuesses': False, 'sources': [graph['sources'][0]],
                    'stage': 3, 'iteration': 1, 'reason': 'x'}
        full = unpack_evidence(graph)
        full['comparisons'] = [{**template, 'status': status} for status in ('merged', 'below-threshold', 'superseded')]
        tree['evidence'][view] = pack_evidence(full)
        apply(inputs, tree)
        saved = json.loads((self.root / 'data/tree.json').read_text())
        self.assertEqual(['merged'], [c['status'] for c in unpack_evidence(saved['evidence'][view])['comparisons']])
        self.assertNotIn(b'\n  ', (self.root / 'data/tree.json').read_bytes().strip())
        debug = json.loads((self.root / '.cache/tree-debug.json').read_text())
        self.assertEqual(3, len(unpack_evidence(debug['evidence'][view])['comparisons']))
        self.assertEqual(debug['fingerprint'], saved['fingerprint'])

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
        self.assertIn('evidence', json.loads((self.root / 'data/tree.json').read_text()))

    def test_confirmed_registry_rejects_computation_fields(self):
        self.inputs()
        self.write('data/people.json', [person('a', 'Alex', relationships=[])])
        with self.assertRaisesRegex(ValueError, 'only id and name'):
            load_inputs(self.root)


if __name__ == '__main__':
    unittest.main()
