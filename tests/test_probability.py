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
from family_graph.probability import DEFAULTS, ProbabilityModel, Profile, parameters, reliability, title_category
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

    def test_source_factors_and_guess_factor_apply_independently(self):
        for category, source_factor in [('documents', 1), ('images', 1), ('books', .5), ('notes', .5)]:
            for kind, guess_factor in [('facts', 1), ('guesses', DEFAULTS['guessWeight'])]:
                profile = self.profile('Vogt zu North', category=category, kind=kind)
                self.assertEqual(source_factor * guess_factor, reliability(profile.mentions[0].assertion.source, DEFAULTS))
                comparison = self.model.compare(profile, profile)
                feature = next(f for f in comparison['features'] if 'office title' in f['name'])
                self.assertAlmostEqual(8 * source_factor * guess_factor, feature['contribution'])

    def test_conflicting_deaths_drastically_reduce_probability(self):
        comparison = self.model.compare(self.profile(death='1390'), self.profile(death='1391'))
        self.assertLess(comparison['probability'], 1e-8)
        guessed = self.model.compare(self.profile(death='1390'), self.profile(death='1391', kind='guesses'))
        self.assertGreater(guessed['probability'], comparison['probability'])
        self.assertLess(guessed['probability'], .001)

    def test_a_later_ordinary_attestation_is_not_a_death_conflict(self):
        result = self.model.compare(self.profile(death='1390'), self.profile('Ritter', date='1400'))
        self.assertFalse(any('death' in f['name'] for f in result['features']))

    def test_more_time_distance_lowers_probability_without_an_age_model(self):
        near = self.model.compare(self.profile(), self.profile(date='1394'))
        far = self.model.compare(self.profile(), self.profile(date='1494'))
        self.assertGreater(near['probability'], far['probability'])

    def test_names_and_places_are_recognized_without_surname_double_counting(self):
        self.assertEqual({'alex von south', 'bea von north'}, self.model.person_names('Alex von South sold property at North to Bea von North.'))
        profile = self.profile()
        ref, bounds = profile.mentions[0].assertion.source, profile.mentions[0].assertion.bounds
        self.model.add_context(profile, ref, bounds, 'Alex von South met Bea von North.', self_names={'alex von south'})
        self.assertFalse(profile.places)
        self.assertIn('bea von north', profile.associates)
        self.model.add_context(profile, ref, bounds, 'Alex von South held property at North.', self_names={'alex von south'})
        self.assertIn(('property', 'north'), profile.places)

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

    def test_formal_distinction_reduces_probability_and_prevents_merge(self):
        parents = [{'type': 'parent', 'person': 'Alex von South', 'of': 'Alex von South',
                    'personTitle': ['Vogt zu North'], 'ofTitle': ['Vogt zu North']}]
        inputs = self.repository(parents, [])
        graph = build(inputs).evidence_graph
        self.assertEqual(2, len(graph['nodes']))
        self.assertTrue(any(c['probability'] < .001 and any('distinct' in f['name'] for f in c['features']) for c in graph['comparisons']))

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
