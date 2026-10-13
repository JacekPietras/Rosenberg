#!/usr/bin/env python3
"""Parse metadata and image URLs exposed by a Bavarikon object page."""

from __future__ import annotations

import argparse
from http.cookiejar import CookieJar
import html
import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from time import monotonic
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen


ROOT = Path(__file__).resolve().parent.parent
IMAGE_DIR = ROOT / "data" / "letters" / "img-temp" / "bavarikon"
USER_AGENT = "Mozilla/5.0 (compatible; RosenbergResearch/1.0)"
TIMEOUT = 45


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
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/ld+json,application/json,*/*"}
    request = Request(url, headers=headers)
    with opener.open(request, timeout=TIMEOUT) as response:
        return response.geturl(), response.read(), response.headers.get_content_type()


def solve_anubis(opener, page_url: str, challenge_html: str) -> None:
    """Complete Anubis's published SHA-256 proof-of-work challenge."""
    challenge_match = re.search(
        r'<script\s+id=["\']anubis_challenge["\']\s+type=["\']application/json["\']\s*>(.*?)</script>',
        challenge_html,
        re.I | re.S,
    )
    if not challenge_match:
        raise ValueError("Bavarikon returned an Anubis check without a readable challenge")
    challenge = json.loads(html.unescape(challenge_match.group(1)))
    challenge_data = challenge["challenge"]
    difficulty = int(challenge.get("rules", {}).get("difficulty", challenge_data.get("difficulty", 0)))
    random_data = challenge_data["randomData"]
    challenge_id = challenge_data["id"]
    started = monotonic()
    nonce = 0
    while nonce < 10_000_000:
        digest = hashlib.sha256(f"{random_data}{nonce}".encode()).digest()
        if digest[: difficulty // 2] == bytes(difficulty // 2) and (difficulty % 2 == 0 or digest[difficulty // 2] >> 4 == 0):
            break
        nonce += 1
    else:
        raise ValueError(f"Anubis proof-of-work difficulty {difficulty} exceeded the nonce limit")

    base_match = re.search(r'<script\s+id=["\']anubis_base_prefix["\']\s+type=["\']application/json["\']\s*>(.*?)</script>', challenge_html, re.I | re.S)
    base_prefix = json.loads(html.unescape(base_match.group(1))) if base_match else ""
    pass_url = urljoin(page_url, f"{base_prefix}/.within.website/x/cmd/anubis/api/pass-challenge")
    query = urlencode({
        "id": challenge_id,
        "response": digest.hex(),
        "nonce": nonce,
        "redir": page_url,
        "elapsedTime": max(0, int((monotonic() - started) * 1000)),
    })
    request = Request(f"{pass_url}?{query}", headers={"User-Agent": USER_AGENT})
    with opener.open(request, timeout=TIMEOUT) as response:
        response.read()


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


def scrape(page_url: str) -> tuple[dict[str, object], list[str], list[str]]:
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    final_url, raw, content_type = fetch(opener, page_url)
    text = raw.decode("utf-8", "replace")
    if "text/html" not in content_type and not text.lstrip().startswith("<"):
        raise ValueError(f"Expected an HTML object page; server returned {content_type}")
    if "Making sure you're not a bot" in text or "Protected by" in text and "Anubis" in text:
        solve_anubis(opener, final_url, text)
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


def download(urls: list[str]) -> list[Path]:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, url in enumerate(urls, 1):
        suffix = Path(urlsplit(url).path).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}:
            suffix = ".jpg"
        target = IMAGE_DIR / f"bavarikon_{index:03d}{suffix}"
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=TIMEOUT) as response:
            contents = response.read()
        if not contents:
            raise ValueError(f"Empty image response from {url}")
        target.write_bytes(contents)
        paths.append(target)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Bavarikon object page URL")
    parser.add_argument("--download", action="store_true", help="cache discovered images under data/letters/img-temp/bavarikon/")
    args = parser.parse_args()
    try:
        metadata, images, manifests = scrape(args.url)
        print(f"Title: {metadata['title'] or '(not found)'}")
        if metadata["date"]:
            print(f"Date: {metadata['date']}")
        if metadata["institution"]:
            print(f"Holding institution: {metadata['institution']}")
        identifiers = metadata["identifiers"]
        if isinstance(identifiers, list) and identifiers:
            print("Identifiers: " + "; ".join(str(item.get("id", "")) for item in identifiers if isinstance(item, dict)))
        if metadata["remark"]:
            print(f"Reference: {metadata['remark']}")
        if metadata["license"]:
            print(f"Rights: {metadata['license']}")
        if metadata["rights_declarations"]:
            print("Rights declaration: " + "; ".join(str(item) for item in metadata["rights_declarations"]))
        if metadata["description_de"]:
            print("German description:")
            print(metadata["description_de"])
        if manifests:
            print("IIIF manifest(s):")
            for url in absolute(args.url, manifests):
                print(f"  {url}")
        print(f"Images found: {len(images)}")
        for url in images:
            print(url)
        if args.download:
            for path in download(images):
                print(f"Downloaded: {path.relative_to(ROOT)}")
        if not images:
            print("No image URLs were exposed in the page HTML or IIIF manifest.", file=sys.stderr)
            return 1
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
