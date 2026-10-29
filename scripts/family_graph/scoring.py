"""Explainable comparisons against profiles grounded in exact source IDs."""

from collections import defaultdict
import re
from place_names import resolve_place_names
from .dates import compatible_deaths, date_bounds, near
from .model import Candidate, registry_keys
from .policy import title_class


def passage(mention):
    return mention.assertion.source.key.rsplit('/' + mention.assertion.source.kind + '/', 1)[0]


def place_patterns(places):
    patterns = defaultdict(set)
    for index, place in enumerate(places):
        key = place.get('id') or f'@place/{index}'
        for name in place.get('variations', []):
            patterns[name].add(key)
    return [(re.compile(r'(?<![^\W_])' + re.escape(name).replace(r',\ ', r'\s*,\s*').replace(r'\ ', r'\s+') + r'(?![^\W_])', re.I), keys)
            for name, keys in patterns.items()]


def places_for(mention, patterns):
    # Do not turn surname geography or the place in an office title into a
    # second feature. Issuance and unclassified death circumstances stay apart.
    assertion = mention.assertion
    result = set()
    for role, text in (
        ('issuance', assertion.context.get('place', '')),
        ('death-context', assertion.original.get('circumstances', '')),
    ):
        if not isinstance(text, str) or not text:
            continue
        matches = defaultdict(set)
        for pattern, keys in patterns:
            for match in pattern.finditer(text):
                matches[match.span()].update(keys)
        selected = []
        for (start, end), keys in sorted(matches.items(), key=lambda item: (-(item[0][1] - item[0][0]), item[0][0])):
            if any(start < right and end > left for left, right in selected):
                continue
            selected.append((start, end))
            # Keep ambiguous alternatives out of scoring. Selecting the first
            # Essingen or same-name site would manufacture contextual support.
            if len(keys) == 1:
                result.add((role, next(iter(keys))))
    return result


def anchor_profiles(assertions, people):
    registry = dict(zip(registry_keys(people), people))
    ids = {person['id'] for person in people if person.get('id')}
    profiles = defaultdict(list)
    for assertion in assertions:
        for mention in assertion.mentions:
            if mention.reference in ids:
                profiles[mention.reference].append(mention)
    return registry, profiles


def make_candidates(assertions, people, names, rules):
    registry, profiles = anchor_profiles(assertions, people)
    ids = {person['id']: person['id'] for person in people if person.get('id')}
    source_refs = {assertion.source.key: assertion for assertion in assertions}
    places = resolve_place_names(names.raw_places)
    patterns = place_patterns(places)
    place_cache = {}
    def mention_places(mention):
        key = mention.handle
        if key not in place_cache:
            place_cache[key] = places_for(mention, patterns)
        return place_cache[key]
    result = {}
    for assertion in assertions:
        for mention in assertion.mentions:
            if mention.reference in ids:
                continue
            candidates = []
            compatible = {key: person for key, person in registry.items() if names.key(person['name']) == names.key(mention.reference)}
            matching_rules = []
            for rule in rules:
                basis = source_refs.get(rule.path + '#' + rule.pointer)
                if (rule.target in ids and basis and basis.source.kind == 'facts'
                    and basis.original.get('person') == rule.target
                    and rule.title in basis.original.get('personTitle', [])
                    and names.key(rule.name) == names.key(mention.reference)
                    and rule.title in mention.titles
                    and date_bounds(rule.start)[0] <= assertion.bounds[0]
                    and assertion.bounds[1] <= date_bounds(rule.end)[1]):
                    matching_rules.append((rule, basis.source))
            for identity in compatible:
                candidate = Candidate(identity)
                for rule, ref in matching_rules:
                    candidate.sources.append(ref)
                    if identity == rule.target:
                        candidate.features.append({'name': 'reviewed office rule within scope', 'score': 20})
                        candidate.reviewed = True
                    else:
                        candidate.exclusions.append('reviewed identifying designation selects a distinct anchor')
                observations = profiles[identity]
                if not compatible_deaths([*observations, mention]):
                    candidate.exclusions.append('no compatible death chronology')
                    candidate.sources.extend(observation.assertion.source for observation in observations)
                seen_features = set()
                for observation in observations:
                    other_assertion = observation.assertion
                    if passage(mention) == passage(observation) or assertion.event_key == other_assertion.event_key:
                        continue
                    if near(assertion.bounds, other_assertion.bounds):
                        for title in set(mention.titles) & set(observation.titles):
                            category = title_class(title)
                            weight = {'age': 1.5, 'territory': 1, 'rank': .25}.get(category, 0)
                            feature_key = ('title', title)
                            if weight and feature_key not in seen_features:
                                seen_features.add(feature_key)
                                candidate.features.append({'name': f'{category} title: {title}', 'score': weight})
                                candidate.sources.append(other_assertion.source)
                        overlap = mention_places(mention) & mention_places(observation)
                        for role, place in sorted(overlap):
                            feature_key = ('place', role, place)
                            if feature_key not in seen_features:
                                seen_features.add(feature_key)
                                frequency = sum(any((role, place) in mention_places(item) for item in profiles[key]) for key in compatible)
                                candidate.features.append({'name': f'{role} overlap: {place}', 'score': 1 / max(1, frequency)})
                                candidate.sources.append(other_assertion.source)
                    # The other relative must already be explicitly grounded.
                    # Never use an inferred endpoint to corroborate its own edge.
                    if assertion.original['type'] not in {'parent', 'spouse', 'sibling', 'kin'}:
                        continue
                    other_field = 'of' if mention.field == 'person' else 'person'
                    relative = assertion.original.get(other_field)
                    if relative not in ids or other_assertion.original['type'] != assertion.original['type']:
                        continue
                    if assertion.original['type'] == 'parent' and observation.field != mention.field:
                        continue
                    if assertion.original.get('term') != other_assertion.original.get('term'):
                        continue
                    other_relative = other_assertion.original.get('of' if observation.field == 'person' else 'person')
                    feature_key = ('relative', assertion.original['type'], relative, mention.field if assertion.original['type'] == 'parent' else '')
                    if other_relative == relative and relative != identity and feature_key not in seen_features:
                        seen_features.add(feature_key)
                        candidate.features.append({'name': f'independently anchored {assertion.original["type"]} context: {relative}', 'score': 8})
                        candidate.sources.append(other_assertion.source)
                candidates.append(candidate)
            # Every occurrence also has a provisional alternative. This is a
            # candidate group for inspection, never automatic name clustering.
            provisional = Candidate(mention.handle)
            provisional.features.append({'name': 'unresolved / possibly another person', 'score': 0})
            candidates.append(provisional)
            result[mention.handle] = sorted(candidates, key=lambda item: (-item.score, item.identity))
    return registry, profiles, result
