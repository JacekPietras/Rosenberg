import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/archive_records'))
sys.path.insert(0, str(ROOT / 'scripts/archive_images'))
import archive_record_gda_bayern as bayern
import archive_record_nrw as nrw
import download_selected_archive_image as images


def error(code):
    return HTTPError('https://example.org', code, 'error', {}, None)


class ArchiveActionRetryTests(unittest.TestCase):
    @patch('search_retry.time.sleep')
    def test_standalone_record_fetches_retry(self, sleep):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'page'
        response.geturl.return_value = 'https://example.org'
        response.headers.get_content_type.return_value = 'text/html'
        response.headers.get_content_charset.return_value = 'utf-8'
        for code in (403, 429, 502):
            with self.subTest(code=code), patch.object(nrw.OPENER, 'open', side_effect=[error(code), response]) as opening:
                self.assertEqual(nrw.request('https://example.org')[1], b'page')
                self.assertEqual(opening.call_count, 2)
            with self.subTest(code=code), patch.object(bayern, 'urlopen', side_effect=[error(code), response]) as opening:
                self.assertEqual(bayern.fetch('https://example.org'), 'page')
                self.assertEqual(opening.call_count, 2)
        self.assertEqual(sleep.call_count, 6)

    @patch('search_retry.time.sleep')
    def test_image_request_retries(self, sleep):
        response = MagicMock()
        with patch.object(images, 'urlopen', side_effect=[error(429), response]) as opening:
            self.assertIs(images.Client().open('https://example.org/image'), response)
        self.assertEqual(opening.call_count, 2)
        sleep.assert_called_once_with(5)
