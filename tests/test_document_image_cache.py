import hashlib
import importlib.util
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


server = load_module('viewer_server', ROOT / 'docs/serve.py')
downloader = load_module('image_downloader', ROOT / 'scripts/download_missing_document_images.py')


class FakeResponse:
    def __init__(self, content):
        self.content = content
        self.headers = self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, *args):
        return self.content

    def get_content_type(self):
        return 'image/jpeg'


class ImageCacheTest(unittest.TestCase):
    def test_distinct_urls_do_not_reuse_legacy_or_each_others_images(self):
        urls = [f'https://api.digitale-sammlungen.de/iiif/image/v2/{page}/full/max/0/default.jpg' for page in ('first', 'second')]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / 'data/documents/img-temp'
            cache.mkdir(parents=True)
            (cache / 'default.jpg').write_bytes(b'wrong legacy image')
            with patch.object(server, 'ROOT', root), patch.object(server, 'urlopen', side_effect=lambda request, timeout: FakeResponse(request.full_url.encode())) as fetch:
                httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.ViewerHandler)
                thread = threading.Thread(target=httpd.serve_forever, daemon=True)
                thread.start()
                try:
                    for url in urls + urls:
                        with urlopen(f'http://127.0.0.1:{httpd.server_port}/api/document-image?url={quote(url, safe="")}') as response:
                            self.assertEqual(response.read(), url.encode())
                    self.assertEqual(fetch.call_count, 2)
                    for url in urls:
                        name = hashlib.sha256(url.encode()).hexdigest() + '.jpg'
                        self.assertEqual(downloader.cache_name(url), name)
                        self.assertEqual((cache / name).read_bytes(), url.encode())
                finally:
                    httpd.shutdown()
                    thread.join()
                    httpd.server_close()
