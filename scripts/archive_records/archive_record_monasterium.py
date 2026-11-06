#!/usr/bin/env python3
"""Route a Monasterium charter to the downloader for its archival repository."""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit, urlunsplit
from urllib.request import Request, build_opener
from xml.etree import ElementTree

from archive_record_monasterium_internal import create_record as create_internal_record
from archive_record_landesarchiv_bw import create_record as create_landesarchiv_record
from archive_record_gda_bayern import create_record as create_gda_record
from archive_record_gda_resolver import resolve as resolve_gda_record
from archive_record_nrw import create_record as create_nrw_record
from archive_record_arcinsys_hessen import create_record as create_hessen_record


USER_AGENT = "Rosenberg research downloader/1.0"
REQUEST_TIMEOUT = 60
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent.parent
HOSTS = {"www.monasterium.net", "monasterium.net"}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def archival_permalink(root: ElementTree.Element):
    for node in root.iter():
        if local_name(node.tag) == "archidentifier":
            for ref in node.iter():
                if local_name(ref.tag) == "ref" and ref.get("target"):
                    target = urlsplit(ref.get("target", "").strip())
                    if target.scheme not in {"http", "https"}:
                        continue
                    host = (target.hostname or "").removeprefix("www.")
                    query = parse_qs(target.query)
                    downloader = None
                    if host == "landesarchiv-bw.de" and query.get("f", [""])[0]:
                        downloader = create_landesarchiv_record
                    elif host == "gda.bayern.de" and target.path.startswith("/gvl/") and query.get("id", [""])[0]:
                        downloader = create_gda_record
                    elif (host == "archive.nrw.de" and target.path.rstrip("/") == "/archivsuche"
                          and re.fullmatch(r"VERZEICHNUNGSEINHEIT-Vz_[0-9a-f-]+", query.get("link", [""])[0], re.I)):
                        downloader = create_nrw_record
                    elif (target.hostname == "arcinsys.hessen.de" and target.path.rstrip("/") == "/arcinsys/showArchivalDescriptionDetails.action"
                          and re.fullmatch(r"\d+", query.get("archivalDescriptionId", [""])[0])):
                        downloader = create_hessen_record
                    if downloader:
                        return urlunsplit(target._replace(scheme="https")), downloader
    return None


def monasterium_metadata_url(parsed) -> str:
    match = re.fullmatch(r"/mom/((?:[^/]+/){1,2}[^/]+)/charter/?", parsed.path)
    if not match:
        raise ValueError("Expected a Monasterium charter page URL")
    return (
        "https://www.monasterium.net/mom/atom/GET/metadata.charter.public/"
        f"{match[1]}.cei.xml"
    )


def fetch_page(url: str) -> bytes:
    request = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/xml,text/xml,*/*",
        "Referer": "https://www.monasterium.net/",
    })
    with build_opener().open(request, timeout=REQUEST_TIMEOUT) as response:
        return response.read()


def fetch_cei(url: str) -> bytes:
    payload = fetch_page(url)
    # Monasterium can append Cloudflare scripts and an incomplete HTML wrapper
    # inside its CEI response. Remove those additions and repair the open body.
    payload = re.sub(rb"<script(?:\s[^>]*)?>.*?</script>\s*</body>", b"", payload, flags=re.S)
    payload = re.sub(rb"<back\b.*?</back>", b"", payload, flags=re.S)
    payload = re.sub(rb"</chDesc>\s*</text>", b"</chDesc></body></text>", payload)
    end = payload.find(b"</atom:entry>")
    return payload[:end + len(b"</atom:entry>")] if end >= 0 else payload


class EditionReferences(HTMLParser):
    """Retain explicit edition record links; image hosts are not record IDs."""

    def __init__(self):
        super().__init__()
        self.sources = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        link = attrs.get('href', '') if tag == 'a' else attrs.get('src', '') if tag == 'img' else ''
        parsed = urlsplit(link)
        if parsed.scheme in {'http', 'https'} and parsed.hostname in {'www.ingrossaturbuecher.de', 'ingrossaturbuecher.de'}:
            query = parse_qs(parsed.query)
            record_id = re.fullmatch(r'/id/source/(\d+)/?', parsed.path)
            source_id = query.get('tx_hisodat_sources[source]', query.get('tx_hisodat_search[source]', []))
            if not record_id and not (len(source_id) == 1 and re.fullmatch(r'\d+', source_id[0])):
                return
            identifier = record_id[1] if record_id else source_id[0]
            reference = f'https://www.ingrossaturbuecher.de/id/source/{identifier}'
            if reference not in self.sources:
                self.sources.append(reference)


def fallback_sources(root, url):
    # CEI can contain only image filenames; the charter HTML supplies their host.
    # Inspect explicit CEI links first and fetch HTML only for unresolved images.
    parser = EditionReferences()
    for node in root.iter():
        for key in ('target', 'url'):
            if node.get(key):
                parser.handle_starttag('a', [('href', node.get(key))])
    if not parser.sources and any(local_name(node.tag) == 'graphic' and node.get('url')
                                  and not urlsplit(node.get('url')).netloc for node in root.iter()):
        try:
            parser.feed(fetch_page(url).decode('utf-8', 'replace'))
        except OSError as exc:
            print(f'Could not inspect edition references on Monasterium: {exc}; retaining CEI fallback', file=sys.stderr)
    return parser.sources


def add_monasterium_url(path: Path, monasterium_url: str, archive_url: str, root: ElementTree.Element) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    for entry in document.get("entries", []):
        if not isinstance(entry, dict):
            continue
        old_urls = entry.get("url", [])
        old_urls = [old_urls] if isinstance(old_urls, str) else list(old_urls)
        if archive_url not in old_urls:
            continue
        from archive_record_storage import merge_entry
        # The archive downloader supplies its current image URLs. Monasterium's
        # mirrored links can be obsolete and must not reintroduce broken images.
        merge_entry(entry, {"url": monasterium_url})
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return
    raise ValueError(f"The archive downloader did not save an entry for {archive_url}")


def create_record(url: str) -> tuple[Path, bool]:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in HOSTS:
        raise ValueError("Expected an https://www.monasterium.net/mom/.../charter URL")
    metadata_url = monasterium_metadata_url(parsed)
    try:
        root = ElementTree.fromstring(fetch_cei(metadata_url))
    except ElementTree.ParseError as exc:
        raise ValueError("Monasterium did not return a usable CEI record") from exc

    archive = archival_permalink(root)
    if archive is None:
        parts = re.fullmatch(r"/mom/([^/]+)/([^/]+)/([^/]+)/charter/?", parsed.path)
        date_node = next((node for node in root.iter() if local_name(node.tag) == "date"), None)
        archive_url = resolve_gda_record(*parts.groups(), date_node.get("value", "") if date_node is not None else "", root=root) if parts else None
        if archive_url is None:
            sources = fallback_sources(root, url)
            print(f"Archive catalog URL unresolved for {parsed.path}; importing Monasterium metadata as a fallback", file=sys.stderr)
            return create_internal_record(root, url, source_references=sources)
        archive = (archive_url, create_gda_record)
    archive_url, downloader = archive
    path, updated = downloader(archive_url)
    add_monasterium_url(path, url, archive_url, root)
    return path, updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Monasterium charter page URL")
    args = parser.parse_args()
    try:
        path, updated = create_record(args.url)
    except (OSError, ValueError, HTTPError, URLError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Only updated existing file: {path.relative_to(REPOSITORY_ROOT)}" if updated else path.relative_to(REPOSITORY_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
