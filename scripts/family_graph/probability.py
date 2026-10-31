"""Explicit, uncalibrated log-odds model shared by all source identities.

Positive features are capped by evidence category, not multiplied by the number
of copies of a fact. Source factors are never inferred from catalogue quality.
"""

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date
from itertools import combinations
from functools import lru_cache
import math
import re

from place_names import resolve_place_names
from .dates import death_interval
from .names import normalize
from .scoring import place_patterns

DEFAULTS = {
    'model': 'weighted-log-odds-v3', 'calibrated': False,
    'priorProbability': 0.05, 'mergeProbability': 0.8,
    'ambiguityLogOddsMargin': 1.0, 'clusterMinimumProbability': 0.35,
    'guessWeight': 0.45,
    'sourceWeights': {'documents': 1.0, 'images': 1.0, 'books': 0.5, 'notes': 0.5},
    'adultAgeYears': 16.0, 'maxAgeYears': 80.0, 'ageComfortYears': 60.0, 'ageScaleYears': 10.0,
    'titleWeights': {'office': 8.0, 'designation': 6.0, 'age': 3.0, 'territory': 3.0, 'rank': 0.75, 'other': 1.0},
    'titleHalfLivesYears': {'office': 15.0, 'designation': 30.0, 'age': 12.0, 'territory': 15.0, 'rank': 20.0, 'other': 15.0},
    'placeWeights': {'issuance': 2.0, 'property': 4.0, 'context': 2.5}, 'placeHalfLifeYears': 20.0,
    'crossRolePlaceFactor': 0.5,
    'associateWeight': 2.0, 'associateMaxWeight': 4.0, 'associateHalfLifeYears': 15.0,
    'familyWeights': {'anchored': 9.0, 'linked': 7.5, 'name': 4.0, 'spouse': 9.0},
    'familyRelationFactors': {'parent': 1.0, 'spouse': 1.0, 'sibling': 0.8, 'kin': 0.5},
    'sharedRelativeWeight': 12.0, 'familyMaxWeight': 16.0, 'familyHalfLifeYears': 35.0,
    'relativeRarityWeight': 1.0, 'relativeRarityMaxWeight': 1.5, 'relativeRarityReferenceFrequency': 0.1,
    'opposedAgePenalty': 5.0, 'rankRegressionPenalty': 1.0,
    'deathConflictPenalty': 20.0, 'maxRounds': 12,
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
    if result['crossRolePlaceFactor'] > 1 or result['relativeRarityReferenceFrequency'] >= 1:
        raise ValueError('matching: invalid cross-role factor or rarity reference frequency')
    if any(value > 1 for value in result['familyRelationFactors'].values()):
        raise ValueError('matching.familyRelationFactors: expected values not above one')
    if not result['adultAgeYears'] < result['ageComfortYears'] < result['maxAgeYears']:
        raise ValueError('matching: expected adult age < comfortable age < maximum age')
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


YEAR = 365.2425


def adult(mention, names=None):
    kind = mention.assertion.original['type']
    if kind == 'spouse' or kind == 'parent' and mention.field == 'person':
        return True
    return any(title_category(title, names)[0] in {'rank', 'office'} or title_category(title, names) == ('age', 'elder') for title in mention.titles)


def chronology(mentions, settings, names=None):
    """Extremes per reliability level; an unmarked typed mention means alive."""
    levels = {}
    def keep(level, key, value, source, larger):
        current = level.get(key)
        if current is None or (value > current[0] if larger else value < current[0]):
            level[key] = value, source
    for mention in mentions:
        if mention.field == 'text':
            continue
        source, (start, end) = mention.assertion.source, mention.assertion.bounds
        level = levels.setdefault(reliability(source, settings), {})
        keep(level, 'birth', end.toordinal() - (settings['adultAgeYears'] * YEAR if adult(mention, names) else 0), source, False)
        died = death_interval(mention)
        if died:
            keep(level, 'deathStart', died[0].toordinal(), source, True)
            keep(level, 'deathEnd', died[1].toordinal(), source, False)
            if mention.assertion.original.get('diedOn'):
                keep(level, 'last', died[0].toordinal(), source, True)
        elif mention.assertion.original['type'] != 'death':
            keep(level, 'alive', start.toordinal(), source, True)
            keep(level, 'last', start.toordinal(), source, True)
    return levels


def merge_chronology(*summaries):
    result = {}
    for summary in summaries:
        for value, level in summary.items():
            target = result.setdefault(value, {})
            for key, item in level.items():
                larger = key in {'deathStart', 'alive', 'last'}
                if key not in target or (item[0] > target[key][0] if larger else item[0] < target[key][0]):
                    target[key] = item
    return result


def cumulative(summary, threshold):
    return merge_chronology(*({0: level} for value, level in summary.items() if value >= threshold)).get(0, {})


def age_penalty(summary, settings):
    """Strongest age penalty over reliability levels: (contribution, minimum age, year, sources, blocked)."""
    worst = 0, None, None, (), False
    for value in sorted(summary, reverse=True):
        level = cumulative(summary, value)
        if 'birth' not in level or 'last' not in level:
            continue
        age = (level['last'][0] - level['birth'][0]) / YEAR
        impossible = age > settings['maxAgeYears']
        penalty = settings['deathConflictPenalty'] if impossible else max(0, age - settings['ageComfortYears']) / settings['ageScaleYears']
        result = penalty * value, age, date.fromordinal(level['last'][0]).year, (level['birth'][1], level['last'][1]), impossible and value == 1
        if result[4] or result[0] > worst[0] and not worst[4]:
            worst = result
    return worst


def death_conflicts(left, right, settings):
    """Conflicts between two sides only: (penalty, label, sources, blocked)."""
    worst = 0, '', (), False
    for a, first in left.items():
        for b, second in right.items():
            weight = min(a, b)
            for one, other in ((first, second), (second, first)):
                checks = [('mention after recorded death', 'alive', 'deathEnd'), ('incompatible death dates', 'deathStart', 'deathEnd')]
                for label, late, bound in checks:
                    if late in one and bound in other and one[late][0] > other[bound][0]:
                        result = settings['deathConflictPenalty'] * weight, label, (one[late][1], other[bound][1]), weight == 1
                        if result[3] or result[0] > worst[0] and not worst[3]:
                            worst = result
    return worst


def chronology_blocked(mentions, settings, names=None):
    """Document facts alone make this identity chronologically impossible."""
    level = chronology(mentions, settings, names).get(1, {})
    if 'deathEnd' in level and any(key in level and level[key][0] > level['deathEnd'][0] for key in ('alive', 'deathStart')):
        return True
    return 'birth' in level and 'last' in level and (level['last'][0] - level['birth'][0]) / YEAR > settings['maxAgeYears']


OFFICES = {'vogt', 'amtmann', 'hofmeister', 'burggraf', 'domherr', 'vizedom', 'komtur', 'keller', 'schultheiss'}
DESIGNATED = r'(?:called|born|genannt|gennant|genant|gen|dictus|dicti|dicta|geboren|geborene|geb|nee|nata)'
CONNECTOR = r'(?:von|vom|van|de|zu|ze|zum|zur|in|of|at)'


def title_category(title, names=None):
    """Meaning of a title; equivalents come from data/titles.md and places.json."""
    value = normalize(title)
    translate = (lambda text: names.titles.get(text, text)) if names else (lambda text: text)
    place = (lambda text: names.places.get(text, text)) if names else (lambda text: text)
    value = translate(value)
    if value in {'der junge', 'der jungere', 'der alte', 'der altere'}:
        return 'age', 'young' if 'jung' in value else 'elder'
    if value in {'ritter', 'miles', 'edelknecht', 'knecht', 'armiger'}:
        return 'rank', 'ritter' if value in {'ritter', 'miles'} else 'edelknecht'
    words = value.split()
    for index, word in enumerate(words[:-1]):
        office = translate(word)
        if office in OFFICES:
            # The connector (zu, in, von …) does not change the office.
            rest = re.sub(rf'^{CONNECTOR}\s+', '', ' '.join(words[index + 1:]))
            return 'office', f'{office} {place(rest)}'
    designated = re.match(rf'^(?:{DESIGNATED}\s+)?(?:{CONNECTOR}\s+(?:und\s+{CONNECTOR}\s+)?)?(.+)$', value)
    if designated and designated.group(1) != value:
        # genannt X, called von X, von X and zu X name the same designation.
        return 'designation', place(designated.group(1))
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
    office_scopes: dict = field(default_factory=dict)
    designation_places: dict = field(default_factory=dict)


# Deliberately deterministic; no extraction of relationships from prose.
PERSON_NAME = re.compile(r'\b[A-ZÄÖÜ][\wÄÖÜäöüß’\'-]*(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß’\'-]*)?\s+von\s+[A-ZÄÖÜ][\wÄÖÜäöüß’\'-]*')


class ProbabilityModel:
    def __init__(self, settings, names):
        self.settings, self.names = parameters(settings), names
        self.patterns = place_patterns(resolve_place_names(names.raw_places))
        self.background = {'total': 0.0, 'counts': {}}

    def set_name_frequencies(self, assertions, observations, registry):
        counts = {}
        for assertion in assertions:
            if assertion.source.kind != 'facts':
                continue
            found = {self.names.key(registry[m.reference]['name'] if m.reference in registry else m.reference) for m in assertion.mentions}
            for name in found:
                if len(name.split()) >= 2:
                    counts[name] = counts.get(name, 0) + reliability(assertion.source, self.settings)
        for observation in observations:
            if observation.source.kind != 'facts':
                continue
            found = self.person_names(observation.text)
            found |= {self.names.key(person['name']) for identity, person in registry.items() if '[' + identity + ']' in observation.text}
            for name in found:
                if len(name.split()) >= 2:
                    counts[name] = counts.get(name, 0) + reliability(observation.source, self.settings)
        self.background = {'total': round(sum(counts.values()), 8), 'counts': {name: round(counts[name], 8) for name in sorted(counts)}}

    def relative_rarity(self, name):
        if self.background['total'] <= 0 or len(name.split()) < 2:
            return 0, 0
        # Add-one smoothing and a cap prevent a rare typo from becoming an
        # overwhelming discriminator. Counts are factual and frozen per build.
        frequency = (self.background['counts'].get(name, 0) + 1) / (self.background['total'] + 1)
        value = max(0, math.log(self.settings['relativeRarityReferenceFrequency'] / frequency))
        return min(self.settings['relativeRarityMaxWeight'], self.settings['relativeRarityWeight'] * value), frequency

    @lru_cache(maxsize=None)
    def person_references(self, text):
        result = set()
        for match in PERSON_NAME.finditer(text):
            value = match.group()
            first = value.split()[0].casefold()
            if first in {'the', 'a', 'an', 'family', 'familie'}:
                continue
            prefixes = {'herr', 'frau', 'graf', 'count', 'sir', 'ritter', 'freiherr', 'markgraf', 'pfalzgraf', 'archbishop', 'bishop', 'erzbischof', 'bischof'}
            if first in prefixes and len(value.split()) <= 3:
                continue
            if first in prefixes:
                value = value.split(' ', 1)[1]
            result.add(value)
        return frozenset(result)

    @lru_cache(maxsize=None)
    def person_names(self, text):
        return frozenset(self.names.key(value) for value in self.person_references(text))

    @lru_cache(maxsize=None)
    def places(self, text):
        if not isinstance(text, str):
            return frozenset()
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
        return frozenset(result)

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

        blocks = []
        # Time distance alone is neutral; only the years a merge adds to the
        # minimum implied age count, and only beyond a comfortable age.
        own = chronology(left.mentions, p, self.names), chronology(right.mentions, p, self.names)
        value, age, year, sources, blocked = age_penalty(merge_chronology(*own), p)
        if blocked:
            blocks.append(f'impossible age: at least {age:.0f} years old by {year}')
        else:
            value -= max(age_penalty(summary, p)[0] for summary in own)
            if value > 0:
                add(f'age: at least {age:.0f} years old by {year}', -value, sources)
        value, label, sources, blocked = death_conflicts(*own, p)
        if blocked:
            blocks.append(label)
        elif value:
            add(label, -value, sources)

        by_category = {}
        for key in sorted(set(left.titles) & set(right.titles)):
            category, title = key
            value, sources = best(left.titles[key], right.titles[key], p['titleWeights'][category], p['titleHalfLivesYears'][category])
            if value > by_category.get(category, (0, '', ()))[0]:
                by_category[category] = value, title, sources
        for category, (value, title, sources) in sorted(by_category.items()):
            add(f'{category} title: {title}', value, sources)
        # Different offices, or an office and a bare place designation, can
        # share a place. It is weaker than an exact match and counts once.
        if 'office' not in by_category and 'designation' not in by_category:
            territory = p['titleWeights']['territory'], p['titleHalfLivesYears']['territory']
            scope_values = [(*best(left.office_scopes[place], right.office_scopes[place], *territory), 'shared office scope', place)
                            for place in sorted(set(left.office_scopes) & set(right.office_scopes))]
            scope_values += [(*best(one.office_scopes[place], other.designation_places[place], *territory), 'office and designation place', place)
                             for one, other in ((left, right), (right, left))
                             for place in sorted(set(one.office_scopes) & set(other.designation_places))]
            if scope_values:
                value, sources, label, place = max(scope_values, key=lambda item: (item[0], item[2], item[3]))
                add(f'{label}: {place}', value, sources)
        # Younger → elder and Edelknecht → Ritter are normal progressions;
        # only the reverse order counts against identity.
        def regression(earlier, later, weight):
            choices = [weight * min(reliability(x, p), reliability(y, p)) for profile, other in ((left, right), (right, left))
                       for x, dx in profile.titles.get(earlier, []) for y, dy in other.titles.get(later, []) if dx[1] < dy[0]]
            return max(choices, default=0)
        add('elder title before younger title', -regression(('age', 'elder'), ('age', 'young'), p['opposedAgePenalty']))
        add('Ritter before Edelknecht', -regression(('rank', 'ritter'), ('rank', 'edelknecht'), p['rankRegressionPenalty']))

        # One strongest observation per place; distinct place roles are not
        # independent evidence about the same geographical association.
        place_values = {}
        for (left_role, place), a in sorted(left.places.items()):
            for (right_role, other_place), b in sorted(right.places.items()):
                if place != other_place:
                    continue
                weight = min(p['placeWeights'][left_role], p['placeWeights'][right_role])
                if left_role != right_role:
                    weight *= p['crossRolePlaceFactor']
                value, sources = best(a, b, weight, p['placeHalfLifeYears'])
                role = left_role if left_role == right_role else '/'.join(sorted((left_role, right_role)))
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
            relation = 'spouse' if role[0] == 'family context' else role[0]
            # An unresolved spouse pairs two families' names and is more
            # distinctive than a relative's name repeated across generations.
            weight = p['familyWeights']['anchored' if grounded else 'linked' if identity else 'spouse' if relation == 'spouse' else 'name']
            weight *= p['familyRelationFactors'][relation]
            # Same-named siblings, parents, children, or spouses of one
            # identified person are rarely different people.
            if relation in {'sibling', 'parent', 'spouse'} and identity:
                weight = max(weight, p['sharedRelativeWeight'])
            # A bare given name alone cannot bootstrap two provisional families.
            if not identity and len(relative_name.split()) < 2:
                continue
            value, sources = best(left.relatives[token], right.relatives[token], weight * confidence, p['familyHalfLifeYears'])
            rarity, frequency = self.relative_rarity(relative_name)
            bonus, _ = best(left.relatives[token], right.relatives[token], rarity * confidence, p['familyHalfLifeYears'])
            if value + bonus > relatives.get(key, (0, '', (), 0, 0, 0))[0]:
                label = 'shared family context' if role[0] == 'family context' else f'{role[0]} family context'
                relatives[key] = value + bonus, f'{label}: {relative_name}', sources, value, bonus, frequency
        remaining = p['familyMaxWeight']
        for _, label, sources, value, bonus, frequency in sorted(relatives.values(), key=lambda item: (-item[0], item[1])):
            value = min(value, remaining)
            add(label, value, sources)
            remaining -= value
            bonus = min(bonus, remaining)
            add(f'full relative name rarity: {label.split(": ", 1)[1]} ({frequency:.2%} of factual references)', bonus, sources)
            remaining -= bonus

        if left.distinctions.get(right.key) or right.distinctions.get(left.key):
            blocks.append('explicitly distinct relationship participants')
        prior = math.log(p['priorProbability'] / (1 - p['priorProbability']))
        log_odds = prior + sum(feature['contribution'] for feature in features)
        probability = 1 / (1 + math.exp(-max(-700, min(700, log_odds))))
        return {'probability': round(probability, 8), 'logOdds': round(log_odds, 8),
                'features': features, 'sources': [refs[key] for key in sorted(refs)],
                'blocks': blocks,
                # Name/age-only candidates are not worth persisting.
                'substantive': any(f['contribution'] > 0 or 'death' in f['name'] for f in features)
                               or any(not block.startswith('impossible age') for block in blocks)}
