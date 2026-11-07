import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/archive_search'))
from search_retry import retry_get


class RetryGetTests(unittest.TestCase):
    @patch('search_retry.time.sleep')
    def test_timeout_retries_once_with_configured_spacing(self, sleep):
        operation = Mock(side_effect=[TimeoutError('read timed out'), b'ok'])
        self.assertEqual(retry_get(operation, 30), b'ok')
        self.assertEqual(operation.call_count, 2)
        sleep.assert_called_once_with(30)

    @patch('search_retry.time.sleep')
    def test_wrapped_timeout_stops_after_second_failure(self, sleep):
        operation = Mock(side_effect=URLError(TimeoutError('timed out')))
        with self.assertRaises(URLError):
            retry_get(operation)
        self.assertEqual(operation.call_count, 2)
        sleep.assert_called_once_with(15)

    @patch('search_retry.time.sleep')
    def test_http_and_other_network_errors_are_not_retried(self, sleep):
        for error in (HTTPError('https://example.org', 429, 'rate limit', {}, None),
                      URLError('connection refused')):
            with self.subTest(error=error):
                operation = Mock(side_effect=error)
                with self.assertRaises(type(error)):
                    retry_get(operation)
                self.assertEqual(operation.call_count, 1)
        sleep.assert_not_called()


if __name__ == '__main__':
    unittest.main()
