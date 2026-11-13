"""Versioned heuristics; scores are not calibrated probabilities."""

from dataclasses import dataclass
from pathlib import Path

MIN_SCORE = 7
MIN_MARGIN = 3
SEARCH_LIMIT = 10000
def _read_person_name_titles():
    sections = {'age titles': set(), 'rank titles': set()}
    section = None
    path = Path(__file__).resolve().parents[2] / 'data' / 'person-name-titles.md'
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith('## '):
            section = line[3:].strip().casefold()
        elif section in sections and line.startswith('- '):
            sections[section].add(line[2:].strip())
    return frozenset(sections['age titles']), frozenset(sections['rank titles'])


AGE_TITLES, RANK_TITLES = _read_person_name_titles()


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
