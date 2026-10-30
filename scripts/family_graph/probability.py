"""Explicit, uncalibrated log-odds model shared by all source identities.

Positive features are capped by evidence category, not multiplied by the number
of copies of a fact. Source factors are never inferred from catalogue quality.
"""

from copy import deepcopy
from dataclasses import dataclass, field
from itertools import combinations
from functools import lru_cache
import math
import re

from place_names import resolve_place_names
from .dates import death_interval
from .names import normalize
from .scoring import place_patterns

DEFAULTS = {
    'model': 'weighted-log-odds-v1', 'calibrated': False,
    'priorProbability': 0.05, 'mergeProbability': 0.85,
    'ambiguityLogOddsMargin': 1.0, 'clusterMinimumProbability': 0.35,
    'guessWeight': 0.45,
    'sourceWeights': {'documents': 1.0, 'images': 1.0, 'books': 0.5, 'notes': 0.5},
    'timeDistanceScaleYears': 35.0, 'clusterSpanStartYears': 60.0, 'clusterSpanScaleYears': 20.0,
    'titleWeights': {'office': 8.0, 'designation': 6.0, 'age': 3.0, 'territory': 3.0, 'rank': 0.75, 'other': 1.0},
    'titleHalfLivesYears': {'office': 15.0, 'designation': 30.0, 'age': 12.0, 'territory': 15.0, 'rank': 20.0, 'other': 15.0},
    'placeWeights': {'issuance': 2.0, 'property': 4.0, 'context': 2.5}, 'placeHalfLifeYears': 20.0,
    'associateWeight': 2.0, 'associateMaxWeight': 4.0, 'associateHalfLifeYears': 15.0,
    'familyWeights': {'anchored': 9.0, 'linked': 7.5, 'name': 4.0, 'spouse': 9.0}, 'familyMaxWeight': 16.0,
    'opposedAgePenalty': 5.0, 'opposedAgeHalfLifeYears': 10.0,
    'deathConflictPenalty': 20.0, 'distinctPenalty': 20.0, 'maxRounds': 12,
}


def parameters(value=None):
    result = deepcopy(DEFAULTS if value is None else value)
    def validate(actual, expected, path='matching'):
        if isinstance(expected, dict):
            if not isinstance(actual, dict) or set(actual) != set(expected):
                raise ValueError(f'{path}: unexpected or missing probability parameters')
            for key in expected:
                validate(actual[key], expected[key], f'{path}.{key}')
        elif type(expected) in (int, float):
            if type(actual) not in (int, float) or not math.isfinite(actual) or actual <= 0:
                raise ValueError(f'{path}: expected a positive finite number')
        elif actual != expected or type(actual) is not type(expected):
            raise ValueError(f'{path}: unsupported model setting')
    validate(result, DEFAULTS)
    for key in ('priorProbability', 'mergeProbability', 'clusterMinimumProbability', 'guessWeight'):
        if not 0 < result[key] < 1:
            raise ValueError(f'matching.{key}: expected a value between zero and one')
    if result['priorProbability'] >= result['mergeProbability'] or type(result['maxRounds']) is not int:
        raise ValueError('matching: invalid prior, threshold, or iteration bound')
    if result['sourceWeights'] != DEFAULTS['sourceWeights']:
        raise ValueError('matching.sourceWeights: documents/images require 1.0; books/notes require 0.5')
    return result


def reliability(ref, settings):
    category = ref.path.split('/')[1]
    return settings['sourceWeights'][category] * (settings['guessWeight'] if ref.kind == 'guesses' else 1.0)


def gap_years(left, right):
    return max(0, (max(left[0], right[0]) - min(left[1], right[1])).days) / 365.2425


def decay(left, right, half_life):
    return 2 ** (-gap_years(left, right) / half_life)


def title_category(title):
    value = normalize(title)
    if value in {'der junge', 'der jungere', 'der alte', 'der altere'}:
        return 'age', 'young' if 'jung' in value else 'elder'
    if re.match(r'^(called|born|genannt|dictus|geboren|geborene|nee|nata)\b', value):
        return 'designation', value
    if value in {'ritter', 'miles', 'edelknecht', 'knecht', 'armiger'}:
        return 'rank', 'ritter' if value in {'ritter', 'miles'} else 'edelknecht'
    if value.startswith('zu '):
        return 'territory', value
    if re.match(r'^(vogt|amtmann|hofmeister|burggraf|domherr|vizedom|vitztum|komtur)\s+\S', value):
        return 'office', value
    return 'other', value


@dataclass
class Observation:
    source: object
    text: str
    historical_date: str
    bounds: tuple | None
    context: dict


@dataclass
class Profile:
    handles: list
    mentions: list
    refs: dict = field(default_factory=dict)
    titles: dict = field(default_factory=dict)
    places: dict = field(default_factory=dict)
    associates: dict = field(default_factory=dict)
    relatives: dict = field(default_factory=dict)
    anchored: bool = False
    confidence: float = 1.0
    key: str = ''
    distinctions: dict = field(default_factory=dict)


# Deliberately deterministic; no extraction of relationships from prose.
PERSON_NAME = re.compile(r'\b[A-ZÄÖÜ][\wÄÖÜäöüß’\'-]*(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß’\'-]*)?\s+von\s+[A-ZÄÖÜ][\wÄÖÜäöüß’\'-]*')


class ProbabilityModel:
    def __init__(self, settings, names):
        self.settings, self.names = parameters(settings), names
        self.patterns = place_patterns(resolve_place_names(names.raw_places))

    @lru_cache(maxsize=None)
    def person_names(self, text):
        return {self.names.key(match.group()) for match in PERSON_NAME.finditer(text)}

    @lru_cache(maxsize=None)
    def places(self, text):
        if not isinstance(text, str):
            return set()
        matches = {}
        for pattern, keys in self.patterns:
            for match in pattern.finditer(text):
                matches.setdefault(match.span(), set()).update(keys)
        selected, result = [], set()
        for (start, end), keys in sorted(matches.items(), key=lambda pair: (-(pair[0][1] - pair[0][0]), pair[0])):
            if any(start < right and end > left for left, right in selected):
                continue
            selected.append((start, end))
            if len(keys) == 1:
                result.update(keys)
        return result

    def add_context(self, profile, source, bounds, text='', issuance='', self_names=()):
        if bounds is None:
            return
        evidence = (source, bounds)
        profile.refs[source.key] = source
        for place in self.places(issuance):
            profile.places.setdefault(('issuance', place), []).append(evidence)
        # Strip personal names before place matching: a surname is not residence.
        remaining = PERSON_NAME.sub('', text)
        role = 'property' if re.search(r'\b(property|properties|estate|estates|fief|held|holds|sold|owned|goods|rent|inherit\w*)\b', remaining, re.I) else 'context'
        for place in self.places(remaining):
            profile.places.setdefault((role, place), []).append(evidence)
        for name in self.person_names(text) - set(self_names):
            profile.associates.setdefault(name, []).append(evidence)

    def compare(self, left, right):
        p = self.settings
        features, refs = [], {**left.refs, **right.refs}
        def add(name, contribution, sources=()):
            if not contribution:
                return
            features.append({'name': name, 'contribution': round(contribution, 8)})
            refs.update({source.key: source for source in sources})
        def best(a, b, weight, half_life):
            choices = [(weight * min(reliability(x, p), reliability(y, p)) * decay(dx, dy, half_life), (x, y))
                       for x, dx in a for y, dy in b]
            return max(choices, key=lambda choice: choice[0], default=(0, ()))

        # Date distance is a prior adjustment, not an invented age estimate.
        pairs = [(gap_years(a.assertion.bounds, b.assertion.bounds), a, b) for a in left.mentions for b in right.mentions]
        distance, first, second = min(pairs, key=lambda item: (item[0], item[1].handle, item[2].handle))
        add('document time distance', -distance / p['timeDistanceScaleYears'], [first.assertion.source, second.assertion.source])
        dates = [m.assertion.bounds for m in left.mentions + right.mentions]
        span = (max(d[1] for d in dates) - min(d[0] for d in dates)).days / 365.2425
        add('combined attestation time span', -max(0, span - p['clusterSpanStartYears']) / p['clusterSpanScaleYears'])

        by_category = {}
        for key in sorted(set(left.titles) & set(right.titles)):
            category, title = key
            value, sources = best(left.titles[key], right.titles[key], p['titleWeights'][category], p['titleHalfLivesYears'][category])
            if value > by_category.get(category, (0, '', ()))[0]:
                by_category[category] = value, title, sources
        for category, (value, title, sources) in sorted(by_category.items()):
            add(f'{category} title: {title}', value, sources)
        for a, b in (('young', 'elder'), ('elder', 'young')):
            value, sources = best(left.titles.get(('age', a), []), right.titles.get(('age', b), []),
                                  p['opposedAgePenalty'], p['opposedAgeHalfLifeYears'])
            add('opposed age titles', -value, sources)

        # One strongest observation per place; distinct place roles are not
        # independent evidence about the same geographical association.
        place_values = {}
        for role, place in sorted(set(left.places) & set(right.places)):
            value, sources = best(left.places[(role, place)], right.places[(role, place)], p['placeWeights'][role], p['placeHalfLifeYears'])
            if value > place_values.get(place, (0, '', ()))[0]:
                place_values[place] = value, role, sources
        for place, (value, role, sources) in sorted(place_values.items()):
            add(f'{role} place: {place}', value, sources)

        associate_values = []
        for name in sorted(set(left.associates) & set(right.associates)):
            value, sources = best(left.associates[name], right.associates[name], p['associateWeight'], p['associateHalfLifeYears'])
            associate_values.append((value, name, sources))
        remaining = p['associateMaxWeight']
        for value, name, sources in sorted(associate_values, key=lambda item: (-item[0], item[1])):
            value = min(value, remaining)
            add(f'same-fact associate: {name}', value, sources)
            remaining -= value

        relatives = {}
        for token in sorted(set(left.relatives) & set(right.relatives), key=str):
            role, identity, relative_name, grounded, confidence = token
            key = relative_name
            weight = p['familyWeights']['anchored' if grounded else 'linked' if identity else 'spouse' if role[0] in {'spouse', 'family context'} else 'name']
            # A bare given name alone cannot bootstrap two provisional families.
            if not identity and len(relative_name.split()) < 2:
                continue
            value, sources = best(left.relatives[token], right.relatives[token], weight * confidence, p['timeDistanceScaleYears'])
            if value > relatives.get(key, (0, '', ()))[0]:
                relatives[key] = value, f'{role[0]} family context: {relative_name}', sources
        remaining = p['familyMaxWeight']
        for value, label, sources in sorted(relatives.values(), key=lambda item: (-item[0], item[1])):
            value = min(value, remaining)
            add(label, value, sources)
            remaining -= value

        # Conflicting guessed deaths are drastic negative evidence, not a hard
        # identity assertion. Ordinary late mentions do not prove life.
        death_values = []
        for a in left.mentions:
            for b in right.mentions:
                da, db = death_interval(a), death_interval(b)
                if da and db and max(da[0], db[0]) > min(da[1], db[1]):
                    death_values.append((p['deathConflictPenalty'] * min(reliability(a.assertion.source, p), reliability(b.assertion.source, p)),
                                         (a.assertion.source, b.assertion.source)))
        if death_values:
            value, sources = max(death_values, key=lambda item: item[0])
            add('conflicting death chronology', -value, sources)
        distinctions = [*left.distinctions.get(right.key, []), *right.distinctions.get(left.key, [])]
        if distinctions:
            source = max(distinctions, key=lambda ref: reliability(ref, p))
            add('explicitly distinct relationship participants', -p['distinctPenalty'] * reliability(source, p), [source])
        prior = math.log(p['priorProbability'] / (1 - p['priorProbability']))
        log_odds = prior + sum(feature['contribution'] for feature in features)
        probability = 1 / (1 + math.exp(-max(-700, min(700, log_odds))))
        return {'probability': round(probability, 8), 'logOdds': round(log_odds, 8),
                'features': features, 'sources': [refs[key] for key in sorted(refs)],
                'substantive': any(f['contribution'] > 0 or 'death' in f['name'] or 'distinct' in f['name'] for f in features)}
