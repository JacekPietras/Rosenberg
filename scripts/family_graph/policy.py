"""Versioned heuristics; scores are not calibrated probabilities."""

from dataclasses import dataclass

MIN_SCORE = 7
MIN_MARGIN = 3
SEARCH_LIMIT = 10000
AGE_TITLES = frozenset({'der Junge', 'der Jüngere', 'der Alte', 'der Ältere'})
RANK_TITLES = frozenset({'Ritter', 'Edelknecht', 'miles', 'armiger', 'Knecht'})


def title_class(title):
    if title in AGE_TITLES:
        return 'age'
    if title in RANK_TITLES:
        return 'rank'
    if title.startswith('zu '):
        return 'territory'
    return 'unclassified'


@dataclass(frozen=True)
class OfficeRule:
    name: str
    title: str
    target: str
    start: str
    end: str
    path: str
    pointer: str


# Project-reviewed designations, restricted to the attested historical scope.
# These rules deliberately make no claim about all holders of either office.
OFFICE_RULES = (
    OfficeRule('Eberhard von Rosenberg', 'Vogt zu Lauda', 'vogt_zu_Lauda', '1385', '1385',
               'data/documents/1385_2.json', '/entries/0/facts/3'),
    OfficeRule('Eberhard von Rosenberg', 'Vogt zu Dürn', 'vogt_zu_Durn', '1342-09-03', '1342-09-03',
               'data/documents/1342-09-03.json', '/entries/0/facts/0'),
)
