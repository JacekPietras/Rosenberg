from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from family_graph.person_names import PersonNameRecognizer
from family_graph.names import Names
from family_graph.sources import walk_assertions


NAMES = '# Men\nArnold\nEberhard\nKonrad\n# Women\nElisabeth, Elsbeth'
PLACES = [{'id': place.lower(), 'variations': [place]}
          for place in ('Uissigheim', 'Lauda', 'Rosenberg', 'Pappenheim', 'Bartenstein')]


def recognizer():
    return PersonNameRecognizer(NAMES, 'von\nzu', PLACES, 'Ritter\nVogt', '', 'Marschalk')


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

    def test_birth_surname_replaces_later_designation_for_context_name(self):
        names = recognizer().find(
            'Issuer: Elsbeth Rosenberg, née Marschalk zu Pappenheim. '
            'Sealer: Elisabeth von Rosenberg, née Marschalk zu Pappenheim.'
        )
        self.assertEqual({'Elsbeth Marschalk zu Pappenheim', 'Elisabeth Marschalk zu Pappenheim'}, names)

    def test_zum_place_form_is_recognized_and_normalized_like_zu(self):
        phrase = 'transferred the said Amt Klingenberg to Konrad von Rosenberg zum Bartenstein and his cousin'
        found = recognizer().find(phrase)
        self.assertEqual({'Konrad von Rosenberg'}, found)
        name_rules = Names(NAMES, PLACES)
        self.assertEqual(name_rules.key('Konrad von Rosenberg zu Bartenstein'),
                         name_rules.key('Konrad von Rosenberg zum Bartenstein'))


if __name__ == '__main__':
    unittest.main()
