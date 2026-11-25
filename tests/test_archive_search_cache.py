import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts/archive_search' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SearchCacheTests(unittest.TestCase):
    def test_complete_and_partial_searches(self):
        for archive in ('arcinsys_hessen', 'landesarchiv_bw'):
            with self.subTest(archive=archive), tempfile.TemporaryDirectory() as directory:
                module = load('search_' + archive)
                client = module.Client(1, directory)
                rows = [{'id': str(i)} for i in range(35)]
                with patch.object(client, '_search', return_value=iter((row, 35) for row in rows)):
                    self.assertEqual(len(list(client.search('example', limit=2))), 35)
                # The mocked source did not enforce its limit; all 35 rows were observed.
                with patch.object(client, '_search', side_effect=AssertionError('network search')):
                    self.assertEqual(list(client.search('example', limit=2)), [(rows[0], 35), (rows[1], 35)])
                    self.assertEqual(next(client.search('example', exists=True)), (None, 35))
                    if archive == 'landesarchiv_bw':
                        self.assertEqual(list(client.search('example', skip_pages=1)), [(row, 35) for row in rows[30:]])
                        self.assertEqual(client.current_page, 2)
                with patch.object(client, '_search', return_value=iter([(rows[0], 35)])):
                    list(client.search('partial', limit=1))
                with patch.object(client, '_search', return_value=iter([(rows[0], 35)])) as search:
                    list(client.search('partial', limit=1))
                    search.assert_called_once()

    def test_empty_and_exists_does_not_cache_partial(self):
        for archive in ('arcinsys_hessen', 'landesarchiv_bw'):
            with self.subTest(archive=archive), tempfile.TemporaryDirectory() as directory:
                client = load('search_' + archive).Client(1, directory)
                with patch.object(client, '_search', return_value=iter([(None, 1)])):
                    self.assertEqual(next(client.search('positive', exists=True)), (None, 1))
                self.assertFalse(list(Path(directory).glob('*.json')))
                with patch.object(client, '_search', return_value=iter([])):
                    self.assertEqual(list(client.search('empty')), [])
                with patch.object(client, '_search', side_effect=AssertionError('network search')):
                    self.assertEqual(list(client.search('empty')), [])


if __name__ == '__main__':
    unittest.main()
