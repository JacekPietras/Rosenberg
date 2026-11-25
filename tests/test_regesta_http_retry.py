import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, call, patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/archive_search'))
import search_regesta_imperii as regesta


def http_error(code):
    return HTTPError('https://example.org', code, 'error', {}, None)


class RegestaHttpRetryTests(unittest.TestCase):
    @patch('search_retry.time.sleep')
    def test_anubis_403_reaches_challenge_handler_without_retry(self, sleep):
        body = b'<script id="anubis_challenge" type="application/json">{}</script>'
        challenge = HTTPError('https://example.org', 403, 'Forbidden', {}, BytesIO(body))
        client = regesta.Client(1, Path('/unused'))
        client.wait = Mock()
        with patch.object(regesta.ri.OPENER, 'open', side_effect=challenge) as opening:
            self.assertEqual(client.request_url('https://example.org'), ('https://example.org', body))
        opening.assert_called_once()
        sleep.assert_not_called()

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
        for code in (403, 429, 500, 502, 503, 599):
            with self.subTest(code=code):
                sleep.reset_mock()
                operation = Mock(side_effect=[http_error(code) for _ in range(8)])
                with self.assertRaises(HTTPError):
                    regesta.retry_http_500(operation, Mock())
                self.assertEqual(operation.call_count, 8)
                self.assertEqual(sleep.call_count, 7)
        for code in (400, 404, 499, 600):
            with self.subTest(code=code):
                sleep.reset_mock()
                operation = Mock(side_effect=http_error(code))
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

    @patch('search_retry.time.sleep')
    def test_http_502_retries_get_and_search_post(self, sleep):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'page'
        response.geturl.return_value = 'https://example.org'
        client = regesta.Client(1, Path('/unused'))
        client.wait = Mock()
        for method in (lambda: client.request_url('https://example.org'),
                       lambda: client.post('https://example.org', {})):
            with self.subTest(method=method), patch.object(
                    regesta.ri.OPENER, 'open', side_effect=[http_error(502), http_error(502), response]) as opening:
                method()
                self.assertEqual(opening.call_count, 3)
        self.assertEqual(sleep.call_args_list, [call(5), call(10), call(5), call(10)])


if __name__ == '__main__':
    unittest.main()
