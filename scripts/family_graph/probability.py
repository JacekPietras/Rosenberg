"""Explicit, uncalibrated log-odds model shared by all source identities.

Positive features are capped by evidence category, not multiplied by the number
of copies of a fact. Source factors are never inferred from catalogue quality.
"""

from copy import deepcopy
from dataclasses import dataclass, field, fields
from hashlib import blake2b
from datetime import date
from itertools import combinations
from functools import lru_cache
import math
import re

from .dates import death_interval
from .names import normalize
from .policy import AGE_TITLE_CLASSES

DEFAULTS = {
    'model': 'weighted-log-odds-v7', 'calibrated': False,
    'priorProbability': 0.1, 'mergeProbability': 0.7,
    'ambiguityLogOddsMargin': 1.0, 'clusterMinimumProbability': 0.35,
    'guessWeight': 0.45,
    'sourceWeights': {'documents': 1.0, 'images': 1.0, 'books': 0.5, 'notes': 0.5},
    'adultAgeYears': 16.0, 'maxAgeYears': 80.0, 'ageComfortYears': 60.0, 'ageScaleYears': 10.0,
    'titleWeights': {'office': 8.0, 'designation': 6.0, 'age': 3.0, 'territory': 3.0, 'rank': 0.75, 'other': 1.0},
    'titleHalfLivesYears': {'office': 15.0, 'designation': 30.0, 'age': 12.0, 'territory': 15.0, 'rank': 20.0, 'other': 15.0},
    'placeWeight': 2.0, 'placeHalfLifeYears': 20.0,
    'associateWeight': 2.0,
    'associateMaxWeight': 4.0, 'associateHalfLifeYears': 15.0,
    'familyWeights': {'anchored': 9.0, 'linked': 7.5, 'name': 4.0, 'spouse': 9.0},
    'familyRelationFactors': {'parent': 1.0, 'spouse': 1.0, 'sibling': 0.8, 'kin': 0.5},
    'sharedRelativeWeight': 12.0, 'familyMaxWeight': 16.0, 'familyHalfLifeYears': 35.0,
    'relativeRarityWeight': 1.0, 'relativeRarityMaxWeight': 1.5, 'relativeRarityReferenceFrequency': 0.1,
    'opposedAgePenalty': 5.0, 'rankRegressionPenalty': 1.0,
    'deathConflictPenalty': 20.0, 'maxRounds': 12,
    'sameDateRankConflictPenalty': 3.0,
    'retrospectiveLookBackYears': 20.0, 'passageTitleAgreementWeight': 1.0,
    'posthumousBirthYears': 1.0,
    'possibleSameDisplayProbability': 0.5,
    'bestCandidate': {'maxLivingSpanYears': 64.0, 'attachmentTieLogOdds': 0.25,
                      'minJoinEvidence': 0.5, 'maxRelativePathSteps': 6},
    'secondPass': {'maxPathSteps': 3,
                   'specificityFactors': {'exact': 1.0, 'narrow': 0.5, 'broad': 0.3},
                   'eliminationWeight': 1.5, 'ageTitleNamesakeWeight': 1.0,
                   'widowhoodNameWeight': 5.0},
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
    if result['relativeRarityReferenceFrequency'] >= 1:
        raise ValueError('matching: invalid rarity reference frequency')
    if any(value > 1 for value in result['familyRelationFactors'].values()):
        raise ValueError('matching.familyRelationFactors: expected values not above one')
    if not result['adultAgeYears'] < result['ageComfortYears'] < result['maxAgeYears']:
        raise ValueError('matching: expected adult age < comfortable age < maximum age')
    second = result['secondPass']
    if type(second['maxPathSteps']) is not int or type(result['bestCandidate']['maxRelativePathSteps']) is not int:
        raise ValueError('matching: invalid path length')
    if not 0 < result['possibleSameDisplayProbability'] < 1:
        raise ValueError('matching.possibleSameDisplayProbability: expected a value between zero and one')
    if any(value > 1 for value in second['specificityFactors'].values()):
        raise ValueError('matching.secondPass.specificityFactors: expected values not above one')
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
    return any(title_category(title, names)[0] in {'rank', 'office'} or title_category(title, names) == ('age', 'older') for title in mention.titles)


def names_relative(mention):
    """Being named as someone's parent or sibling says nothing about being alive then."""
    kind = mention.assertion.original['type']
    return kind == 'sibling' or kind == 'parent' and mention.field == 'person'


def chronology(mentions, settings, names=None, derived=()):
    """Extremes per reliability level; an unmarked typed mention means alive.

    `derived` adds latest-birth bounds implied by relatives: (level, ordinal, source)."""
    levels = {}
    def keep(level, key, value, source, larger):
        current = level.get(key)
        if current is None or (value > current[0] if larger else value < current[0]):
            level[key] = value, source
    # Alternative guessed death dates of one passage ("died 1383, 1387 or
    # 1388") are one uncertain death: the union of their intervals.
    alternatives = {}
    for mention in mentions:
        if mention.assertion.source.kind == 'guesses' and mention.assertion.original['type'] == 'death' and death_interval(mention):
            passage = mention.assertion.source.path, mention.assertion.source.pointer.rsplit('/guesses/', 1)[0], mention.reference
            died = death_interval(mention)
            low, high = alternatives.get(passage, died)
            alternatives[passage] = min(low, died[0]), max(high, died[1])
    for mention in mentions:
        if mention.field == 'text':
            continue
        source, (start, end) = mention.assertion.source, mention.assertion.bounds
        level = levels.setdefault(reliability(source, settings), {})
        keep(level, 'birth', end.toordinal() - (settings['adultAgeYears'] * YEAR if adult(mention, names) else 0), source, False)
        died = death_interval(mention)
        if died and mention.assertion.source.kind == 'guesses' and mention.assertion.original['type'] == 'death':
            died = alternatives[mention.assertion.source.path, mention.assertion.source.pointer.rsplit('/guesses/', 1)[0], mention.reference]
        if died:
            keep(level, 'deathStart', died[0].toordinal(), source, True)
            keep(level, 'deathEnd', died[1].toordinal(), source, False)
            if mention.assertion.original.get('diedOn'):
                keep(level, 'last', died[0].toordinal(), source, True)
        elif mention.assertion.original['type'] != 'death' and not names_relative(mention):
            keep(level, 'alive', start.toordinal(), source, True)
            keep(level, 'first', end.toordinal(), source, False)
            keep(level, 'last', start.toordinal(), source, True)
    for value, ordinal, source in derived:
        keep(levels.setdefault(value, {}), 'birth', ordinal, source, False)
    return levels


LATEST_KEYS = frozenset({'deathStart', 'alive', 'last'})


def merge_chronology(*summaries):
    result = {}
    for summary in summaries:
        for value, level in summary.items():
            target = result.setdefault(value, {})
            for key, item in level.items():
                if key not in target or (item[0] > target[key][0] if key in LATEST_KEYS else item[0] < target[key][0]):
                    target[key] = item
    return result


def cumulative(summary, threshold):
    result = {}
    for value, level in summary.items():
        if value >= threshold:
            for key, item in level.items():
                if key not in result or (item[0] > result[key][0] if key in LATEST_KEYS else item[0] < result[key][0]):
                    result[key] = item
    return result


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


KNIGHT, SQUIRE = frozenset({'ritter', 'miles'}), frozenset({'edelknecht', 'armiger'})


def mention_rank(mention):
    """Distinguishing rank of one occurrence; `Knecht` alone and mixed ranks give none."""
    titles = {normalize(title) for title in mention.titles}
    knight, squire = bool(titles & KNIGHT), bool(titles & SQUIRE)
    return 'ritter' if knight and not squire else 'edelknecht' if squire and not knight else None


def single_day(bounds):
    return bounds is not None and bounds[0] == bounds[1]


def living_span(mentions, settings, names=None):
    """Years between the first and last living mention, over all reliability levels."""
    level = cumulative(chronology(mentions, settings, names), 0)
    if 'first' not in level or 'alive' not in level:
        return 0
    return (level['alive'][0] - level['first'][0]) / YEAR


def child_age(summary, children, settings):
    """Strongest penalty from children born after this parent's death bound:
    (penalty, minimum child age, sources, impossible for any source, impossible for documents)."""
    worst = 0, 0, (), False, False
    for value, level in summary.items():
        if 'deathEnd' not in level:
            continue
        born = level['deathEnd'][0] + settings['posthumousBirthYears'] * YEAR
        for weight, last, source in children:
            age = (last - born) / YEAR
            impossible = age > settings['maxAgeYears']
            factor = min(value, weight)
            penalty = settings['deathConflictPenalty'] if impossible else max(0, age - settings['ageComfortYears']) / settings['ageScaleYears']
            result = penalty * factor, age, (level['deathEnd'][1], source), impossible, impossible and factor == 1
            if result[0] > worst[0] or result[3] and not worst[3]:
                worst = result
    return worst


def chronology_blocked(mentions, settings, names=None):
    """Document facts alone make this identity chronologically impossible."""
    level = chronology(mentions, settings, names).get(1, {})
    if 'deathEnd' in level and any(key in level and level[key][0] > level['deathEnd'][0] for key in ('alive', 'deathStart')):
        return True
    return 'birth' in level and 'last' in level and (level['last'][0] - level['birth'][0]) / YEAR > settings['maxAgeYears']


OFFICES = {'vogt', 'reichsvogt', 'amtmann', 'hofmeister', 'burggraf', 'domherr', 'vizedom', 'komtur', 'keller', 'schultheiss'}
DESIGNATED = r'(?:called|born|genannt|gennant|genant|gen|dictus|dicti|dicta|geboren|geborene|geb|nee|nata)'
CONNECTOR = r'(?:von|vom|van|de|zu|ze|zum|zur|in|of|at)'


@lru_cache(maxsize=32768)
def title_category(title, names=None):
    """Meaning of a title; equivalents come from data/titles-age.md, data/titles-office.md and places.json."""
    value = normalize(title)
    translate = (lambda text: names.titles.get(text, text)) if names else (lambda text: text)
    place = (lambda text: names.places.get(text, text)) if names else (lambda text: text)
    value = translate(value)
    # A Reichsvogt is a kind of Vogt. Keep its full title for display, but
    # compare scoped offices under the shared Vogt category.
    value = re.sub(r'\breichs\s+vogt\b|\breichsvogt\b', 'vogt', value)
    if value in AGE_TITLE_CLASSES:
        return 'age', AGE_TITLE_CLASSES[value]
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


CHURCH_HEADS = {'domherr', 'presbyter', 'bischof', 'furstbischof', 'erzbischof', 'abt', 'abtissin', 'domdekan', 'dompropst', 'propst', 'papst'}
ORDER_HEADS = {'deutschmeister', 'hochmeister'}
ORDER_WORDS = re.compile(r'(?<![nv])orden|johanniter|templer')
EXCLUDES = {'church': {'knight': 'knight', 'schultheiss': 'Schultheiß', 'king': 'king', 'spouse': 'spouse', 'children': 'children'},
            'order': {'spouse': 'spouse', 'children': 'children'}}
REASONS = {'church': 'church title', 'order': 'order member'}


@lru_cache(maxsize=32768)
def title_traits(title, names=None):
    """Church, order, knight, Schultheiß and king titles by head word; order members are not knights."""
    translate = (lambda text: names.titles.get(text, text)) if names else (lambda text: text)
    traits = set()
    for segment in re.split(r'\s+und\s+', normalize(title)):
        if names and segment in names.epithets:
            continue
        words = segment.split()
        head = translate(' '.join(words[:2])) if len(words) > 1 else ''
        if head not in CHURCH_HEADS | ORDER_HEADS:
            head = translate(words[0]) if words else ''
        if head in CHURCH_HEADS:
            traits.add('church')
        elif head in ORDER_HEADS or ORDER_WORDS.search(head) or head.endswith('ritter') and ORDER_WORDS.search(segment):
            traits.add('order')
        elif head.endswith('ritter'):
            traits.add('knight')
        elif head.endswith('schultheiss'):
            traits.add('schultheiss')
        elif head == 'konig':
            traits.add('king')
    return frozenset(traits)


def vow_conflict(left, right):
    """Reason a church-titled person or order member cannot be one person with the other, from trait sets."""
    for own, other in ((left, right), (right, left)):
        for kind, excluded in EXCLUDES.items():
            if kind in own:
                for trait, label in excluded.items():
                    if trait in other:
                        return f'{REASONS[kind]} with {label}'
    return None


@dataclass
class Observation:
    source: object
    text: str
    historical_date: str
    bounds: tuple | None
    context: dict
    people: tuple = ()
    places: tuple = ()


@dataclass
class Profile:
    handles: list
    mentions: list
    refs: dict = field(default_factory=dict)
    titles: dict = field(default_factory=dict)
    places: dict = field(default_factory=dict)
    associates: dict = field(default_factory=dict)
    relatives: dict = field(default_factory=dict)
    household: set = field(default_factory=set)
    anchored: bool = False
    confidence: float = 1.0
    key: str = ''
    distinctions: dict = field(default_factory=dict)
    # (rank, source, bounds, passage) for Ritter/miles versus Edelknecht/armiger.
    ranks: list = field(default_factory=list)
    # Latest-birth bounds from a parent's death: (reliability, ordinal, source).
    derived: list = field(default_factory=list)
    # Children's last living mentions: (reliability, ordinal, source).
    children: list = field(default_factory=list)


# Non-ASCII characters that a case-insensitive pattern can match to an ASCII letter.
class ProbabilityModel:
    def __init__(self, settings, names):
        self.settings, self.names = parameters(settings), names
        self.background = {'total': 0.0, 'counts': {}}
        self.compare_cache = {}

    def set_name_frequencies(self, assertions, observations, registry):
        counts, by_source, weights = {}, {}, {}
        for assertion in assertions:
            if assertion.source.kind != 'facts':
                continue
            found = {self.names.key(registry[m.reference]['name'] if m.reference in registry else m.reference) for m in assertion.mentions}
            by_source.setdefault(assertion.source.key, set()).update(found)
            weights[assertion.source.key] = reliability(assertion.source, self.settings)
        for observation in observations:
            if observation.source.kind not in {'facts', 'text'}:
                continue
            found = self.person_names(observation.people)
            by_source.setdefault(observation.source.key, set()).update(found)
            weights[observation.source.key] = reliability(observation.source, self.settings)
        # A generic fact supplies both its typed subject and textual context.
        # Count a name only once in that fact, regardless of its representations.
        for key, found in by_source.items():
            for name in found:
                if len(name.split()) >= 2:
                    counts[name] = counts.get(name, 0) + weights[key]
        self.background = {'total': round(sum(counts.values()), 8), 'counts': {name: round(counts[name], 8) for name in sorted(counts)}}
        self.compare_cache.clear()

    def relative_rarity(self, name):
        if self.background['total'] <= 0 or len(name.split()) < 2:
            return 0, 0
        # Add-one smoothing and a cap prevent a rare typo from becoming an
        # overwhelming discriminator. Counts are factual and frozen per build.
        frequency = (self.background['counts'].get(name, 0) + 1) / (self.background['total'] + 1)
        value = max(0, math.log(self.settings['relativeRarityReferenceFrequency'] / frequency))
        return min(self.settings['relativeRarityMaxWeight'], self.settings['relativeRarityWeight'] * value), frequency

    @lru_cache(maxsize=None)
    def person_names(self, people):
        return frozenset(self.names.key(value) for value in people)

    def add_context(self, profile, source, bounds, people=(), places=(), self_names=(), keys=()):
        if bounds is None:
            return
        evidence = (source, bounds)
        profile.refs[source.key] = source
        for place in places:
            profile.places.setdefault(('context', place), []).append(evidence)
        for name in (self.person_names(people) | set(keys)) - set(self_names):
            profile.associates.setdefault(name, []).append(evidence)

    def profile_age_penalty(self, profile):
        stamp = (len(profile.mentions), len(profile.derived))
        cached = profile.__dict__.get('_age_penalty')
        if cached is None or cached[0] != stamp:
            cached = profile.__dict__['_age_penalty'] = stamp, age_penalty(self.profile_chronology(profile), self.settings)[0]
        return cached[1]

    def profile_living(self, profile):
        """(first, last) living ordinals over all reliability levels, as `living_span` uses."""
        level = cumulative(self.profile_chronology(profile), 0)
        return (level['first'][0], level['alive'][0]) if 'first' in level and 'alive' in level else None

    def profile_traits(self, profile):
        stamp = len(profile.mentions), len(profile.household)
        cached = profile.__dict__.get('_traits')
        if cached is None or cached[0] != stamp:
            traits = set(profile.household).union(*(title_traits(title, self.names) for m in profile.mentions for title in m.titles))
            cached = profile.__dict__['_traits'] = stamp, traits
        return cached[1]

    def profile_chronology(self, profile, facts_only=False):
        stamp = (len(profile.mentions), len(profile.derived))
        slot = '_chronology_facts' if facts_only else '_chronology'
        cached = profile.__dict__.get(slot)
        if cached is None or cached[0] != stamp:
            if facts_only:
                value = chronology([m for m in profile.mentions if m.assertion.source.kind == 'facts'], self.settings, self.names)
            else:
                value = chronology(profile.mentions, self.settings, self.names, profile.derived)
            cached = profile.__dict__[slot] = stamp, value
        return cached[1]

    @staticmethod
    def signature(profile):
        """Digest of everything `compare` reads; the cached mentions keep their ids unique."""
        cached = profile.__dict__.get('_signature')
        if cached is None or cached[1] != len(profile.mentions):
            content = repr([getattr(profile, f.name) for f in fields(profile) if f.name != 'mentions'])
            content += repr([id(mention) for mention in profile.mentions])
            cached = profile.__dict__['_signature'] = blake2b(content.encode(), digest_size=16).digest(), len(profile.mentions), tuple(profile.mentions)
        return cached

    def compare(self, left, right):
        """Pure in the two profiles, so an unchanged pair keeps its earlier record."""
        one, other = self.signature(left), self.signature(right)
        key = left.key, right.key
        entry = self.compare_cache.get(key)
        if entry is None or entry[0] != one[0] or entry[1] != other[0]:
            entry = self.compare_cache[key] = one[0], other[0], one[2], other[2], self.compare_uncached(left, right)
        return {name: list(value) if isinstance(value, list) else value for name, value in entry[4].items()}

    def compare_uncached(self, left, right):
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

        blocks, hard = [], []
        # Time distance alone is neutral; only the years a merge adds to the
        # minimum implied age count, and only beyond a comfortable age.
        own = self.profile_chronology(left), self.profile_chronology(right)
        merged = merge_chronology(*own)
        value, age, year, sources, blocked = age_penalty(merged, p)
        if blocked:
            blocks.append(f'impossible age: at least {age:.0f} years old by {year}')
        else:
            value -= max(self.profile_age_penalty(left), self.profile_age_penalty(right))
            if value > 0:
                add(f'age: at least {age:.0f} years old by {year}', -value, sources)
        value, label, sources, blocked = death_conflicts(*own, p)
        if blocked:
            blocks.append(label)
        elif value:
            add(label, -value, sources)
        # A parent's death bounds each child's birth; a merge that moves the
        # death earlier ages the children (posthumousBirthYears allowance).
        children = [*left.children, *right.children]
        value, age, sources, impossible, documented = child_age(merged, children, p)
        if documented:
            blocks.append('child born after parent death')
        if impossible:
            hard.append('child born after parent death')
        elif value:
            value -= max(child_age(summary, children, p)[0] for summary in own)
            if value > 0:
                add(f'child at least {age:.0f} years old after parent death', -value, sources)
        # Joins without a probability threshold still respect impossibility:
        # any impossible age, death conflicts between facts, and too long a life.
        for level in sorted(merged):
            summary = cumulative(merged, level)
            if 'birth' in summary and 'last' in summary and (summary['last'][0] - summary['birth'][0]) / YEAR > p['maxAgeYears']:
                hard.append('impossible age')
                break
        factual = [self.profile_chronology(side, facts_only=True) for side in (left, right)]
        if death_conflicts(*factual, p)[0]:
            hard.append(death_conflicts(*factual, p)[1])
        living = [item for item in (self.profile_living(left), self.profile_living(right)) if item]
        span = (max(item[1] for item in living) - min(item[0] for item in living)) / YEAR if living else 0
        if span > p['bestCandidate']['maxLivingSpanYears']:
            hard.append(f'living mentions span {span:.0f} years')

        by_category = {}
        for key in sorted(set(left.titles) & set(right.titles)):
            category, title = key
            value, sources = best(left.titles[key], right.titles[key], p['titleWeights'][category], p['titleHalfLivesYears'][category])
            if value > by_category.get(category, (0, '', ()))[0]:
                by_category[category] = value, title, sources
        for category, (value, title, sources) in sorted(by_category.items()):
            add(f'{category} title: {title}', value, sources)
        # Younger → elder and Edelknecht → Ritter are normal progressions;
        # only the reverse order counts against identity.
        def regression(earlier, later, weight):
            choices = [weight * min(reliability(x, p), reliability(y, p)) for profile, other in ((left, right), (right, left))
                       for x, dx in profile.titles.get(earlier, []) for y, dy in other.titles.get(later, []) if dx[1] < dy[0]]
            return max(choices, default=0)
        add('elder title before younger title', -regression(('age', 'older'), ('age', 'younger'), p['opposedAgePenalty']))
        add('Ritter before Edelknecht', -regression(('rank', 'ritter'), ('rank', 'edelknecht'), p['rankRegressionPenalty']))
        # Ritter in one source and Edelknecht in another on the same day.
        conflicts = [(min(reliability(x, p), reliability(y, p)), (x, y))
                     for rank, x, dx, scope in left.ranks for other, y, dy, other_scope in right.ranks
                     if rank != other and scope != other_scope and single_day(dx) and dx == dy]
        if conflicts:
            weight, sources = max(conflicts, key=lambda item: item[0])
            if weight == 1:
                blocks.append('same-date opposite ranks in two documents')
            add('same-date opposite ranks', -p['sameDateRankConflictPenalty'] * weight, sources)

        # One strongest observation per place; distinct place roles are not
        # independent evidence about the same geographical association.
        place_values = {}
        for (left_role, place), a in sorted(left.places.items()):
            for (right_role, other_place), b in sorted(right.places.items()):
                if place != other_place:
                    continue
                value, sources = best(a, b, p['placeWeight'], p['placeHalfLifeYears'])
                role = 'context'
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

        def best_family(a, b, weight):
            # Each relative mention carries its own membership confidence.
            choices = [(weight * min(reliability(x, p), reliability(y, p)) * min(cx, cy) * decay(dx, dy, p['familyHalfLifeYears']), (x, y))
                       for x, dx, cx in a for y, dy, cy in b]
            return max(choices, key=lambda choice: choice[0], default=(0, ()))
        relatives = {}
        for token in sorted(set(left.relatives) & set(right.relatives), key=str):
            role, identity, relative_name, grounded = token
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
            value, sources = best_family(left.relatives[token], right.relatives[token], weight)
            rarity, frequency = self.relative_rarity(relative_name)
            bonus, _ = best_family(left.relatives[token], right.relatives[token], rarity)
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
            hard.append('explicitly distinct relationship participants')
        reason = vow_conflict(self.profile_traits(left), self.profile_traits(right))
        if reason:
            blocks.append(reason)
        hard.extend(block for block in blocks if block not in hard and not block.startswith(('mention after', 'incompatible death', 'impossible age')))
        prior = math.log(p['priorProbability'] / (1 - p['priorProbability']))
        log_odds = prior + sum(feature['contribution'] for feature in features)
        probability = 1 / (1 + math.exp(-max(-700, min(700, log_odds))))
        return {'probability': round(probability, 8), 'logOdds': round(log_odds, 8),
                'features': features, 'sources': [refs[key] for key in sorted(refs)],
                'blocks': blocks, 'hardBlocks': hard,
                # Name/age-only candidates are not worth persisting.
                'substantive': any(f['contribution'] > 0 or 'death' in f['name'] for f in features)
                               or any(not block.startswith('impossible age') for block in blocks)}
