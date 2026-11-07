#!/usr/bin/env python3
"""Create a review document record from an Archive NRW catalogue URL."""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener
from xml.etree import ElementTree


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from archive_anubis import ANUBIS_CHALLENGE_RE, solve_anubis


USER_AGENT = "Rosenberg research downloader/1.0"
REQUEST_TIMEOUT = 60
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent.parent
DOCUMENT_DIR = REPOSITORY_ROOT / "data" / "documents"
HOSTS = {"www.archive.nrw.de", "archive.nrw.de"}
OPENER = build_opener(HTTPCookieProcessor(CookieJar()))


class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def request(url: str) -> tuple[str, bytes]:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,application/xml,text/html,*/*"})
    try:
        with OPENER.open(req, timeout=REQUEST_TIMEOUT) as response:
            return response.geturl(), response.read()
    except HTTPError as exc:
        if exc.code != 403:
            raise
        return exc.geturl(), exc.read()


def fetch(url: str) -> tuple[str, bytes]:
    final_url, body = request(url)
    for _ in range(2):
        pass_url = solve_anubis(body, final_url)
        if pass_url is None:
            return final_url, body
        final_url, body = request(pass_url)
    if solve_anubis(body, final_url):
        raise ValueError("Could not pass Archive NRW bot protection")
    return final_url, body


def normalize_date(raw: str) -> str:
    """Keep the catalog's year precision while removing EAD uncertainty brackets."""
    value = re.sub(r"[\[\]() ]", "", raw.strip())
    years = re.findall(r"(?<!\d)(\d{4})(?!\d)", value)
    if not years:
        raise ValueError(f"Could not determine a document date from unitDate: {raw!r}")
    years = list(dict.fromkeys(years))
    return years[0] if len(years) == 1 else f"{years[0]}-{years[-1]}"


def description_text(value: object) -> str:
    if isinstance(value, list):
        value = "\n".join(str(part) for part in value if part)
    if not isinstance(value, str) or not value.strip():
        return ""
    parser = TextOnly()
    parser.feed(value.replace("<@nxt@ />", "\n"))
    text = "".join(parser.parts)
    return "\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip())


def image_urls(mets_url: str) -> list[str]:
    _, body = fetch(mets_url)
    root = ElementTree.fromstring(body)
    ns = {"mets": "http://www.loc.gov/METS/", "xlink": "http://www.w3.org/1999/xlink"}
    images: list[str] = []
    for location in root.findall(".//mets:fileGrp[@USE='DEFAULT']/mets:file/mets:FLocat", ns):
        source = location.get(f"{{{ns['xlink']}}}href")
        if source and source.lower().endswith((".jp2", ".jpg", ".jpeg", ".png")):
            images.append(source.rstrip("/") + "/full/max/0/default.jpg")
    return list(dict.fromkeys(images))


def dated_paths(date: str) -> list[Path]:
    stem = re.sub(r"[^0-9-]+", "_", date)
    pattern = re.compile(rf"{re.escape(stem)}(?:_(\d+))?\.json$")
    return sorted((p for p in DOCUMENT_DIR.glob(f"{stem}*.json") if pattern.fullmatch(p.name)),
                  key=lambda p: (int(pattern.fullmatch(p.name).group(1) or 1), p.name))


def save_record(record: dict[str, object]) -> tuple[Path, bool]:
    from archive_record_storage import save_record as save
    return save(record, DOCUMENT_DIR)


def create_record(url: str) -> tuple[Path, bool]:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.path.rstrip("/") != "/archivsuche":
        raise ValueError("Expected an https://www.archive.nrw.de/archivsuche record URL")
    node_id = parse_qs(parsed.query).get("link", [""])[0]
    if not re.fullmatch(r"VERZEICH(?:NUNG|UNG)SEINHEIT-[A-Za-z0-9_-]+", node_id, re.I):
        raise ValueError("The URL must identify a VERZEICHNUNGSEINHEIT record")
    api_url = "https://www.archive.nrw.de/sufservice/api/listContextByNodeId?" + urlencode({"nodeId": node_id})
    _, body = fetch(api_url)
    try:
        selected = json.loads(body)["selectedNode"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("Archive NRW did not return a selected catalog record") from exc
    if selected.get("type", {}).get("value") != "VERZEICHNUNGSEINHEIT":
        raise ValueError("The Archive NRW link did not resolve to a record unit")

    date = normalize_date(str(selected.get("unitDate") or ""))
    signature = str(selected.get("signatur") or "").strip()
    fonds = str(selected.get("bestaendeId") or selected.get("bestandSignature") or "").strip()
    archive = str(selected.get("corpName") or "Landesarchiv NRW").strip()
    division = archive.replace("Landesarchiv NRW ", "")
    source_parts = [division]
    if fonds:
        source_parts.append(fonds)
    if signature:
        source_parts.append(f"Nr. {signature}")
    source = ", ".join(source_parts)

    abstract_parts = [str(selected.get("title") or "").strip()]
    abstract = description_text(selected.get("abstrakt"))
    if abstract:
        abstract_parts.append(abstract)
    note = description_text(selected.get("note"))
    if note:
        abstract_parts.append(note)
    physical = description_text(selected.get("physicalDescriptionContent"))
    if physical:
        abstract_parts.append(physical)
    german = "\n\n".join(part for part in abstract_parts if part)
    entry: dict[str, object] = {"source": source, "url": url, "german": german}
    mets_links = selected.get("daogrpDaolocHrefs") or []
    images: list[str] = []
    for viewer in mets_links:
        match = re.search(r"[?&]tx_dlf\[id\]=([^&]+)", str(viewer))
        if match:
            from urllib.parse import unquote
            mets_url = unquote(match.group(1))
            try:
                images.extend(image_urls(mets_url))
            except (HTTPError, URLError, ElementTree.ParseError, ValueError):
                continue
    if images:
        entry["img"] = [{"src": image} for image in dict.fromkeys(images)]
    return save_record({"date": date, "label": ["to review"], "entries": [entry]})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Archive NRW record URL")
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
