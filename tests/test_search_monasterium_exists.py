import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/archive_search/search_monasterium.py'
spec = importlib.util.spec_from_file_location('search_monasterium', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ExistenceTests(unittest.TestCase):
    def test_one_request_for_positive_and_negative_results(self):
        pages = [
            b'<div class="hits">Hits 1 to 10 of 123</div>',
            b'<form id="search-form"></form>Sorry, no results were found for your search.',
        ]
        with tempfile.TemporaryDirectory() as directory:
            client = module.Client(15, Path(directory))
            with patch.object(client, 'wait'), patch.object(module, 'urlopen', side_effect=[io.BytesIO(page) for page in pages]) as fetch:
                self.assertTrue(client.exists('Rosinberg'))
                self.assertFalse(client.exists('Rosenburgk'))
                self.assertEqual(fetch.call_count, 2)

    def test_complete_search_cache_avoids_request(self):
        with tempfile.TemporaryDirectory() as directory:
            client = module.Client(15, Path(directory))
            key = module.hashlib.sha256(b'and-quoted-v1\0Rosinberg').hexdigest()
            (Path(directory) / (key + '.json')).write_text(json.dumps({
                'query': 'Rosinberg', 'total': 1, 'rows': [{'url': 'example'}],
            }))
            with patch.object(module, 'urlopen') as fetch:
                self.assertTrue(client.exists('Rosinberg'))
                fetch.assert_not_called()

    def test_unrecognized_page_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            client = module.Client(15, Path(directory))
            with patch.object(client, 'wait'), patch.object(module, 'urlopen', return_value=io.BytesIO(b'blocked')):
                with self.assertRaises(ValueError):
                    client.exists('Rosinberg')


if __name__ == '__main__':
    unittest.main()
