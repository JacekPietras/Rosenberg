"""Behavioral tests for the configured source-to-source probability model."""
from copy import deepcopy
from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from family_graph import build, load_inputs
from family_graph.names import Names
from family_graph.sources import walk_assertions
from family_graph.probability import DEFAULTS, ProbabilityModel, Profile, Observation, parameters, reliability, title_category
from family_graph.export import serialize, validate_generated


class ProbabilityTests(unittest.TestCase):
    def setUp(self):
        self.names = Names('Alex\nBea\nChris\n', [{'id': 'north', 'variations': ['North']}])
        self.model = ProbabilityModel(None, self.names)

    def profile(self, title=None, date='1393', category='documents', kind='facts', death=None):
        fact = {'type': 'title', 'person': 'Alex von South', 'personTitle': [title or 'Ritter']}
        if death:
            fact = {'type': 'death', 'person': 'Alex von South', 'diedOn': death}
        _, assertion = next(walk_assertions({kind: [{**fact, 'date': date}]}, f'data/{category}/{date}.json'))
        profile = Profile([assertion.mentions[0].handle], assertion.mentions)
        profile.refs[assertion.source.key] = assertion.source
        if title:
            profile.titles[title_category(title)] = [(assertion.source, assertion.bounds)]
            if title_category(title)[0] == 'office':
                for place in self.model.places(title):
                    profile.office_scopes[place] = [(assertion.source, assertion.bounds)]
        return profile

    def test_every_title_category_decays_with_time(self):
        for title in ('Ritter', 'der Jüngere', 'zu North', 'Vogt zu North', 'genannt von North', 'born von North', 'Edelmann'):
            with self.subTest(title=title):
                first = self.profile(title)
                near = self.model.compare(first, self.profile(title, '1394'))
                far = self.model.compare(first, self.profile(title, '1423'))
                positive = lambda result: sum(f['contribution'] for f in result['features'] if f['contribution'] > 0)
                self.assertGreater(positive(near), positive(far))
                self.assertGreater(near['probability'], far['probability'])

    def test_scoped_office_is_much_stronger_than_generic_rank(self):
        office = self.model.compare(self.profile('Vogt zu North'), self.profile('Vogt zu North'))
        rank = self.model.compare(self.profile('Ritter'), self.profile('Ritter'))
        self.assertGreater(office['probability'], .99)
        self.assertLess(rank['probability'], .2)

    def test_prefixed_offices_and_their_shared_geography_are_recognized(self):
        first = self.profile('erzb. Amtmann zu North')
        exact = self.model.compare(first, self.profile('erzb. Amtmann zu North'))
        self.assertGreater(exact['probability'], .99)
        self.assertFalse(any('shared office scope' in f['name'] for f in exact['features']))
        different = self.model.compare(first, self.profile('Burggraf zu North'))
        self.assertTrue(any(f['name'] == 'shared office scope: north' for f in different['features']))
        self.assertLess(different['probability'], exact['probability'])

    def test_source_factors_and_guess_factor_apply_independently(self):
        for category, source_factor in [('documents', 1), ('images', 1), ('books', .5), ('notes', .5)]:
            for kind, guess_factor in [('facts', 1), ('guesses', DEFAULTS['guessWeight'])]:
                profile = self.profile('Vogt zu North', category=category, kind=kind)
                self.assertEqual(source_factor * guess_factor, reliability(profile.mentions[0].assertion.source, DEFAULTS))
                comparison = self.model.compare(profile, profile)
                feature = next(f for f in comparison['features'] if 'office title' in f['name'])
                self.assertAlmostEqual(8 * source_factor * guess_factor, feature['contribution'])

    def person(self, *facts, date='1393', category='documents', kind='facts'):
        document = {kind: [{**fact, 'date': date} for fact in facts]}
        mentions = [m for _, a in walk_assertions(document, f'data/{category}/{date}.json') for m in a.mentions
                    if m.reference == 'Alex von South']
        profile = Profile([m.handle for m in mentions], mentions)
        for mention in mentions:
            profile.refs[mention.assertion.source.key] = mention.assertion.source
            for title in mention.titles:
                profile.titles.setdefault(title_category(title), []).append((mention.assertion.source, mention.assertion.bounds))
        return profile

    def feature(self, result, name):
        return sum(f['contribution'] for f in result['features'] if name in f['name'])

    def test_incompatible_document_deaths_block_and_weaker_sources_are_penalized(self):
        comparison = self.model.compare(self.profile(death='1390'), self.profile(death='1391'))
        self.assertEqual(['incompatible death dates'], comparison['blocks'])
        book = self.model.compare(self.profile(death='1390'), self.profile(death='1391', category='books'))
        self.assertEqual([], book['blocks'])
        self.assertAlmostEqual(-20 * .5, self.feature(book, 'incompatible death dates'))
        guessed = self.model.compare(self.profile(death='1390'), self.profile(death='1391', category='books', kind='guesses'))
        self.assertAlmostEqual(-20 * .225, self.feature(guessed, 'incompatible death dates'))

    def test_unmarked_mention_after_death_is_a_different_person(self):
        dead = self.person({'type': 'death', 'person': 'Alex von South', 'diedBefore': '1300'}, date='1300')
        later = {'type': 'title', 'person': 'Alex von South', 'personTitle': ['Vogt zu North']}
        self.assertEqual(['mention after recorded death'], self.model.compare(dead, self.person(later, date='1328'))['blocks'])
        guessed = self.model.compare(dead, self.person(later, date='1328', category='books', kind='guesses'))
        self.assertEqual([], guessed['blocks'])
        self.assertAlmostEqual(-20 * .225, self.feature(guessed, 'mention after recorded death'))
        marked = self.model.compare(dead, self.person({**later, 'personDeceased': True}, date='1328'))
        self.assertEqual([], marked['blocks'])
        self.assertFalse(any('death' in f['name'] for f in marked['features']))

    def test_compatible_deceased_bounds_and_earlier_life_are_neutral(self):
        widow = lambda: {'type': 'spouse', 'person': 'Bea', 'of': 'Alex von South', 'ofDeceased': True}
        first, second = self.person(widow(), date='1300'), self.person(widow(), date='1357')
        result = self.model.compare(first, second)
        self.assertEqual([], result['blocks'])
        self.assertFalse(any('death' in f['name'] for f in result['features']))
        earlier = self.person({'type': 'title', 'person': 'Alex von South', 'personTitle': ['Ritter']}, date='1290')
        self.assertEqual([], self.model.compare(earlier, first)['blocks'])

    def test_time_distance_counts_only_through_implied_age(self):
        office = lambda: {'type': 'title', 'person': 'Alex von South', 'personTitle': ['Vogt zu North']}
        first = self.person(office(), date='1300')
        self.assertEqual(0, self.feature(self.model.compare(first, self.person(office(), date='1315')), 'age:'))
        # Year precision is read permissively: end of 1300 to start of 1357.
        result = self.model.compare(first, self.person(office(), date='1357'))
        self.assertAlmostEqual(-1.2, self.feature(result, 'age:'), places=2)
        self.assertEqual([], result['blocks'])
        self.assertTrue(self.model.compare(first, self.person(office(), date='1375'))['blocks'][0].startswith('impossible age'))
        book = self.model.compare(first, self.person(office(), date='1375', category='books'))
        self.assertAlmostEqual(-20 * .5, self.feature(book, 'age:'))

    def test_later_activity_favors_the_younger_generation(self):
        parent = {'type': 'parent', 'person': 'Alex von South', 'personTitle': ['der Ältere'], 'of': 'Alex von South', 'ofTitle': ['der Jüngere']}
        document = {'facts': [{**parent, 'date': '1300'}]}
        elder, younger = next(walk_assertions(document, 'data/documents/1300.json'))[1].mentions
        later = self.person({'type': 'title', 'person': 'Alex von South', 'personTitle': ['der Ältere']}, date='1357')
        scores = {}
        for mention in (elder, younger):
            profile = Profile([mention.handle], [mention])
            profile.titles = {title_category(t): [(mention.assertion.source, mention.assertion.bounds)] for t in mention.titles}
            scores[mention.field] = self.model.compare(profile, later)
        self.assertAlmostEqual(-1.2, self.feature(scores['person'], 'age:'), places=2)
        self.assertEqual(0, self.feature(scores['of'], 'age:'))
        self.assertEqual(0, self.feature(scores['of'], 'elder title before younger'))
        self.assertGreater(scores['of']['logOdds'] - scores['person']['logOdds'], DEFAULTS['ambiguityLogOddsMargin'])

    def test_title_regressions_are_directional(self):
        title = lambda value, date: self.person({'type': 'title', 'person': 'Alex von South', 'personTitle': [value]}, date=date)
        self.assertEqual(0, self.feature(self.model.compare(title('der Jüngere', '1300'), title('der Ältere', '1330')), 'before'))
        self.assertEqual(-DEFAULTS['opposedAgePenalty'], self.feature(self.model.compare(title('der Ältere', '1300'), title('der Jüngere', '1330')), 'elder title before younger'))
        self.assertEqual(0, self.feature(self.model.compare(title('Edelknecht', '1300'), title('Ritter', '1330')), 'before'))
        self.assertEqual(-DEFAULTS['rankRegressionPenalty'], self.feature(self.model.compare(title('Ritter', '1300'), title('Edelknecht', '1330')), 'Ritter before Edelknecht'))

    def test_names_and_places_are_recognized_without_surname_double_counting(self):
        self.assertEqual({'alex von south', 'bea von north'}, self.model.person_names('Alex von South sold property at North to Bea von North.'))
        profile = self.profile()
        ref, bounds = profile.mentions[0].assertion.source, profile.mentions[0].assertion.bounds
        self.model.add_context(profile, ref, bounds, 'Alex von South met Bea von North.', self_names={'alex von south'})
        self.assertFalse(profile.places)
        self.assertIn('bea von north', profile.associates)
        self.model.add_context(profile, ref, bounds, 'Alex von South held property at North.', self_names={'alex von south'})
        self.assertIn(('property', 'north'), profile.places)

    def test_person_prefixes_do_not_hide_associates_or_invent_family_people(self):
        self.assertEqual({'rudolf von north', 'hans georg von south'}, self.model.person_names('Graf Rudolf von North met Hans Georg von South. The von North family.'))

    def test_frequency_extraction_does_not_mutate_cached_plain_text_names(self):
        profile = self.profile()
        ref, bounds = profile.mentions[0].assertion.source, profile.mentions[0].assertion.bounds
        text = '[a] held property at North.'
        self.assertEqual(set(), self.model.person_names(text))
        self.model.set_name_frequencies([], [Observation(ref, text, '1393', bounds, {})], {'a': {'name': 'Alex von South'}})
        self.assertIn('alex von south', self.model.background['counts'])
        self.assertEqual(set(), self.model.person_names(text))

    def test_rare_full_relative_names_have_capped_additional_support(self):
        self.model.background = {'total': 100, 'counts': {'bea von east': 1, 'chris von west': 40}}
        rare, _ = self.model.relative_rarity('bea von east')
        common, _ = self.model.relative_rarity('chris von west')
        self.assertGreater(rare, common)
        self.assertLessEqual(rare, DEFAULTS['relativeRarityMaxWeight'])
        self.assertEqual(0, self.model.relative_rarity('Bea')[0])

    def test_family_pair_without_ids_can_bootstrap_from_specific_names(self):
        relation = lambda left, right: {'type': 'sibling', 'person': left, 'of': right, 'personTitle': ['Ritter'], 'ofTitle': ['Ritter']}
        background = [{'type': 'title', 'person': f'Person{i} von West', 'personTitle': ['Ritter']} for i in range(100)]
        inputs = self.repository([relation('Alex von South', 'Bea von East')], [relation('Alex von South', 'Bea von East')], background)
        graph = build(inputs).evidence_graph
        self.assertEqual(2, len(graph['nodes']))
        self.assertEqual(1, len(graph['relationships']))
        self.assertTrue(any('relative name rarity' in f['name'] for c in graph['comparisons'] for f in c['features']))

    def test_context_dates_use_interval_overlap_not_identical_spelling(self):
        first = [{'type': 'parent', 'person': 'Alex von South', 'personTitle': ['der Jüngere'], 'of': 'Bea', 'date': '1393-05-01'}]
        second = [{'type': 'parent', 'person': 'Alex von South', 'personTitle': ['der Jüngere'], 'of': 'Chris', 'date': '1394-05-01'}]
        inputs = self.repository(first, second, ['Alex von South held property at North.'], ['Alex von South held property at North.'])
        graph = build(inputs).evidence_graph
        self.assertEqual(1, len([n for n in graph['nodes'] if n['name'] == 'Alex von South']))
        self.assertEqual(2, graph['contextCoverage']['attached'])

    def test_informative_prose_can_bridge_family_records_without_creating_edges(self):
        first = [{'type': 'parent', 'person': 'Alex von South', 'of': 'Bea'}, 'Alex von South held property at North with Peter von West.']
        second = [{'type': 'parent', 'person': 'Alex von South', 'of': 'Chris'}, 'Alex von South held property at East with Peter von West.']
        inputs = self.repository(first, second)
        (inputs.root / 'data/places.json').write_text(json.dumps([{'id': 'north', 'variations': ['North']}, {'id': 'east', 'variations': ['East']}]))
        (inputs.root / 'data/documents/bridge.json').write_text(json.dumps({'date': '1393', 'facts': ['Alex von South held property at North and East with Peter von West.']}))
        # The prose-only occurrence can enrich an existing family identity;
        # its potential evidence is considered, without inventing parentage.
        graph = build(load_inputs(inputs.root, validate=False)).evidence_graph
        alex = [node for node in graph['nodes'] if node['name'] == 'Alex von South']
        self.assertEqual(1, len(alex))
        self.assertTrue(any(m['field'] == 'text' and m['source']['path'].endswith('bridge.json') for m in alex[0]['mentions']))
        self.assertGreaterEqual(alex[0]['identityProbability'], DEFAULTS['mergeProbability'])
        self.assertEqual(2, len(graph['relationships']))
        self.assertTrue(graph['contextCoverage']['contextOnlyOccurrences'] > 0)
        self.assertTrue(all(edge['type'] == 'parent' for edge in graph['relationships']))
        # A context occurrence is never an additional standalone family card.
        participants = {edge[field] for edge in graph['relationships'] for field in ('person', 'of')}
        self.assertEqual(participants, {node['key'] for node in graph['nodes']})

    def test_untyped_known_id_context_has_a_fixed_anchor_and_valid_export(self):
        inputs = self.repository([{'type': 'parent', 'person': 'Alex von South', 'of': 'Bea'},
                                  'Alex von South held property at North and East.'], [])
        root = inputs.root
        (root / 'data/people.json').write_text(json.dumps([{'id': 'a', 'name': 'Alex von South'}]))
        (root / 'data/places.json').write_text(json.dumps([{'id': 'north', 'variations': ['North']}, {'id': 'east', 'variations': ['East']}]))
        (root / 'data/documents/context.json').write_text(json.dumps({'date': '1393', 'facts': ['[a] held property at North and East.']}))
        inputs = load_inputs(root, validate=False)
        graph = build(inputs).evidence_graph
        self.assertTrue(any(node.get('registry') == 'a' for node in graph['nodes']))
        output = serialize(inputs, [build(inputs)])
        validate_generated(output, inputs.people, root)
        node = next(node for node in output['evidence']['facts']['nodes'] if node.get('registry') == 'a')
        context = next(m for m in node['mentions'] if m['field'] == 'text')
        context['reference'] = 'forged'
        with self.assertRaisesRegex(ValueError, 'context participant'):
            validate_generated(output, inputs.people, root)

    def test_context_record_cannot_override_another_confirmed_id(self):
        inputs = self.repository([{'type': 'parent', 'person': 'a', 'of': 'Bea'}], [],
                                 ['[a] held property at North and East.'])
        root = inputs.root
        (root / 'data/people.json').write_text(json.dumps([{'id': 'a', 'name': 'Alex von South'}, {'id': 'b', 'name': 'Other von West'}]))
        inputs = load_inputs(root, validate=False)
        output = serialize(inputs, [build(inputs)])
        node = next(n for n in output['evidence']['facts']['nodes'] if n.get('registry') == 'a')
        context = next(m for m in node['mentions'] if m['field'] == 'text')
        context['reference'] = 'b'
        with self.assertRaisesRegex(ValueError, 'context participant'):
            validate_generated(output, inputs.people, root)

    def test_same_place_across_roles_supplies_weaker_support(self):
        left, right = self.profile(), self.profile()
        ref, bounds = left.mentions[0].assertion.source, left.mentions[0].assertion.bounds
        self.model.add_context(left, ref, bounds, issuance='North')
        self.model.add_context(right, ref, bounds, text='Alex von South held property at North.')
        result = self.model.compare(left, right)
        cross = next(f for f in result['features'] if 'issuance/property place' in f['name'])
        self.assertEqual(DEFAULTS['placeWeights']['issuance'] * DEFAULTS['crossRolePlaceFactor'], cross['contribution'])

    def test_explicit_prose_ids_supply_context_without_a_local_typed_occurrence(self):
        relation = lambda child, title: {'type': 'parent', 'person': 'Alex von South', 'personTitle': [title], 'of': child}
        inputs = self.repository([relation('Bea', 'der Jüngere')], [relation('Chris', 'Ritter')])
        root = inputs.root
        (root / 'data/people.json').write_text(json.dumps([{'id': 'a', 'name': 'Alex von South'}]))
        (root / 'data/documents/anchor.json').write_text(json.dumps({'date': '1393', 'facts': [{'type': 'title', 'person': 'a', 'personTitle': ['der Jüngere', 'Ritter']}]}))
        (root / 'data/documents/context.json').write_text(json.dumps({'date': '1393', 'facts': ['[a] held property at North.']}))
        # This context source has no typed participant. The exact ID, rather
        # than an inferred same-name attachment, establishes whose property it is.
        for filename in ('first', 'second'):
            path = root / f'data/documents/{filename}.json'
            document = json.loads(path.read_text()); document['facts'].append('Alex von South held property at North.')
            path.write_text(json.dumps(document))
        graph = build(load_inputs(root, validate=False)).evidence_graph
        self.assertEqual(1, len([n for n in graph['nodes'] if n['name'] == 'Alex von South']))
        self.assertTrue(any(ref['path'].endswith('context.json') for c in graph['comparisons'] for ref in c['sources']))
        self.assertEqual(1, graph['contextCoverage']['explicitIdFacts'])

    def test_partial_names_do_not_merge_on_geography_and_associates_alone(self):
        inputs = self.repository([{'type': 'spouse', 'person': 'Alex', 'of': 'Bea von East'}],
                                 [{'type': 'spouse', 'person': 'Alex von South', 'of': 'Chris von West'}],
                                 ['Alex von South held property at North with Peter von East.'],
                                 ['Alex von South held property at North with Peter von East.'])
        # Give the bare reference a confirmed ID and explicit context. It is
        # still not the fully named person's identity merely due to shared land.
        root = inputs.root
        (root / 'data/people.json').write_text(json.dumps([{'id': 'a', 'name': 'Alex'}]))
        path = root / 'data/documents/first.json';document = json.loads(path.read_text())
        document['facts'] = [{'type': 'spouse', 'person': 'a', 'of': 'Bea von East'}, '[a] held property at North with Peter von East.']
        path.write_text(json.dumps(document))
        graph = build(load_inputs(root, validate=False)).evidence_graph
        self.assertTrue(any(n['name'] == 'Alex von South' and not n.get('registry') for n in graph['nodes']))
        self.assertTrue(any('omitted surname' in c['reason'] for c in graph['comparisons']))

    def test_different_age_titles_in_one_passage_are_different_people(self):
        facts = [{'type': 'parent', 'person': 'Alex von South', 'personTitle': [age], 'of': child}
                 for age, child in [('der Junge', 'Bea'), ('der Jüngere', 'Chris'), ('der Alte', 'Dora')]]
        facts.append({'type': 'parent', 'person': 'Alex von South', 'of': 'Eve'})
        inputs = self.repository(facts, [])
        graph = build(inputs).evidence_graph
        alex = [n for n in graph['nodes'] if n['name'] == 'Alex von South']
        self.assertEqual(4, len(alex))
        self.assertTrue(all(len(n['titles']) <= 1 for n in alex))

    def test_namesake_father_and_son_in_one_passage_are_split_by_generation(self):
        father = lambda child: {'type': 'parent', 'person': 'Alex von South', 'personTitle': ['zu North'], 'of': child}
        brother = lambda other: {'type': 'sibling', 'person': 'Alex von South', 'of': other}
        for explicit in ([], [{'type': 'parent', 'person': 'Alex von South', 'of': 'Alex von South'}]):
            with self.subTest(explicit=bool(explicit)):
                facts = [*map(father, ('Bea von South', 'Chris von South')), *map(brother, ('Bea von South', 'Chris von South')), *explicit]
                graph = build(self.repository(facts, [])).evidence_graph
                alex = [n for n in graph['nodes'] if n['name'] == 'Alex von South']
                self.assertEqual(2, len(alex))
                by_key = {n['key']: n for n in graph['nodes']}
                siblings = {key for edge in graph['relationships'] if edge['type'] == 'sibling'
                            for key in (edge['person'], edge['of']) if by_key[key]['name'] == 'Alex von South'}
                parents = {edge['person'] for edge in graph['relationships'] if edge['type'] == 'parent' and by_key[edge['of']]['name'] != 'Alex von South'}
                self.assertEqual(1, len(siblings)); self.assertEqual(1, len(parents))
                self.assertNotEqual(siblings, parents)

    def test_repeated_parent_records_do_not_manufacture_same_named_coparents(self):
        inputs = self.repository([{'type': 'parent', 'person': 'Alex von South', 'of': 'c'}],
                                 [{'type': 'parent', 'person': 'Alex von South', 'of': 'c'}])
        (inputs.root / 'data/people.json').write_text(json.dumps([{'id': 'c', 'name': 'Chris'}]))
        graph = build(load_inputs(inputs.root, validate=False)).evidence_graph
        self.assertFalse(any(f['name'] == 'shared family context: alex von south' for c in graph['comparisons'] for f in c['features']))

    def test_guess_and_parameter_validation(self):
        for key, value in [('guessWeight', 1), ('mergeProbability', 0), ('maxRounds', 1.5)]:
            bad = deepcopy(DEFAULTS); bad[key] = value
            with self.assertRaises(ValueError): parameters(bad)
        bad = deepcopy(DEFAULTS); bad['sourceWeights']['documents'] = .5
        with self.assertRaises(ValueError): parameters(bad)

    def repository(self, first, second, extra_first=(), extra_second=()):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / 'data/documents').mkdir(parents=True)
        (root / 'data/names.md').write_text('Alex\nBea\nChris\n')
        (root / 'data/places.json').write_text(json.dumps([{'id': 'north', 'variations': ['North']}]))
        (root / 'data/people.json').write_text(json.dumps([{'id': 'unrelated', 'name': 'Unrelated'}]))
        (root / 'data/matching.json').write_text(json.dumps(DEFAULTS))
        for filename, date, facts in [('first', '1393', [*first, *extra_first]), ('second', '1394', [*second, *extra_second])]:
            (root / f'data/documents/{filename}.json').write_text(json.dumps({'date': date, 'facts': facts}))
        return load_inputs(root, validate=False)

    def test_places_and_titles_link_people_without_registry_ids(self):
        relation = lambda child: {'type': 'parent', 'person': 'Alex von South', 'personTitle': ['der Jüngere', 'Ritter'], 'of': child}
        property_fact = 'Alex von South held property at North.'
        inputs = self.repository([relation('Bea')], [relation('Chris')], [property_fact], [property_fact])
        graph = build(inputs).evidence_graph
        self.assertEqual(1, len([node for node in graph['nodes'] if node['name'] == 'Alex von South']))
        self.assertEqual(2, len(graph['relationships']))
        self.assertTrue(any(c['status'] == 'merged' and c['probability'] >= DEFAULTS['mergeProbability'] for c in graph['comparisons']))
        self.assertTrue(any('property place' in feature['name'] for c in graph['comparisons'] for feature in c['features']))

    def test_formal_distinction_blocks_merge(self):
        parents = [{'type': 'parent', 'person': 'Alex von South', 'of': 'Alex von South',
                    'personTitle': ['Vogt zu North'], 'ofTitle': ['Vogt zu North']}]
        inputs = self.repository(parents, [])
        graph = build(inputs).evidence_graph
        self.assertEqual(2, len(graph['nodes']))
        self.assertTrue(any(c['status'] == 'incompatible' and 'explicitly distinct' in c['reason'] for c in graph['comparisons']))

    def test_associates_require_cooccurrence_in_one_fact(self):
        relation = lambda child: {'type': 'parent', 'person': 'Alex von South', 'personTitle': ['der Jüngere'], 'of': child}
        together = 'Alex von South met Bea von East and Chris von West.'
        inputs = self.repository([relation('Bea')], [relation('Chris')], [together], [together])
        graph = build(inputs).evidence_graph
        self.assertEqual(1, len([node for node in graph['nodes'] if node['name'] == 'Alex von South']))
        inputs = self.repository([relation('Bea')], [relation('Chris')], ['Alex von South witnessed.', 'Bea von East met Chris von West.'], [together])
        graph = build(inputs).evidence_graph
        self.assertEqual(2, len([node for node in graph['nodes'] if node['name'] == 'Alex von South']))

    def test_negative_guessed_rival_evidence_remains_in_match_provenance(self):
        title = lambda name: {'type': 'title', 'person': name, 'personTitle': ['Vogt zu North']}
        inputs = self.repository([title('Alex von South'), {'type': 'death', 'person': 'Alex von South', 'diedOn': '1390'},
                                  {'type': 'spouse', 'person': 'Alex von South', 'of': 'Bea'}], [])
        root = inputs.root
        (root / 'data/people.json').write_text(json.dumps([{'id': 'a', 'name': 'Alex von South'}, {'id': 'b', 'name': 'Alex von South'}]))
        (root / 'data/documents/anchors.json').write_text(json.dumps({'date': '1393', 'facts': [title('a'), title('b')],
            'guesses': [{'type': 'death', 'person': 'b', 'diedOn': '1391'}]}))
        graph = build(load_inputs(root, validate=False), include_guesses=True).evidence_graph
        matched = next(node for node in graph['nodes'] if node.get('registry') == 'a')
        self.assertTrue(any(m['source']['path'].endswith('first.json') for m in matched['mentions']))
        self.assertTrue(any(c['status'] == 'merged' and c['usesGuesses'] for c in graph['comparisons']))
        self.assertTrue(any(d['usesGuesses'] for edge in graph['relationships'] for d in edge['derivations']))

    def test_same_place_and_generic_rank_are_insufficient_to_merge_namesakes(self):
        relation = lambda child: {'type': 'parent', 'person': 'Alex von South', 'personTitle': ['Ritter'], 'of': child}
        inputs = self.repository([relation('Bea')], [relation('Chris')])
        for filename in ('first', 'second'):
            path = inputs.root / f'data/documents/{filename}.json'
            document = json.loads(path.read_text()); document['place'] = 'North'
            path.write_text(json.dumps(document))
        graph = build(load_inputs(inputs.root, validate=False)).evidence_graph
        self.assertEqual(2, len([node for node in graph['nodes'] if node['name'] == 'Alex von South']))

    def test_comparison_export_is_verified_and_parameters_are_fingerprinted(self):
        relation = lambda child: {'type': 'parent', 'person': 'Alex von South', 'personTitle': ['Vogt zu North'], 'of': child}
        inputs = self.repository([relation('Bea')], [relation('Chris')])
        tree = serialize(inputs, [build(inputs)])
        self.assertTrue(tree['evidence']['facts']['comparisons'])
        tree['evidence']['facts']['comparisons'][0]['probability'] = .1
        with self.assertRaisesRegex(ValueError, 'probability'): validate_generated(tree, inputs.people, inputs.root)


if __name__ == '__main__': unittest.main()
