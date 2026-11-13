import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from family_graph.person_names import PersonNameRecognizer
from family_graph.sources import walk_assertions


ROOT = Path(__file__).resolve().parents[1]


def recognizer():
    names = (ROOT / 'data/names.md').read_text(encoding='utf-8')
    particles = (ROOT / 'data/nobiliary_particles.md').read_text(encoding='utf-8')
    connectors = (ROOT / 'data/name-connectors.md').read_text(encoding='utf-8')
    titles = '\n'.join([
        (ROOT / 'data/titles-age.md').read_text(encoding='utf-8'),
        (ROOT / 'data/titles-office.md').read_text(encoding='utf-8'),
    ])
    places = json.loads((ROOT / 'data/places.json').read_text(encoding='utf-8'))
    return PersonNameRecognizer(names, particles, places, titles, connectors)


class PersonNameRecognitionTests(unittest.TestCase):
    def test_recognizes_listed_names_with_titles_and_deduplicates(self):
        found = recognizer().find(
            'Ritter Arnold von Uissigheim, Vogt zu Lauda met Eberhard von Rosenberg. '
            'Eberhard von Rosenberg signed the charter.'
        )
        self.assertIn('Arnold von Uissigheim', found)
        self.assertIn('Eberhard von Rosenberg', found)
        self.assertEqual(1, len([name for name in found if 'Eberhard' in name]))

    def test_document_english_is_an_observation_but_book_english_is_not(self):
        document = {'date': '1399', 'entries': [{'english': 'Eberhard von Rosenberg witnessed it.',
                                                  'facts': [{'date': '1399', 'type': 'generic', 'person': 'Eberhard von Rosenberg', 'content': 'witnessed it.'}]}]}
        book = {'book': 'Example', 'entries': document['entries']}
        document_refs = [ref for ref, value in walk_assertions(document, 'data/documents/example.json', include_text=True)
                         if ref.kind == 'text']
        book_refs = [ref for ref, value in walk_assertions(book, 'data/books/example.json', include_text=True)
                     if ref.kind == 'text']
        self.assertEqual([('/entries/0/english', 'text')], [(ref.pointer, ref.kind) for ref in document_refs])
        self.assertFalse(book_refs)


if __name__ == '__main__':
    unittest.main()
