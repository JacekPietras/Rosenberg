"""Internal evidence records; these are not extensions of source fact objects."""

from dataclasses import dataclass, field
from datetime import date
import hashlib
import json
import struct


def canonical(value):
    # Tagged containers and IEEE-754 numbers give Python and JavaScript the
    # same encoding (including 1 versus 1.0 and non-ASCII text).
    def encode(item):
        if isinstance(item, dict):
            return ['object', [[key, encode(item[key])] for key in sorted(item)]]
        if isinstance(item, list):
            return ['array', [encode(child) for child in item]]
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            return ['number', struct.pack('>d', item or 0).hex()]
        return item
    return json.dumps(encode(value), ensure_ascii=True, separators=(',', ':'), allow_nan=False)


def fingerprint(value):
    return 'sha256:' + hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def registry_keys(people):
    ids = {person['id'] for person in people if person.get('id')}
    keys = []
    for index, person in enumerate(people):
        key = person.get('id') or f'@registry/{index}'
        if not person.get('id'):
            while key in ids:
                key += '~'
        keys.append(key)
    return keys


@dataclass(frozen=True)
class SourceRef:
    path: str
    pointer: str
    fingerprint: str
    kind: str
    citation: str = ''

    def export(self):
        return {key: getattr(self, key) for key in ('path', 'pointer', 'fingerprint')}

    @property
    def key(self):
        return self.path + '#' + self.pointer


@dataclass
class Mention:
    handle: str
    reference: str
    field: str
    titles: tuple
    deceased: bool
    assertion: 'Assertion' = field(repr=False, default=None)


@dataclass
class Assertion:
    source: SourceRef
    original: dict
    historical_date: str
    bounds: tuple[date, date]
    context: dict
    mentions: list[Mention] = field(default_factory=list)

    @property
    def event_key(self):
        # Only weight demonstrably identical attestations once. A general book
        # citation alone never makes two different statements one event.
        return fingerprint([self.original, self.historical_date, self.source.citation])


@dataclass
class Candidate:
    identity: str
    features: list = field(default_factory=list)
    exclusions: list = field(default_factory=list)
    sources: list[SourceRef] = field(default_factory=list)
    reviewed: bool = False

    @property
    def score(self):
        return sum(feature['score'] for feature in self.features)


@dataclass
class IdentityDecision:
    mention: Mention
    status: str
    identity: str | None
    method: str
    candidates: list[Candidate] = field(default_factory=list)
    sources: list[SourceRef] = field(default_factory=list)
    uses_guesses: bool = False
    reason: str = ''


@dataclass
class Relationship:
    type: str
    person: str
    of: str
    term: str
    derivations: list = field(default_factory=list)


@dataclass
class BuildResult:
    view: str
    decisions: dict
    relationships: list
    conflicts: list
    diagnostics: list
    alternatives: list = field(default_factory=list)
    omitted: int = 0
    provisional_groups: dict = field(default_factory=dict)
    configuration: dict = field(default_factory=dict)
    evidence_graph: dict = field(default_factory=dict)


@dataclass
class Inputs:
    root: object
    people: list
    names: str
    places: list
    assertions: list
    manifest: dict
    prose: dict
    registry_bytes: bytes
    tree_bytes: bytes | None = None
    matching: dict = field(default_factory=dict)
    observations: list = field(default_factory=list)
