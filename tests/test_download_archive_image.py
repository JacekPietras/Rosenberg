"""Archive page selection and safe download behavior, without network access."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from download_archive_image import DownloadError, Image, download, resolve


class FakeClient:
    def __init__(self, responses=None, image=b""):
        self.responses = responses or {}
        self.image = image
        self.requests = []

    def text(self, url):
        self.requests.append(url)
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        return value

    def json(self, url):
        return json.loads(self.text(url))

    def open(self, url):
        self.requests.append(url)
        return io.BytesIO(self.image)


class SelectionTests(unittest.TestCase):
    def test_internet_archive_leaf_zero_and_sequence_conversion(self):
        url = "https://archive.org/details/book/page/n0/mode/1up"
        self.assertEqual("https://archive.org/download/book/page/n0.jpg",
                         resolve(url, FakeClient()).image_url)
        self.assertEqual("n455", resolve("https://archive.org/details/book", FakeClient(), page=456).page)
        with self.assertRaises(DownloadError):
            resolve("https://archive.org/details/book", FakeClient())
        with self.assertRaises(DownloadError):
            resolve("https://archive.org/details/book/page/80r", FakeClient())

    def test_vatican_exact_folio_uses_manifest_not_arithmetic(self):
        url = "https://digi.vatlib.it/view/MSS_Test"
        canvases = [{"label": label, "images": [{"resource": {"service": {"@id": service}}}]}
                    for label, service in [("108v", "https://images/wrong.jp2"),
                                           ("108r", "https://images/correct.jp2")]]
        client = FakeClient({"https://digi.vatlib.it/iiif/MSS_Test/manifest.json":
                             json.dumps({"label": "Test", "sequences": [{"canvases": canvases}]})})
        image = resolve(url, client, folio="108 R")
        self.assertEqual("108r", image.folio)
        self.assertEqual("https://images/correct.jp2/full/full/0/default.jpg", image.image_url)
        self.assertEqual("108v", resolve(url + "/0001", client).folio)
        with self.assertRaises(DownloadError):
            resolve(url, client, folio="109r")
        with self.assertRaises(DownloadError):
            resolve(url, client, page=3)
        canvases.append(canvases[-1])
        client.responses[next(iter(client.responses))] = json.dumps({"sequences": [{"canvases": canvases}]})
        with self.assertRaises(DownloadError):
            resolve(url, client, folio="108r")

    def test_blb_ignores_social_preview_for_other_leaf(self):
        url = "https://digital.blb-karlsruhe.de/blbhs/content/pageview/4185505"
        client = FakeClient({url: '<meta property="og:title" content="Wappen &amp; Namen">'
                             '<meta property="og:image" content="https://images/wrong.jpg">'
                             '<div class="row pagin"><div>Seite</div><div><span>207</span></div></div>'})
        image = resolve(url, client)
        self.assertEqual("207", image.page)
        self.assertEqual("Wappen & Namen", image.title)
        self.assertIn("/4185505/full/max/", image.image_url)

    def test_gnm_uses_page_record_and_matches_folio(self):
        url = "https://dlib.gnm.de/item/Hs6599/196"
        data = {"issue": {"titel": "Wappenbuch"}, "pages": [
            {"page": 196, "label": "196 / 91v", "imgmax": "https://images/91v.jpg"}]}
        client = FakeClient({"https://dlib.gnm.de/viewer/index.php?id=Hs6599/json": json.dumps(data)})
        self.assertEqual("91v", resolve(url, client).folio)
        self.assertEqual("https://images/91v.jpg", resolve(url, client, folio="91 v").image_url)
        with self.assertRaises(DownloadError):
            resolve(url, client, folio="91r")

    def test_blb_blocked_metadata_still_selects_exact_image_and_reports_limit(self):
        url = "https://digital.blb-karlsruhe.de/blbhs/content/pageview/4185533"
        image = resolve(url, FakeClient({url: '<title>Verifying your browser</title>'}))
        self.assertIn("/4185533/full/max/", image.image_url)
        self.assertEqual("", image.title)
        self.assertEqual("", image.page)
        self.assertTrue(image.notes)

    def test_findbuch_uses_array_index_not_filename_number(self):
        base = "https://www.noela.findbuch.net/php/view.php?link=record"
        selected = "http://offline.example/HS_0162_Nr_189.jpg"
        client = FakeClient({base: "var be_id = 12; var ve_id = '1393432';"
                             f"paths[7] = '{selected}';"})
        image = resolve(base + "#&zoom=0.025&path=" + selected, client)
        self.assertEqual("HS_0162_Nr_189.jpg", image.filename)
        self.assertEqual("https://www.noela.findbuch.net/php/gtpc.php?be_id=12&ve_id=1393432&count=7",
                         image.image_url)
        with self.assertRaises(DownloadError):
            resolve(base, client)
        with self.assertRaises(DownloadError):
            resolve(base + "#&path=http://offline.example/missing.jpg", client)

    def test_loc_uses_resource_sequence_and_largest_jpeg(self):
        url = "https://www.loc.gov/resource/rbc.2011rosen0017/?sp=2"
        api = "https://www.loc.gov/resource/rbc.2011rosen0017/?fo=json"
        data = {"resource": {"files": [[], [
            {"mimetype": "image/jpeg", "width": 100, "url": "https://images/small.jpg"},
            {"mimetype": "image/jpeg", "width": 3000, "url": "https://images/large.jpg"}]]}}
        self.assertEqual("https://images/large.jpg", resolve(url, FakeClient({api: json.dumps(data)})).image_url)

    def test_loc_blocked_api_checks_four_digit_image_and_reports_fallback(self):
        url = "https://www.loc.gov/resource/rbc.2011rosen0017/?sp=189"
        api = "https://www.loc.gov/resource/rbc.2011rosen0017/?fo=json"
        base = "https://tile.loc.gov/image-services/iiif/service:rbc:rbc0001:2011:2011rosen0017:0189"
        client = FakeClient({api: OSError("403"), base + "/info.json": '{"width": 3688}'})
        image = resolve(url, client)
        self.assertEqual(base + "/full/full/0/default.jpg", image.image_url)
        self.assertTrue(image.notes)
        self.assertIn(base + "/info.json", client.requests)

    def test_unknown_hosts_and_conflicting_selectors_fail(self):
        for url, args in [("https://example.com/view", {}),
                          ("file:///tmp/test", {}),
                          ("https://digi.vatlib.it/view/MSS_Test", {"folio": "1r", "page": 1})]:
            with self.subTest(url=url), self.assertRaises(DownloadError):
                resolve(url, FakeClient(), **args)


class DownloadTests(unittest.TestCase):
    def test_html_response_is_rejected_without_leaving_file(self):
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / "image.jpg"
            with self.assertRaises(DownloadError):
                download(Image("source", "https://images/page", "page.jpg"), dest,
                         FakeClient(image=b"<!doctype html><title>Access denied</title>"))
            self.assertEqual([], list(Path(folder).iterdir()))

    def test_download_preserves_bytes_and_refuses_overwrite(self):
        payload = b"\xff\xd8\xff" + b"test-image-bytes" * 100
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / "image.jpg"
            client = FakeClient(image=payload)
            image = Image("source", "https://images/page", "page.jpg")
            self.assertEqual("jpeg", download(image, dest, client))
            self.assertEqual(payload, dest.read_bytes())
            with self.assertRaises(DownloadError):
                download(image, dest, FakeClient(image=b"different"))
            self.assertEqual(payload, dest.read_bytes())
            self.assertEqual([dest], list(Path(folder).iterdir()))

    def test_interrupted_download_cleans_partial_file(self):
        class Interrupted(io.BytesIO):
            def read(self, count=-1):
                if self.tell():
                    raise OSError("connection lost")
                return super().read(count)
        client = FakeClient()
        client.open = lambda url: Interrupted(b"\xff\xd8\xff" + b"x" * 100)
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(OSError):
                download(Image("source", "https://images/page", "page.jpg"), Path(folder) / "image.jpg", client)
            self.assertEqual([], list(Path(folder).iterdir()))


if __name__ == "__main__":
    unittest.main()
