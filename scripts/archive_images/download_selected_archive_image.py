#!/usr/bin/env python3
"""Resolve and download one selected archive image (standard library only)."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from html import unescape
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import parse_qs, quote, urlsplit
from urllib.request import Request, urlopen


class DownloadError(ValueError):
    pass


class Client:
    def __init__(self, timeout=25):
        self.timeout = timeout

    def open(self, url):
        if urlsplit(url).scheme not in {"http", "https"}:
            raise DownloadError("Only HTTP(S) URLs are supported")
        return urlopen(Request(url, headers={"User-Agent": "RosenbergResearch/1.0"}),
                       timeout=self.timeout)

    def text(self, url):
        with self.open(url) as response:
            return response.read().decode("utf-8")

    def json(self, url):
        return json.loads(self.text(url))


@dataclass
class Image:
    source: str
    image_url: str
    filename: str
    title: str = ""
    folio: str = ""
    page: str = ""
    notes: list[str] = field(default_factory=list)


def plain(value):
    return unescape(re.sub(r"<[^>]+>", " ", value)).strip()


def normalize_folio(value):
    return re.sub(r"\s+", "", value).lower()


def positive_page(value):
    if value is None or value < 1:
        raise DownloadError("Supply a positive --page (one-based viewer sequence number)")
    return value


def archive_org(url, client, folio, page):
    if folio:
        raise DownloadError("Internet Archive needs a scan leaf; do not infer it from a folio")
    match = re.fullmatch(r"/details/([^/]+)(?:/page/(n\d+)(?:/mode/[^/]+)?)?/?", urlsplit(url).path)
    if not match:
        raise DownloadError("Expected /details/ITEM/page/nNNN[/mode/1up]")
    item, leaf = match.groups()
    if leaf is None:
        leaf = f"n{positive_page(page) - 1}"
    elif page is not None:
        raise DownloadError("Use either the URL's nNNN leaf or --page")
    return Image(url, f"https://archive.org/download/{item}/page/{leaf}.jpg",
                 f"{item}_{leaf}.jpg", page=leaf,
                 notes=["nNNN is a zero-based scan leaf, not a manuscript folio."])


def vatican(url, client, folio, page):
    match = re.search(r"/(?:view|iiif)/(MSS_[^/]+)", urlsplit(url).path)
    if not match:
        raise DownloadError("Expected a DigiVatLib manuscript viewer URL")
    item = match[1]
    manifest_url = f"https://digi.vatlib.it/iiif/{item}/manifest.json"
    manifest = client.json(manifest_url)
    canvases = manifest["sequences"][0]["canvases"]
    if folio:
        matches = [c for c in canvases if normalize_folio(c["label"]) == normalize_folio(folio)]
        if len(matches) != 1:
            raise DownloadError(f"Expected one exact folio {folio!r}; found {len(matches)}")
        canvas = matches[0]
    else:
        selector = re.search(r"/view/[^/]+/(\d+)", urlsplit(url).path)
        index = positive_page(page if page is not None else int(selector[1]) if selector else None)
        if index > len(canvases):
            raise DownloadError("Page exceeds the manifest's canvas count")
        canvas = canvases[index - 1]
    service = canvas["images"][0]["resource"]["service"]["@id"]
    name = service.rsplit("/", 1)[-1].removesuffix(".jp2") + ".jpg"
    return Image(url, service + "/full/full/0/default.jpg", name,
                 title=manifest.get("label", item), folio=canvas["label"],
                 notes=[f"Folio verified in {manifest_url}",
                        "© Biblioteca Apostolica Vaticana. Personal study use; publication requires permission."])


def blb(url, client, folio, page):
    if folio or page is not None:
        raise DownloadError("BLB needs the exact /content/pageview/ID URL")
    match = re.search(r"/content/pageview/(\d+)", urlsplit(url).path)
    if not match:
        raise DownloadError("Expected a BLB /content/pageview/ID URL")
    number = match[1]
    text = client.text(url)
    title = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', text)
    label = re.search(r'<div class="row pagin">(.*?)</div></div>', text, re.S)
    page_label = re.sub(r"^Seite\s*", "", plain(label[1])) if label else ""
    return Image(url, f"https://digital.blb-karlsruhe.de/i3f/v20/{number}/full/max/0/default.jpg",
                 f"blb_{number}.jpg", title=unescape(title[1]) if title else "", page=page_label,
                 notes=[] if title and label else ["Viewer metadata unavailable; verify page numbering "
                                                   "and title from the image or catalog."])


def gnm(url, client, folio, page):
    match = re.search(r"/item/([^/]+)(?:/(\d+))?", urlsplit(url).path)
    if not match:
        raise DownloadError("Expected a GNM /item/SHELFMARK/PAGE URL")
    item, selected = match.groups()
    data = client.json(f"https://dlib.gnm.de/viewer/index.php?id={quote(item)}/json")
    if folio:
        matches = [p for p in data["pages"]
                   if normalize_folio(p["label"].split("/")[-1]) == normalize_folio(folio)]
    else:
        number = positive_page(page if page is not None else int(selected) if selected else None)
        matches = [p for p in data["pages"] if p["page"] == number]
    if len(matches) != 1:
        raise DownloadError(f"Expected one GNM page; found {len(matches)}")
    selected = matches[0]
    label = selected["label"].split("/")[-1].strip()
    return Image(url, selected["imgmax"], f"gnm_{item}_{selected['page']}.jpg",
                 title=data.get("issue", {}).get("titel", "").strip(),
                 folio=label if re.fullmatch(r"\d+[rv]", label) else "", page=str(selected["page"]))


def findbuch(url, client, folio, page):
    if folio or page is not None:
        raise DownloadError("Findbuch needs the viewer fragment's exact path= image selection")
    parts = urlsplit(url)
    selected = parse_qs(parts.fragment.lstrip("&")).get("path", [None])[0]
    if not selected:
        raise DownloadError("Findbuch URL is missing #&path=...; select an image in the viewer")
    text = client.text(url.split("#", 1)[0])
    paths = re.findall(r"paths\[(\d+)\]\s*=\s*['\"]([^'\"]+)['\"]", text)
    matches = [index for index, path in paths if unescape(path) == selected]
    be = re.search(r"var\s+be_id\s*=\s*['\"]?(\d+)", text)
    ve = re.search(r"var\s+ve_id\s*=\s*['\"]?(\d+)", text)
    if len(matches) != 1 or not be or not ve:
        raise DownloadError("Cannot map selected Findbuch path to its catalog download endpoint")
    # The original image host can be offline while this viewer endpoint still works.
    image_url = (f"{parts.scheme}://{parts.netloc}/php/gtpc.php?"
                 f"be_id={be[1]}&ve_id={ve[1]}&count={matches[0]}")
    return Image(url, image_url, Path(urlsplit(selected).path).name,
                 notes=[f"Selected catalog image: {selected}"])


def loc(url, client, folio, page):
    if folio:
        raise DownloadError("LOC requires its viewer sequence --page or ?sp=, not a guessed folio")
    parts = urlsplit(url)
    number = positive_page(page if page is not None else int(parse_qs(parts.query).get("sp", ["0"])[0]))
    match = re.search(r"/resource/(rbc(?:0001)?\.(\d{4}[^/]+))", parts.path)
    if not match:
        raise DownloadError("Supported LOC fallback requires a /resource/rbc.YYYY.../ URL")
    resource, item = match.groups()
    try:
        data = client.json(f"https://www.loc.gov/resource/{resource}/?fo=json")
    except (OSError, ValueError):
        data = None
    if data is not None:
        files = data.get("resource", {}).get("files")
        if files is None:
            files = data.get("resources", [{}])[0].get("files")
        if not isinstance(files, list):
            raise DownloadError("LOC metadata does not expose the image sequence")
        if number > len(files):
            raise DownloadError("Page exceeds the LOC image sequence")
        candidates = [f for f in files[number - 1] if f.get("mimetype") == "image/jpeg"]
        if not candidates:
            raise DownloadError("LOC metadata contains no JPEG for the selected page")
        image = max(candidates, key=lambda f: f.get("width", 0) or 0)
        return Image(url, image["url"], f"loc_{item}_{number:04d}.jpg",
                     title=data.get("item", {}).get("title", ""), page=str(number))
    # Observed RBC convention: four digits, not five; verify the image exists.
    base = f"https://tile.loc.gov/image-services/iiif/service:rbc:rbc0001:{item[:4]}:{item}:{number:04d}"
    client.json(base + "/info.json")
    return Image(url, base + "/full/full/0/default.jpg", f"loc_{item}_{number:04d}.jpg",
                 page=str(number), notes=["LOC API unavailable; used verified RBC image-service filename. "
                                          "Visually confirm the requested page before cataloging."])


HANDLERS = {"archive.org": archive_org, "digi.vatlib.it": vatican,
            "digital.blb-karlsruhe.de": blb, "dlib.gnm.de": gnm, "loc.gov": loc}


def resolve(url, client, folio=None, page=None):
    parts = urlsplit(url)
    host = (parts.hostname or "").removeprefix("www.")
    if parts.scheme not in {"http", "https"}:
        raise DownloadError("Supply an HTTP(S) archive viewer URL")
    if folio and page is not None:
        raise DownloadError("Choose --folio or --page, not both")
    handler = findbuch if host.endswith(".findbuch.net") else HANDLERS.get(host)
    if not handler:
        raise DownloadError(f"Unsupported viewer: {host}. Add and verify a handler before retrying.")
    return handler(url, client, folio, page)


def image_type(header):
    if header.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    if header[:4] in {b"II*\x00", b"MM\x00*"}:
        return "tiff"
    return None


def download(image, destination, client):
    """Refuse overwrites and never leave a failed response at the destination."""
    destination = Path(destination)
    if destination.exists():
        raise DownloadError(f"Destination already exists: {destination}")
    temporary = None
    try:
        with client.open(image.image_url) as response:
            header = response.read(32)
            kind = image_type(header)
            if not kind:
                raise DownloadError("Response is not a recognized image (possibly an HTML error page)")
            with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as output:
                temporary = Path(output.name)
                output.write(header)
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
        os.link(temporary, destination)  # Atomic creation; refuses concurrent overwrites too.
        return kind
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Archive viewer URL; quote URLs containing & or #")
    parser.add_argument("--folio", help="Exact folio, e.g. '108 r' (Vatican or GNM)")
    parser.add_argument("--page", type=int, help="One-based viewer sequence number")
    parser.add_argument("--output", type=Path, help="Destination file; existing files are refused")
    parser.add_argument("--resolve-only", action="store_true", help="Print image details without downloading")
    parser.add_argument("--timeout", type=float, default=25, help="Timeout per HTTP request in seconds")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if not args.resolve_only and args.output is None:
        parser.error("--output is required unless --resolve-only is used")
    try:
        client = Client(args.timeout)
        image = resolve(args.url, client, args.folio, args.page)
        result = asdict(image)
        if not args.resolve_only:
            result["format"] = download(image, args.output, client)
            result["path"] = str(args.output.resolve())
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
