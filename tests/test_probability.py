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


KINSHIP_TERMS = """Vetter, Vettern: PS SC PSC | S P C Sp | narrow
Schwager, swager: SpS SSp SpSSp | blood | narrow
Eidam: CSp | blood | exact
consanguineus: blood | Sp in-law | broad
"""


def context_fact(text, *mention):
    fact = {"type": "generic", "subject": "The source passage", "content": text}
    return {**fact, "mention": list(mention)} if mention else fact


def alex_mention(*extra):
    return [{"person": "Alex von South"}, *extra]


class ProbabilityTests(unittest.TestCase):
    def setUp(self):
        self.names = Names('Alex\nBea\nChris\n', [{'id': 'north', 'variations': ['North']}],
                           '# Younger\nder Jüngere, the Younger\nder Junge\n'
                           '# Older\nder Ältere, the Elder, the Older\nder Alte\n'
                           'Vogt, advocatus\nder Rote, Rufus\n')
        self.model = ProbabilityModel(None, self.names)

    def profile(self, title=None, date='1393', category='documents', kind='facts', death=None):
        fact = {'type': 'title', 'person': 'Alex von South', 'personTitle': [title or 'Ritter']}
        if death:
            fact = {'type': 'death', 'person': 'Alex von South', 'diedOn': death}
        _, assertion = next(walk_assertions({kind: [{**fact, 'date': date}]}, f'data/{category}/{date}.json'))
        profile = Profile([assertion.mentions[0].handle], assertion.mentions)
        profile.refs[assertion.source.key] = assertion.source
        if title:
            category = title_category(title, self.names)
            profile.titles[category] = [(assertion.source, assertion.bounds)]
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

    def test_associates_use_only_the_person_field_of_mentions(self):
        profile = self.profile()
        ref, bounds = profile.mentions[0].assertion.source, profile.mentions[0].assertion.bounds
        people = ('Bea von North', 'Bea von North')
        self.model.add_context(profile, ref, bounds, people, (), self_names={'alex von south'})
        self.assertEqual({'bea von north'}, set(profile.associates))
        self.assertEqual(1, len(profile.associates['bea von north']))

    def test_age_title_direction_comes_from_title_data_sections(self):
        self.assertEqual(('age', 'younger'), title_category('der Jüngere', self.names))
        self.assertEqual(('age', 'younger'), title_category('der Junge', self.names))
        self.assertEqual(('age', 'older'), title_category('der Ältere', self.names))
        self.assertEqual(('age', 'older'), title_category('der Alte', self.names))

    def test_titles_are_compared_by_meaning_not_wording(self):
        title = lambda result: [(f['name'], f['contribution']) for f in result['features']]
        for left, right in [('genannt North', 'called von North'), ('zu North', 'von North'), ('dictus de North', 'gennant North')]:
            with self.subTest(left=left, right=right):
                self.assertEqual([('designation title: north', DEFAULTS['titleWeights']['designation'])],
                                 title(self.model.compare(self.profile(left), self.profile(right))))
        for left, right in [('Vogt zu North', 'Vogt in North'), ('Vogt zu North', 'erzbischöflicher advocatus von North')]:
            with self.subTest(left=left, right=right):
                self.assertEqual([('office title: vogt north', DEFAULTS['titleWeights']['office'])],
                                 title(self.model.compare(self.profile(left), self.profile(right))))
        self.assertEqual([], title(self.model.compare(self.profile('Vogt zu North'), self.profile('zu North'))))
        self.assertEqual([('other title: der rote', DEFAULTS['titleWeights']['other'])],
                         title(self.model.compare(self.profile('Rufus'), self.profile('der Rote'))))

    def test_scoped_office_is_much_stronger_than_generic_rank(self):
        office = self.model.compare(self.profile('Vogt zu North'), self.profile('Vogt zu North'))
        rank = self.model.compare(self.profile('Ritter'), self.profile('Ritter'))
        self.assertGreater(office['probability'], .99)
        self.assertLess(rank['probability'], .2)

    def test_prefixed_offices_are_recognized(self):
        first = self.profile('erzb. Amtmann zu North')
        exact = self.model.compare(first, self.profile('erzb. Amtmann zu North'))
        self.assertGreater(exact['probability'], .99)
        different = self.model.compare(first, self.profile('Burggraf zu North'))
        self.assertFalse(any('office scope' in f['name'] for f in different['features']))
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
        inputs = self.repository(first, second, [context_fact('Alex von South held property at North.', *alex_mention({'place': 'north'}))],
                                 [context_fact('Alex von South held property at North.', *alex_mention({'place': 'north'}))])
        graph = build(inputs).evidence_graph
        self.assertEqual(1, len([n for n in graph['nodes'] if n['name'] == 'Alex von South']))
        self.assertEqual(2, graph['contextCoverage']['attached'])

    def test_generic_subject_and_context_count_once_and_preserve_deceased_status(self):
        facts = [{'type': 'parent', 'person': 'a', 'of': 'Bea', 'personDeceased': True},
                 {'type': 'generic', 'person': 'a', 'personDeceased': True,
                  'content': 'held property at North.'}]
        inputs = self.repository(facts, [])
        (inputs.root / 'data/people.json').write_text(json.dumps([{'id': 'a', 'name': 'Alex von South'}]))
        inputs = load_inputs(inputs.root, validate=False)
        graph = build(inputs).evidence_graph
        self.assertEqual(2, graph['nameFrequencies']['counts']['alex von south'])
        alex = next(node for node in graph['nodes'] if node.get('registry') == 'a')
        self.assertEqual({'person'}, {mention['field'] for mention in alex['mentions']})
        validate_generated(serialize(inputs, [build(inputs)]), inputs.people, inputs.root)

    def test_untyped_context_is_rejected_even_without_schema_validation(self):
        with self.assertRaisesRegex(ValueError, 'expected a typed assertion'):
            self.repository(['Alex von South held property at North.'], [])

    def test_informative_prose_can_bridge_family_records_without_creating_edges(self):
        first = [{'type': 'parent', 'person': 'Alex von South', 'of': 'Bea'}, context_fact('Alex von South held property at North with Peter von West.', *alex_mention({'person': 'Peter von West'}, {'place': 'north'}))]
        second = [{'type': 'parent', 'person': 'Alex von South', 'of': 'Chris'}, context_fact('Alex von South held property at East with Peter von West.', *alex_mention({'person': 'Peter von West'}, {'place': 'east'}))]
        inputs = self.repository(first, second)
        (inputs.root / 'data/places.json').write_text(json.dumps([{'id': 'north', 'variations': ['North']}, {'id': 'east', 'variations': ['East']}]))
        (inputs.root / 'data/documents/bridge.json').write_text(json.dumps({'date': '1393', 'facts': [context_fact('Alex von South held property at North and East with Peter von West.', *alex_mention({'person': 'Peter von West'}, {'place': 'east'}, {'place': 'north'}))]}))
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

    def test_partial_names_do_not_merge_on_geography_and_associates_alone(self):
        inputs = self.repository([{'type': 'spouse', 'person': 'Alex', 'of': 'Bea von East'}],
                                 [{'type': 'spouse', 'person': 'Alex von South', 'of': 'Chris von West'}],
                                 [context_fact('Alex von South held property at North with Peter von East.', *alex_mention({'person': 'Peter von East'}, {'place': 'north'}))],
                                 [context_fact('Alex von South held property at North with Peter von East.', *alex_mention({'person': 'Peter von East'}, {'place': 'north'}))])
        # Give the bare reference a confirmed ID and explicit context. It is
        # still not the fully named person's identity merely due to shared land.
        root = inputs.root
        (root / 'data/people.json').write_text(json.dumps([{'id': 'a', 'name': 'Alex'}]))
        path = root / 'data/documents/first.json';document = json.loads(path.read_text())
        document['facts'] = [{'type': 'spouse', 'person': 'a', 'of': 'Bea von East'}, {'type': 'generic', 'person': 'a', 'content': 'held property at North with Peter von East.',
                                            'mention': [{'person': 'Peter von East'}, {'place': 'north'}]}]
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

    def test_same_named_siblings_of_one_identified_person_merge(self):
        sibling = lambda: {'type': 'sibling', 'person': 'Alex von South', 'of': 'b'}
        inputs = self.repository([sibling()], [sibling()])
        (inputs.root / 'data/people.json').write_text(json.dumps([{'id': 'b', 'name': 'Bea von South'}]))
        (inputs.root / 'data/documents/second.json').write_text(json.dumps({'date': '1394', 'facts': [sibling()]}))
        (inputs.root / 'data/books').mkdir()
        (inputs.root / 'data/books/retold.json').write_text(json.dumps({'entries': [{'facts': [{**sibling(), 'date': '1393'}]}]}))
        graph = build(load_inputs(inputs.root, validate=False)).evidence_graph
        self.assertEqual(1, len([n for n in graph['nodes'] if n['name'] == 'Alex von South']))
        self.assertTrue(any(link['reason'] == 'same-named relatives of one identity' for link in graph['links']))

    def test_same_named_spouses_of_one_identified_person_merge(self):
        inputs = self.repository([{'type': 'spouse', 'person': 'w', 'of': 'Alex von South'}], [])
        root = inputs.root
        (root / 'data/people.json').write_text(json.dumps([{'id': 'w', 'name': 'Bea'}]))
        (root / 'data/books').mkdir()
        (root / 'data/books/retold.json').write_text(json.dumps({'entries': [{'facts': [
            {'type': 'spouse', 'person': 'Alex von South', 'of': 'Bea', 'date': '1393'}]}]}))
        graph = build(load_inputs(root, validate=False)).evidence_graph
        self.assertEqual(1, len([n for n in graph['nodes'] if n['name'] == 'Alex von South']))
        self.assertEqual(1, len([n for n in graph['nodes'] if n['name'] == 'Bea']))

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
        (root / 'data/nobiliary_particles.md').write_text('von')
        (root / 'data/places.json').write_text(json.dumps([{'id': 'north', 'variations': ['North']}]))
        (root / 'data/people.json').write_text(json.dumps([{'id': 'unrelated', 'name': 'Unrelated'}]))
        (root / 'data/matching.json').write_text(json.dumps(DEFAULTS))
        for filename, date, facts in [('first', '1393', [*first, *extra_first]), ('second', '1394', [*second, *extra_second])]:
            (root / f'data/documents/{filename}.json').write_text(json.dumps({'date': date, 'facts': facts}))
        return load_inputs(root, validate=False)

    def test_places_and_titles_link_people_without_registry_ids(self):
        relation = lambda child: {'type': 'parent', 'person': 'Alex von South', 'personTitle': ['der Jüngere', 'Ritter'], 'of': child}
        property_fact = context_fact('Alex von South held property at North.', *alex_mention({'place': 'north'}))
        inputs = self.repository([relation('Bea')], [relation('Chris')], [property_fact], [property_fact])
        graph = build(inputs).evidence_graph
        self.assertEqual(1, len([node for node in graph['nodes'] if node['name'] == 'Alex von South']))
        self.assertEqual(2, len(graph['relationships']))
        self.assertTrue(any(c['status'] == 'merged' and c['probability'] >= DEFAULTS['mergeProbability'] for c in graph['comparisons']))
        self.assertTrue(any('context place' in feature['name'] for c in graph['comparisons'] for feature in c['features']))

    def test_formal_distinction_blocks_merge(self):
        parents = [{'type': 'parent', 'person': 'Alex von South', 'of': 'Alex von South',
                    'personTitle': ['Vogt zu North'], 'ofTitle': ['Vogt zu North']}]
        inputs = self.repository(parents, [])
        graph = build(inputs).evidence_graph
        self.assertEqual(2, len(graph['nodes']))
        self.assertTrue(any(c['status'] == 'incompatible' and 'explicitly distinct' in c['reason'] for c in graph['comparisons']))

    def test_associates_require_cooccurrence_in_one_fact(self):
        relation = lambda child: {'type': 'parent', 'person': 'Alex von South', 'personTitle': ['der Jüngere'], 'of': child}
        together = context_fact('Alex von South met Bea von East and Chris von West.')
        inputs = self.repository([relation('Bea')], [relation('Chris')], [together], [together])
        graph = build(inputs).evidence_graph
        self.assertEqual(1, len([node for node in graph['nodes'] if node['name'] == 'Alex von South']))
        inputs = self.repository([relation('Bea')], [relation('Chris')], [context_fact('Alex von South witnessed.'), context_fact('Bea von East met Chris von West.')], [together])
        graph = build(inputs).evidence_graph
        self.assertFalse(any(f['name'].startswith('same-fact associate') for c in graph['comparisons'] for f in c['features']))

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

    def test_same_place_and_generic_rank_join_only_as_best_candidate(self):
        relation = lambda child: {'type': 'parent', 'person': 'Alex von South', 'personTitle': ['Ritter'], 'of': child}
        inputs = self.repository([relation('Bea')], [relation('Chris')])
        for filename in ('first', 'second'):
            path = inputs.root / f'data/documents/{filename}.json'
            document = json.loads(path.read_text()); document['mention'] = [{'place': 'north'}]
            path.write_text(json.dumps(document))
        graph = build(load_inputs(inputs.root, validate=False)).evidence_graph
        self.assertEqual(1, len([node for node in graph['nodes'] if node['name'] == 'Alex von South']))
        record = next(c for c in graph['comparisons'] if c['status'] == 'merged')
        self.assertEqual(4, record['stage'])
        self.assertLess(record['probability'], DEFAULTS['mergeProbability'])
        self.assertLess(record['share'], .7)

    def test_comparison_export_is_verified_and_parameters_are_fingerprinted(self):
        relation = lambda child: {'type': 'parent', 'person': 'Alex von South', 'personTitle': ['Vogt zu North'], 'of': child}
        inputs = self.repository([relation('Bea')], [relation('Chris')])
        tree = serialize(inputs, [build(inputs)])
        self.assertTrue(tree['evidence']['facts']['comparisons'])
        tree['evidence']['facts']['comparisons'][0]['probability'] = .1
        with self.assertRaisesRegex(ValueError, 'probability'): validate_generated(tree, inputs.people, inputs.root)


    def family(self, extra):
        """Vogt Eberhard with brother Arnold and sons Eberhard and Arnold, plus extra dated facts."""
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / 'data/documents').mkdir(parents=True)
        (root / 'data/names.md').write_text('Arnold\nEberhard\n')
        (root / 'data/nobiliary_particles.md').write_text('von')
        (root / 'data/kinship.md').write_text(KINSHIP_TERMS)
        (root / 'data/places.json').write_text(json.dumps([{'id': 'north', 'variations': ['North']}]))
        (root / 'data/matching.json').write_text(json.dumps(DEFAULTS))
        (root / 'data/people.json').write_text(json.dumps([
            {'id': 'vogt', 'name': 'Eberhard von Rosenberg'}, {'id': 'uncle', 'name': 'Arnold von Rosenberg'},
            {'id': 'son_e', 'name': 'Eberhard von Rosenberg'}, {'id': 'son_a', 'name': 'Arnold von Rosenberg'}]))
        facts = {'1381': [{'type': 'sibling', 'person': 'uncle', 'of': 'vogt'}],
                 '1395': [{'type': 'parent', 'person': 'vogt', 'of': 'son_e'}, {'type': 'parent', 'person': 'vogt', 'of': 'son_a'},
                          {'type': 'sibling', 'person': 'son_e', 'of': 'son_a'}], **extra}
        for date, items in facts.items():
            (root / f'data/documents/{date}.json').write_text(json.dumps({'date': date, 'facts': items}))
        return build(load_inputs(root, validate=False)).evidence_graph

    def test_second_pass_attaches_vetter_to_fathers_brother(self):
        graph = self.family({'1401': [{'type': 'kin', 'person': 'Arnold von Rosenberg', 'personTitle': ['der Ältere'], 'of': 'son_e', 'term': 'Vetter'},
                                      {'type': 'sibling', 'person': 'son_e', 'of': 'son_a'}]})
        uncle = next(n for n in graph['nodes'] if n['key'] == 'uncle')
        self.assertIn('1401', uncle['dates'])
        record = next(c for c in graph['comparisons'] if c.get('stage') == 4 and c['status'] == 'merged')
        names = {f['name'] for f in record['features']}
        self.assertIn('kinship position PS of son_e (Vetter)', names)
        self.assertIn('age-title namesake one generation below', names)
        self.assertTrue(any(name.startswith('only compatible candidate') for name in names))
        self.assertGreater(record['share'], 0)

    def test_second_pass_vetter_never_matches_a_brother(self):
        graph = self.family({'1401': [{'type': 'kin', 'person': 'Arnold von Rosenberg', 'of': 'son_e', 'term': 'Vetter'}],
                             '1381': []})
        self.assertFalse(any('1401' in n['dates'] for n in graph['nodes'] if n['key'] == 'son_a'))
        self.assertTrue(any(c['status'] == 'incompatible' and 'Vetter excludes position S' in c['reason'] for c in graph['comparisons']))

    def test_broad_term_fitting_brother_and_son_joins_the_nearer_candidate(self):
        graph = self.family({'1387': [{'type': 'kin', 'person': 'Arnold von Rosenberg', 'of': 'vogt', 'term': 'consanguineus'}]})
        self.assertTrue(any('1387' in n['dates'] for n in graph['nodes'] if n['key'] == 'uncle'))
        self.assertFalse(any('1387' in n['dates'] for n in graph['nodes'] if n['key'] == 'son_a'))
        positions = {f['name'] for c in graph['comparisons'] if c.get('stage') == 4 for f in c['features'] if f['name'].startswith('kinship position')}
        self.assertEqual({'kinship position S of vogt (consanguineus)', 'kinship position C of vogt (consanguineus)'}, positions)

    def test_kinship_terms_combine_and_invert(self):
        from family_graph.kinship import Kinship, invert
        kinship = Kinship(KINSHIP_TERMS)
        self.assertEqual('Schwager', kinship.canonical('swager'))
        self.assertEqual('Vetter und Schwager', kinship.canonical('Vettern und swager'))
        self.assertEqual('unknown word', kinship.canonical('unknown word'))
        combined = kinship.term('Vetter und Schwager')
        self.assertTrue(combined.excludes(('S',)))
        self.assertFalse(combined.excludes(('Sp',)))
        self.assertTrue(combined.allowed.contains(('Sp', 'S')))
        self.assertEqual({('Sp', 'P')}, set(kinship.term('Eidam').inverted().allowed.paths))
        self.assertEqual(('S', 'C'), invert(('P', 'S')))
        self.assertTrue(kinship.term('unknown word').allowed.contains(('P', 'P')))

    def passage(self, facts, guesses=(), date='1381-05-25'):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / 'data/documents').mkdir(parents=True)
        (root / 'data/names.md').write_text('Alex\nBea\nChris\nKonrad\n')
        (root / 'data/nobiliary_particles.md').write_text('von')
        (root / 'data/places.json').write_text(json.dumps([{'id': 'north', 'variations': ['North']}]))
        (root / 'data/people.json').write_text(json.dumps([{'id': 'unrelated', 'name': 'Unrelated'}]))
        (root / 'data/matching.json').write_text(json.dumps(DEFAULTS))
        (root / 'data/documents/one.json').write_text(json.dumps({'date': date, 'facts': list(facts), 'guesses': list(guesses)}))
        return load_inputs(root, validate=False)

    def test_opposite_ranks_in_one_passage_are_two_people(self):
        ritter = lambda other: {'type': 'sibling', 'person': 'Konrad von South', 'personTitle': ['Ritter'], 'of': other}
        squire = lambda other: {'type': 'sibling', 'person': 'Konrad von South', 'personTitle': ['Edelknecht'], 'of': other}
        graph = build(self.passage([ritter('Bea von South'), ritter('Chris von South'), squire('Bea von South'), squire('Chris von South')])).evidence_graph
        konrads = [n for n in graph['nodes'] if n['name'] == 'Konrad von South']
        self.assertEqual(2, len(konrads))
        self.assertEqual([['Edelknecht'], ['Ritter']], sorted(n['titles'] for n in konrads))

    def test_explicit_deceased_marker_separates_but_a_death_record_does_not(self):
        late = {'type': 'parent', 'person': 'Alex von South', 'personDeceased': True, 'of': 'Bea von South'}
        living = {'type': 'generic', 'person': 'Alex von South', 'content': 'sealed the charter.'}
        sibling = {'type': 'spouse', 'person': 'Alex von South', 'of': 'Chris von South'}
        graph = build(self.passage([late, living, sibling])).evidence_graph
        self.assertEqual(2, len([n for n in graph['nodes'] if n['name'] == 'Alex von South']))
        # Being named as a brother is not a living mention.
        brother = {'type': 'sibling', 'person': 'Alex von South', 'of': 'Chris von South'}
        graph = build(self.passage([late, brother])).evidence_graph
        self.assertEqual(1, len([n for n in graph['nodes'] if n['name'] == 'Alex von South']))
        death = {'type': 'death', 'person': 'Alex von South', 'diedOn': '1381'}
        graph = build(self.passage([sibling, living, death], date='1381')).evidence_graph
        alex = [n for n in graph['nodes'] if n['name'] == 'Alex von South']
        self.assertEqual(1, len(alex))

    def test_known_relatives_never_join(self):
        # A father and his same-named son, each also named elsewhere with the same place.
        father = {'type': 'parent', 'person': 'Alex von South', 'personTitle': ['der Ältere'], 'of': 'Alex von South', 'ofTitle': ['der Jüngere']}
        place = lambda: context_fact('Alex von South held property at North.')
        inputs = self.repository([father], [{'type': 'spouse', 'person': 'Alex von South', 'of': 'Bea von South'}], [place()], [place()])
        graph = build(inputs).evidence_graph
        by_key = {n['key']: n for n in graph['nodes']}
        edge = next(e for e in graph['relationships'] if e['type'] == 'parent')
        self.assertNotEqual(edge['person'], edge['of'])
        self.assertEqual('Alex von South', by_key[edge['person']]['name'])

    def test_cousins_with_the_same_name_never_join(self):
        place = context_fact('Alex von South held property at North.')
        inputs = self.repository([{'type': 'parent', 'person': 'bea', 'of': 'Alex von South'}, {'type': 'sibling', 'person': 'bea', 'of': 'chris'}],
                                 [{'type': 'parent', 'person': 'chris', 'of': 'Alex von South'}], [place], [place])
        (inputs.root / 'data/people.json').write_text(json.dumps([{'id': 'bea', 'name': 'Bea von South'}, {'id': 'chris', 'name': 'Chris von South'}]))
        graph = build(load_inputs(inputs.root, validate=False)).evidence_graph
        self.assertEqual(2, len([n for n in graph['nodes'] if n['name'] == 'Alex von South']))
        self.assertTrue(any(c['status'] == 'incompatible' and 'known relatives' in c['reason'] for c in graph['comparisons']))

    def test_name_and_date_alone_do_not_join(self):
        inputs = self.repository([{'type': 'parent', 'person': 'Alex von South', 'of': 'Bea'}],
                                 [{'type': 'parent', 'person': 'Alex von South', 'of': 'Chris'}])
        graph = build(inputs).evidence_graph
        self.assertEqual(2, len([n for n in graph['nodes'] if n['name'] == 'Alex von South']))

    def test_rank_alone_does_not_join(self):
        relation = lambda child: {'type': 'parent', 'person': 'Alex von South', 'personTitle': ['Ritter'], 'of': child}
        graph = build(self.repository([relation('Bea')], [relation('Chris')])).evidence_graph
        self.assertEqual(2, len([n for n in graph['nodes'] if n['name'] == 'Alex von South']))

    def test_best_candidate_join_is_independent_of_input_order(self):
        relation = lambda child: {'type': 'parent', 'person': 'Alex von South', 'personTitle': ['der Jüngere'], 'of': child}
        place = context_fact('Alex von South held property at North.')
        first = build(self.repository([relation('Bea'), place], [relation('Chris')])).evidence_graph
        second = build(self.repository([relation('Chris')], [place, relation('Bea')])).evidence_graph
        size = lambda graph: sorted(len(n['mentions']) for n in graph['nodes'] if n['name'] == 'Alex von South')
        self.assertEqual(size(first), size(second))

    def test_guessed_alternative_death_dates_form_one_interval(self):
        from family_graph.probability import chronology
        _, early = next(walk_assertions({'guesses': [{'type': 'death', 'person': 'Alex von South', 'diedOn': '1383', 'date': '1383'}]}, 'data/books/x.json'))
        records = list(walk_assertions({'entries': [{'guesses': [
            {'type': 'death', 'person': 'Alex von South', 'diedOn': '1383', 'date': '1383'},
            {'type': 'death', 'person': 'Alex von South', 'diedOn': '1388', 'date': '1388'}]}]}, 'data/books/x.json'))
        levels = chronology([assertion.mentions[0] for _, assertion in records], DEFAULTS)
        self.assertEqual(1388, __import__('datetime').date.fromordinal(next(iter(levels.values()))['deathEnd'][0]).year)

    def test_same_date_opposite_ranks_across_sources_are_penalized(self):
        left, right = self.profile('Ritter', '1381-05-25'), self.profile('Edelknecht', '1381-05-25', category='books')
        left.ranks = [('ritter', left.mentions[0].assertion.source, left.mentions[0].assertion.bounds, 'a')]
        right.ranks = [('edelknecht', right.mentions[0].assertion.source, right.mentions[0].assertion.bounds, 'b')]
        record = self.model.compare(left, right)
        self.assertIn(('same-date opposite ranks', -DEFAULTS['sameDateRankConflictPenalty'] * .5),
                      [(f['name'], f['contribution']) for f in record['features']])

    def book_section(self, facts):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / 'data/books').mkdir(parents=True)
        (root / 'data/names.md').write_text('Alex\nBea\nChris\n')
        (root / 'data/nobiliary_particles.md').write_text('von')
        (root / 'data/places.json').write_text(json.dumps([]))
        (root / 'data/people.json').write_text(json.dumps([{'id': 'unrelated', 'name': 'Unrelated'}]))
        (root / 'data/matching.json').write_text(json.dumps(DEFAULTS))
        (root / 'data/books/book.json').write_text(json.dumps({'entries': [{'facts': facts}]}))
        return build(load_inputs(root, validate=False)).evidence_graph

    def test_pass_zero_merges_same_name_and_titles_in_one_section_across_years(self):
        elder = lambda kind, other, date: {'type': kind, 'person': 'Alex von South', 'personTitle': ['der Ältere'], 'of': other, 'date': date}
        graph = self.book_section([elder('spouse', 'Bea von East', '1383'), elder('parent', 'Chris von South', '1407')])
        alex = [n for n in graph['nodes'] if n['name'] == 'Alex von South']
        self.assertEqual(1, len(alex))
        self.assertEqual(1, alex[0]['identityProbability'])
        self.assertTrue(any(link['reason'] == 'same name and titles in one document or section' for link in graph['links']))

    def test_pass_zero_merges_untitled_namesakes_of_one_section(self):
        graph = self.book_section([{'type': 'spouse', 'person': 'Bea von East', 'of': 'Alex von South', 'date': '1383'},
                                   {'type': 'parent', 'person': 'Bea von East', 'of': 'Chris von South', 'date': '1407'},
                                   {'type': 'death', 'person': 'Bea von East', 'diedBefore': '1420', 'date': '1419'}])
        bea = [n for n in graph['nodes'] if n['name'] == 'Bea von East']
        self.assertEqual(1, len(bea))
        self.assertEqual(3, len(bea[0]['mentions']))
        self.assertEqual(1, bea[0]['identityProbability'])

    def test_pass_zero_needs_identical_titles_and_respects_blocks(self):
        titled = lambda title, other, date: {'type': 'parent', 'person': 'Alex von South', 'personTitle': [title], 'of': other, 'date': date}
        graph = self.book_section([titled('Ritter', 'Bea von East', '1383'), titled('der Ältere', 'Chris von South', '1407')])
        self.assertFalse(any(link['reason'] == 'same name and titles in one document or section' for link in graph['links']))
        # Father and son with the same name and title stay two people.
        graph = self.book_section([{'type': 'parent', 'person': 'Alex von South', 'personTitle': ['Ritter'], 'of': 'Alex von South',
                                    'ofTitle': ['Ritter'], 'date': '1383'}])
        self.assertEqual(2, len([n for n in graph['nodes'] if n['name'] == 'Alex von South']))
        # Living mentions more than 64 years apart stay two people.
        knight = lambda date: {'type': 'title', 'person': 'Alex von South', 'personTitle': ['Ritter'], 'date': date}
        graph = self.book_section([titled('Ritter', 'Bea von East', '1300'), knight('1300'),
                                   titled('Ritter', 'Chris von South', '1390'), knight('1390')])
        pointers = lambda node: {m['source']['pointer'] for m in node['mentions']}
        self.assertFalse(any({'/entries/0/facts/1', '/entries/0/facts/3'} <= pointers(n) for n in graph['nodes']))

    def test_a_parent_can_be_named_after_death_and_bounds_the_childs_birth(self):
        # "Albrecht, son of Eberhard" years after Eberhard's death is not a mention after death.
        graph = self.book_section([{'type': 'death', 'person': 'Alex von South', 'diedOn': '1519', 'date': '1519'},
                                   {'type': 'parent', 'person': 'Alex von South', 'of': 'Chris von South', 'date': '1555'}])
        self.assertEqual(1, len([n for n in graph['nodes'] if n['name'] == 'Alex von South']))
        from family_graph.probability import chronology
        _, parent = next(walk_assertions({'facts': [{'type': 'parent', 'person': 'Alex von South', 'of': 'Bea', 'date': '1555'}]}, 'data/books/x.json'))
        self.assertNotIn('alive', next(iter(chronology([parent.mentions[0]], DEFAULTS).values())))
        # A father dead in 1300 makes a son alive in 1375 at least 74: the age penalty applies.
        child = self.profile('Ritter', '1375')
        child.derived = [(1.0, __import__('datetime').date(1301, 12, 31).toordinal(), child.mentions[0].assertion.source)]
        other = self.profile('Ritter', '1381')
        record = self.model.compare(child, other)
        self.assertTrue(any(f['name'].startswith('age: at least 7') and f['contribution'] < 0 for f in record['features']))

if __name__ == '__main__': unittest.main()
