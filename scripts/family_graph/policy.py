"""Versioned heuristics; scores are not calibrated probabilities."""

from dataclasses import dataclass
from pathlib import Path

MIN_SCORE = 7
MIN_MARGIN = 3
SEARCH_LIMIT = 10000
RANK_TITLE_HEADS = frozenset({'Ritter', 'Edelknecht', 'Knecht'})


def _read_title_groups(name):
    path = Path(__file__).resolve().parents[2] / 'data' / name
    groups = []
    for line in path.read_text(encoding='utf-8').splitlines():
        forms = [form.strip() for form in line.split('//', 1)[0].split(',') if form.strip()]
        if forms:
            groups.append(forms)
    return groups


AGE_TITLES = frozenset(form for group in _read_title_groups('titles-age.md') for form in group)
RANK_TITLES = frozenset(form for group in _read_title_groups('titles-office.md') if group[0] in RANK_TITLE_HEADS for form in group)


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
