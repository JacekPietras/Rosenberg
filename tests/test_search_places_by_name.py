"""Verify place counts reflect matching records, not individual mentions."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import search_places_by_name as search


class SearchPlacesTests(unittest.TestCase):
    def test_count_each_place_once_per_record_including_multiline_records(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'data').mkdir()
            (root / 'data/places.json').write_text(json.dumps([
                {'variations': ['Boxberg', 'Bocksberg']},
                {'variations': ['Lauda']},
            ]))

            def fake_search(args, on_match):
                self.assertEqual(['person', '--direct'], args)
                on_match('Boxberg and Bocksberg\nLauda')
                on_match('Bocksberg')

            output = io.StringIO()
            with patch.object(search, 'ROOT', root), patch.object(search, 'search_facts', fake_search), \
                 patch.object(sys, 'argv', ['search_places_by_name.py', 'person', '--direct', '--count']), \
                 contextlib.redirect_stdout(output):
                search.main()
            self.assertEqual('Boxberg: 2\nLauda: 1\n', output.getvalue())


if __name__ == '__main__':
    unittest.main()
