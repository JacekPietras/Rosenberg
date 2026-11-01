"""Name compatibility, never person identification or ID-token expansion."""

import re
import unicodedata
from place_names import resolve_place_names


def normalize(value):
    text = unicodedata.normalize('NFKD', value.replace('ß', 'ss').replace('ſ', 's')).casefold()
    return re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in text if not unicodedata.combining(c))).strip()


class Names:
    def __init__(self, names_text, places, titles_text='', kinship_text=''):
        from .kinship import Kinship
        self.raw_places = places
        self.kinship = Kinship(kinship_text)
        # Equivalent title words and epithets, e.g. Vogt/advocatus, der Rote/Rufus.
        self.titles = {}
        self.title_display = {}
        for line in titles_text.splitlines():
            forms = [item.strip() for item in line.split('//', 1)[0].split(',') if item.strip()]
            for form in forms:
                self.titles[normalize(form)] = normalize(forms[0])
                self.title_display[normalize(form)] = forms[0]
        self.given = {}
        for line in names_text.splitlines():
            forms = [normalize(item) for item in line.split('//', 1)[0].split(',') if item.strip()]
            for form in forms:
                self.given[form] = forms[0]
        variants = {}
        for place in resolve_place_names(places):
            for variant in place.get('variations', []):
                variants.setdefault(normalize(variant), set()).add(normalize(place['variations'][0]))
        self.places = {name: next(iter(values)) for name, values in variants.items() if len(values) == 1}

    def canonical_title(self, title):
        """Canonicalize configured equivalents without changing source assertions."""
        whole = self.title_display.get(normalize(title))
        if whole:
            return whole
        from .probability import OFFICES
        def office_word(match):
            canonical = self.title_display.get(normalize(match.group()))
            return canonical if canonical and normalize(canonical) in OFFICES else match.group()
        words = re.sub(r'[^\W\d_]+', office_word, title)
        # The matching model treats these office connectors as equivalent.
        parts = words.split()
        for index, word in enumerate(parts[:-2]):
            if normalize(word) in OFFICES and normalize(parts[index + 1]) in {'in', 'zu'}:
                parts[index + 1] = 'zu'
                return ' '.join(parts)
        return words

    def key(self, name):
        # Only normalize the given name and the complete surname/place phrase.
        # Münch von Rosenberg therefore cannot become von Rosenberg.
        parts = normalize(name).split(' ')
        if not parts:
            return ''
        parts[0] = self.given.get(parts[0], parts[0])
        if len(parts) > 1 and parts[1] == 'de':
            parts[1] = 'von'
        if 'von' in parts:
            index = parts.index('von')
            surname = ' '.join(parts[index + 1:])
            parts[index + 1:] = [self.places.get(surname, surname)]
        return ' '.join(parts)
