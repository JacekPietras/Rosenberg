import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/archive_search'))
from search_results import ResultsStore, search_delay
from search_retry import retry_get


class ArchiveDelayTests(unittest.TestCase):
    def test_configuration_survives_result_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'archive.json'
            path.write_text(json.dumps({'archive': 'example', 'delaySeconds': 2.5, 'queries': {}}))
            self.assertEqual(search_delay('example', path), 2.5)
            ResultsStore('example', path).record('query', True)
            self.assertEqual(search_delay('example', path), 2.5)

    def test_missing_and_invalid_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'archive.json'
            self.assertEqual(search_delay('example', path), 15)
            for value in (0, -1, True, '2', float('nan')):
                path.write_text(json.dumps({'delaySeconds': value}))
                with self.subTest(value=value), self.assertRaises(ValueError):
                    search_delay('example', path)

    @patch('search_retry.time.sleep')
    def test_retry_uses_configured_delay(self, sleep):
        with patch('search_retry.sys.stderr'):
            self.assertEqual(retry_get(unittest.mock.Mock(side_effect=[TimeoutError(), 'ok']), 2), 'ok')
        sleep.assert_called_once_with(2)


if __name__ == '__main__':
    unittest.main()
