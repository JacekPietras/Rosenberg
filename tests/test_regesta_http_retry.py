import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/archive_search'))
import search_regesta_imperii as regesta


def http_error(code):
    return HTTPError('https://example.org', code, 'error', {}, None)


class RegestaHttpRetryTests(unittest.TestCase):
    @patch('search_regesta_imperii.time.sleep')
    def test_retries_through_schedule_then_succeeds(self, sleep):
        operation = Mock(side_effect=[*[http_error(500) for _ in range(7)], 'ok'])
        before_retry = Mock()
        self.assertEqual(regesta.retry_http_500(operation, before_retry), 'ok')
        self.assertEqual(sleep.call_args_list, [call(n) for n in (5, 10, 20, 30, 60, 120, 240)])
        self.assertEqual(before_retry.call_count, 7)
        self.assertEqual(operation.call_count, 8)

    @patch('search_regesta_imperii.time.sleep')
    def test_exhaustion_and_other_errors(self, sleep):
        operation = Mock(side_effect=http_error(500))
        with self.assertRaises(HTTPError):
            regesta.retry_http_500(operation, Mock())
        self.assertEqual(operation.call_count, 8)
        self.assertEqual(sleep.call_count, 7)
        sleep.reset_mock()
        operation = Mock(side_effect=http_error(429))
        with self.assertRaises(HTTPError):
            regesta.retry_http_500(operation, Mock())
        operation.assert_called_once()
        sleep.assert_not_called()

    @patch('search_regesta_imperii.time.sleep')
    def test_get_and_search_post_retry(self, sleep):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'page'
        response.geturl.return_value = 'https://example.org'
        client = regesta.Client(1, Path('/unused'))
        client.wait = Mock()
        for method in (lambda: client.request_url('https://example.org'),
                       lambda: client.post('https://example.org', {})):
            with self.subTest(method=method), patch.object(regesta.ri.OPENER, 'open', side_effect=[http_error(500), response]) as opening:
                method()
                self.assertEqual(opening.call_count, 2)
        self.assertEqual(sleep.call_args_list, [call(5), call(5)])


if __name__ == '__main__':
    unittest.main()
