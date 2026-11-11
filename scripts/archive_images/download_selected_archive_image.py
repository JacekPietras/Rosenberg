#!/usr/bin/env python3
"""Resolve and download one selected archive image (standard library only)."""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from html import unescape
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.parse import parse_qs, quote, urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from archive_anubis import solve_anubis

BAVARIKON_USER_AGENT = "Mozilla/5.0 (compatible; RosenbergResearch/1.0)"
BAVARIKON_TIMEOUT = 45


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


def landesarchiv_bw(url, client, folio, page):
    """Download an exact Landesarchiv BW image URL recorded by its catalog."""
    if folio or page is not None:
        raise DownloadError("Landesarchiv BW needs the exact selected bild.php image URL")
    parts = urlsplit(url)
    if not re.fullmatch(r"/ofs21/bild_zoom/bild\.php", parts.path):
        raise DownloadError("Expected a Landesarchiv BW /ofs21/bild_zoom/bild.php image URL")
    selected = parse_qs(parts.query).get("originalBilddatei", [""])[0]
    if not selected or not selected.lower().endswith((".jpg", ".jpeg")):
        raise DownloadError("Landesarchiv BW image URL has no selected JPEG filename")
    return Image(url, url, Path(selected).name,
                 notes=[f"Selected catalog image: {selected}"])


def landesarchiv_nrw(url, client, folio, page):
    """Use the direct JPEG; NRW's appended IIIF-style path currently returns 404."""
    if folio or page is not None:
        raise DownloadError("Landesarchiv NRW needs the exact selected image URL")
    parts = urlsplit(url)
    match = re.fullmatch(r"(.+?\.jpe?g)(?:/full/max/0/default\.jpg)?", parts.path, re.I)
    if not match or "/data02/" not in match[1]:
        raise DownloadError("Expected a Landesarchiv NRW data02 image URL")
    image_url = f"{parts.scheme}://{parts.netloc}{match[1]}"
    return Image(url, image_url, Path(match[1]).name,
                 notes=["Uses the direct catalog JPEG; the appended /full/max/0/default.jpg endpoint returns 404."])


def e_codices(url, client, folio, page):
    """Resolve the selected e-codices page from its IIIF viewer data."""
    if folio or page is not None:
        raise DownloadError("e-codices needs the exact selected page in the viewer URL")
    parts = urlsplit(url)
    match = re.fullmatch(r"/(?:de|en|fr|it)/([a-z0-9]+)/([^/]+)/([^/]+)/?", parts.path)
    if not match:
        raise DownloadError("Expected an e-codices /LANG/COLLECTION/SHELF_MARK/PAGE URL")
    text = client.text(url)
    title_match = re.search(r"<title>(.*?)</title>", text, re.S | re.I)
    viewer = re.search(r":viewer-data='(.*?)'", text, re.S)
    if not viewer:
        raise DownloadError("e-codices page does not expose viewer data")
    data = json.loads(html.unescape(viewer[1]))
    tile_sources = data.get("tileSources")
    if not isinstance(tile_sources, list) or len(tile_sources) != 1:
        raise DownloadError("Expected one selected e-codices page image")
    info_url = tile_sources[0]
    image_match = re.fullmatch(r"(https://media\.e-codices\.ch/iip/[^/]+/[^/]+/[^/]+\.jp2)/info\.json", info_url)
    if not image_match:
        raise DownloadError("e-codices selected page has an unexpected IIIF image URL")
    page_label = data.get("breadcrumbData", {}).get("primaryManuscript", {}).get("page", {}).get("label", "")
    name = Path(urlsplit(image_match[1]).path).name.removesuffix(".jp2") + ".jpg"
    return Image(url, image_match[1] + "/full/max/0/default.jpg", name,
                 title=plain(title_match[1]) if title_match else "", page=page_label)



class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.in_title = False
        self.links: list[str] = []
        self.images: list[str] = []
        self.meta: dict[str, str] = {}
        self.jsonld: list[str] = []
        self.in_jsonld = False
        self.jsonld_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            key = values.get("property") or values.get("name") or values.get("itemprop")
            content = values.get("content")
            if key and content:
                self.meta[key.lower()] = content
        if tag == "link":
            href = values.get("href", "")
            rel = values.get("rel", "").lower()
            typ = values.get("type", "").lower()
            if href and ("manifest" in rel or "iiif" in typ or "ld+json" in typ):
                self.links.append(href)
        if tag == "img":
            for attr in ("src", "data-src", "data-original", "data-image"):
                if values.get(attr):
                    self.images.append(values[attr])
            self.images.extend(values.get("srcset", "").split()[::2])
        if tag == "script" and "ld+json" in values.get("type", "").lower():
            self.in_jsonld = True
            self.jsonld_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag == "script" and self.in_jsonld:
            self.jsonld.append("".join(self.jsonld_parts))
            self.in_jsonld = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self.in_jsonld:
            self.jsonld_parts.append(data)


def fetch(opener, url: str) -> tuple[str, bytes, str]:
    headers = {"User-Agent": BAVARIKON_USER_AGENT, "Accept": "text/html,application/ld+json,application/json,*/*"}
    request = Request(url, headers=headers)
    with opener.open(request, timeout=BAVARIKON_TIMEOUT) as response:
        return response.geturl(), response.read(), response.headers.get_content_type()


def absolute(base: str, values: list[str]) -> list[str]:
    return list(dict.fromkeys(urljoin(base, html.unescape(value.strip())) for value in values if value.strip()))


def json_strings(value: object) -> list[str]:
    """Collect URL-valued fields from embedded JSON/JSON-LD."""
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str) and re.search(r"image|manifest|thumbnail|contenturl|url", key, re.I):
                found.append(item)
            else:
                found.extend(json_strings(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(json_strings(item))
    return found


def iiif_image_ids(manifest: object) -> list[str]:
    """Extract IIIF image resources from Presentation API 2 or 3 manifests."""
    found: list[str] = []
    if not isinstance(manifest, dict):
        return found
    sequences = manifest.get("sequences", [])
    canvases = list(manifest.get("items", [])) if isinstance(manifest.get("items"), list) else []
    if isinstance(sequences, list):
        for sequence in sequences:
            if isinstance(sequence, dict) and isinstance(sequence.get("canvases"), list):
                canvases.extend(sequence["canvases"])
    for canvas in canvases:
        if not isinstance(canvas, dict):
            continue
        # Presentation 3: Canvas.items[].items[].body
        for page in canvas.get("items", []) if isinstance(canvas.get("items"), list) else []:
            if isinstance(page, dict):
                for annotation in page.get("items", []) if isinstance(page.get("items"), list) else []:
                    if isinstance(annotation, dict):
                        body = annotation.get("body", {})
                        bodies = body if isinstance(body, list) else [body]
                        found.extend(str(b.get("id") or b.get("@id")) for b in bodies if isinstance(b, dict) and (b.get("id") or b.get("@id")))
        # Presentation 2: images[].resource
        for annotation in canvas.get("images", []) if isinstance(canvas.get("images"), list) else []:
            if isinstance(annotation, dict) and isinstance(annotation.get("resource"), dict):
                body = annotation["resource"]
                if body.get("@id") or body.get("id"):
                    found.append(str(body.get("id") or body.get("@id")))
    return found


def embedded_bav_object(document: str) -> dict[str, object]:
    match = re.search(r"window\.bavObject\s*=\s*(\{.*?\})\s*;\s*\$\(document\)", document, re.S)
    if not match:
        return {}
    try:
        value = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def as_full_iiif_image(url: str) -> str:
    """Request the full image for a standard IIIF Image API service URL."""
    match = re.match(r"^(https?://.+?)/(?:full|\d+,\d+|pct:[^/]+)/[^/]+/[^/]+/(?:default|native)(?:\.[a-z0-9]+)?$", url, re.I)
    if match:
        return match.group(1) + "/full/max/0/default.jpg"
    return url


def scrape_bavarikon(page_url: str) -> tuple[dict[str, object], list[str], list[str]]:
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    final_url, raw, content_type = fetch(opener, page_url)
    text = raw.decode("utf-8", "replace")
    if "text/html" not in content_type and not text.lstrip().startswith("<"):
        raise ValueError(f"Expected an HTML object page; server returned {content_type}")
    if "Making sure you're not a bot" in text or "Protected by" in text and "Anubis" in text:
        pass_url = solve_anubis(raw, final_url)
        if not pass_url:
            raise ValueError("Bavarikon returned an Anubis check without a readable challenge")
        request = Request(pass_url, headers={"User-Agent": BAVARIKON_USER_AGENT})
        with opener.open(request, timeout=BAVARIKON_TIMEOUT) as response:
            response.read()
        final_url, raw, content_type = fetch(opener, page_url)
        text = raw.decode("utf-8", "replace")
        if "Making sure you're not a bot" in text or "Protected by" in text and "Anubis" in text:
            raise ValueError("Bavarikon's Anubis challenge did not grant access; try again later")
    parser = PageParser()
    parser.feed(text)
    bav_object = embedded_bav_object(text)
    title = str(bav_object.get("title") or " ".join("".join(parser.title_parts).split()) or parser.meta.get("og:title", ""))
    candidates = list(parser.images)
    candidates.extend(value for key, value in parser.meta.items() if re.search(r"image|thumbnail", key, re.I))
    manifests = [url for url in parser.links if "manifest" in url.lower() or "iiif" in url.lower()]
    for block in parser.jsonld:
        try:
            candidates.extend(json_strings(json.loads(block)))
        except json.JSONDecodeError:
            pass
    image_endpoint = re.search(r"iiifImageApiEndpoint\s*:\s*[\"']([^\"']+)", text)
    pages = bav_object.get("pages", [])
    if image_endpoint and isinstance(pages, list):
        endpoint = image_endpoint.group(1).rstrip("/")
        page_ids = [item.get("identifier") for item in pages if isinstance(item, dict) and item.get("identifier")]
        if page_ids:
            candidates = [f"{endpoint}/{page_id}/full/max/0/default.jpg" for page_id in page_ids]
    for manifest_url in absolute(final_url, manifests):
        try:
            _, manifest_bytes, _ = fetch(opener, manifest_url)
            candidates.extend(iiif_image_ids(json.loads(manifest_bytes)))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            print(f"Warning: could not read IIIF manifest {manifest_url}: {error}", file=sys.stderr)
    image_urls = absolute(final_url, candidates)
    image_urls = [as_full_iiif_image(url) for url in image_urls]
    image_urls = [url for url in dict.fromkeys(image_urls) if urlsplit(url).scheme in {"http", "https"}]
    # Keep generic page chrome out of the result when the page supplies image metadata.
    preferred = [url for url in image_urls if re.search(r"iiif|image|media|bild|full", url, re.I)]
    image_urls = preferred or image_urls
    raw_blocks = bav_object.get("contentBlocksContainer", {})
    description = ""
    if isinstance(raw_blocks, dict) and isinstance(raw_blocks.get("de"), list):
        description = "\n".join(
            html.unescape(str(block.get("data", {}).get("text", "")))
            for block in raw_blocks["de"]
            if isinstance(block, dict)
            and isinstance(block.get("data"), dict)
            and block["data"].get("text")
            and block.get("type") in {"HTML", "TEXT"}
        )
    holding = bav_object.get("holdingInstitution", {})
    metadata: dict[str, object] = {
        "id": bav_object.get("id", ""),
        "title": title,
        "date": bav_object.get("creationDate", ""),
        "description_de": description,
        "institution": holding.get("name", "") if isinstance(holding, dict) else "",
        "identifiers": bav_object.get("identifiers", []),
        "remark": bav_object.get("remark", ""),
        "license": bav_object.get("license", ""),
        "rights_declarations": bav_object.get("rightsDeclarations", []),
    }
    return metadata, image_urls, manifests


def bavarikon(url, client, folio, page):
    if folio:
        raise DownloadError("Bavarikon page selection uses --page or the URL's p= parameter, not a folio")
    query_page = parse_qs(urlsplit(url).query).get("p", [None])[0]
    if page is not None:
        selected_page = positive_page(page)
    elif query_page is not None:
        try:
            selected_page = positive_page(int(query_page))
        except ValueError as error:
            raise DownloadError(f"Invalid Bavarikon p= page selector: {query_page!r}") from error
    else:
        selected_page = None

    metadata, image_urls, _manifests = scrape_bavarikon(url)
    if not image_urls:
        raise DownloadError("Bavarikon object exposes no image URLs")
    if selected_page is None:
        if len(image_urls) != 1:
            raise DownloadError(
                f"Bavarikon object exposes {len(image_urls)} images; supply --page or use a URL with p="
            )
        selected_page = 1
    if selected_page > len(image_urls):
        raise DownloadError(f"Bavarikon page {selected_page} exceeds its {len(image_urls)} images")

    image_url = image_urls[selected_page - 1]
    item = str(metadata.get("id") or urlsplit(url).path.rsplit("/", 1)[-1])
    item = re.sub(r"[^A-Za-z0-9_-]+", "_", item).strip("_") or "object"
    suffix = Path(urlsplit(image_url).path).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}:
        suffix = ".jpg"
    notes = []
    rights = metadata.get("license")
    if rights:
        notes.append(f"Bavarikon rights notice: {rights}")
    return Image(url, image_url, f"bavarikon_{item}_{selected_page:04d}{suffix}",
                 title=str(metadata.get("title", "")), page=str(selected_page), notes=notes)


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
            "digital.blb-karlsruhe.de": blb, "dlib.gnm.de": gnm, "loc.gov": loc,
            "e-codices.unifr.ch": e_codices,
            "bavarikon.de": bavarikon, "www2.landesarchiv-bw.de": landesarchiv_bw,
            "landesarchiv-nrw.de": landesarchiv_nrw}


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
