"""Recognize full personal names in prose using the project's name lists."""

import re

from given_names import name_groups
from place_names import resolve_place_names


def _forms(text):
    return [part.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#')
            for part in line.split('//', 1)[0].split(',') if part.strip()]


class PersonNameRecognizer:
    """Python counterpart for the shared text-name recognizer.

    It deliberately returns literal recognized forms. The family graph resolves
    their identity separately and conservatively.
    """

    def __init__(self, names_text, particles_text, places, titles_text='', connectors_text=''):
        given = [form for group, _gender in name_groups(names_text) for form in group]
        place_names = [form for place in resolve_place_names(places)
                       for form in place.get('variations', [])]
        particles = _forms(particles_text)
        titles = _forms(titles_text)
        connectors = _forms(connectors_text)

        def alternatives(values):
            return '|'.join(re.escape(value).replace(r'\ ', r'\s+')
                            for value in sorted(set(values), key=lambda item: (-len(item), item)))

        if not given or not place_names or not particles:
            self.pattern = None
            return
        name = alternatives(given)
        particle = alternatives([*particles, 'of'])
        place = alternatives(place_names)
        title = alternatives(titles)
        connector = alternatives(connectors)
        ordinal = r'(?:\s+(?:\(\s*[IVXLCDM]+\s*\)|\[\s*[IVXLCDM]+\s*\]|[IVXLCDM]+\.?))?'
        leading_titles = rf'(?:(?:{title})[\s,;]+)*' if title else ''
        title_suffix = rf'(?:[\s,;]+(?:{title})(?:\s+(?:zu|an|of)\s+(?:{place}|[^\W\d_][^\W\d_.-]*))?)*' if title else ''
        internal_titles = rf'(?:[\s,;]+(?:{title})(?:\s+(?:zu|an|of)\s+(?:{place}|[^\W\d_][^\W\d_.-]*))?)*' if title else ''
        lead_connector = rf'(?:(?:{connector})\s+)?' if connector else ''
        middle_connector = rf'(?:\s+(?:{connector}))?' if connector else ''
        self.pattern = re.compile(
            rf'(?<![\w]){leading_titles}{lead_connector}(?P<person>(?:{name})(?:\s+(?:{name}))*{ordinal}'
            rf'{internal_titles}{middle_connector}[\s,]+(?:{particle})\s+(?:{place})'
            rf'(?:\s+(?:zu|an)\s+(?:{place}))?)(?:\s*\([^)]*\))?{title_suffix}(?![\w])',
            re.IGNORECASE | re.UNICODE,
        )
        self.strip_titles = re.compile(
            rf'[\s,;]+(?:{title})(?:\s+(?:zu|an|of)\s+(?:{place}|[^\W\d_][^\W\d_.-]*))?',
            re.IGNORECASE | re.UNICODE,
        ) if title else None
        self.strip_connectors = re.compile(rf'\s+(?:{connector})\s+', re.IGNORECASE | re.UNICODE) if connector else None

    def find(self, text):
        if not self.pattern or not isinstance(text, str):
            return frozenset()
        values = set()
        for match in self.pattern.finditer(text):
            value = match.group('person').strip(' ,;')
            if self.strip_titles:
                value = self.strip_titles.sub('', value)
            if self.strip_connectors:
                value = self.strip_connectors.sub(' ', value)
            values.add(value)
        return frozenset(values)
