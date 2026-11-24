import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/archive_search'))
import search_arcinsys_hessen as hessen
import search_gda_bayern as bayern
import search_landesarchiv_bw as bw
import search_landesarchiv_nrw as nrw
import search_monasterium as monasterium


def error():
    return HTTPError('https://example.org', 500, 'error', {}, None)


class ArchiveHttpRetryTests(unittest.TestCase):
    @patch('search_retry.time.sleep')
    def test_search_requests_retry_http_500(self, sleep):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            for module, client in ((hessen, hessen.Client(1)), (bw, bw.Client(1)),
                                   (bayern, bayern.Client(1, cache)), (nrw, nrw.Client(1, cache))):
                for data in ((None,) if module is nrw else (None, b'search')):
                    with self.subTest(archive=module.__name__, data=data):
                        response = MagicMock()
                        response.__enter__.return_value = response
                        response.read.return_value = b'page'
                        response.headers.get_content_charset.return_value = 'utf-8'
                        opener = nrw.nrw.OPENER if module is nrw else client.opener
                        client.wait = MagicMock()
                        with patch.object(opener, 'open', side_effect=[error(), response]) as opening:
                            if module is bayern:
                                client.request(data)
                            elif module is nrw:
                                client.request('https://example.org')
                            else:
                                client.request('https://example.org', data)
                            self.assertEqual(opening.call_count, 2)
                        self.assertEqual(client.wait.call_count, 2)

    @patch('search_retry.time.sleep')
    def test_monasterium_existence_search_retries(self, sleep):
        with tempfile.TemporaryDirectory() as directory:
            client = monasterium.Client(1, Path(directory))
            client.wait = MagicMock()
            with patch.object(monasterium, 'read_search', side_effect=[error(), 'No results found']) as read, \
                 patch.object(monasterium.Results, 'total', return_value=0):
                self.assertFalse(client.exists('example'))
                self.assertEqual(read.call_count, 2)
                self.assertEqual(client.wait.call_count, 2)


if __name__ == '__main__':
    unittest.main()
